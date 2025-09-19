#!/bin/bash
PROJECT_DIR=/home/volodya/roverPi

# Создаем папку для логов, если ее нет
mkdir -p $PROJECT_DIR/logs

echo "=== Setting up virtual camera device ==="
sudo modprobe -r v4l2loopback
sudo modprobe v4l2loopback devices=1 video_nr=2 card_label="OpenCV_Final" max_buffers=4 exclusive_caps=1

sudo chmod 666 /dev/video2
echo "Virtual camera created: /dev/video2"

cd $PROJECT_DIR
# --- 2. Запуск основного приложения управления (которое включает детектор) ---
echo "Starting main control application (with object detection)..."
venv/bin/python src/main.py &
MAIN_PID=$!
echo "Main application started in background with PID $MAIN_PID."
sleep 5 # Даем время Python-скрипту инициализироваться и начать стримить

# --- 3. Запуск видеострима WebRTC ---
echo "Starting WebRTC video stream..."
/home/volodya/pi-webrtc \
  --camera=v4l2:2 \
  --v4l2-format=yuyv \
  --width=640 \
  --height=480 \
  --fps=30 \
  --http-port=8080 \
  --uid=rover-camera \
  --use-whep \
  --no-audio > $PROJECT_DIR/logs/pi-webrtc.log 2>&1 &
WEBRTC_PID=$!
echo "pi-webrtc started with PID: $WEBRTC_PID"


sleep 5
if kill -0 $WEBRTC_PID 2>/dev/null; then
    echo "SUCCESS: pi-webrtc is running!"
else
    echo "ERROR: pi-webrtc failed! Check logs:"
    cat $PROJECT_DIR/logs/pi-webrtc.log
fi

wait $MAIN_PID
kill $WEBRTC_PID 2>/dev/null
