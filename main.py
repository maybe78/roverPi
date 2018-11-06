#!/usr/bin/python3
import qik
import logging
from time import sleep
from control_utils import Steering
from approxeng.input.selectbinder import ControllerResource
logger = logging.getLogger('rover')
logger.setLevel(logging.ERROR)

ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# hardware devices setup
mc = qik.MotorController()
mc.get_firmware_version()

logger.info('Rover is on. Waiting for commands')


ls = rs = 0
speed = {
    'ls':0,
    'rs':0
}
x_axis = y_axis = 0
class RobotStopException(Exception):
    """
    The simplest possible subclass of Exception, we'll raise this if we want to stop the robot
    for any reason. Creating a custom exception like this makes the code more readable later.
    """
    pass
try:
    while True:
        try:
            with ControllerResource(dead_zone=0.05, hot_zone=0.1) as joystick:
                while joystick.connected:
                    for rx, ry in joystick.stream['lx', 'ly']:
                        ls, rs = Steering.joystick_to_diff_control(rx,ry)
                        print("Axis:{0}|{1} \t Power:{2}|{3}".format(rx, ry, ls, rs ))
                        mc.set_l_speed(ls)
                        mc.set_r_speed(rs)
                        #print("L:{0} R:{1}".format(power_left,power_right))
                        # joystick.check_presses()
                        # if joystick.has_presses and 'home' in joystick.presses:
                        #     raise RobotStopException()
                        sleep(0.01)
        except IOError:
            print('No controller found yet')
except RobotStopException:
    mc.stop_all()
