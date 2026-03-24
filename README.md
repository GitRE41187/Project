# Python Field Control System

ระบบควบคุมการทำโค้ด Python บนสนามที่ควบคุมด้วย Raspberry Pi สำหรับการจัดการคิวและควบคุมหุ่นยนต์

## โครงสร้างโปรเจกต์

```
Project/
├── backend-aspnet/           # Backend API (C#) + Frontend
│   └── wwwroot/
│       ├── css/              # variables, base, layout, sidebar, header, components, auth, forms, responsive
│       ├── js/               # config, api, utils, auth, sidebar, pages/*.js
│       └── templates/        # HTML partials (auth, dashboard, queue, control, admin)
├── database/                 # Schema PostgreSQL
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
psql -U postgres -d field_control -f database/schema.sql
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

### 4. Raspberry Pi

ตั้งค่า `SERVER_URL` ให้ชี้ไปที่ **Backend ASP.NET**

```bash
export SERVER_URL=http://<IP-เครื่องที่รัน-backend>:5000
cd raspberry-pi
pip install -r requirements.txt
python app.py
```

Raspberry Pi จะเชื่อมต่อ SignalR ไปที่ `{SERVER_URL}/hubs/robot` โดยตรง ไม่ต้องผ่านตัวกลาง

## ลำดับการสตาร์ท

1. PostgreSQL  
2. Backend ASP.NET (port 5000)  
3. Raspberry Pi  

## การตั้งค่าที่สำคัญ

| ส่วน | Config |
|------|--------|
| **backend-aspnet** | `ConnectionStrings:Default`, `Jwt:Secret`, `ClientUrl` |
| **raspberry-pi** | `SERVER_URL` = URL ของ Backend (เช่น http://192.168.1.132:5000) |

## บัญชีเริ่มต้น

- Email: `admin@fieldcontrol.com`
- Password: `admin123`

## การตั้งค่า Raspberry Pi (ฮาร์ดแวร์)

ดูรายละเอียดการเชื่อมต่อ GPIO, กล้อง, มอเตอร์ และเซ็นเซอร์ในเอกสารเดิม (เก็บไว้ใน git history ถ้าต้องการ)
