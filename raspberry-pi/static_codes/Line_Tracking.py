import time
from Motor import *
import RPi.GPIO as GPIO

class Line_Tracking:
 def __init__(self):
     # Define GPIO pins for three infrared sensors
     self.IR01 = 14    # Left sensor
     self.IR02 = 15    # Middle sensor
     self.IR03 = 23    # Right sensor
     # Set GPIO mode and configure pins as inputs
     GPIO.setmode(GPIO.BCM)
     GPIO.setup(self.IR01,GPIO.IN)
     GPIO.setup(self.IR02,GPIO.IN)
     GPIO.setup(self.IR03,GPIO.IN)

 def run(self):
     while True:
         # Initialize sensor state variable
         self.LMR=0x00
         # Read sensors and update state using bitwise operations
         if GPIO.input(self.IR01)==True:    # If left sensor detects line
             self.LMR=(self.LMR | 4)        # Set bit 2 (binary 100)
         if GPIO.input(self.IR02)==True:    # If middle sensor detects line
             self.LMR=(self.LMR | 2)        # Set bit 1 (binary 010)
         if GPIO.input(self.IR03)==True:    # If right sensor detects line
             self.LMR=(self.LMR | 1)        # Set bit 0 (binary 001)

         # Control car movement based on sensor states
         if self.LMR==2:      # Only middle sensor detects line (010)
             PWM.setMotorModel(1000,1000,1000,1000)    # Move forward
         elif self.LMR==6:    # Left and middle sensors detect line (110)
             PWM.setMotorModel(-1100,-1100,1100,1100)  # Turn left slightly
         elif self.LMR==4:    # Only left sensor detects line (100)
             PWM.setMotorModel(-1300,-1300,1300,1300)  # Turn left sharply
         elif self.LMR==3:    # Middle and right sensors detect line (011)
             PWM.setMotorModel(1100,1100,-1100,-1100)  # Turn right slightly
         elif self.LMR==1:    # Only right sensor detects line (001)
             PWM.setMotorModel(1300,1300,-1300,-1300)  # Turn right sharply
         elif self.LMR==0:    # No sensor detects line (000)
             PWM.setMotorModel(0,0,0,0)     # Stop
         elif self.LMR==7:    # All sensors detect line (111)
             PWM.setMotorModel(0,0,0,0)     # Stop

 # Create instance of Line_Tracking class
infrared=Line_Tracking()

 # Main program logic follows:
if __name__ == '__main__':
    print('Program is starting ... ')
    try:
        infrared.run()    # Start line tracking
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, stop the car
        PWM.setMotorModel(0,0,0,0)
    except Exception as e:    # Handle other exceptions
        print(f'An error occurred: {e}')
    finally:    # Ensure motor stops in any case
        PWM.setMotorModel(0,0,0,0)
        print('Motor model has been set to stop state.')