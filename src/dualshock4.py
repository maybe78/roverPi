from __future__ import print_function
from select import select

import evdev
from evdev import InputDevice
from evdev import ecodes
from utils import Steering
import qik

gamepad = InputDevice ('/dev/input/event2')
print(gamepad)
print(gamepad.capabilities(verbose=True))

mc = qik.MotorController ()
# mc.get_firmware_version()
rx = ry = 0
ls = rs = 0

speed = {'ls': 0, 'rs': 0}

while True:
    rlist, wlist, xlist = select([gamepad.fd], [], [], 0.1)
    if rlist:
        for event in gamepad.read():
            if event.type == evdev.ecodes.EV_ABS:
                if event.code == ecodes.ABS_RX:
                    rx = event.value - 127
                elif event.code == ecodes.ABS_RY:
                    ry = event.value - 127
                ls, rs = Steering.joystick_to_diff_control(rx, ry)
                mc.set_speed(ls, rs)
