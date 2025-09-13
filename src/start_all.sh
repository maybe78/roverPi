#!/bin/bash
PROJECT_DIR=/home/volodya/roverPi
MJPEG_PLUGIN_DIR=/home/volodya/mjpg-streamer/mjpg-streamer-experimental/_build/plugins
cd $PROJECT_DIR/src/

# Start Cam Stream
while [ ! -e /dev/video0 ]; do
  echo "Waiting for camera (/dev/video0)..."
  sleep 1 
done
echo "Cam was found!"
mjpg_streamer -i "$MJPEG_PLUGIN_DIR/input_uvc/input_uvc.so -d /dev/video0 -r 854x480 -f 10" -o "$MJPEG_PLUGIN_DIR/output_http/output_http.so -p 8080" &
# Start main python app
$PROJECT_DIR/venv/bin/python $PROJECT_DIR/src/main.py