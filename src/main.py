import logging
from time import sleep
from evdev._ecodes import ABS_X, ABS_Y
import serial

import dualshock4
from qik import MotorController
from QikErrorChecker import QikErrorChecker
import utils

from web_commands import WebCommands

dead_zone = 10
timeout = 0.1

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger('rover')

pad = dualshock4.DualShock(dead_zone)
motor_control = MotorController()
web_commands = WebCommands()

qik_port = None
try:
	logger.info("Qik Motor check...")
	qik_port = serial.Serial(port="/dev/ttyUSB0", baudrate=38400, timeout=0.5)
	qc = QikErrorChecker(serial_port=qik_port, model="2s12v10")
	qc.check_and_print()
except serial.SerialException as se:
	logger.error(f"Ошибка serial-порта Qik: {se}")
except Exception as e:
	logger.error(f"Не удалось проверить статус Qik: {e}")
finally:
	if qik_port and qik_port.is_open:
		qik_port.close()


try:
	while True:
		if pad.is_connected():
			active_keys = pad.read_events()
			
			ls, rs = utils.joystick_to_diff_control(
			active_keys[ABS_X], 
			active_keys[ABS_Y], 
				dead_zone
			)
			
			motor_control.set_speed(ls, rs)
			logger.debug(f"Left {ls}, Right: {rs}")

		else:
			# Приоритет №2: Веб-интерфейс
			web_ls, web_rs = web_commands.get_speed()
			if web_ls is not None and web_rs is not None:
				logger.debug(f"Команда из веба -> Левый: {web_ls}, Правый: {web_rs}")
				motor_control.set_speed(web_ls, web_rs)
				# Сбрасываем команду, чтобы робот не ехал бесконечно по последней команде
				web_commands.clear()
			else:
				# Если нет никаких команд - стоп
				logger.debug("Нет активных команд. Остановка моторов.")
				motor_control.stop_all()
		
		# Попытка подключения геймпада, если он не активен
		if not pad.is_connected():
			logger.info("Геймпад не найден, попытка переподключения...")
			pad.connect()

		sleep(timeout)

		sleep(timeout)
		motor_control.print_motor_currents()

except KeyboardInterrupt:
	logger.info("Получен сигнал завершения (Ctrl+C).")
except Exception as e:
	logger.critical(f"В основном цикле произошла критическая ошибка: {e}", exc_info=True)
finally:
	# Этот блок гарантирует, что моторы будут остановлены при любом выходе из скрипта.
	logger.info("Завершение работы. Остановка всех моторов.")
	motor_control.stop_all()
