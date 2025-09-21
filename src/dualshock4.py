from __future__ import print_function

from select import select
import logging
import evdev
import requests 
import threading  
from evdev import InputDevice
from evdev.ecodes import ABS_RX, ABS_RY, ABS_X, ABS_Y
from evdev.ecodes import BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST

logging.basicConfig(
	level=logging.DEBUG,
	format="[%(asctime)s] %(threadName)s %(message)s",
	datefmt="%H:%M:%S"
)
j_logger = logging.getLogger("rover.pad")

class DualShock:
	def __init__(self, dead_zone, tts_url="https://192.168.0.38:5000/audio/speak"):
		self.dev = None
		self.dead_zone = dead_zone
		self.tts_url = tts_url
		
		self.active_keys = {
			ABS_RX: 0, ABS_Y: 0,
			ABS_X: 0, ABS_RY: 0
		}
		
		self.button_states = {
			BTN_SOUTH: False,
			BTN_EAST: False,
			BTN_NORTH: False,
			BTN_WEST: False
		}
		
		self.button_phrases = {
			BTN_SOUTH: "Жужа, сидеть!",
			BTN_EAST: "Всем оставаться на местах!",
			BTN_NORTH: "Задача выполнена.",
			BTN_WEST: "Я здесь, чтобы помогать."
		}

		self.known_devices = ["Wireless Controller", "8Bitdo"]

	def speak_async(self, text):
		"""Отправляет запрос на TTS сервер асинхронно."""
		def send_request():
			try:
				response = requests.post(
					self.tts_url, 
					json={"text": text}, 
					timeout=3,
					verify=False
				)
				if response.status_code == 200:
					j_logger.info(f"Отправлен запрос на озвучку: '{text}'")
				else:
					j_logger.warning(f"TTS сервер вернул статус {response.status_code}")
			except requests.exceptions.RequestException as e:
				j_logger.warning(f"Не удалось подключиться к TTS-серверу: {e}")
		
		threading.Thread(target=send_request, daemon=True, name="TTS-Request").start()

	def connect(self):
		"""
		Ищет и подключается к геймпаду. Возвращает True в случае успеха.
		"""
		if self.is_connected():
			return True
			
		try:
			devices = [InputDevice(path) for path in evdev.list_devices()]
			for device in devices:
				if any(name in device.name for name in self.known_devices):
					self.dev = device
					print(f"Геймпад найден и подключен: {self.dev.name}")
					return True
		except Exception as e:
			print(f"Ошибка при поиске устройств: {e}")
			self.dev = None
			return False
			
		self.dev = None
		return False

	def is_connected(self):
		"""
		Проверяет, активно ли подключение к геймпаду.
		"""
		return self.dev is not None

	def read_events(self):
		"""
		Читает события. Защищено от падений при отключении геймпада.
		"""
		if not self.is_connected():
			return self.active_keys

		try:
			r_list, _, _ = select([self.dev.fd], [], [], 0.01)
			if r_list:
				for event in self.dev.read():
					if event.type == evdev.ecodes.EV_ABS:
						value = int(max(min(event.value, 254), 0)) - 127.5
						
						self.active_keys[event.code] = value

					elif event.type == evdev.ecodes.EV_KEY:
						if event.code in self.button_phrases:
							if event.value == 1 and not self.button_states[event.code]:
								self.button_states[event.code] = True
								phrase = self.button_phrases[event.code]
								j_logger.info(f"Кнопка {event.code} нажата, озвучиваем: '{phrase}'")
								self.speak_async(phrase)
							elif event.value == 0:
								self.button_states[event.code] = False

		except (IOError, OSError) as e:
			print(f"Геймпад отключен. Ошибка: {e}")
			self.dev = None
			self.active_keys = {k: 0 for k in self.active_keys}
			self.button_states = {k: False for k in self.button_states}
		
		return self.active_keys
