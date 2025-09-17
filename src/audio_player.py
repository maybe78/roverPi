import pygame
import time

class AudioPlayer:
    def __init__(self):
        """Инициализирует pygame.mixer."""
        pygame.mixer.init()
        print("AudioPlayer инициализирован.")

    def play(self, file_path):
        """
        Загружает и проигрывает MP3-файл.
        Если что-то уже играет, сначала останавливает предыдущий трек.
        """
        if pygame.mixer.music.get_busy():
            self.stop()
            time.sleep(0.1) # Небольшая пауза для корректной остановки

        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            print(f"Воспроизведение файла: {file_path}")
        except pygame.error as e:
            print(f"Ошибка при загрузке или воспроизведении файла: {e}")

    def stop(self):
        """Останавливает воспроизведение музыки."""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            # pygame.mixer.music.unload() # Можно раскомментировать, если нужно освобождать файл
            print("Воспроизведение остановлено.")

    def is_playing(self):
        """Проверяет, проигрывается ли что-то в данный момент."""
        return pygame.mixer.music.get_busy()
