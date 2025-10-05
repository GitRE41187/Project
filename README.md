# Python Field Control System

ระบบควบคุมการทำโค้ด Python บนสนามที่ควบคุมด้วย Raspberry Pi สำหรับการจัดการคิวและควบคุมหุ่นยนต์

## ภาพรวมระบบ

ระบบนี้ประกอบด้วย 3 ส่วนหลัก:
- **Backend API** (Node.js/Express) - จัดการผู้ใช้, คิว, และการควบคุม
- **Frontend Web** (React.js) - หน้าจอสำหรับผู้ใช้และผู้ดูแลระบบ
- **Raspberry Pi Controller** (Python/Flask) - ควบคุมหุ่นยนต์และรับโค้ด Python

## ความต้องการของระบบ

### เซิร์ฟเวอร์หลัก
- Node.js 16+ 
- MySQL 8.0+
- Python 3.8+
- ระบบปฏิบัติการ: Windows 10+, Ubuntu 20.04+, หรือ macOS

### Raspberry Pi
- Raspberry Pi 4 (แนะนำ 4GB RAM ขึ้นไป)
- SD Card 32GB+ (Class 10)
- กล้อง USB หรือ Pi Camera
- ฮาร์ดแวร์หุ่นยนต์ (มอเตอร์, เซ็นเซอร์, ฯลฯ)

## การติดตั้งระบบ

### 1. เตรียมฐานข้อมูล

```bash
# ติดตั้ง MySQL
# Windows: ดาวน์โหลดจาก https://dev.mysql.com/downloads/mysql/
# Ubuntu: sudo apt update && sudo apt install mysql-server
# macOS: brew install mysql

# เข้าสู่ MySQL
mysql -u root -p

# สร้างฐานข้อมูล
CREATE DATABASE field_control;
exit
```

### 2. ติดตั้ง Backend

```bash
# คัดลอกไฟล์ environment
cd backend
cp env.example .env

# แก้ไข .env ตามการตั้งค่าของคุณ
# DB_HOST=localhost
# DB_USER=root
# DB_PASSWORD=your_mysql_password
# DB_NAME=field_control
# JWT_SECRET=your_super_secret_jwt_key_here
# PORT=5000

# ติดตั้ง dependencies
npm install

# รันฐานข้อมูล
mysql -u root -p field_control < ../database/schema.sql

# รันเซิร์ฟเวอร์
npm run dev
```

### 3. ติดตั้ง Frontend

```bash
cd frontend

# ติดตั้ง dependencies
npm install

# รันแอปพลิเคชัน
npm start
```

### 4. ติดตั้ง Raspberry Pi Controller

```bash
cd raspberry-pi

# ติดตั้ง dependencies
pip install -r requirements.txt

# รันเซิร์ฟเวอร์ Raspberry Pi
python app.py
```

## การตั้งค่า Raspberry Pi

### 1. ติดตั้งระบบปฏิบัติการ

```bash
# ดาวน์โหลด Raspberry Pi OS
# ใช้ Raspberry Pi Imager เพื่อ burn ลง SD Card

# เปิดใช้งาน SSH
sudo systemctl enable ssh
sudo systemctl start ssh

# เปิดใช้งาน Camera (ถ้าใช้ Pi Camera)
sudo raspi-config
# เลือก Interface Options > Camera > Enable
```

### 2. ติดตั้งซอฟต์แวร์ที่จำเป็น

```bash
# อัปเดตระบบ
sudo apt update && sudo apt upgrade -y

# ติดตั้ง Python และ pip
sudo apt install python3 python3-pip python3-venv -y

# ติดตั้ง OpenCV dependencies
sudo apt install libopencv-dev python3-opencv -y

# ติดตั้ง GPIO library
sudo apt install python3-rpi.gpio -y

# ติดตั้ง camera dependencies
sudo apt install python3-picamera2 -y
```

