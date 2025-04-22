from fastapi import FastAPI, Request, Response
import logging
from datetime import datetime
import csv
import requests

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

LINE_CHANNEL_ACCESS_TOKEN = 'i3hUHF2P0LgI26XnRTVEdo3AexIyn1RGLMVdzqP5ZGU7zmviy7xkqRJi1UAFWzIGyJtMVb+rpya3dP+xbSHktI2tsZTaMmnvKMne3JmdM7xCz6fbOljGaauJLbhpZ0OozM7RQGA0yZGRBqIv4MB52gdB04t89/1O/w1cDnyilFU='
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
    response = requests.post(url, json=body, headers=headers)
    logging.info(f"LINE response: {response.status_code}, {response.text}")

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

# Endpoint สำหรับรับ POST จาก ZKTeco
@app.post("/scan")
async def receive_scan(request: Request):
    raw_data = await request.body()
    text_data = raw_data.decode('utf-8')
    logging.info(f"Received raw data: {text_data}")

    data = parse_device_data(text_data)
    if data:
        # หาชื่อจาก PIN
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
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(log_entry)

        logging.info(f"Scan - PIN: {data['pin']}, Name: {name}, Time: {data['time']}")

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

# ใช้ตอนรัน local (render ไม่ต้องใช้)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
