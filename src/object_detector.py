import os
import cv2
import time
import fcntl
import v4l2
import logging
import numpy as np
import requests  # <--- Добавили импорт

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger('object_detector')


class VirtualCameraObjectDetector:
    def __init__(self, width=640, height=480, input_device_index=0, output_device="/dev/video2", tts_url="http://127.0.0.1:5000/audio/speak"):
        self.width = width
        self.height = height
        self.input_device_index = int(input_device_index)
        self.output_device = output_device
        self.tts_url = "https://192.168.0.38:5000/audio/speak" # <--- URL для TTS
        self.running = False
        self.fd_out = None
        self.cap = None

        # --- Состояние для TTS ---
        self.dog_detected_recently = False # <--- Флаг для предотвращения спама

        prototxt_path = '../models/MobileNetSSD_deploy.prototxt'
        model_path = '../models/MobileNetSSD_deploy.caffemodel'
        self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        self.CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"]
        
        self._initialize_camera()
        self._initialize_virtual_device()


    def _initialize_camera(self):
        self.cap = cv2.VideoCapture(self.input_device_index)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera with index {self.input_device_index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        self.cap.set(cv2.CAP_PROP_FPS, 30.0)
        logger.info(f"Camera {self.input_device_index} initialized.")


    def _initialize_virtual_device(self):
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

    def _process_and_write_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
        self.net.setInput(blob)
        detections = self.net.forward()
        
        is_dog_in_current_frame = False # <--- Проверяем наличие собаки в ТЕКУЩЕМ кадре

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                idx = int(detections[0, 0, i, 1])
                # Проверяем, является ли найденный объект собакой
                if self.CLASSES[idx] == "dog":
                    is_dog_in_current_frame = True

                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (startX, startY, endX, endY) = box.astype("int")
                label = f"{self.CLASSES[idx]}: {confidence:.2f}"
                cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
                cv2.putText(frame, label, (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # --- Логика озвучки ---
        if is_dog_in_current_frame and not self.dog_detected_recently:
            self.speak("Жужа, жужа, скорее иди сюда!!!")
            self.dog_detected_recently = True # Взводим флаг
        
        # Если собака пропала из кадра, сбрасываем флаг, чтобы среагировать в следующий раз
        if not is_dog_in_current_frame:
            self.dog_detected_recently = False

        yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        
        try:
            os.write(self.fd_out, yuv_frame.tobytes())
        except Exception as e:
            logger.error(f"Failed to write to virtual camera: {e}")
            self.stop()

    def run(self):
        self.running = True
        logger.info("Starting virtual camera stream...")
        try:
            while self.running:
                self._process_and_write_frame()
                time.sleep(1/30) # Оставляем небольшую задержку
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received.")
        finally:
            self.stop()


    def stop(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.fd_out:
            os.close(self.fd_out)
        logger.info("Streaming stopped.")
