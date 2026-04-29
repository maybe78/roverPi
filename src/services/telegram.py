import cv2
import requests
import os
import logging
from typing import Optional
from io import BytesIO
from datetime import datetime


class TelegramBot:
    """
    Класс для работы с Telegram Bot API
    Поддерживает отправку текстовых сообщений, фото и захват изображений с камеры
    """
    
    # Константы класса - замените на ваши реальные значения
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Токен вашего бота
    DEFAULT_CHAT_ID = "YOUR_CHAT_ID_HERE"  # ID вашего чата по умолчанию
    
    def __init__(self, bot_token: Optional[str] = None, default_chat_id: Optional[str] = None):
        """
        Инициализация бота
        
        Args:
            bot_token (str, optional): Токен бота. Если не указан, используется константа класса
            default_chat_id (str, optional): Chat ID по умолчанию. Если не указан, используется константа класса
        """
        self.bot_token = bot_token or self.BOT_TOKEN
        self.default_chat_id = default_chat_id or self.DEFAULT_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Настройка логирования"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    def send_text_message(self, text: str, chat_id: Optional[str] = None, 
                         parse_mode: Optional[str] = None) -> dict:
        """
        Отправка текстового сообщения
        
        Args:
            text (str): Текст сообщения
            chat_id (str, optional): ID чата. Если не указан, используется default_chat_id
            parse_mode (str, optional): Режим парсинга (HTML, Markdown)
            
        Returns:
            dict: Ответ от Telegram API
        """
        chat_id = chat_id or self.default_chat_id
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': text
        }
        
        if parse_mode:
            payload['parse_mode'] = parse_mode
            
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            self.logger.info(f"Текстовое сообщение отправлено в чат {chat_id}")
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка отправки сообщения: {e}")
            return {"ok": False, "error": str(e)}
    
    def send_photo_message(self, photo_path: str, caption: Optional[str] = None, 
                          chat_id: Optional[str] = None) -> dict:
        """
        Отправка фото с текстом
        
        Args:
            photo_path (str): Путь к файлу изображения
            caption (str, optional): Подпись к фото (до 1024 символов)
            chat_id (str, optional): ID чата. Если не указан, используется default_chat_id
            
        Returns:
            dict: Ответ от Telegram API
        """
        chat_id = chat_id or self.default_chat_id
        url = f"{self.base_url}/sendPhoto"
        
        try:
            with open(photo_path, 'rb') as photo_file:
                files = {
                    'photo': photo_file
                }
                
                data = {
                    'chat_id': chat_id
                }
                
                if caption:
                    data['caption'] = caption
                
                response = requests.post(url, files=files, data=data, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                self.logger.info(f"Фото отправлено в чат {chat_id}")
                return result
                
        except FileNotFoundError:
            error_msg = f"Файл {photo_path} не найден"
            self.logger.error(error_msg)
            return {"ok": False, "error": error_msg}
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка отправки фото: {e}")
            return {"ok": False, "error": str(e)}
    
    def send_photo_from_bytes(self, photo_bytes: bytes, filename: str = "image.jpg", 
                             caption: Optional[str] = None, chat_id: Optional[str] = None) -> dict:
        """
        Отправка фото из байтов (например, захваченного с камеры)
        
        Args:
            photo_bytes (bytes): Данные изображения в байтах
            filename (str): Имя файла для отправки
            caption (str, optional): Подпись к фото
            chat_id (str, optional): ID чата. Если не указан, используется default_chat_id
            
        Returns:
            dict: Ответ от Telegram API
        """
        chat_id = chat_id or self.default_chat_id
        url = f"{self.base_url}/sendPhoto"
        
        try:
            files = {
                'photo': (filename, BytesIO(photo_bytes), 'image/jpeg')
            }
            
            data = {
                'chat_id': chat_id
            }
            
            if caption:
                data['caption'] = caption
            
            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            self.logger.info(f"Фото из байтов отправлено в чат {chat_id}")
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка отправки фото из байтов: {e}")
            return {"ok": False, "error": str(e)}
    
    def capture_photo_from_camera(self, camera_index: int = 0, 
                                 save_path: Optional[str] = None) -> Optional[str]:
        """
        Захват фото с камеры
        
        Args:
            camera_index (int): Индекс камеры (0 - основная камера)
            save_path (str, optional): Путь для сохранения. Если не указан, 
                                     генерируется автоматически
            
        Returns:
            str: Путь к сохранённому файлу или None при ошибке
        """
        # Создание объекта для захвата видео с камеры
        cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            self.logger.error(f"Не удалось открыть камеру с индексом {camera_index}")
            return None
        
        try:
            # Захват одного кадра
            ret, frame = cap.read()
            
            if not ret:
                self.logger.error("Не удалось захватить кадр с камеры")
                return None
            
            # Генерация имени файла, если не указано
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"camera_photo_{timestamp}.jpg"
            
            # Сохранение изображения
            success = cv2.imwrite(save_path, frame)
            
            if success:
                self.logger.info(f"Фото сохранено: {save_path}")
                return save_path
            else:
                self.logger.error("Ошибка при сохранении изображения")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка при захвате фото: {e}")
            return None
            
        finally:
            # Освобождение ресурсов камеры
            cap.release()
            cv2.destroyAllWindows()
    
    def capture_and_send_photo(self, caption: Optional[str] = None, 
                              camera_index: int = 0, chat_id: Optional[str] = None,
                              delete_after_send: bool = True) -> dict:
        """
        Захват фото с камеры и отправка в Telegram
        
        Args:
            caption (str, optional): Подпись к фото
            camera_index (int): Индекс камеры
            chat_id (str, optional): ID чата. Если не указан, используется default_chat_id
            delete_after_send (bool): Удалить файл после отправки
            
        Returns:
            dict: Ответ от Telegram API
        """
        # Захват фото
        photo_path = self.capture_photo_from_camera(camera_index)
        
        if photo_path is None:
            return {"ok": False, "error": "Не удалось захватить фото"}
        
        try:
            # Отправка фото
            result = self.send_photo_message(photo_path, caption, chat_id)
            
            # Удаление временного файла
            if delete_after_send and os.path.exists(photo_path):
                os.remove(photo_path)
                self.logger.info(f"Временный файл {photo_path} удален")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка при отправке захваченного фото: {e}")
            return {"ok": False, "error": str(e)}


# Пример использования класса
if __name__ == "__main__":
    # Теперь можно создавать бота без параметров - все настройки в классе
    bot = TelegramBot()
    
    # 1. Отправка текстового сообщения (используется default_chat_id)
    text_result = bot.send_text_message("Привет! Это тестовое сообщение от бота.")
    print("Результат отправки текста:", text_result)
    
    # 2. Захват и отправка фото с камеры (используется default_chat_id)
    photo_result = bot.capture_and_send_photo(caption="Фото с камеры")
    print("Результат отправки фото:", photo_result)
    
    # 3. Отправка существующего изображения (используется default_chat_id)
    # file_result = bot.send_photo_message("путь/к/изображению.jpg", "Подпись к изображению")
    
    # 4. Отправка в другой чат (переопределяем chat_id)
    # other_result = bot.send_text_message("Сообщение в другой чат", chat_id="OTHER_CHAT_ID")
