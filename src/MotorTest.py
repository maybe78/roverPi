import sys
import termios
import tty
import select
from time import sleep

# Импортируем оба класса из ваших файлов
from qik import MotorController
from QikErrorChecker import QikErrorChecker


class FourWheelRobotController:
    """
    Класс для управления роботом. Принимает объект MotorController.
    """
    def __init__(self, motor_controller):
        self.mc = motor_controller
        self.debug = True

    def set_debug(self, on=True):
        self.debug = on

    def drive(self, command):
        """
        Устанавливает скорость моторов в зависимости от команды.
        """
        speed = 75  # Базовая скорость (от 0 до 127)

        if command == 'w': # Вперед
            self.mc.set_speed(speed, speed)
        elif command == 's': # Назад
            self.mc.set_speed(-speed, -speed)
        elif command == 'a': # Поворот влево
            self.mc.set_speed(-speed, speed)
        elif command == 'd': # Поворот вправо
            self.mc.set_speed(speed, -speed)
        elif command == ' ': # Стоп
            self.mc.stop_all()
        # Если команда неизвестна, ничего не делаем,
        # чтобы робот продолжал выполнять предыдущую команду.


def is_data():
    """
    Проверяет, есть ли данные для чтения в стандартном вводе (stdin).
    Возвращает True, если пользователь нажал клавишу.
    """
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])


if __name__ == '__main__':
    # Сохраняем старые настройки терминала, чтобы вернуть их при выходе
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        # Устанавливаем режим терминала для немедленного чтения символов
        tty.setcbreak(sys.stdin.fileno())

        # --- ИНИЦИАЛИЗАЦИЯ ОБОРУДОВАНИЯ ---
        print("Инициализация контроллера моторов...")
        # 1. Создаем контроллер моторов. Он открывает и держит порт.
        motor_ctrl = MotorController(port="/dev/ttyS0", baudrate=38400)

        # 2. Создаем проверщик ошибок, передавая ему уже открытый порт
        error_checker = QikErrorChecker(serial_port=motor_ctrl.ser)

        # 3. Создаем объект робота
        robot = FourWheelRobotController(motor_ctrl)
        
        print("\nУправление роботом через WASD.")
        print("Пробел - экстренная остановка.")
        print("Нажмите 'q' для выхода.\n")
        
        last_key = ' '  # Последняя нажатая клавиша, по умолчанию - стоп

        # --- ОСНОВНОЙ ЦИКЛ ---
        while True:
            # Проверяем, нажал ли пользователь новую клавишу
            if is_data():
                key = sys.stdin.read(1).lower() # Читаем 1 символ
                if key == 'q':
                    print("Завершение работы...")
                    break
                last_key = key  # Сохраняем последнюю команду

            # Выполняем последнюю команду на каждой итерации цикла.
            # Это предотвращает ошибку таймаута на контроллере qik.
            robot.drive(last_key)

            # Периодически выводим диагностическую информацию
            print("--- Статус ---")
            error_checker.check_and_print() # Проверяем и печатаем ошибки
            motor_ctrl.print_motor_currents() # Печатаем ток
            print(f"Последняя команда: '{last_key}'")
            print("--------------\n")

            # Пауза, чтобы не перегружать UART и процессор
            sleep(0.2) # Отправляем команды и проверяем статус 5 раз в секунду

    except Exception as e:
        print(f"\nПроизошла критическая ошибка: {e}")
    finally:
        # Важнейший блок: выполняется всегда при выходе из цикла
        print("Остановка моторов и восстановление терминала.")
        if 'motor_ctrl' in locals():
            motor_ctrl.stop_all() # Гарантированно останавливаем моторы
        # Возвращаем терминалу его исходные настройки
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