### 3. ตั้งค่าเครือข่าย

```bash
# ตั้งค่า IP แบบ static (แนะนำ)
sudo nano /etc/dhcpcd.conf

# เพิ่มบรรทัดต่อไปนี้ (ปรับ IP ตามเครือข่ายของคุณ)
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4

# หรือสำหรับ WiFi
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

### 4. คัดลอกโค้ดและตั้งค่า

```bash
# คัดลอกโฟลเดอร์ raspberry-pi ไปยัง Raspberry Pi
scp -r raspberry-pi/ pi@192.168.1.100:/home/pi/

# เข้าสู่ Raspberry Pi
ssh pi@192.168.1.100

# เข้าสู่โฟลเดอร์
cd raspberry-pi

# สร้าง virtual environment
python3 -m venv venv
source venv/bin/activate

# ติดตั้ง dependencies
pip install -r requirements.txt

# สร้างโฟลเดอร์สำหรับโค้ดผู้ใช้
mkdir user_codes

# รันแอปพลิเคชัน
python app.py
```

## การตั้งค่าหุ่นยนต์

### 1. ฮาร์ดแวร์ที่จำเป็น

- **Raspberry Pi 4** - ตัวควบคุมหลัก
- **Motor Driver** (เช่น L298N, TB6612FNG)
- **DC Motors** x2 - สำหรับการเคลื่อนที่
- **Wheels** - ล้อสำหรับหุ่นยนต์
- **Power Supply** - แบตเตอรี่หรืออะแดปเตอร์
- **Ultrasonic Sensor** - สำหรับตรวจจับสิ่งกีดขวาง
- **Camera Module** - สำหรับการมองเห็น
- **Chassis** - โครงหุ่นยนต์

### 2. การเชื่อมต่อฮาร์ดแวร์

```
Raspberry Pi GPIO Connections:
- GPIO 18, 23 → Motor Driver IN1, IN2 (Motor A)
- GPIO 24, 25 → Motor Driver IN3, IN4 (Motor B)
- GPIO 12, 16 → Motor Driver ENA, ENB (PWM)
- GPIO 20, 21 → Ultrasonic Sensor TRIG, ECHO
- GPIO 2, 3 → Camera I2C (SDA, SCL)
```

### 3. การทดสอบฮาร์ดแวร์

```python
# สร้างไฟล์ test_hardware.py บน Raspberry Pi
import RPi.GPIO as GPIO
import time

# ตั้งค่า GPIO
GPIO.setmode(GPIO.BCM)

# ทดสอบมอเตอร์
motor_pins = [18, 23, 24, 25]
for pin in motor_pins:
    GPIO.setup(pin, GPIO.OUT)

# ทดสอบการหมุนมอเตอร์
def test_motor():
    GPIO.output(18, GPIO.HIGH)
    GPIO.output(23, GPIO.LOW)
    time.sleep(2)
    GPIO.output(18, GPIO.LOW)
    GPIO.output(23, GPIO.LOW)

test_motor()
GPIO.cleanup()
```

## การลงทะเบียนหุ่นยนต์

### 1. ลงทะเบียนหุ่นยนต์กับระบบ

```bash
# ใช้สคริปต์ตัวอย่าง
cd backend/examples
node robot-registration.js
```

### 2. ตั้งค่า Heartbeat

```bash
# สร้างไฟล์ heartbeat.py บน Raspberry Pi
import requests
import time

def send_heartbeat():
    try:
        response = requests.post('http://YOUR_SERVER_IP:5000/api/robots/heartbeat', 
                               json={'carId': 'robot-001'})
        print(f"Heartbeat sent: {response.status_code}")
    except Exception as e:
        print(f"Heartbeat failed: {e}")

# ส่ง heartbeat ทุก 30 วินาที
while True:
    send_heartbeat()
    time.sleep(30)
