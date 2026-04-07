# สรุปโปรเจกต์ Python Field Control System  
เอกสารนี้สรุปโครงสร้าง การทำงาน และส่วนประกอบทั้งหมดของโปรเจกต์ สำหรับใช้ในรายงานและการนำเสนอ

---

## 1. บทนำและวัตถุประสงค์

**Python Field Control System** เป็นระบบควบคุมสนามทดลองรถหุ่นยนต์ที่รันสคริปต์ **Python** บน **Raspberry Pi** โดยมี **เว็บแอปพลิเคชัน** เป็นศูนย์กลางสำหรับ:

- **ยืนยันตัวตนและสิทธิ์** (ผู้ใช้ทั่วไป / ผู้ดูแลระบบ)
- **จัดคิวการใช้สนาม** (จองช่วงเวลา)
- **เลือกหุ่นยนต์** และ **ควบคุมการรันโค้ด** (อัปโหลด รัน หยุด รีเซ็ต)
- **สตรีมกล้อง** และ **ดีบักผ่าน SignalR แบบเรียลไทม์**
- **บันทึกกิจกรรม** ลงฐานข้อมูลสำหรับตรวจสอบย้อนหลัง

กลุ่มเป้าหมายของระบบคือการเรียนการสอนหรือการแข่งขันที่ต้องการ **แยกพื้นที่ปลอดภัย** (คิว + การล็อกผู้ใช้ปัจจุบันกับหุ่น/กล้อง) และ **สื่อสารระหว่างเซิร์ฟเวอร์กับ Pi ผ่าน WebSocket** โดยไม่ต้องเปิดพอร์ตเข้าหา Pi จากอินเทอร์เน็ตโดยตรงในทิศทางหลัก

---

## 2. ภาพรวมสถาปัตยกรรม (สามชั้นหลัก)

| ชั้น | เทคโนโลยี | บทบาท |
|------|-----------|--------|
| **เว็บ + API** | ASP.NET Core 8, หน้า Static ใน `wwwroot` | ให้ UI, REST API, JWT, SignalR Hub, เสิร์ฟไฟล์คงที่ |
| **ฐานข้อมูล** | PostgreSQL | ผู้ใช้, การจอง, หุ่นยนต์, อัปโหลด, บันทึกการทำงาน |
| **เอเจนต์บนรถ** | Python 3, Flask (health เล็กน้อย), `signalrcore` | เชื่อม Hub, รับคำสั่ง, รัน subprocess โค้ดผู้ใช้, กล้อง, heartbeat |

**ลำดับการสตาร์ทที่แนะนำ:** PostgreSQL → Backend ASP.NET (พอร์ต 5000) → Raspberry Pi (เชื่อม `SERVER_URL` ไปยัง backend)

---

## 3. โครงสร้างโฟลเดอร์ใน Repository (มุมมองภาพรวม)

```
Project/
├── backend-aspnet/          # Backend + Frontend รวมในโปรเจกต์เดียว
│   ├── Controllers/         # API: Auth, Queue, Control, Robots, Logs, Uploads
│   ├── Services/            # DB, เวลาเขต, การเชื่อมหุ่น, โบรกเกอร์คำสั่ง, แคตตาล็อกโค้ดตัวอย่าง
│   ├── Hubs/                # SignalR RobotHub
│   ├── database/            # schema.sql (PostgreSQL)
│   └── wwwroot/             # HTML, CSS, JS, templates (SPA แบบหลายหน้า)
├── raspberry-pi/            # เอเจนต์บน Raspberry Pi
│   ├── app.py               # จุดเข้า Flask + สตาร์ท threads
│   ├── config.py            # ค่าคงที่และอ่าน environment
│   ├── signalr_client.py    # ลูกค้า SignalR: รับคำสั่ง ส่งผลลัพธ์ เฟรมกล้อง
│   ├── state.py             # สถานะแชร์ (โปรเซสที่รัน ผู้ใช้ปัจจุบัน ฯลฯ)
│   ├── user_scripts.py      # จัดการไฟล์ .py ต่อผู้ใช้
│   ├── utils.py             # ตรวจสอบความปลอดภัยของโค้ด
│   ├── services/            # code_runner, camera
│   └── static_codes/        # สคริปต์ตัวอย่าง + manifest.json (คำอธิบายภาษาไทย)
├── README.md                # คู่มือติดตั้งและรัน
├── HowToDeployCloud.md      # คู่มือ deploy ไปคลาวด์ (เช่น Render)
└── .env.example             # ตัวอย่างตัวแปรสภาพแวดล้อม (ถ้ามีใน repo)
```

