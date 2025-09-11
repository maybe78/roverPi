import sys
import termios
import tty
from qik import MotorController

class FourWheelRobotController:
    def __init__(self, motor_controller):
        self.mc = motor_controller
        self.debug = True

    def set_debug(self, on=True):
        self.debug = on

    def drive(self, command):
        speed = 20  # скорость (0-127)
        if command == 'w':
            self.mc.set_speed(speed, speed)
        elif command == 's':
            self.mc.set_speed(-speed, -speed)
        elif command == 'a':
            self.mc.set_speed(-speed, speed)  # левый мотор назад, правый вперёд
        elif command == 'd':
            self.mc.set_speed(speed, -speed)  # левый мотор вперёд, правый назад
        else:
            if self.debug:
                print(f"Неизвестная команда: {command}")
            self.mc.stop_all()

def getch():
    # Функция для чтения одного символа с клавиатуры (без Enter)
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

if __name__ == '__main__':
    motor_ctrl = MotorController()
    robot = FourWheelRobotController(motor_ctrl)

    print("Управление роботoм через WASD. Нажмите q для выхода.")

    try:
        while True:
            key = getch()
            if key == 'q':
                print("Выход из программы...")
                robot.mc.stop_all()
                break
            robot.drive(key)
    except KeyboardInterrupt:
        robot.mc.stop_all()
        print("Программа остановлена пользователем.")
