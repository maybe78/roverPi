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
		self.dev = None  # Изначально устройство не найдено
		self.dead_zone = dead_zone
		self.active_keys = {
			ABS_RX: 0, ABS_Y: 0,
			ABS_X: 0, ABS_RY: 0
		}
		# Имена, по которым будем искать геймпад
		self.known_devices = ["Wireless Controller", "8Bitdo"]

	def connect(self):
		"""
		Ищет и подключается к геймпаду. Возвращает True в случае успеха.
		"""
		if self.is_connected():
			return True

		try:
			devices = [InputDevice(path) for path in evdev.list_devices()]
			for device in devices:
				# Проверяем, содержит ли имя устройства одно из известных нам
				if any(name in device.name for name in self.known_devices):
					self.dev = device
					print(f"Геймпад найден и подключен: {self.dev.name}")
					return True
		except Exception as e:
			print(f"Ошибка при поиске устройств: {e}")
			self.dev = None # Сбрасываем на всякий случай
			return False
			
		# Если цикл завершился, а геймпад не найден
		self.dev = None
		return False

	def is_connected(self):
		"""
		Проверяет, активно ли подключение к геймпаду.
		"""
		# Просто проверяем, существует ли объект устройства
		return self.dev is not None

	def read_events(self):
		"""
		Читает события. Защищено от падений при отключении геймпада.
		"""
		if not self.is_connected():
			return self.active_keys # Возвращаем нейтральные значения, если не подключены

		try:
			r_list, _, _ = select([self.dev.fd], [], [], 0.01)
			if r_list:
				for event in self.dev.read():
					if event.type == evdev.ecodes.EV_ABS:
						# Ваша логика обработки значений
						value = int(max(min(event.value, 254), 0)) - 127.5
						if event.code == evdev.ecodes.ABS_RY or event.code == evdev.ecodes.ABS_Y:
							value = value * -1
						self.active_keys[event.code] = value
		except (IOError, OSError) as e:
			# Эта ошибка возникает, когда устройство физически отключается
			print(f"Геймпад отключен. Ошибка: {e}")
			self.dev = None # Сбрасываем подключение
			# Сбрасываем стики в центр
			self.active_keys = {k: 0 for k in self.active_keys}
		
		return self.active_keys
