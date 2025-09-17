import logging
from time import sleep
from threading import Thread, Lock
from evdev._ecodes import ABS_X, ABS_Y
import serial

from flask import Flask, render_template, request
from flask_socketio import SocketIO

import dualshock4
from qik import MotorController
from QikErrorChecker import QikErrorChecker
import utils
from web_commands import WebCommands
from audio_player import AudioPlayer

# --- НАСТРОЙКИ ---
dead_zone = 10
timeout = 0.1
shutdown_requested = False

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    level=logging.INFO,  # Установим INFO для меньшего количества логов
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger('rover')

# --- ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ ---
try:
    pad = dualshock4.DualShock(dead_zone)
    logger.info("DualShock контроллер инициализирован.")
except Exception as e:
    logger.error(f"Не удалось инициализировать DualShock: {e}")
    pad = None

motor_control = MotorController()
web_commands = WebCommands()
audio_player = AudioPlayer()

# --- ВЕБ-СЕРВЕР ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_for_rover'
socketio = SocketIO(
    app, 
    async_mode='threading',
    engineio_logger=False,
    socketio_logger=False,
)

# --- УПРАВЛЕНИЕ ПОТОКАМИ ---
thread_count_lock = Lock()
active_threads = 0

@socketio.on('control')
def handle_control(data):
    """
    Принимает данные от веб-джойстика.
    """
    global active_threads
    with thread_count_lock:
        if active_threads > 20: # Уменьшаем лимит потоков
            logger.warning(f"Слишком много команд управления, сбрасываем. Потоков: {active_threads}")
            return
        active_threads += 1
    
    try:
        lx = float(data.get('lx', 0.0))
        ly = float(data.get('ly', 0.0))

        scaled_x = int(lx * 127)
        scaled_y = int(ly * 127)

        ls, rs = utils.joystick_to_diff_control(scaled_x, scaled_y, dead_zone)
        web_commands.set_speed(ls, rs)
        logger.debug(f"Команда с веба: L={ls}, R={rs}")

    except (ValueError, TypeError) as e:
        logger.error(f"Некорректные данные от веб-клиента: {e}")
    finally:
        with thread_count_lock:
            active_threads -= 1

@app.route('/')
def index():
    """Отдает главную HTML-страницу."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Обработчик подключения нового клиента."""
    logger.info("Клиент подключился к веб-интерфейсу управления.")

# --- ПРОВЕРКА МОТОРОВ ---      
def check_motor_controller():
    qik_port = None
    try:
        logger.info("Проверка контроллера моторов Qik...")
        qik_port = serial.Serial(port="/dev/ttyUSB0", baudrate=38400, timeout=0.5)
        qc = QikErrorChecker(serial_port=qik_port, model="2s12v10")
        qc.check_and_print()
        logger.info("Контроллер Qik найден и исправен.")
    except serial.SerialException as se:
        logger.error(f"Ошибка serial-порта Qik: {se}")
    except Exception as e:
        logger.error(f"Не удалось проверить статус Qik: {e}")
    finally:
        if qik_port and qik_port.is_open:
            qik_port.close()

# --- ГЛАВНЫЙ ЦИКЛ УПРАВЛЕНИЯ МОТОРАМИ ---
def motor_control_loop():
    logger.info("Запуск основного цикла управления моторами...")
    try:
        while not shutdown_requested:
            # Приоритет №1: Геймпад
            if pad and pad.is_connected():
                active_keys = pad.read_events()
                if ABS_X in active_keys and ABS_Y in active_keys:
                    ls, rs = utils.joystick_to_diff_control(
                        active_keys[ABS_X], active_keys[ABS_Y], dead_zone
                    )
                else:
                    ls, rs = 0, 0 # Если нет данных, останавливаемся
                motor_control.set_speed(ls, rs)
            else:
                # Приоритет №2: Веб-интерфейс
                web_ls, web_rs = web_commands.get_speed()
                if web_ls is not None and web_rs is not None:
                    motor_control.set_speed(web_ls, web_rs)
                else:
                    motor_control.stop_all()
            
            # Попытка переподключения геймпада, если он отключен
            if pad and not pad.is_connected():
                pad.connect()

            sleep(timeout)
    except KeyboardInterrupt:
        logger.info("Цикл управления моторами прерван.")
    finally:
        logger.info("Цикл управления моторами завершен. Остановка моторов.")
        motor_control.stop_all()

# --- ФУНКЦИЯ ОЧИСТКИ ---
def cleanup():
    """Функция очистки ресурсов при завершении работы."""
    global shutdown_requested
    if shutdown_requested:
        return
        
    logger.info("Выполняется очистка ресурсов...")
    shutdown_requested = True
    
    # Останавливаем моторы
    try:
        motor_control.stop_all()
        logger.info("Моторы остановлены.")
    except Exception as e:
        logger.error(f"Ошибка при остановке моторов: {e}")
    
    logger.info("Очистка ресурсов завершена.")

# --- ТОЧКА ВХОДА ---
if __name__ == '__main__':
    check_motor_controller()
    motor_thread = None
    audio_player.play("media/police.mp3")
    try:
        # Создаем и запускаем поток для управления моторами
        motor_thread = Thread(target=motor_control_loop, daemon=True, name="MotorControlThread")
        motor_thread.start()
        
        # Запускаем веб-сервер в основном потоке
        logger.info("Запуск веб-сервера на http://0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал завершения. Начинаем остановку...")
    finally:
        cleanup()
        if motor_thread and motor_thread.is_alive():
            motor_thread.join(timeout=2.0)
        logger.info("Программа завершена.")

