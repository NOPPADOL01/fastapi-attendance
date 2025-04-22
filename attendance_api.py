from fastapi import FastAPI, Request, Response
import httpx
import logging
from datetime import datetime
import csv
import uvicorn
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

# ตั้งค่าเซิร์ฟเวอร์ ZKTeco และ LINE
TARGET_SERVER = "http://localhost:80"
LINE_CHANNEL_ACCESS_TOKEN = 'i3hUHF2P0LgI26XnRTVEdo3AexIyn1RGLMVdzqP5ZGU7zmviy7xkqRJi1UAFWzIGyJtMVb+rpya3dP+xbSHktI2tsZTaMmnvKMne3JmdM7xCz6fbOljGaauJLbhpZ0OozM7RQGA0yZGRBqIv4MB52gdB04t89/1O/w1cDnyilFU='
LOG_FILE = "attendance_log.csv"
DEFAULT_NAME = "Unknown"

# โหลดข้อมูล PIN - Name Mapping
def load_pin_name_map(filename="pin_name_map.csv"):
    pin_map = {}
    try:
        with open(filename, newline='', encoding='utf-8') as f:
            next(f)  # Skip the header
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    pin_map[parts[0]] = parts[1]
    except Exception as e:
        print(f"Error loading PIN map: {e}")
    return pin_map

PIN_NAME_MAP = load_pin_name_map()

# ฟังก์ชั่นในการส่งข้อความไปยัง LINE
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

# ฟังก์ชั่นในการแยกข้อมูลจาก ZKTeco
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
    except Exception:
        pass
    return None

# ฟังก์ชั่น proxy เพื่อส่งข้อมูลไปยัง ZKTeco
async def proxy_to_zkteco(request: Request):
    target_url = f"{TARGET_SERVER}{request.url.path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('content-length', None)

    body = await request.body()

    async with httpx.AsyncClient() as client:
        proxy_response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
            timeout=30.0
        )
    return proxy_response

# ฟังก์ชั่น middleware สำหรับ proxy การเชื่อมต่อ
@app.middleware("http")
async def proxy_and_log_traffic(request: Request, call_next):
    client_host = request.client.host if request.client else "unknown"
    logging.info(f"Incoming request: {request.method} {request.url} from {client_host}")
    logging.info(f"Headers: {dict(request.headers)}")
    
    try:
        # Forward ข้อมูลไปยัง ZKTeco
        proxy_response = await proxy_to_zkteco(request)
        logging.info(f"Forwarded to {TARGET_SERVER} - Status: {proxy_response.status_code}")
        
        # ตรวจสอบข้อมูลการสแกนจาก ZKTeco
        raw_data_str = await request.body()
        data = parse_device_data(raw_data_str.decode('utf-8'))
        
        if data:
            # ค้นหาชื่อจาก PIN
            name = PIN_NAME_MAP.get(data['pin'], data['name'])
            log_entry = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                data['pin'],
                name,
                data['time'],
                data['status'],
                raw_data_str.decode('utf-8').replace('\t', '|')
            ]
            # บันทึกข้อมูลลงในไฟล์ CSV
            with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(log_entry)

            logging.info(f"Scan - PIN: {data['pin']}, Name: {name}, Time: {data['time']}")

            # ส่งข้อความแจ้งเตือน LINE
            user_id = "U0463b655fa77fba3115f1018ba5b1f82"  # ตัวอย่าง user ID
            message = f"แจ้งเตือนการสแกน - PIN: {data['pin']}, ชื่อ: {name}, เวลา: {data['time']}"
            send_line_message(user_id, message)
        
        # ส่งกลับผลการ proxy
        return Response(
            content=proxy_response.content,
            status_code=proxy_response.status_code,
            headers=dict(proxy_response.headers),
            media_type=proxy_response.headers.get("content-type", None)
        )

    except httpx.ConnectError:
        logging.error(f"Failed to connect to target server at {TARGET_SERVER}")
        return Response(status_code=502, content="Bad Gateway")
    except Exception as e:
        logging.error(f"Error forwarding request: {str(e)}")
        return Response(status_code=500, content="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
