#!/usr/bin/python3.5
import logging
import evdev
import time
from evdev import *
logging.basicConfig(level=logging.ERROR, format="[%(asctime)s] %(threadName)s %(message)s", datefmt="%H:%M:%S")
logging.info("Controller output script started")



class ControllerInput:
    def_location = None
    def __init__(self, controller_name):
        # Get the list of available input devices
        dev = evdev.InputDevice('/dev/input/event0')
        #print("Input device found: {}".format(dev.name))
        if dev.name == controller_name:
            self.dev_location = dev.fn
            self.device = dev


    def get_events(self):
        return self.device.read()



