#!/bin/bash
PROJECT_DIR=/home/volodya/roverPi

# Создаем папку для логов, если ее нет
mkdir -p $PROJECT_DIR/logs

# --- 1. Запуск видеострима WebRTC ---
echo "Starting WebRTC video stream with H.264 hardware acceleration..."

# Ждем, пока камера определится системой
while [ ! -e /dev/video0 ]; do
  echo "Waiting for camera (/dev/video0)..."
  sleep 1 
done
echo "Camera found!"

# Запускаем pi-webrtc в фоновом режиме (&)
# и перенаправляем весь вывод в лог-файл
/home/volodya/pi-webrtc \
  --camera=v4l2:0 \
  --v4l2-format=h264 \
  --fps=15 \
  --width=640 \
  --height=480 \
  --use-whep \
  --http-port=8080 \
  --uid=rover-camera \
  --no-audio \
  --hw-accel > $PROJECT_DIR/logs/pi-webrtc.log 2>&1 &

echo "WebRTC server started in background. Logs are in $PROJECT_DIR/logs/pi-webrtc.log"
sleep 2 # Даем время серверу запуститься

# --- 2. Запуск основного приложения управления ---
echo "Starting main control application..."
$PROJECT_DIR/venv/bin/python $PROJECT_DIR/src/main.py

#ffplay -nodisp -autoexit ~/roverPi/media/startup.mp3 
# --- Очистка при завершении ---
echo "Stopping background processes..."
# Убиваем процесс pi-webrtc по имени при завершении скрипта
killall pi-webrtc
echo "All processes stopped."
