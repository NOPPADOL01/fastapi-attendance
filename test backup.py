from fastapi_attendance import FastAPI, Request, HTTPException
from datetime import datetime
import csv
import os

app = FastAPI()

LOG_FILE = "attendance_log.csv"
DEFAULT_NAME = "Unknown"

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

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["ServerTime", "DeviceSN", "PIN", "EmployeeName", "DeviceTime", "Status", "RawData"])

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

@app.post("/iclock/cdata")
async def handle_attendance(request: Request):
    sn = request.query_params.get('SN', 'UNKNOWN')
    table = request.query_params.get('table')

    if table == 'ATTLOG':
        raw_data = await request.body()
        raw_data_str = raw_data.decode('utf-8')
        data = parse_device_data(raw_data_str)
        
        if data:
            name = PIN_NAME_MAP.get(data['pin'], data['name'])
            log_entry = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                sn,
                data['pin'],
                name,
                data['time'],
                data['status'],
                raw_data_str.replace('\t', '|')
            ]
            with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(log_entry)
            print(f"Scan - PIN: {data['pin']}, Name: {name}, Time: {data['time']}")
        else:
            print(f"Unparseable data: {raw_data_str}")

    return {"message": "OK"}

@app.get("/iclock/getrequest")
async def handle_device_request():
    return {"message": "OK"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9000)