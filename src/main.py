import logging
from time import sleep
from threading import Thread, Lock
from evdev._ecodes import ABS_X, ABS_Y
import serial

# Ваши существующие импорты
import dualshock4
from qik import MotorController
from QikErrorChecker import QikErrorChecker
import utils
from web_commands import WebCommands
from audio_player import AudioPlayer

# Новый импорт для веб-сервера
from web_server.app_factory import create_app
from object_detector import VirtualCameraObjectDetector

# --- НАСТРОЙКИ ---
dead_zone = 10
timeout = 0.1
shutdown_requested = False

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    level=logging.INFO,
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

app, socketio = create_app(web_commands, audio_player)

thread_count_lock = Lock()
active_threads = 0

# Инициализация детектора объектов
object_detector = None

def start_object_detection():
    global object_detector
    try:
        logger.info("Инициализация детектора объектов...")
        object_detector = VirtualCameraObjectDetector(input_device_index=0, output_device="/dev/video2")
        object_detector.run()
    except Exception as e:
        logger.error(f"Ошибка в детекторе объектов: {e}")

# --- ПРОВЕРКА МОТОРОВ  ---      
# def check_motor_controller():
#     qik_port = None
#     try:
#         logger.info("Проверка контроллера моторов Qik...")
#         qik_port = serial.Serial(port="/dev/ttyUSB0", baudrate=38400, timeout=0.5)
#         qc = QikErrorChecker(serial_port=qik_port, model="2s12v10")
#         qc.check_and_print()
#         logger.info("Контроллер Qik найден и исправен.")
#     except serial.SerialException as se:
#         logger.error(f"Ошибка serial-порта Qik: {se}")
#     except Exception as e:
#         logger.error(f"Не удалось проверить статус Qik: {e}")
#     finally:
#         if qik_port and qik_port.is_open:
#             qik_port.close()

# --- ГЛАВНЫЙ ЦИКЛ УПРАВЛЕНИЯ МОТОРАМИ ---
def motor_control_loop(web_commands_instance):
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
                    ls, rs = 0, 0
                motor_control.set_speed(ls, rs)
            else:
                # Приоритет №2: Веб-интерфейс
                web_ls, web_rs = web_commands_instance.get_speed()
                motor_control.set_speed(web_ls, web_rs)
            
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
    global shutdown_requested
    if shutdown_requested:
        return
        
    logger.info("Выполняется очистка ресурсов...")
    shutdown_requested = True
    
    try:
        motor_control.stop_all()
        logger.info("Моторы остановлены.")
    except Exception as e:
        logger.error(f"Ошибка при остановке моторов: {e}")
    
    logger.info("Очистка ресурсов завершена.")

# --- ТОЧКА ВХОДА ---
if __name__ == '__main__':
    # check_motor_controller()
    motor_thread = None
    audio_player.play("media/startup.mp3")  # Ваш существующий стартовый звук
    
    try:
        # Создаем и запускаем поток для управления моторами (БЕЗ ИЗМЕНЕНИЙ)
        motor_thread = Thread(target=motor_control_loop, 
                                    args=(web_commands,),  # <-- Вот ключевое изменение
                                    daemon=True, 
                                    name="MotorControlThread")
        motor_thread.start()

        # Создаем и запускаем поток для детекции объектов
        detection_thread = Thread(target=start_object_detection,
                                 daemon=True,
                                 name="ObjectDetectionThread")
        detection_thread.start()
        logger.info("Поток детекции объектов запущен")

        # Запускаем веб-сервер в основном потоке
        logger.info("Запуск веб-сервера на http://0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, ssl_context=('certs/cert.pem', 'certs/key.pem'), allow_unsafe_werkzeug=True)
        #socketio.run(app, host='0.0.0.0', port=5000)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал завершения. Начинаем остановку...")
    finally:
        cleanup()
        if motor_thread and motor_thread.is_alive():
            motor_thread.join(timeout=2.0)
        if detection_thread and detection_thread.is_alive():
            detection_thread.join(timeout=2.0)
        logger.info("Программа завершена.")
