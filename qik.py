# !/usr/bin/python3
import array
import logging
import struct
from serial import serial

QIK_AUTODETECT_BAUD_RATE         = 0xAA

QIK_GET_FIRMWARE_VERSION         = 0x81
QIK_GET_ERROR_BYTE               = 0x82
QIK_GET_CONFIGURATION_PARAMETER  = 0x83
QIK_SET_CONFIGURATION_PARAMETER  = 0x84

# Motor Parameters
QIK_MOTOR_M0_FORWARD = 0x88
QIK_MOTOR_M0_REVERSE = 0x8A
QIK_MOTOR_M1_FORWARD = 0x8C
QIK_MOTOR_M1_REVERSE = 0x8E

QIK_MOTOR_M0_FORWARD_8_BIT       = 0x89
QIK_MOTOR_M0_REVERSE_8_BIT       = 0x8B
QIK_MOTOR_M1_FORWARD_8_BIT       = 0x8D
QIK_MOTOR_M1_REVERSE_8_BIT       = 0x8F

# 2s9v1 only
QIK_2S9V1_MOTOR_M0_COAST         = 0x86
QIK_2S9V1_MOTOR_M1_COAST         = 0x87

# 2s12v10 only
QIK_2S12V10_MOTOR_M0_BRAKE       = 0x86
QIK_2S12V10_MOTOR_M1_BRAKE       = 0x87
QIK_2S12V10_GET_MOTOR_M0_CURRENT = 0x90
QIK_2S12V10_GET_MOTOR_M1_CURRENT = 0x91
QIK_2S12V10_GET_MOTOR_M0_SPEED   = 0x92
QIK_2S12V10_GET_MOTOR_M1_SPEED   = 0x93

QIK_CONFIG_DEVICE_ID                        = 0
QIK_CONFIG_PWM_PARAMETER                    = 1
QIK_CONFIG_SHUT_DOWN_MOTORS_ON_ERROR        = 2
QIK_CONFIG_SERIAL_TIMEOUT                   = 3
QIK_CONFIG_MOTOR_M0_ACCELERATION            = 4
QIK_CONFIG_MOTOR_M1_ACCELERATION            = 5
QIK_CONFIG_MOTOR_M0_BRAKE_DURATION          = 6
QIK_CONFIG_MOTOR_M1_BRAKE_DURATION          = 7
QIK_CONFIG_MOTOR_M0_CURRENT_LIMIT_DIV_2     = 8
QIK_CONFIG_MOTOR_M1_CURRENT_LIMIT_DIV_2     = 9
QIK_CONFIG_MOTOR_M0_CURRENT_LIMIT_RESPONSE  = 10
QIK_CONFIG_MOTOR_M1_CURRENT_LIMIT_RESPONSE  = 11

m_logger = logging.getLogger('rover.qik')
logging.basicConfig(level = logging.DEBUG, format = "[%(asctime)s] %(threadName)s %(message)s", datefmt = "%H:%M:%S")

class SerialDriver:
	def __init__(self, serial_device, baud):
		self.ser = serial.Serial(serial_device, baud, timeout = 1)
		#help(self.ser)
		self.debug = False
		self.pololu = True
		if (self.pololu):
			self.ser.write(chr(0xAA).encode())
		self.controllers = {}
		
	def get_controller(self, device_id):
		if device_id in self.controllers:
			new_controller = self.controllers[device_id]
			return 
		else:
			new_controller = MotorController(self, device_id)
			self.controllers[device_id] = new_controller
		return new_controller
			
	def send_message(self, device_id, cmd, value=None, rcv_length=None):
		self.ser.flushInput()
		msg = bytearray([0xAA])		
		msg.append(device_id)
		if (self.pololu):
			cmd = cmd^0x80 
		msg.append(cmd)
		if value != None:
			msg.append(value)
		out = array.array('B', msg)
		#logging.debug("Tx >  > {}".format(out))
		self.ser.write(out)
		reply = ''
		if rcv_length != None:
			bytes_to_read = self.ser.inWaiting()
			if bytes_to_read > 0:
				reply = self.ser.read(bytes_to_read)
				#logging.debug("Rx <  < " + " ".join(hex(n) for n in reply))
		return reply

