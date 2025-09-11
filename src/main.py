import logging
from time import sleep
from collections import namedtuple
from evdev._ecodes import ABS_RX, ABS_RY, ABS_X, ABS_Y
import serial
from select import select
import evdev

import camera_rest_api
import dualshock4
from qik import MotorController
from dualshock4 import DualShock
import utils

dead_zone = 10
camera_ip = '192.168.1.100'
camera_port = 8080
timeout = 0.1
ls = rs = 0
last_l = last_r = 0
rx = ry = lx = ly = 0

logger = logging.getLogger('rover')
logging.basicConfig(
	level=logging.DEBUG,
	format="[%(asctime)s] %(threadName)s %(message)s",
	datefmt="%H:%M:%S"
)

# Peripheral hardware instances
pad = dualshock4.DualShock(dead_zone)
motor_control = MotorController()
#cam = camera_rest_api.CloudCam(camera_ip, camera_port)

while True:
	r = ''
	active_keys = pad.read_events()
	# convert right analog stick values to motor speed using differential control algorithm
	ls, rs = utils.joystick_to_diff_control(pad.active_keys[ABS_X], pad.active_keys[ABS_Y], dead_zone)
	# send ptz commands for camera movement using rest api
	#ptz_command = utils.joystick_to_ptz(pad.active_keys[ABS_X], pad.active_keys[ABS_Y], dead_zone)
	motor_control.set_speed(ls/4, rs/4)
	#if ptz_command:
	#	r = cam.send(ptz_command)
	sleep(timeout)
	motor_control.print_motor_currents()
	logger.debug("Speed: l: %s\tr: %s\t ptz: %s", ls/4, rs/4, r)