---

## 4. Backend ASP.NET — รายละเอียด

### 4.1 การตั้งค่าแอปพลิเคชัน (`Program.cs`)

- ใช้ **Kestrel** จำกัดขนาด body ~20 MB สำหรับอัปโหลด
- ลงทะเบียนบริการสำคัญ: `DatabaseService`, `AppTimeService`, `RobotConnectionService`, `RobotCommandBrokerService`, `StaticCodesCatalogService`, `HttpClient`, **SignalR**
- **CORS** รองรับ `localhost` และค่า `ClientUrl` จาก configuration
- **JWT Bearer** สำหรับ API ที่ต้องล็อกอิน (คีย์จาก `Jwt:Secret`)
- ลำดับ middleware: CORS → Static Files → Authentication → Authorization → Controllers → **Hub `/hubs/robot`** → fallback `index.html`
- ตอนสตาร์ทจะเรียก **EnsureSchemaAppliedAsync** เพื่อให้ schema ฐานข้อมูลพร้อมใช้ (หากล้มเหลวจะ log แต่ยังรันแอปต่อได้)

### 4.2 SignalR — `RobotHub`

Hub นี้เป็นศูนย์กลางการสื่อสารแบบสองทิศทางกับ Raspberry Pi และไคลเอนต์เว็บ:

| เมธอด / เหตุการณ์ | ทิศทาง | ความหมายโดยย่อ |
|-------------------|--------|------------------|
| `RobotConnect(carId, name, ip, port)` | Pi → Server | ลงทะเบียนหุ่น แจ้งทุก client `RobotStatusUpdate` |
| `RobotHeartbeat(...)` | Pi → Server | อัปเดตสถานะ battery/position (ในโค้ด Pi ใช้ค่าสมมติบางส่วน) และ broadcast |
| `DeployCode` | Server → Pi | (legacy) ส่งข้อความโค้ดให้ Pi เซฟและตรวจสอบ |
| `RobotCommandRequest` | Server → Pi | คำสั่งที่มี correlation id สำหรับรอผลตอบกลับ |
| `RobotCommandResult` | Pi → Server | Pi ตอบกลับ → `RobotCommandBrokerService` ปิด Task ที่รอ |
| `RobotCameraFrame` | Pi → Server | เฟรมภาพ base64 สำหรับสตรีม |
| `DeployResult`, `RobotDebug`, ฯลฯ | ส่งต่อ | แจ้ง UI / ดีบัก |

เมื่อ connection ขาด `OnDisconnectedAsync` จะถอดหุ่นออกจากการเชื่อมต่อและ broadcast สถานะ `disconnected`

### 4.3 `RobotConnectionService`

- เก็บสถานะหุ่นใน **หน่วยความจำ** (ConnectionId, CarId, IP, พอร์ต, สถานะ, ผู้ใช้ล่าสุด)
- **ซิงก์กับ PostgreSQL** (`ROBOT_CARS`) เมื่อ Pi เชื่อมใหม่ (upsert โดย `car_id`)
- ให้รายการหุ่นที่ “ว่าง/พร้อมเลือก” ตามสถานะ (เช่น `idle`, `available`)
- รองรับการ **ผูกผู้ใช้กับหุ่นที่เลือก** (ผ่านเมธอดอื่นใน service เช่น `SelectRobotAsync`)

### 4.4 `RobotCommandBrokerService`

- รูปแบบ **Request–Response แบบ asynchronous**: สร้าง `correlationId` ส่ง `RobotCommandRequest` ไปกลุ่ม SignalR `robot-{carId}` รอ Pi ตอบ `RobotCommandResult`
- มีการ **timeout** และกรณี Pi offline / broker ล้มเหลว แยกเป็น status code ที่เหมาะสม (503, 504 ฯลฯ)

กลไกนี้ทำให้ REST API ฝั่งควบคุมสนามสามารถเรียก “คำสั่งเดียว” แล้วได้ผลจาก Pi โดยไม่ต้อง polling HTTP ไปที่ Pi โดยตรง

### 4.5 Controllers สำคัญ

