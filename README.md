# Python Field Control System

ระบบควบคุมการทำโค้ด Python บนสนามที่ควบคุมด้วย Raspberry Pi สำหรับการจัดการคิวและควบคุมหุ่นยนต์

## โครงสร้างโปรเจกต์

```
Project/
├── backend-aspnet/           # Backend API (C#) + Frontend
│   ├── database/             # schema.sql (PostgreSQL)
│   └── wwwroot/
│       ├── css/              # variables, base, layout, sidebar, header, components, auth, forms, responsive
│       ├── js/               # config, api, utils, auth, sidebar, pages/*.js
│       └── templates/        # HTML partials (auth, dashboard, queue, control, admin)
├── raspberry-pi/              # Python Flask Controller
│   ├── config.py             # Config, constants
│   ├── state.py               # Shared state
│   ├── utils.py               # Helpers
│   ├── signalr_client.py     # SignalR connection
│   ├── services/             # code_runner, camera
│   ├── routes/               # api, camera_routes
│   └── app.py                # Entry point
├── .env.example
└── README.md
```

## ความต้องการของระบบ

- **.NET 8** (สำหรับ Backend)
- **PostgreSQL 14+** (หรือใช้ instance ฟรีบน Render / Neon / ฯลฯ)
- **Python 3.8+** (สำหรับ Raspberry Pi)

## ฟีเจอร์ Frontend

- **แดชบอร์ด** – เลือกหุ่นยนต์ ดูสถานะ
- **จองคิว** – จองช่วงเวลาการใช้งานสนาม
- **ควบคุมสนาม** – อัปโหลดโค้ด Python, รัน/หยุด/รีเซ็ต, ควบคุมกล้อง
- **จัดการระบบ** (Admin) – ดูสถิติ การจอง และบันทึกกิจกรรม
- **Sidebar** – เมนูหลัก responsive มี toggle บนมือถือ
- **ธีม** – Dark theme สี cyan/teal อ่านง่ายบนทุกอุปกรณ์

## การติดตั้งและรัน

### 1. ฐานข้อมูล PostgreSQL

สร้าง database ชื่อ `field_control` แล้วรัน schema:

```bash
# ตัวอย่าง (ปรับ user/host ให้ตรงเครื่องคุณ)
psql -U postgres -c "CREATE DATABASE field_control;"
psql -U postgres -d field_control -f backend-aspnet/database/schema.sql
```

### 2. ตั้งค่าสภาพแวดล้อม

```bash
# คัดลอก .env.example เป็น .env ที่ Project root
copy .env.example .env
# แก้ไขค่า DB_* ถ้าใช้สคริปต์อ้างอิง — หรือตั้ง ConnectionStrings ใน appsettings โดยตรง
```

### 3. Backend ASP.NET (พอร์ต 5000)

```bash
cd backend-aspnet
# แก้ ConnectionStrings ใน appsettings.json
dotnet run
```

- **API**: http://localhost:5000/api/*
- **Frontend**: http://localhost:5000/
- **SignalR Hub**: http://localhost:5000/hubs/robot

### 4. Raspberry Pi (เชื่อมกับ backend-aspnet)

`raspberry-pi/config.py` รองรับ env สำหรับเชื่อม ASP.NET backend โดยตรงแล้ว (SignalR Hub: `/hubs/robot`)

ค่าที่แนะนำ:

- `SERVER_URL` (บังคับ) เช่น `http://192.168.1.132:5000`
- `ROBOT_CAR_ID` เช่น `robot-001`
- `ROBOT_CAR_NAME` เช่น `Alpha Bot`
- `ROBOT_CAR_IP` เช่น `192.168.1.50` (ไม่ใส่จะ auto detect)
- `ROBOT_CAR_PORT` เช่น `5001` (รองรับ alias เดิม `PORT`)

ตัวอย่างไฟล์ `raspberry-pi/.env`

```env
FLASK_ENV=development
FLASK_DEBUG=True
SERVER_URL=http://192.168.1.132:5000
ROBOT_CAR_ID=robot-001
ROBOT_CAR_NAME=Alpha Bot
ROBOT_CAR_IP=192.168.1.50
ROBOT_CAR_PORT=5001
UPLOAD_FOLDER=user_codes
MAX_FILE_SIZE=10485760
```

