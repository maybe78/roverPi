#!/usr/bin/python3.5
import logging
import evdev
from evdev import *

logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] %(threadName)s %(message)s", datefmt="%H:%M:%S")
logging.info("Controller output script started")


class ControllerInput:
    def __init__(self, controller_name):
        # Get the list of available input devices
        list_devices()
        devices = [InputDevice(device) for device in list_devices()]
        # must_have = {i for i in range(1, 32)}
        # must_not_have = {0}
        # logging.debug("Found devices: " + str(len(devices)))
        for dev in devices:
            print("Input device found: {}".format(dev.name))
            if dev.name == self.controller_name:
                dev_location = dev.fn
                break

    def events_get(self):
        if dev_location is None:
            raise "Device not found!"
        print("Dev found: " + dev.name)
        # self.dev = evdev.InputDevice(dev_location)