```

## การใช้งานระบบ

### 1. เข้าสู่ระบบ

- เปิดเบราว์เซอร์ไปที่ `http://localhost:3000`
- ใช้บัญชี admin: `admin@fieldcontrol.com` / `admin123`
- หรือสมัครสมาชิกใหม่

### 2. จองเวลาใช้งาน

- ไปที่หน้า Queue
- เลือกเวลาที่ต้องการ
- กดจองเวลา

### 3. อัปโหลดและรันโค้ด

- ไปที่หน้า Control
- เลือกหุ่นยนต์ที่ต้องการ
- อัปโหลดไฟล์ Python
- กดรันโค้ด

## การแก้ไขปัญหา

### ปัญหาการเชื่อมต่อ Raspberry Pi

```bash
# ตรวจสอบ IP Address
ip addr show

# ตรวจสอบการเชื่อมต่อ
ping 192.168.1.100

# ตรวจสอบพอร์ต
netstat -tlnp | grep 5001
```

### ปัญหาฐานข้อมูล

```bash
# ตรวจสอบสถานะ MySQL
sudo systemctl status mysql

# รีสตาร์ท MySQL
sudo systemctl restart mysql

# ตรวจสอบการเชื่อมต่อ
mysql -u root -p -e "SHOW DATABASES;"
```

### ปัญหาการอัปโหลดไฟล์

```bash
# ตรวจสอบสิทธิ์โฟลเดอร์
ls -la backend/uploads/

# แก้ไขสิทธิ์
chmod 755 backend/uploads/
```

## การบำรุงรักษา

### 1. การสำรองข้อมูล

```bash
# สำรองฐานข้อมูล
mysqldump -u root -p field_control > backup_$(date +%Y%m%d).sql

# สำรองไฟล์โค้ด
tar -czf code_backup_$(date +%Y%m%d).tar.gz backend/uploads/
```

### 2. การอัปเดตระบบ

```bash
# อัปเดต dependencies
cd backend && npm update
cd frontend && npm update
cd raspberry-pi && pip install --upgrade -r requirements.txt
```

### 3. การตรวจสอบสถานะ

```bash
# ตรวจสอบการทำงานของเซิร์ฟเวอร์
curl http://localhost:5000/api/health

# ตรวจสอบสถานะหุ่นยนต์
curl http://localhost:5000/api/robots/available
```

## การตั้งค่าความปลอดภัย

### 1. เปลี่ยนรหัสผ่านเริ่มต้น

```sql
-- เปลี่ยนรหัสผ่าน admin
UPDATE USERS SET password_hash = '$2a$10$new_hashed_password' WHERE username = 'admin';
```

### 2. ตั้งค่า Firewall

```bash
# Ubuntu/Debian
sudo ufw enable
sudo ufw allow 22    # SSH
sudo ufw allow 3000  # Frontend
sudo ufw allow 5000  # Backend
sudo ufw allow 5001  # Raspberry Pi

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --permanent --add-port=5001/tcp
sudo firewall-cmd --reload
```

## การติดต่อและสนับสนุน

หากพบปัญหาหรือต้องการความช่วยเหลือ:

1. ตรวจสอบ Log ไฟล์ในโฟลเดอร์ `logs/`
2. ตรวจสอบสถานะระบบผ่านหน้า Admin Dashboard
3. ดูเอกสารเพิ่มเติมในโฟลเดอร์ `docs/`

## ข้อมูลเพิ่มเติม

- **เวอร์ชัน**: 1.0.0
- **ไลเซนส์**: MIT
- **ผู้พัฒนา**: Your Name
- **อัปเดตล่าสุด**: 2024

---

**หมายเหตุ**: เอกสารนี้ครอบคลุมการติดตั้งและใช้งานพื้นฐาน หากต้องการการตั้งค่าขั้นสูงหรือการปรับแต่งเฉพาะ กรุณาอ่านเอกสารเพิ่มเติมในโฟลเดอร์ `docs/`