ทดสอบรันแบบ manual:

```bash
cd raspberry-pi
pip install -r requirements.txt
python app.py
```

เมื่อเชื่อมสำเร็จ จะเห็น log แนว `Robot car registered` และ backend จะเห็น robot ผ่าน endpoint `GET /api/robots/available`

## ลำดับการสตาร์ท (แนะนำ)

1. PostgreSQL
2. Backend ASP.NET (port 5000)
3. Raspberry Pi

## การตั้งค่าที่สำคัญ

| ส่วน | Config |
|------|--------|
| **backend-aspnet** | `ConnectionStrings:Default`, `Jwt:Secret`, `ClientUrl` |
| **raspberry-pi** | `SERVER_URL`, `ROBOT_CAR_ID`, `ROBOT_CAR_NAME`, `ROBOT_CAR_IP`, `ROBOT_CAR_PORT` |

## การรันโค้ดผู้ใช้แบบแยกสภาพแวดล้อม (Sandbox + ติดตั้ง package อัตโนมัติ)

ฝั่ง Raspberry Pi จะจัดการ dependency และการรันโค้ดผู้ใช้ให้แบบนี้:

- **ตอนอัปโหลด (`upload_code` / deploy)**: ระบบจะสแกน `import` ในไฟล์ด้วย `ast` แปลงชื่อ module เป็นชื่อ pip package (เช่น `cv2` → `opencv-python`, `PIL` → `Pillow`) แล้ว `pip install` เข้า venv เฉพาะของหุ่นยนต์ให้ล่วงหน้า ผู้ใช้จะเห็น log การติดตั้งใน console และผลสรุปอยู่ใน payload ฟิลด์ `dependencies` — ทำให้ตอนกด Run ไม่เจอ `ModuleNotFoundError` อีก
- **ตอนรัน (`run`)**: รันผ่าน virtual environment (`.runtime-venv` สร้างด้วย `--system-site-packages` จึงยังเห็น `RPi.GPIO` / กล้องของระบบ) พร้อมจำกัด memory/CPU และ kill ทั้ง process group เวลา stop

ปรับพฤติกรรมผ่าน env บน Pi ได้:

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|--------|-----------|----------|
| `RUN_SANDBOX` | `venv` | `venv` (แนะนำ) / `docker` (ต้องมี Docker บนเครื่อง) / `none` (รันตรงแบบเดิม) |
| `AUTO_INSTALL_DEPENDENCIES` | `true` | ติดตั้ง package ที่ขาดตอนอัปโหลด |
| `RESTRICT_INSTALL_TO_WHITELIST` | `true` | ติดตั้งเฉพาะ import ที่อยู่ใน `ALLOWED_IMPORTS` (ปิดเพื่อรองรับ package อิสระโดยพึ่ง sandbox) |
| `PIP_INDEX_URL` / `PIP_TIMEOUT` | – / `120` | mirror และ timeout ของ pip |
| `RUN_MEMORY_LIMIT_MB` / `RUN_CPU_SECONDS` | `512` / `0` | เพดาน RAM/CPU ต่อการรัน (POSIX, `0` = ไม่จำกัด) |
| `DOCKER_IMAGE` / `DOCKER_MEMORY` / `DOCKER_CPUS` / `DOCKER_NETWORK` | `python:3.11-slim` / `512m` / `1` / `none` | ตั้งค่าเมื่อใช้ `RUN_SANDBOX=docker` |

> หมายเหตุ: โหมด `docker` จะติดตั้ง package ภายใน container ตอนรัน และโดยปกติเข้าถึง GPIO/กล้องของ Pi ไม่ได้ จึงเหมาะกับโค้ดที่ไม่พึ่งฮาร์ดแวร์ — งานควบคุมหุ่นยนต์จริงแนะนำ `venv`

## บัญชีเริ่มต้น

- Email: `admin@fieldcontrol.com`
- Password: `admin123`

## วิธีเอาขึ้น Raspberry Pi แบบละเอียด (Production)

