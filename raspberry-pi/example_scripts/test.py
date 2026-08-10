"""ทดสอบวิ่งหน้าตรง — duty3 (right_upper) ต้องกลับขั้ว"""
import time
from Motor import PWM

# right_upper_wheel ต่อสายกลับขั้ว → duty3 ต้องเป็นลบเพื่อหมุนหน้า
FORWARD  = ( 2000,  2000, -2000,  2000)
BACKWARD = (-2000, -2000,  2000, -2000)
STOP     = (0, 0, 0, 0)

try:
    print('วิ่งหน้า...')
    PWM.setMotorModel(*FORWARD)
    time.sleep(0.5)

    print('หยุด')
    PWM.setMotorModel(*STOP)

except Exception as e:
    print(f'Error: {e}')
    PWM.setMotorModel(*STOP)
