"""
หลบสิ่งกีดขวางด้วย Ultrasonic sensor
รถจะวิ่งหน้า ถ้าระยะ < 20cm จะหยุดแล้วถอยและเลี้ยว
"""
import time
import RPi.GPIO as GPIO
from Motor import Motor

class Ultrasonic:
    def __init__(self):
        self.trigger_pin = 27
        self.echo_pin = 22
        self.MAX_DISTANCE = 300
        self.timeOut = self.MAX_DISTANCE * 60
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)

    def get_distance(self):
        GPIO.output(self.trigger_pin, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.trigger_pin, GPIO.LOW)
        t0 = time.time()
        while GPIO.input(self.echo_pin) == GPIO.LOW:
            if time.time() - t0 > 0.1:
                return 999
        t1 = time.time()
        while GPIO.input(self.echo_pin) == GPIO.HIGH:
            if time.time() - t1 > 0.1:
                return 999
        return (time.time() - t1) * 34000 / 2

PWM = Motor()
sonar = Ultrasonic()
SPEED = 1500
SAFE_DISTANCE = 20  # cm

try:
    print('เริ่มหลบสิ่งกีดขวาง...')
    while True:
        dist = sonar.get_distance()
        print(f'ระยะ: {dist:.1f} cm')

        if dist > SAFE_DISTANCE:
            PWM.setMotorModel(SPEED, SPEED, SPEED, SPEED)
        else:
            print('พบสิ่งกีดขวาง! ถอยและเลี้ยว')
            PWM.setMotorModel(-SPEED, -SPEED, -SPEED, -SPEED)
            time.sleep(0.5)
            PWM.setMotorModel(SPEED, SPEED, -SPEED, -SPEED)
            time.sleep(0.5)

        time.sleep(0.1)

except KeyboardInterrupt:
    print('หยุด')
    PWM.setMotorModel(0, 0, 0, 0)
    GPIO.cleanup()