### 1) เตรียมเครื่อง Pi

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv
```

> ถ้าใช้กล้อง CSI/USB ให้เปิดใช้งาน camera ตามรุ่น Pi OS ที่ใช้อยู่ก่อน

### 2) ดึงโค้ดลงเครื่อง

มี 2 วิธี (เลือกอย่างใดอย่างหนึ่ง)

**วิธี A: clone จาก Git**

```bash
cd /home/pi
git clone <your-repo-url> Project
cd /home/pi/Project/raspberry-pi
```

**วิธี B: คัดลอกจาก PC ที่อยู่ network เดียวกัน (Windows CMD + SSH)**

บน Windows CMD (copy เฉพาะโฟลเดอร์ `raspberry-pi` ไปที่ Pi):

```bat
scp -r "C:\Users\repri\OneDrive\Desktop\VSFile\Project\raspberry-pi" pi@<PI-IP>:/home/pi/Project/
ssh pi@<PI-IP> "cd /home/pi/Project/raspberry-pi && ls"
```

ตัวอย่าง:

```bat
scp -r "C:\Users\repri\OneDrive\Desktop\VSFile\Project\raspberry-pi" pi@192.168.1.50:/home/pi/Project/
ssh pi@192.168.1.50 "cd /home/pi/Project/raspberry-pi && python3 --version"
```

ถ้าต้องการ copy ทั้งโปรเจกต์:

```bat
scp -r "C:\Users\repri\OneDrive\Desktop\VSFile\Project" pi@192.168.1.50:/home/pi/Project
```

หมายเหตุ:

- เครื่อง Pi ต้องเปิด `SSH` (`sudo raspi-config` -> Interface Options -> SSH)
- บน Windows ต้องมี `OpenSSH Client` (ปกติมีอยู่แล้วใน Windows 10/11)
- ปกติไม่ต้องเปิด OpenSSH Server บน PC เมื่อสั่ง `scp` จาก PC ไป Pi
- ถ้าใช้ `scp` ไม่สะดวก สามารถใช้ shared folder (Samba) หรือ copy ผ่าน USB ได้

### 3) สร้าง virtual environment + ติดตั้งแพ็กเกจ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4) ตั้งค่า environment

สร้างไฟล์ `/home/pi/Project/raspberry-pi/.env`

```env
SERVER_URL=http://<IP-เครื่องที่รัน-backend-aspnet>:5000
ROBOT_CAR_ID=robot-001
ROBOT_CAR_NAME=Alpha Bot
ROBOT_CAR_IP=<IP-ของ-Raspberry-Pi>
ROBOT_CAR_PORT=5001
```

จุดที่ต้องตรวจสอบ:

- เครื่อง Pi ต้อง ping ไปหาเครื่อง backend ได้
- backend ต้องรับจาก LAN ได้ (เช่น bind `http://0.0.0.0:5000`)
- firewall ต้องเปิดพอร์ต `5000` (backend) และ `5001` (Pi API ถ้าจะเรียกตรง)

### 5) ทดสอบรันก่อนทำ service

```bash
cd /home/pi/Project/raspberry-pi
source .venv/bin/activate
python app.py
```

เช็คสุขภาพบริการ:

```bash
curl http://127.0.0.1:5001/health
```

### 6) ทำให้รันอัตโนมัติด้วย systemd

สร้างไฟล์ service:

```bash
sudo nano /etc/systemd/system/field-control-pi.service
```

ใส่ค่า:

```ini
[Unit]
Description=Field Control Raspberry Pi Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Project/raspberry-pi
EnvironmentFile=/home/pi/Project/raspberry-pi/.env
ExecStart=/home/pi/Project/raspberry-pi/.venv/bin/python /home/pi/Project/raspberry-pi/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

สั่งเปิดใช้งาน:

```bash
sudo systemctl daemon-reload
sudo systemctl enable field-control-pi.service
sudo systemctl start field-control-pi.service
sudo systemctl status field-control-pi.service
```

ดู log แบบ realtime:

```bash
journalctl -u field-control-pi.service -f
```

### 7) อัปเดตเวอร์ชันภายหลัง

```bash
cd /home/pi/Project
git pull
cd raspberry-pi
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart field-control-pi.service
```

### Troubleshooting เร็วๆ

- ต่อ backend ไม่ได้: ตรวจ `SERVER_URL` และพอร์ต `5000`
- Robot ไม่ขึ้นในหน้าเว็บ: เช็ค log Pi ว่ามี `Robot car registered`
- service ล้มบ่อย: ดู `journalctl -u field-control-pi.service -n 200`
