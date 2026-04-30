#!/bin/bash
PROJECT_DIR=/home/volodya/roverPi
mkdir -p $PROJECT_DIR/logs

# PipeWire/PulseAudio сокеты — нужны когда запускаемся из systemd без сессии
export XDG_RUNTIME_DIR=/run/user/1000
export PULSE_SERVER=unix:/run/user/1000/pulse/native
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus

BT_SPEAKER="41:42:E0:C6:CC:DB"
AIRPODS="4C:B9:10:5D:82:C8"
AIRPODS_SRC="bluez_input.4C_B9_10_5D_82_C8.0"
USB_SRC="alsa_input.usb-GeneralPlus_USB_Audio_Device-00.mono-fallback"

# --- 1. Ollama ---
echo "[1/4] Starting ollama..."
pkill -x ollama 2>/dev/null; sleep 1
ollama serve >> $PROJECT_DIR/logs/ollama.log 2>&1 &
for i in $(seq 1 30); do
    if curl -sf http://localhost:11434 > /dev/null 2>&1; then
        echo "  ollama ready (${i}s)"
        break
    fi
    sleep 1
done

# --- 2. Bluetooth speaker ---
echo "[2/4] Connecting BT speaker..."
bluetoothctl connect $BT_SPEAKER >> $PROJECT_
DIR/logs/bt.log 2>&1 && echo "  speaker connected" || echo "  speaker not available"
sleep 2

# --- 3. Microphone ---
echo "[3/4] Setting up microphone..."
if bluetoothctl info $AIRPODS 2>/dev/null | grep -q "Connected: yes"; then
    sleep 2
    pactl set-default-source $AIRPODS_SRC 2>/dev/null && echo "  AirPods mic active" || echo "  AirPods mic not ready"
else
    pactl set-default-source $USB_SRC 2>/dev/null && echo "  USB mic active" || echo "  no mic available"
fi

# --- 4. Camera + WebRTC (started AFTER rover initializes lidar) ---
# pi-webrtc is now launched from main.py once lidar is up to avoid USB contention

# --- 5. Main app ---
echo "Starting rover..."
exec $PROJECT_DIR/venv/bin/python $PROJECT_DIR/src/main.py

# Cleanup (exec above replaces shell, but leave for manual runs)
killall pi-webrtc 2>/dev/null || true
