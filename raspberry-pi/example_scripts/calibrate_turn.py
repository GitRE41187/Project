"""Calibration script สำหรับหา ODOMETRY_TURN_RATE และ ODOMETRY_SPEED_SCALE

ใช้เมื่อ RETURN_HOME_MODE=direct เท่านั้น

วิธีใช้ (ขั้นหมุนองศา):
  1. วางเทป/เส้นตรงด้านหน้ารถเป็นหลัก
  2. Upload แล้วรันสคริปต์นี้
  3. หลังขั้น 1 หยุดวัดองศาที่หมุนได้ (เทียบกับเทป)
  4. คำนวณแล้วใส่ใน .env แล้ว restart app.py

สำคัญ: SPEED ต้องตรงกับ ODOMETRY_RETURN_SPEED ใน .env
"""
import time
import math
from Motor import PWM

SPEED = 1500  # ต้องตรงกับ ODOMETRY_RETURN_SPEED ใน .env
# ถ้าหมุนไม่ครบ 360° → เพิ่มค่านี้ (เช่น 2.5, 3.0, 3.5) จนใกล้/เกิน 360° แล้ววัดองศา
TURN_TIME = 3.2
FWD_TIME = 2.0


def stop():
    PWM.setMotorModel(0, 0, 0, 0)


def pause(s=1.0):
    stop()
    time.sleep(s)


try:
    # === ขั้นที่ 1: หา ODOMETRY_TURN_RATE ===
    print('=== ขั้น 1: วัด turn rate ===')
    print('วางเทปที่ด้านหน้ารถเป็นหลัก')
    print('รอ 3 วินาที...')
    time.sleep(3)

    # คำสั่งหมุนซ้าย — ต้องตรงกับ turn_left_cmd ใน return_home (duty3 inverted)
    print(f'หมุนซ้าย {TURN_TIME}s @ duty={SPEED}...')
    PWM.setMotorModel(-SPEED, -SPEED, -SPEED, SPEED)
    time.sleep(TURN_TIME)
    pause()

    print('วัดองศาที่หมุนได้ = X (เทียบเทป/เข็มทิศ)')
    print()
    print('สูตร (ถูกต้อง):')
    print(f'  ODOMETRY_TURN_RATE = radians(X) / {TURN_TIME}')
    print(f'  = (X × π / 180) / {TURN_TIME}')
    print()
    print('ตัวอย่าง:')
    for x in (180, 270, 360, 450):
        rate = math.radians(x) / TURN_TIME
        print(f'  X={x:>3}° → ODOMETRY_TURN_RATE={rate:.4f}')
    print()
    print('วิธีแม่นกว่า: ปรับ TURN_TIME ในไฟล์นี้จนหมุนพอดี 360°')
    print('  แล้ว ODOMETRY_TURN_RATE = 2π / TURN_TIME')
    print(f'  เช่น TURN_TIME=1.96 → {2 * math.pi / 1.96:.4f}')
    print()
    print('ใส่ใน .env:')
    print('  RETURN_HOME_MODE=direct')
    print('  ODOMETRY_RETURN_SPEED=1500')
    print('  ODOMETRY_TURN_RATE=<ค่าที่คำนวณได้>')
    print()

    # === ขั้นที่ 2: หา ODOMETRY_SPEED_SCALE ===
    print('=== ขั้น 2: วัด forward speed (เริ่มใน 3 วินาที) ===')
    print('ถ้ายังไม่วัดระยะ ให้ Ctrl+C / Stop ตอนนี้ได้')
    print('วางรถที่ขอบไม้บรรทัด...')
    time.sleep(3)

    print(f'วิ่งหน้า {FWD_TIME}s...')
    PWM.setMotorModel(SPEED, SPEED, -SPEED, SPEED)
    time.sleep(FWD_TIME)
    pause()

    print(f'วัดระยะที่วิ่งได้ (เมตร) = D')
    print(f'  ODOMETRY_SPEED_SCALE = D / ({SPEED} × {FWD_TIME})')
    print(f'  เช่น D=0.30m → {0.30 / (SPEED * FWD_TIME):.7f}')
    print()
    print('=== ใส่ค่าใน .env แล้ว restart app.py ===')

except Exception as e:
    print(f'Error: {e}')
    stop()
