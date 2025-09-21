import os
import cv2
import time
import fcntl
import v4l2
import logging
import numpy as np
import requests
from datetime import datetime
from telegram_bot import TelegramBot  

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger('object_detector')

class VirtualCameraObjectDetector:
    def __init__(self, width=640, height=480, input_device_index=0, output_device="/dev/video2", 
                 tts_url="http://127.0.0.1:5000/audio/speak", 
                 enable_telegram=True, photo_interval=30):
        """
        Инициализация детектора объектов с виртуальной камерой
        
        Args:
            width (int): Ширина кадра
            height (int): Высота кадра
            input_device_index (int): Индекс входной камеры
            output_device (str): Путь к виртуальному устройству
            tts_url (str): URL TTS сервера
            enable_telegram (bool): Включить отправку в Telegram
            photo_interval (int): Интервал между фото в секундах
        """
        self.width = width
        self.height = height
        self.input_device_index = int(input_device_index)
        self.output_device = output_device
        self.tts_url = "https://192.168.0.38:5000/audio/speak"
        self.running = False
        self.fd_out = None
        self.cap = None

        # --- Состояние для TTS и обнаружения ---
        self.dog_detected_recently = False
        self.cat_detected_recently = False  # Новый флаг для кота
        
        # --- Telegram Bot интеграция ---
        self.telegram_bot = None
        self.photo_interval = photo_interval  # Интервал между фото в секундах
        self.last_dog_photo_time = 0  # Время последней отправки фото собаки
        self.last_cat_photo_time = 0  # Время последней отправки фото кота
        
        # Инициализация Telegram Bot
        if enable_telegram:
            try:
                self.telegram_bot = TelegramBot()
                logger.info("Telegram Bot успешно инициализирован с встроенными настройками")
            except Exception as e:
                logger.error(f"Ошибка инициализации Telegram Bot: {e}")
                self.telegram_bot = None
        else:
            logger.info("Telegram Bot отключен")

        # Инициализация модели детекции
        prototxt_path = '../models/MobileNetSSD_deploy.prototxt'
        model_path = '../models/MobileNetSSD_deploy.caffemodel'
        self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        self.CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"]
        
        self._initialize_camera()
        self._initialize_virtual_device()

    def _initialize_camera(self):
        """Инициализация входной камеры"""
        self.cap = cv2.VideoCapture(self.input_device_index)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera with index {self.input_device_index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        self.cap.set(cv2.CAP_PROP_FPS, 30.0)
        logger.info(f"Camera {self.input_device_index} initialized.")

    def _initialize_virtual_device(self):
        """Инициализация виртуального устройства вывода"""
        if not os.path.exists(self.output_device):
            raise FileNotFoundError(f"Device not found: {self.output_device}")
        self.fd_out = os.open(self.output_device, os.O_RDWR)
        
        format = v4l2.v4l2_format()
        format.type = v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT
        format.fmt.pix.width = self.width
        format.fmt.pix.height = self.height
        format.fmt.pix.pixelformat = v4l2.V4L2_PIX_FMT_YUV420
        format.fmt.pix.bytesperline = self.width
        format.fmt.pix.sizeimage = int(self.width * self.height * 1.5)
        format.fmt.pix.field = v4l2.V4L2_FIELD_NONE
        
        try:
            fcntl.ioctl(self.fd_out, v4l2.VIDIOC_S_FMT, format)
            logger.info(f"Virtual camera format set to YUV420 on {self.output_device}")
        except Exception as e:
            logger.error(f"Failed to set virtual camera format: {e}")
            raise

    def speak(self, text):
        """Отправляет запрос на TTS сервер."""
        try:
            requests.post(self.tts_url, json={"text": text}, timeout=2, verify=False)
            logger.info(f"Отправлен запрос на озвучку: '{text}'")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Не удалось подключиться к TTS-серверу: {e}")

    def _can_send_photo(self, animal_type: str) -> bool:
        """Проверяет, можно ли отправить фото для конкретного животного"""
        current_time = time.time()
        
        if animal_type == "dog":
            return current_time - self.last_dog_photo_time >= self.photo_interval
        elif animal_type == "cat":
            return current_time - self.last_cat_photo_time >= self.photo_interval
        
        return False

    def _send_pet_photo(self, frame, animal_type: str):
        """Отправляет фото с обнаруженным питомцем в Telegram"""
        if not self.telegram_bot or not self._can_send_photo(animal_type):
            return

        try:
            # Кодируем кадр в JPEG
            success, encoded_image = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            if not success:
                logger.error("Не удалось закодировать изображение")
                return
                
            # Конвертируем в байты
            image_bytes = encoded_image.tobytes()
            
            # Создаем подпись и эмодзи в зависимости от животного
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if animal_type == "dog":
                emoji = "🐕"
                caption = f"{emoji} Обнаружена собака! {timestamp}"
                filename = f"dog_detection_{int(time.time())}.jpg"
            elif animal_type == "cat":
                emoji = "🐱"
                caption = f"{emoji} Обнаружен кот! {timestamp}"
                filename = f"cat_detection_{int(time.time())}.jpg"
            else:
                return  # Неизвестный тип животного
            
            # Отправляем фото
            result = self.telegram_bot.send_photo_from_bytes(
                image_bytes, 
                filename, 
                caption
            )
            
            if result.get("ok"):
                # Обновляем время последней отправки для конкретного животного
                if animal_type == "dog":
                    self.last_dog_photo_time = time.time()
                elif animal_type == "cat":
                    self.last_cat_photo_time = time.time()
                
                logger.info(f"Фото с {animal_type} успешно отправлено в Telegram")
            else:
                logger.error(f"Ошибка отправки {animal_type} в Telegram: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке фото {animal_type} в Telegram: {e}")

    def _send_pet_notification(self, animal_type: str, confidence: float):
        """Отправляет текстовое уведомление о питомце"""
        if not self.telegram_bot:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if animal_type == "dog":
                emoji = "🐕"
                message = f"{emoji} Внимание! Жужа обнаружена в {timestamp}\nУровень уверенности: {confidence:.2f}"
            elif animal_type == "cat":
                emoji = "🐱"
                message = f"{emoji} Внимание! Обнаружен кот в {timestamp}\nУровень уверенности: {confidence:.2f}"
            else:
                return
            
            result = self.telegram_bot.send_text_message(message)
            
            if result.get("ok"):
                logger.info(f"Текстовое уведомление о {animal_type} отправлено")
            else:
                logger.error(f"Ошибка отправки уведомления о {animal_type}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о {animal_type}: {e}")

    def _process_and_write_frame(self):
        """Обработка кадра: детекция объектов, отправка уведомлений, запись в виртуальную камеру"""
        ret, frame = self.cap.read()
        if not ret:
            return

        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
        self.net.setInput(blob)
        detections = self.net.forward()
        
        # Флаги обнаружения для текущего кадра
        is_dog_in_current_frame = False
        is_cat_in_current_frame = False
        dog_detected_in_this_frame = False
        cat_detected_in_this_frame = False
        max_dog_confidence = 0.0
        max_cat_confidence = 0.0

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                idx = int(detections[0, 0, i, 1])
                class_name = self.CLASSES[idx]
                
                # Обработка собаки
                if class_name == "dog":
                    is_dog_in_current_frame = True
                    max_dog_confidence = max(max_dog_confidence, confidence)
                    if not self.dog_detected_recently:
                        dog_detected_in_this_frame = True
                
                # Обработка кота
                elif class_name == "cat":
                    is_cat_in_current_frame = True
                    max_cat_confidence = max(max_cat_confidence, confidence)
                    if not self.cat_detected_recently:
                        cat_detected_in_this_frame = True

                # Отрисовка прямоугольника и подписи
                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (startX, startY, endX, endY) = box.astype("int")
                label = f"{class_name}: {confidence:.2f}"
                
                # Разные цвета для разных животных
                if class_name == "dog":
                    color = (0, 255, 0)  # Зеленый для собаки
                elif class_name == "cat":
                    color = (255, 0, 0)  # Синий для кота
                else:
                    color = (0, 255, 255)  # Желтый для других объектов
                
                cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
                cv2.putText(frame, label, (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # --- Логика озвучки для собаки ---
        if is_dog_in_current_frame and not self.dog_detected_recently:
            self.speak("Жужа, жужа, скорее иди сюда!!!")
            self.dog_detected_recently = True
        
        # --- Логика озвучки для кота ---
        if is_cat_in_current_frame and not self.cat_detected_recently:
            self.speak("Кот котик, милый котик!")
            self.cat_detected_recently = True
        
        # --- Логика отправки фото в Telegram ---
        if dog_detected_in_this_frame:
            self._send_pet_photo(frame, "dog")
        
        if cat_detected_in_this_frame:
            self._send_pet_photo(frame, "cat")
        
        # Сброс флагов если животные пропали из кадра
        if not is_dog_in_current_frame:
            self.dog_detected_recently = False
            
        if not is_cat_in_current_frame:
            self.cat_detected_recently = False

        yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        
        try:
            os.write(self.fd_out, yuv_frame.tobytes())
        except Exception as e:
            logger.error(f"Failed to write to virtual camera: {e}")
            self.stop()

    def run(self):
        """Запуск основного цикла детектора"""
        self.running = True
        logger.info("Starting virtual camera stream...")
        try:
            while self.running:
                self._process_and_write_frame()
                time.sleep(1/30)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received.")
        finally:
            self.stop()

    def stop(self):
        """Остановка детектора и освобождение ресурсов"""
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.fd_out:
            os.close(self.fd_out)
        logger.info("Streaming stopped.")

# Пример использования
if __name__ == "__main__":
    detector = VirtualCameraObjectDetector(
        width=640,
        height=480,
        input_device_index=0,
        output_device="/dev/video2",
        enable_telegram=True,
        photo_interval=30  # Интервал между фото для каждого животного отдельно
    )
    
    try:
        detector.run()
    except Exception as e:
        logger.error(f"Ошибка запуска детектора: {e}")
    finally:
        detector.stop()
