"""
วิ่งเป็นรูปสี่เหลี่ยม (Square Pattern)
รถจะวิ่งหน้า → หมุน 90° × 4 รอบ

ปรับ TURN_TIME ถ้ามุมไม่ครบ 90°:
  - เพิ่มเวลา = หมุนมากขึ้น
  - ลดเวลา = หมุนน้อยลง
"""
import time
from Motor import *

PWM = Motor()
SPEED = 2000
FORWARD_TIME = 0.5 # วิ่งหน้ากี่วินาที
TURN_TIME = 0.55     # หมุน 90° (ปรับตามพื้นผิว)

try:
    for i in range(4):
        print(f'ด้านที่ {i + 1}: วิ่งหน้า')
        PWM.setMotorModel(SPEED, SPEED, SPEED, SPEED)
        time.sleep(FORWARD_TIME)

        print(f'ด้านที่ {i + 1}: หมุนขวา 90°')
        PWM.setMotorModel(SPEED, SPEED, -SPEED, -SPEED)  # pivot turn
        time.sleep(TURN_TIME)

    print('ครบ 4 ด้าน หยุด')
    PWM.setMotorModel(0, 0, 0, 0)

except Exception as e:
    print(f'Error: {e}')
    PWM.setMotorModel(0, 0, 0, 0)

