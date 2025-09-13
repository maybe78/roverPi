# web_commands.py

import threading

class WebCommands:
    """
    Потокобезопасный класс для хранения и управления командами,
    поступающими из веб-интерфейса.
    """
    def __init__(self):
        self._ls = None
        self._rs = None
        self._lock = threading.Lock()

    def get_speed(self):
        """
        Потокобезопасно получает последние команды скорости.
        Возвращает кортеж (ls, rs).
        """
        with self._lock:
            return self._ls, self._rs

    def set_speed(self, ls, rs):
        """
        Потокобезопасно устанавливает новые команды скорости.
        Этот метод будет вызываться из потока веб-сервера.
        """
        with self._lock:
            self._ls = ls
            self._rs = rs
            
    def clear(self):
        """
        Потокобезопасно сбрасывает команды.
        """
        with self._lock:
            self._ls = None
            self._rs = None

