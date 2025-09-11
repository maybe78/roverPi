from __future__ import print_function

from select import select
import logging
import evdev
from evdev import InputDevice
from evdev.ecodes import ABS_RX, ABS_RY, ABS_X, ABS_Y

logging.basicConfig(
	level=logging.DEBUG,
	format="[%(asctime)s] %(threadName)s %(message)s",
	datefmt="%H:%M:%S"
)
j_logger = logging.getLogger("rover.pad")


class DualShock:
	def __init__(self, dead_zone):
		self.pad = None
		self.dead_zone = dead_zone
		devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
		self.active_keys = {
			ABS_RX: 0,
			ABS_RY: 0,
			ABS_X: 0,
			ABS_Y: 0
		}

		for device in devices:
			print(device.path, device.name, device.phys)
			if device.name == "Wireless Controller" or "8Bitdo" in device.name:
				self.dev = InputDevice(device.path)
				print(self.dev)
				print(self.dev.capabilities(verbose=True))


	def read_events(self):
		events_list = []
		r_list, w_list, x_list = select([self.dev.fd], [], [], 0.1)
		if r_list:
			controller_events = self.dev.read()
			for event in controller_events:
				if event.type == evdev.ecodes.EV_ABS:
					value = int(max(min(event.value, 254), -254)) - 127
					# PS4 analog stick values are 0 on up and 255 on down, so reverse.
					if event.code == evdev.ecodes.ABS_RY or event.code == evdev.ecodes.ABS_Y:
						value = value * -1
					self.active_keys[event.code] = value
			#logging.debug("R:\tX:{0}\tY:{1}".format(self.active_keys[ABS_RX], self.active_keys[ABS_RY]))
