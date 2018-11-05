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

#pad = inputDevice.ControllerInput('Sony Computer Entertainment Wireless Controller')
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


# except RobotStopException:
#     # This exception will be raised when the home button is pressed, at which point we should
#     # stop the motors.
#     stop_motors()
#     # time"".sleep(0.1)
    # state = 0
    # try:
    #     #print(a)
    #     time.sleep(0.1)
    #     for ev in ds4.get_events():
    #         cmd = ev  # type: Union[InputEvent, Any]
    #         if cmd.code != 0 and cmd.code != 6 and cmd.code != 7  and cmd.code != 8 and cmd.code != 25 and cmd.code != 26 and cmd.code != 27:
    #             logger.debug('X:{0} Y:{1} | L:{2} R:{3} | CODE: {4} VAL: {5}'.format(X,Y,ls,rs,cmd.code,cmd.value  ))
    # except IOError:
    #     pass
    # if cmd.value == 2:  		# key pressed
            # 	if cmd.code == 103:		# move forward
            # 		Y += spinc
            # 	elif cmd.code == 108:	# move back
            # 		Y -= spinc
            # 	if cmd.code == 105:		# move left
            # 		X -= spinc
            # 	elif cmd.code == 106:	# move right
            # 		X += spinc
            # elif cmd.value == 0:  		# key released
            # 	if Y > 0:
            # 		Y -= spRelease
            # 	elif Y < 0:
            # 		Y += spRelease
            # 	if X > 0:
            # 		X -= spRelease
            # 	elif X < 0:
            # 		X += spRelease
            # sp = joystickToDiff(X, Y, -127, 127, -127, 127)
            # ls = sp[0]
            # rs = sp[1]
            # motorControl.set_motor_speed(0, ls)
            # motorControl.set_motor_speed(1, rs)
            # time.sleep(0.1)

