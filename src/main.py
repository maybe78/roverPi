import logging
from time import sleep
from threading import Thread, Lock
from evdev._ecodes import ABS_X, ABS_Y
import serial

from flask import Flask, render_template
from flask_socketio import SocketIO

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

# Web-server Init 
app = Flask(__name__)
# Устанавливаем секретный ключ для безопасных сессий
app.config['SECRET_KEY'] = 'your_very_secret_key'
# Создаем экземпляр SocketIO, передавая ему наше приложение
socketio = SocketIO(app, async_mode='threading')

@app.route('/')
def index():
    """Отдает главную HTML-страницу."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Обработчик подключения нового клиента к WebSocket."""
    logger.info("Клиент подключился к веб-интерфейсу")

@socketio.on('control')
def handle_control(data):
	"""
	Принимает данные от веб-джойстика, масштабирует их
	к диапазону [-127, 127] и передает в утилиту управления.
	"""
	try:
		# Координаты от nipplejs приходят в диапазоне [-1.0, 1.0]
		lx = float(data.get('lx', 0.0))
		ly = float(data.get('ly', 0.0))

		# --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
		# Масштабируем веб-координаты [-1.0, 1.0] до диапазона [-127, 127],
		# который, судя по utils.py, ожидает ваша функция.
		scaled_x = int(lx * 127)
		scaled_y = int(ly * 127)

		# Теперь используем ту же самую функцию, что и для геймпада
		ls, rs = utils.joystick_to_diff_control(scaled_x, scaled_y, dead_zone)

		# Сохраняем команду в потокобезопасный объект
		web_commands.set_speed(ls, rs)
		logger.debug(f"Web command accepted: L={ls}, R={rs}")

	except Exception as e:
		logger.error(f"Ошибка в данных от веб-клиента: {e}", exc_info=True)

# Motor Check		
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

def motor_control_loop():
	logger.info("Запуск основного цикла управления моторами...")
	try:
		while True:
			# Приоритет №1: Геймпад
			if pad.is_connected():
				active_keys = pad.read_events()
				if ABS_X in active_keys and ABS_Y in active_keys:
					# Если есть - рассчитываем скорость
					ls, rs = utils.joystick_to_diff_control(
						active_keys[ABS_X],
						active_keys[ABS_Y],
						dead_zone
					)
				else:
					pass
				motor_control.set_speed(ls, rs)
				motor_control.set_speed(ls, rs)
			else:
				# Приоритет №2: Веб-интерфейс
				web_ls, web_rs = web_commands.get_speed()
				if web_ls is not None and web_rs is not None:
					motor_control.set_speed(web_ls, web_rs)
					# # Сбрасываем команду, чтобы робот не ехал бесконечно
					# web_commands.clear()
				else:
					motor_control.stop_all()
			
			if not pad.is_connected():
				pad.connect()

			sleep(timeout)
	finally:
		logger.info("Цикл управления моторами завершен. Остановка моторов.")
		motor_control.stop_all()

	
if __name__ == '__main__':
    try:
        # Создаем и запускаем поток для управления моторами
        motor_thread = Thread(target=motor_control_loop, daemon=True)
        motor_thread.start()
        
        # Запускаем веб-сервер в основном потоке. Он будет работать, пока не будет прерван.
        logger.info("Запуск веб-сервера на http://0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt. Завершение работы...")
    finally:
        logger.info("Программа завершена.")