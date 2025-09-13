import logging
from time import sleep
from threading import Thread
from evdev._ecodes import ABS_X, ABS_Y
import serial
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

import dualshock4
from qik import MotorController
from QikErrorChecker import QikErrorChecker
import utils
from web_commands import WebCommands
from webrtc_handler import WebRTCHandler

dead_zone = 10
timeout = 0.1

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger('rover')

# Инициализация компонентов
pad = dualshock4.DualShock(dead_zone)
motor_control = MotorController()
web_commands = WebCommands()
webrtc_handler = WebRTCHandler()

# Создаем executor для asyncio задач
executor = ThreadPoolExecutor(max_workers=4)

# Web-server Init 
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key'
socketio = SocketIO(
    app, 
    async_mode='threading',
    max_http_buffer_size=1024 * 1024,  # 1MB буфер
    engineio_logger=False,             # Отключаем лишние логи
    socketio_logger=False,             # Отключаем лишние логи
    ping_timeout=60,                   # Увеличиваем таймауты
    ping_interval=25
)

import threading
thread_count_lock = threading.Lock()
active_threads = 0

@socketio.on('control')
def handle_control(data):
    """
    Принимает данные от веб-джойстика с защитой от перегрузки потоками
    """
    global active_threads
    
    # Защита от создания слишком многих потоков
    with thread_count_lock:
        if active_threads > 50:  # Лимит потоков
            logger.warning(f"Thread limit reached: {active_threads}, dropping command")
            return
        active_threads += 1
    
    try:
        # Координаты от nipplejs приходят в диапазоне [-1.0, 1.0]
        lx = float(data.get('lx', 0.0))
        ly = float(data.get('ly', 0.0))

        # Масштабируем веб-координаты [-1.0, 1.0] до диапазона [-127, 127]
        scaled_x = int(lx * 127)
        scaled_y = int(ly * 127)

        # Используем ту же самую функцию, что и для геймпада
        ls, rs = utils.joystick_to_diff_control(scaled_x, scaled_y, dead_zone)

        # Сохраняем команду в потокобезопасный объект
        web_commands.set_speed(ls, rs)
        logger.debug(f"Web command accepted: L={ls}, R={rs}")

    except Exception as e:
        logger.error(f"Ошибка в данных от веб-клиента: {e}")
    finally:
        # Уменьшаем счетчик потоков
        with thread_count_lock:
            active_threads -= 1
            
@app.route('/')
def index():
    """Отдает главную HTML-страницу."""
    return render_template('index.html')

@app.route('/offer', methods=['POST'])
def offer():
    """
    Обрабатывает WebRTC offer от клиента
    """
    try:
        # Получаем offer от клиента
        params = request.get_json()
        logger.debug(f"Received WebRTC offer: {params['type'] if params else 'Invalid'}")
        
        if not params or 'sdp' not in params or 'type' not in params:
            return jsonify({"error": "Invalid offer format"}), 400
        
        # Используем синхронную версию create_offer
        answer = webrtc_handler.create_offer(params)
        logger.info("WebRTC answer created successfully")
        
        return jsonify(answer)
            
    except Exception as e:
        logger.error(f"Error handling WebRTC offer: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Также обновите функцию cleanup:
def cleanup():
    """Функция очистки ресурсов"""
    logger.info("Выполняется очистка ресурсов...")
    
    # Останавливаем WebRTC (теперь синхронно)
    webrtc_handler.shutdown()
    
    # Останавливаем моторы
    motor_control.stop_all()
    
    logger.info("Очистка ресурсов завершена")

@socketio.on('connect')
def handle_connect():
    """Обработчик подключения нового клиента к WebSocket."""
    logger.info("Клиент подключился к веб-интерфейсу")

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
                    ls, rs = 0, 0
                motor_control.set_speed(ls, rs)
            else:
                # Приоритет №2: Веб-интерфейс
                web_ls, web_rs = web_commands.get_speed()
                if web_ls is not None and web_rs is not None:
                    motor_control.set_speed(web_ls, web_rs)
                else:
                    motor_control.stop_all()
            
            if not pad.is_connected():
                pad.connect()

            sleep(timeout)
    except KeyboardInterrupt:
        logger.info("Цикл управления моторами прерван")
    finally:
        logger.info("Цикл управления моторами завершен. Остановка моторов.")
        motor_control.stop_all()

def cleanup():
    """Функция очистки ресурсов"""
    logger.info("Выполняется очистка ресурсов...")
    
    # Останавливаем WebRTC
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(webrtc_handler.shutdown())
    finally:
        loop.close()
    
    # Останавливаем моторы
    motor_control.stop_all()
    
    logger.info("Очистка ресурсов завершена")

if __name__ == '__main__':
    try:
        # Создаем и запускаем поток для управления моторами
        motor_thread = Thread(target=motor_control_loop, daemon=True)
        motor_thread.start()
        
        # Запускаем веб-сервер в основном потоке
        logger.info("Запуск веб-сервера на http://0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt. Завершение работы...")
    finally:
        cleanup()
        logger.info("Программа завершена.")