- **`AuthController`** — `register`, `login` (BCrypt hash), ออก **JWT** พร้อม claims `userId`, `username`, `role`
- **`QueueController`** — ดูคิว, จอง (`book`), ยกเลิก ฯลฯ โดยซิงก์สถานะ `pending` → `active` → `done` ตามเวลาในเขตที่กำหนด (`AppTimeService`)
- **`RobotsController`** — `available` (หุ่นที่พร้อม), `select` (เลือกหุ่นสำหรับ session)
- **`ControlController`** — ฮับควบคุมสนาม: ตรวจสอบ **booking ที่ active** ก่อนอนุญาตอัปโหลด/รันคำสั่ง, ส่งคำสั่งไป Pi ผ่าน broker, จัดการโค้ดตัวอย่าง (`StaticCodesCatalogService`), บันทึก `EXECUTION_LOGS`
- **`LogsController`** — ผู้ใช้ดู log ของตนเอง, แอดมินดูทั้งระบบ
- **`UploadsController`** — บันทึก metadata การอัปโหลดไฟล์ (เชื่อม `USERS`)

### 4.6 Frontend (`wwwroot`)

- **SPA แบบหลายหน้า** โหลดจาก `index.html` และ partial templates
- โมดูล JS หลัก: `auth.js`, `api`/`utils`, หน้า `pages/` (dashboard, queue, control, admin, robot-selector)
- **ธีม** มืด โทน cyan/teal, responsive, sidebar
- ลูกค้า SignalR ฝั่งเบราว์เซอร์ (ในโค้ดหน้า control) ใช้รับสถานะหุ่น เฟรมกล้อง และอีเวนต์แบบเรียลไทม์

### 4.7 บริการเสริม

- **`StaticCodesCatalogService`** — จัดการโฟลเดอร์ `static_codes` (สคริปต์ตัวอย่าง) ร่วมกับ `manifest.json` สำหรับชื่อเรื่อง/คำอธิบายภาษาไทย
- **`AppTimeService`** — ทำให้การเปรียบเทียบเวลาคิวสอดคล้องกับเขตเวลาที่ตั้งค่าในระบบ

---

## 5. ฐานข้อมูล PostgreSQL — โมเดลข้อมูล

ตารางหลักใน `database/schema.sql`:

| ตาราง | บทบาท |
|--------|--------|
| **USERS** | บัญชีผู้ใช้, รหัสผ่านแฮช, บทบาท `user` / `admin` |
| **FIELDS** | สนาม (โปรเจกต์ seed “Main Field”) |
| **BOOKINGS** | การจองช่วงเวลา, สถานะ pending/active/done/cancelled |
| **UPLOADS** | ประวัติไฟล์ที่อัปโหลด |
| **ROBOT_CARS** | ข้อมูลหุ่นตาม `car_id`, IP, port, สถานะ, ผู้ใช้ปัจจุบัน |
| **EXECUTION_LOGS** | บันทึกการกระทำ: upload, run, stop, reset, กล้อง, error |

มี trigger อัปเดต `updated_at` บนตารางที่เกี่ยวข้อง และ seed ผู้ดูแลเริ่มต้น (รายละเอียดรหัสผ่านดูใน README)

---

## 6. Raspberry Pi — เอเจนต์หุ่นยนต์

### 6.1 บทบาทรวม

1. เปิด **Flask** เล็กน้อยที่เส้นทาง **`GET /health`** สำหรับตรวจสุขภาพใน LAN (สถานะ SignalR, จำนวน subprocess, กล้อง ฯลฯ)
2. เชื่อม **SignalR** ไป `SERVER_URL/hubs/robot`
3. รับคำสั่งผ่าน **`RobotCommandRequest`** แล้วตอบ **`RobotCommandResult`**
4. **รันโค้ดผู้ใช้** ใน subprocess แยก พร้อมอ่าน stdout/stderr เข้า execution log ใน memory
5. **สตรีมกล้อง** (OpenCV) เป็น JPEG base64 ผ่าน `RobotCameraFrame` เมื่อเปิดใช้งาน

### 6.2 การจัดการไฟล์สคริปต์ผู้ใช้

- โฟลเดอร์หลัก `user_codes` แยกย่อยตาม `user_id` (ดู `user_scripts.py`)
- รองรับการอัปโหลด base64, ลิสต์ไฟล์, ลบไฟล์, resolve path สำหรับรัน
- มี **validation** ก่อนรันหรือหลังอัปโหลด (`utils.validate_python_code` + whitelist `ALLOWED_IMPORTS` ใน `config.py`)

### 6.3 `services/code_runner.py`

- ใช้ `subprocess.Popen` รันสคริปต์ด้วย `PYTHON_EXE` (ค่าเริ่มต้น `python3`)
- ตั้ง **cwd** เป็นโฟลเดอร์ของสคริปต์ และตั้ง **PYTHONPATH** ให้รวมโฟลเดอร์สคริปต์, รากโปรเจกต์ Pi, และ `user_codes` เพื่อให้ import โมดูลเสริมใน repo (เช่น ไดรเวอร์มอเตอร์) ได้
- เธรดอ่าน stdout/stderr และเธรดเฝ้าเมื่อโปรเซสจบเพื่อเคลียร์สถานะและ `current_user` หากจำเป็น

