"""
วิ่งเป็นรูปสี่เหลี่ยม (Square Pattern)
รถจะวิ่งหน้า → หมุนขวา 90° × 4 รอบ

duty3 (right_upper) กลับขั้ว — รูปแบบเดียวกับ test.py / Line_Tracking

ปรับ TURN_TIME ถ้ามุมไม่ครบ 90°:
  - เพิ่มเวลา = หมุนมากขึ้น
  - ลดเวลา = หมุนน้อยลง
"""
import time
from Motor import PWM

SPEED = 2000
FORWARD_TIME = 0.5   # วิ่งหน้ากี่วินาที
TURN_TIME = 0.55     # หมุน 90° (ปรับตามพื้นผิว / แบต)

FORWARD = (SPEED, SPEED, -SPEED, SPEED)
PIVOT_RIGHT = (SPEED, SPEED, SPEED, -SPEED)
STOP = (0, 0, 0, 0)

try:
    for i in range(4):
        print(f'ด้านที่ {i + 1}: วิ่งหน้า')
        PWM.setMotorModel(*FORWARD)
        time.sleep(FORWARD_TIME)
        PWM.setMotorModel(*STOP)
        time.sleep(0.1)

        print(f'ด้านที่ {i + 1}: หมุนขวา 90°')
        PWM.setMotorModel(*PIVOT_RIGHT)
        time.sleep(TURN_TIME)
        PWM.setMotorModel(*STOP)
        time.sleep(0.1)

    print('ครบ 4 ด้าน หยุด')
    PWM.setMotorModel(*STOP)

except KeyboardInterrupt:
    pass
except Exception as e:
    print(f'Error: {e}')
finally:
    PWM.setMotorModel(*STOP)
