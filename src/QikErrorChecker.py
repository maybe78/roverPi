import serial
from typing import Dict, List

class QikErrorChecker:
    # ... (карты ошибок без изменений) ...
    ERROR_BITS_2S12V10 = {0: "...", 1: "...", 2: "...", 3: "...", 4: "...", 7: "Timeout"}
    ERROR_BITS_2S9V1 = {3: "...", 4: "...", 5: "..."}

    def __init__(self, serial_port: serial.Serial, model: str = "2s12v10"):
        """
        Принимает УЖЕ открытый serial.Serial объект.
        """
        if not (serial_port and serial_port.is_open):
            raise ValueError("Необходимо передать открытый serial порт")
        self.ser = serial_port  # Используем переданный порт
        self.model = model.lower()
        # Убрали все, что связано с use_pololu_protocol, для простоты

    def _build_get_error_cmd(self) -> bytes:
        # Пока используем только компактный протокол
        return bytes([0x82])

    def get_error_byte(self) -> int:
        cmd = self._build_get_error_cmd()
        try:
            # Очистка буферов важна
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.ser.write(cmd)
            resp = self.ser.read(1)
            if len(resp) == 1:
                return resp[0]
        except serial.SerialException as e:
            print(f"Ошибка порта при чтении ошибки: {e}")
        return -1 # Возвращаем -1 в случае ошибки чтения

    def decode_errors(self, err: int) -> List[str]:
        # ... (метод без изменений) ...
        if err == -1:
            return ["Не удалось прочитать байт ошибки"]
        # ... остальная логика
        msgs = []
        mapping = self.ERROR_BITS_2S12V10 if self.model != "2s9v1" else self.ERROR_BITS_2S9V1
        for bit, text in mapping.items():
            if err & (1 << bit):
                msgs.append(text)
        # ... остальная логика
        if not msgs:
            msgs.append("Ошибок нет (error byte = 0)")
        return msgs

    def check_and_print(self):
        err = self.get_error_byte()
        if err != -1:
            print(f"Qik error byte: 0x{err:02X} ({err})")
            for line in self.decode_errors(err):
                print(f"- {line}")
        else:
            print("Не удалось выполнить проверку ошибок Qik.")

