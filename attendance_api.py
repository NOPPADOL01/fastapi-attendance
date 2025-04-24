from fastapi import FastAPI, Request
import logging
from datetime import datetime
import csv
import requests
import os

app = FastAPI()

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('traffic.log'),
        logging.StreamHandler()
    ]
)

# ใช้ environment variable สำหรับ LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'default_access_token')
LOG_FILE = "attendance_log.csv"
DEFAULT_NAME = "Unknown"

# โหลดข้อมูล PIN - Name Mapping
def load_pin_name_map(filename="pin_name_map.csv"):
    pin_map = {}
    try:
        with open(filename, newline='', encoding='utf-8') as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    pin_map[parts[0]] = parts[1]
    except Exception as e:
        logging.error(f"Error loading PIN map: {e}")
    return pin_map

PIN_NAME_MAP = load_pin_name_map()

# ฟังก์ชั่นส่งข้อความไปยัง LINE
def send_line_message(user_id, message):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    body = {
        'to': user_id,
        'messages': [{
            'type': 'text',
            'text': message
        }]
    }
    try:
        response = requests.post(url, json=body, headers=headers)
        response.raise_for_status()
        logging.info(f"LINE response: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send message to LINE: {e}")

# ฟังก์ชั่นแยกข้อมูลจากเครื่องสแกน
def parse_device_data(raw_data):
    try:
        parts = raw_data.strip().split('\t')
        if len(parts) >= 4 and ':' in parts[2]:
            return {
                'pin': parts[0],
                'name': parts[1] if parts[1] else DEFAULT_NAME,
                'time': parts[2],
                'status': parts[3]
            }
        elif len(parts) >= 3 and ':' in parts[1]:
            return {
                'pin': parts[0],
                'name': DEFAULT_NAME,
                'time': parts[1],
                'status': parts[2]
            }
        elif len(parts) >= 3 and parts[1].isdigit():
            return {
                'pin': parts[0],
                'name': DEFAULT_NAME,
                'time': parts[2],
                'status': parts[1]
            }
    except Exception as e:
        logging.error(f"Failed to parse device data: {e}")
    return None

# Endpoint สำหรับรับ GET และ POST จากเครื่อง ZKTeco
@app.api_route("/scan", methods=["GET", "POST", "HEAD"])
async def receive_scan(request: Request):
    method = request.method
    raw_data = await request.body()
    text_data = raw_data.decode('utf-8') if raw_data else ''
    logging.info(f"Received {method} request at /scan - Data: {text_data}")

    if method == "GET":
        return {"status": "ok", "message": "GET received from device"}

    # ประมวลผล POST
    data = parse_device_data(text_data)
    if data:
        name = PIN_NAME_MAP.get(data['pin'], data['name'])

        # บันทึกลงไฟล์ CSV
        log_entry = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['pin'],
            name,
            data['time'],
            data['status'],
            text_data.replace('\t', '|')
        ]
        try:
            with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(log_entry)
            logging.info(f"Scan - PIN: {data['pin']}, Name: {name}, Time: {data['time']}")
        except Exception as e:
            logging.error(f"Failed to write to log file: {e}")

        # ส่ง LINE แจ้งเตือน
        user_id = "U0463b655fa77fba3115f1018ba5b1f82"
        message = f"แจ้งเตือนการสแกน - PIN: {data['pin']}, ชื่อ: {name}, เวลา: {data['time']}"
        send_line_message(user_id, message)

        return {"status": "success", "message": "Scan received"}
    else:
        return {"status": "error", "message": "Invalid data format"}

# สำหรับเช็คว่า server ยังทำงานอยู่
@app.get("/")
def root():
    return {"status": "ok", "message": "FastAPI Attendance Running"}

# สำหรับรัน local
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))  # ถ้าไม่มี PORT ใน environment จะ fallback เป็น 10000
    uvicorn.run(app, host="0.0.0.0", port=port)