### 6.4 `services/camera.py`

- ใช้ OpenCV `VideoCapture` ความละเอียดประมาณ 640×480
- เธรดใน `signalr_client` ส่งเฟรมเป็น base64 ประมาณ 4 เฟรม/วินาทีเมื่อกล้อง active

### 6.5 ความปลอดภัยและการแยกผู้ใช้บน Pi

- **`current_user`**: จำกัดว่าในเวลาหนึ่งหุ่นหนึ่งคันจะให้คนเดียว “ครอบครอง” การรันโค้ดหรือกล้อง (ป้องกันการชนกันของคำสั่ง)
- คำสั่ง `run`, `camera_start` ฯลฯ ตรวจสอบว่าไม่มีผู้ใช้อื่นกำลังใช้งาน

### 6.6 สคริปต์ตัวอย่าง (`static_codes`)

- ตัวอย่างเช่น **Ultrasonic**, **Line_Tracking**, **Light** พร้อม **manifest.json** อธิบายหัวข้อภาษาไทยสำหรับ UI

---

## 7. ลำดับการทำงานเชิงธุรกิจ (ตัวอย่างสำหรับนำเสนอ)

1. ผู้ใช้ **ลงทะเบียน/ล็อกอิน** → ได้ JWT  
2. **จองคิว** ช่วงเวลาในสนาม → ระบบอัปเดตสถานะเมื่อถึงเวลา  
3. เมื่อถึงช่วงจอง ผู้ใช้เข้า **แดชบอร์ด** เลือกหุ่นที่ออนไลน์  
4. เข้า **หน้าควบคุmlงสนาม** อัปโหลดหรือเลือกไฟล์ Python → backend ตรวจ booking แล้วส่งคำสั่งไป Pi  
5. Pi **ตรวจโค้ด** แล้ว **รัน subprocess** ผลลัพธ์แสดงเป็น execution log ผ่าน SignalR/API  
6. หากต้องการ **ดูภาพ** เปิดกล้อง → Pi ส่งเฟรมขึ้น Hub → เว็บแสดงภาพ  
7. **หยุด / รีเซ็ต** ปิดโปรเซสและปลดล็อกผู้ใช้  
8. แอดมินดู **สถิติและ logs** ผ่าน API และหน้า admin  

---

## 8. การ deploy และการเชื่อมต่อเครือข่าย

- **ท้องถิ่น:** Backend `http://localhost:5000`, Pi ตั้ง `SERVER_URL` ชี้ IP เครื่องที่รัน backend  
- **คลาวด์:** เอกสาร `HowToDeployCloud.md` อธิบายการ deploy บน Render ด้วย Docker, ตั้ง `DATABASE_URL` / connection string, และให้ Pi ชี้ `SERVER_URL` เป็น URL สาธารณะ  
- **ข้อควรระวัง:** Pi ต้องเข้าถึง backend ได้; หาก backend อยู่หลัง HTTPS การตั้งค่าใบรับรองและ CORS/`ClientUrl` ต้องสอดคล้องกัน  

---

## 9. จุดเด่นสำหรับใส่ในรายงาน/สไลด์

- **สถาปัตยกรรมแยกชัด:** เว็บรวมศูนย์ + Pi เป็น worker ที่รันโค้ดจริง  
- **เรียลไทม์:** SignalR สำหรับสถานะหุ่น กล้อง และคำสั่งแบบ sync ด้วย correlation id  
- **การจัดคิว:** ลดการใช้สนามซ้อนกันด้วย booking และการตรวจสอบฝั่ง API  
- **ความปลอดภัยเบื้องต้น:** JWT, BCrypt, whitelist import ของ Python, จำกัดขนาดอัปโหลด  
- **ขยายได้:** หลายหุ่น (`car_id` ต่างกัน), หลายผู้ใช้, แยกแอดมิน  

---

## 10. คำศัพท์อ้างอิงสั้นๆ

| คำศัพท์ | ความหมายในโปรเจกต์ |
|---------|---------------------|
| **Hub** | จุดเชื่อม SignalR `/hubs/robot` |
| **Broker** | ตัวกลางจับคู่คำสั่งกับคำตอบจาก Pi |
| **Booking** | การจองช่วงเวลาใช้สนาม |
| **Agent** | โปรแกรม Python บน Raspberry Pi |

---