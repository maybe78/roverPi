import threading
import time

class WebCommands:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_command_time = 0
        self.ls = None
        self.rs = None
        self.command_timeout = 0.5  # Команды устаревают через 500ms
    
    def set_speed(self, ls, rs):
        with self.lock:
            self.ls = ls
            self.rs = rs
            self.last_command_time = time.time()
    
    def get_speed(self):
        with self.lock:
            # Проверяем не устарела ли команда
            if time.time() - self.last_command_time > self.command_timeout:
                self.ls = None
                self.rs = None
            return self.ls, self.rs
    
    def clear(self):
        with self.lock:
            self.ls = None
            self.rs = None