class MotorController:
	def __init__(self, driver, device_id):
		self.driver = driver
		self.id = device_id
		self.driver.ser.flushOutput()
		self.params = self.get_all_config_params()
		self.version = self.get_firmware_version()
		#motorControl.getError()
		logging.debug("Motor driver Initialized with id #{0:#x};".format(self.id))

	def set_debug(self, on = True):
		self.debug = on

	# Driver Config
	def set_device_id(self, device_id):
		self.id = device_id

	def get_firmware_version(self):
		version = self.driver.send_message(self.id, 0x03, None, 10)
		logging.debug("Motor driver firmware version: " + " ".join(hex(n) for n in version))
		return version

	def get_error_byte(self):
		err = self.driver.send_message(self.id, 0x02, None, 1)
		logging.debug("Requested error byte value: " + " ".join(hex(n) for n in err))
		return err

	def get_config_param(self, param_number):
		res =  self.driver.send_message(self.id, 0x03, param_number, 1)
		return res

	def get_all_config_params(self):
		params = [0]*12
		for i in range(12):
			params[i] = self.get_config_param(i)
			if params[i] != None:
				logging.debug("Parameter {0} = {1} ".format(i, (params[i])))
		return params

	def set_config_param(self, param_number, value):
		currentValue = self.get_config_param(param_number)
		if currentValue != value:
			error = self.driver.send_message(self.id, 0x04, [param_number, value, 0x55, 0x2a], 1)
			if not error:
				self.params[param_number] = value
			return error

	# Motor & Steering / Speed control 	
	def set_l_speed(self, speed):
		self.set_motor_speed(0, speed)
		
	def set_r_speed(self, speed):
		self.set_motor_speed(1, speed)

	def stop_all(self):
		self.set_motor_speed(0, 0)
		self.set_motor_speed(1, 0)

	def set_motor_speed(self, motor_id, speed):
		speed = max(min(speed, 127.0), -127.0) #if its in 8 bit speed mode
		direction = speed < 0 # set reverse direction bit if speed less than 0
		bit8speed = self.params[1]# & 1 #first bit of paramter 1 can be used to determin if its in 8 bit speed mode
		speed_multiplyer = 1 # speed is between 0-127 for 7bit speed mode
		if bit8speed:
			speed_multiplyer = 255 #speed is between 0-255 for 8bit speed mode
		speed_byte = int(abs(speed)*speed_multiplyer)# covert floating speed to scaled byte

		cmd = speed_byte >= 128 # bit 0 of command is used for 8th bit of speedbyte as speedbyte can only use 7 bits

		speed_byte &= 127 #clear the 8th bit of the speedbyte as it can only use 7 bits

		cmd |= direction << 1 #shift direction into bit 1
		cmd |= motor_id << 2 #shift motor id into bit 2
		cmd |= 1 << 3 # just set bit 3

		#send the speed command
		self.driver.send_message(self.id, cmd, speed_byte, 1)
		#logging.debug('Command: {0} | Speed: {1}'.format(cmd, speedByte))

	def get_error(self):
		errorByte = self.getErrorByte()
		if errorByte == 8:
			logging.error("Data Overrun Error: serial receive buffer is full")
		elif errorByte == 16:
			logging.error("Frame Error: a bytes stop bit is not detected, maybe baudrate differs from pololu")
		elif errorByte == 32:
			logging.error("CRC Error: CRC-enable jumper is in place and computed CRC failed")
		elif errorByte == 64:
			logging.error("Format Error: command byte does not match a known command")
		elif errorByte == 128:
			logging.error("Timeout: if enabled, serial timeout")
		return errorByte

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
				print ("parameterNumber (%s) is not 0, 1, 2, 3" % parameterNumber)
			return False
		return True
	def coast(self, motor):
		if not self.__testMotorInput(motor):
			return False
		command = 0x06 + motor
		self.driver.ser.write(self.pololuProtocol + chr(command))
		return True