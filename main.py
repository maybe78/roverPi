#!/usr/bin/python3
import time
import qik
import curses
import asyncio
import logging
import math
import serial
from evdev import *
import inputDevice

# All#ow other computers to attach to ptvsd at this IP address and port.
#ptvsd.enable_attach(address=('10.20.30.12', 3333), redirect_output=True)

# Pause the program until a remote debugger is attached
#ptvsd.wait_for_attach()

# create logger with 'spam_application'
logger = logging.getLogger('rover')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('spam.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


# hardware devices setup 
serialDevice = serialport = qik.SerialDriver("/dev/ttyAMA0", 115200)
motorControl = serialDevice.get_controller(0x0A)
pad = inputDevice.ControllerInput()
dev = pad.dev
logger.info('Rover is on. Waiting for commands')
# Steering differential control
def joystickToDiff(x, y, minJoystick, maxJoystick, minSpeed, maxSpeed):
	if x == 0 and y == 0:
		return (0, 0)
	# First Compute the angle in deg & in radians
	z = math.sqrt(x * x + y * y)
	rad = math.acos(math.fabs(x) / z)
	angle = rad * 180 / math.pi
	# Now angle indicates the measure of turn
	tcoeff = -1 + (angle / 90) * 2
	turn = tcoeff * math.fabs(math.fabs(y) - math.fabs(x))
	turn = round(turn * 100, 0) / 100
	# And max of y or x is the movement
	mov = max(math.fabs(y), math.fabs(x))
	# First and third quadrant
	if (x >= 0 and y >= 0) or (x < 0 and y < 0):
		rawLeft = mov
		rawRight = turn
	else:
		rawRight = mov
		rawLeft = turn
	# Reverse polarity
	if y < 0:
		rawLeft = 0 - rawLeft
		rawRight = 0 - rawRight
	# keep in range
	rightSpeed = map(rawRight, minJoystick, maxJoystick, minSpeed, maxSpeed)
	leftSpeed = map(rawLeft, minJoystick, maxJoystick, minSpeed, maxSpeed)
	return (rightSpeed, leftSpeed)

def map(x, in_min, in_max, out_min, out_max):
    return int((x-in_min) * (out_max-out_min) / (in_max-in_min) + out_min)


ls = rs = X = Y = 0
spinc = 4
spRelease=2
while True:
	time.sleep(0.1)
	gen = dev.read()
	state = 0
	try:
		for ev in gen:
			cmd = ev
			logger.debug('X:{0} Y:{1} | L:{2} R:{3} | CMD: {4} CODE: {5}'.format(X,Y,ls,rs,cmd.value,cmd.code))
			if cmd.value == 2:  		# key pressed
				if cmd.code == 103:		# move forward
					Y += spinc
				elif cmd.code == 108:	# move back
					Y -= spinc
				if cmd.code == 105:		# move left
					X -= spinc
				elif cmd.code == 106:	# move right
					X += spinc
			elif cmd.value == 0:  		# key released
				if Y > 0:				
					Y -= spRelease
				elif Y < 0: 			
					Y += spRelease 
				if X > 0:				
					X -= spRelease
				elif X < 0: 			
					X += spRelease 
			sp = joystickToDiff(X, Y, -127, 127, -127, 127)
			ls = sp[0]
			rs = sp[1]
			motorControl.set_motor_speed(0, ls)
			motorControl.set_motor_speed(1, rs)
	except IOError:
		pass