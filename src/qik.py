# !/usr/bin/python3

from typing import List, Any, Union

import logging
import serial

QIK_AUTODETECT_BAUD_RATE = 0xAA

QIK_GET_FIRMWARE_VERSION = 0x81
QIK_GET_ERROR_BYTE = 0x82
QIK_GET_CONFIGURATION_PARAMETER = 0x83
QIK_SET_CONFIGURATION_PARAMETER = 0x84

# Motor Parameters
QIK_MOTOR_M0_FORWARD = 0x88
QIK_MOTOR_M0_REVERSE = 0x8A
QIK_MOTOR_M1_FORWARD = 0x8C
QIK_MOTOR_M1_REVERSE = 0x8E

QIK_MOTOR_M0_FORWARD_8_BIT = 0x89
QIK_MOTOR_M0_REVERSE_8_BIT = 0x8B
QIK_MOTOR_M1_FORWARD_8_BIT = 0x8D
QIK_MOTOR_M1_REVERSE_8_BIT = 0x8F

# 2s9v1 only
QIK_2S9V1_MOTOR_M0_COAST = 0x86
QIK_2S9V1_MOTOR_M1_COAST = 0x87

# 2s12v10 only
QIK_2S12V10_MOTOR_M0_BRAKE = 0x86
QIK_2S12V10_MOTOR_M1_BRAKE = 0x87
QIK_2S12V10_GET_MOTOR_M0_CURRENT = 0x90
QIK_2S12V10_GET_MOTOR_M1_CURRENT = 0x91
QIK_2S12V10_GET_MOTOR_M0_SPEED = 0x92
QIK_2S12V10_GET_MOTOR_M1_SPEED = 0x93

QIK_CONFIG_DEVICE_ID = 0
QIK_CONFIG_PWM_PARAMETER = 1
QIK_CONFIG_SHUT_DOWN_MOTORS_ON_ERROR = 2
QIK_CONFIG_SERIAL_TIMEOUT = 3
QIK_CONFIG_MOTOR_M0_ACCELERATION = 4
QIK_CONFIG_MOTOR_M1_ACCELERATION = 5
QIK_CONFIG_MOTOR_M0_BRAKE_DURATION = 6
QIK_CONFIG_MOTOR_M1_BRAKE_DURATION = 7
QIK_CONFIG_MOTOR_M0_CURRENT_LIMIT_DIV_2 = 8
QIK_CONFIG_MOTOR_M1_CURRENT_LIMIT_DIV_2 = 9
QIK_CONFIG_MOTOR_M0_CURRENT_LIMIT_RESPONSE = 10
QIK_CONFIG_MOTOR_M1_CURRENT_LIMIT_RESPONSE = 11

m_logger = logging.getLogger('rover.qik')
m_logger.setLevel(logging.ERROR)
logging.basicConfig(
	level=logging.DEBUG,
	format="[%(asctime)s] %(threadName)s %(message)s",
	datefmt="%H:%M:%S"
)


