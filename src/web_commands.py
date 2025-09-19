import threading
import time

class WebCommands:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_command_time = time.time()  # Инициализируем текущим временем
        self.ls = 0  # Инициализируем нулями
        self.rs = 0  # Инициализируем нулями
        self.command_timeout = 0.5  # Команды устаревают через 500ms
    
    def set_speed(self, ls, rs):
        with self.lock:
            self.ls = ls
            self.rs = rs
            self.last_command_time = time.time()
    
    def get_speed(self):
        with self.lock:
            # Если команда устарела, мы не меняем сохраненные значения,
            # а просто возвращаем нули.
            if time.time() - self.last_command_time > self.command_timeout:
                return 0, 0
            
            # Если команда свежая, возвращаем ее.
            return self.ls, self.rs
    
    def clear(self):
        with self.lock:
            self.ls = 0
            self.rs = 0
            self.last_command_time = time.time() # Сбрасываем и время
