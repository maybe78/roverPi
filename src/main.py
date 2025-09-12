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
from QikErrorChecker import QikErrorChecker
from dualshock4 import DualShock
import utils

dead_zone = 10
timeout = 0.1
ls = rs = 0
last_l = last_r = 0
rx = ry = lx = ly = 0
MAX_STRAIGHT_CAP = 65

logger = logging.getLogger('rover')
logging.basicConfig(
	level=logging.DEBUG,
	format="[%(asctime)s] %(threadName)s %(message)s",
	datefmt="%H:%M:%S"
)

# Peripheral hardware instances
pad = dualshock4.DualShock(dead_zone)
motor_control = MotorController()

qik_port = None
try:
    qik_port = serial.Serial(port="/dev/ttyUSB0", baudrate=38400, timeout=0.5)
    qc = QikErrorChecker(serial_port=qik_port, model="2s12v10")
    qc.check_and_print()
except serial.SerialException as se:
    logger.error(f"Ошибка serial-порта при проверке Qik: {se}")
except Exception as e:
    logger.error(f"Не удалось проверить ошибки Qik: {e}")
finally:
    if qik_port and qik_port.is_open:
        qik_port.close()

while True:
	if not pad.is_connected():
		print("Геймпад не подключен. Попытка подключения...")
		motor_control.stop_all() # Останавливаем моторы
		
		# Пытаемся подключиться, и если неудачно, ждем и начинаем цикл заново
		if not pad.connect():
			sleep(2) # Пауза между попытками
			continue
    
    # Рассчитываем и отправляем скорости
	ls, rs = utils.joystick_to_diff_control(
		active_keys[ABS_X],
		active_keys[ABS_Y],
		dead_zone
	)
	motor_control.set_speed(ls, rs)

	sleep(timeout)
	motor_control.print_motor_currents()
	logger.debug("Speed: l: %s\tr: %s\t ptz: %s", ls/2, rs/2, r)