class MotorController:

	def __init__(self):
		self.params = [None] * 12  # Или {}
		self.ser =serial.Serial('/dev/ttyUSB0', 38400, timeout=0.2)
		self.id = 0x0A
		self.pololu = True
		self.ser.flushOutput()
		self.ser.write(0xAA)
		self.debug = True
		self.set_pwm_mode(0)  # Высокочастотный PWM 7 бит (19.7 кГц)
		self.set_current_limit(0, 18)  # Ограничение тока для мотора 0 до 6 А
		self.set_current_limit(1, 18)  # Ограничение тока для мотора 1 до 6 А

	def set_debug(self, on=True):
		self.debug = on

	def send_message(self, device_id: int, cmd: int, value: Union[int, List[int]] = None, rcv_length: int = None) -> object:
		self.ser.flushInput()
		sequence = [0xAA, device_id]
		if self.pololu:
			cmd = cmd ^ 0x80
		sequence.append(cmd)
		if value is not None:
			if isinstance(value, list):
				sequence.extend(value)
			else:
				sequence.append(value)
		self.ser.write(bytearray(sequence))
		reply = []
		if rcv_length is not None:
			while len(reply) < rcv_length:
				x = self.ser.read(1)
				reply.append(x)
		return reply

	def set_pwm_mode(self, mode=0):
		# mode: 0–5 (0 — 7 бит 19.7кГц, 1 — 8 бит 9.8кГц, и т.д. согласно доке)
		self.set_config_param(1, mode)

	def set_current_limit(self, motor_id, limit_amperes):
		# limit_amperes — максимально допустимый ток (например, 6 А)
		# Значение параметра равно limit_amperes / 0.6 / 2 (т.к. делится на 2)
		param_number = 8 if motor_id == 0 else 9
		value = int(limit_amperes / 0.6 / 2)
		if value > 127:
			value = 127
		self.set_config_param(param_number, value)

	def get_firmware_version(self):
		version = self.send_message(self.id, 0x01, None, 1)
		return version


	def get_error_byte(self):
		err = self.send_message(self.id, 0x02, None, 1)
		return err


	def get_config_param(self, param_number):
		reply = self.send_message(self.id, 0x03, param_number, 0x01)
		return reply


	def get_all_config_params(self):
		params = [0] * 12
		for i in range(12):
			params[i] = (self.get_config_param(i))
			if params[i] is not None:
				print("Parameter {0} = {1} ".format(i, (params[i])))
		return params


	def set_config_param(self, param_number, value):
		current_value = self.get_config_param(param_number)
		if current_value != value:
			error = self.send_message(self.id, 0x04, [param_number, value, 0x55, 0x2a], 1)
			if not error:
				self.params[param_number] = value
		return self.params[param_number]


	def set_speed(self, left, right):
		self.set_motor_speed(0, left)
		self.set_motor_speed(1, right)
		#print("{0}\t|\t{1}".format(left, right))


	def stop_all(self):
		self.set_motor_speed(0, 0)
		self.set_motor_speed(1, 0)


	def set_motor_speed(self, motor_id, speed):
		speed = max(min(speed, 127.0), -127.0)  # range limit
		direction = speed < 0  # set reverse direction bit if speed less than 0
		speed_byte = int(abs(speed))  # covert floating speed to scaled byte
		cmd = speed_byte >= 128  # bit 0 of command is used for 8th bit of speed byte as speed byte can only use 7 bits
		speed_byte &= 127  # clear the 8th bit of the speed byte as it can only use 7 bits

		cmd |= direction << 1  # shift direction into bit 1
		cmd |= motor_id << 2  # shift motor id into bit 2
		cmd |= 1 << 3  # just set bit 3
		if motor_id == 0:
			logging.debug(speed_byte)
		self.send_message(self.id, cmd, speed_byte, 1)


	def get_error(self):
		error_byte = self.get_error_byte()
		if error_byte == 8:
			logging.error("Data Overrun Error: serial receive buffer is full")
		elif error_byte == 16:
			logging.error("Frame Error: a bytes stop bit is not detected, maybe baudrate differs from pololu")
		elif error_byte == 32:
			logging.error("CRC Error: CRC-enable jumper is in place and computed CRC failed")
		elif error_byte == 64:
			logging.error("Format Error: command byte does not match a known command")
		elif error_byte == 128:
			logging.error("Timeout: if enabled, serial timeout")
		return error_byte

	# --  --  --  --  --  --  -- 	Tests 	 --  --  --  --  --  --  --  --  --  --  --  --  --  --  --  --  --  -- -
	def __test_binairy_input(self, i):
		if i != 0 and i != 1:
			return False
		return True


	def __test_motor_input(self, motor):
		if not self.__testBinairyInput(motor):
			if self.debug:
				print("motor (%s) is not 0 or 1" % motor)
			return False
		return True


	def __test_parameter_number(self, parameterNumber):
		if parameterNumber < 0 or parameterNumber > 3:
			if self.debug:
				print("parameterNumber (%s) is not 0, 1, 2, 3" % parameterNumber)
			return False
		return True


	def coast(self, motor):
		if not self.__testMotorInput(motor):
			return False
		command = 0x06 + motor
		self.ser.write(self.pololuProtocol + chr(command))
		return True
