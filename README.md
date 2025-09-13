# roverPi
Raspbery Pi robot written in Python
![photo](images/rover_1209.jpg)

# QuickStart
```bash
sudo apt install git python3-pip joystick libgl1
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Software
### Raspberry Config
In raspi-config:
- Enable SSH
- Enable Serial Port

### Service Installation
```bash
chmod +x src/start_all.sh
sudo cp ./rover.service /etc/systemd/system/rover.service
sudo systemctl daemon-reload
sudo systemctl enable rover.service
sudo systemctl start rover.service
```

## Hardware
### Motors And chasis
[Wild Thumper All-Terrain Chassis](https://www.pololu.com/category/88/wild-thumper-all-terrain-chassis) with [Qik Motor Drive](doc/qik_2s12v10.pdf)

### Battery Pack
I use 2 separate 3s 18650 LiOn battery packs for raspberry and motors, (3s5p and 3s3p relatively), balanced by [1$ BMS boards](https://youtu.be/cMEkpHBKMSE?si=hUZkEgKMPaiNRmlu)

### Wifi Interface with Antenna
Bus 001 Device 005: ID 0bda:8176 Realtek Semiconductor Corp. RTL8188CUS 802.11n WLAN Adapter
```
sudo ip route del default dev wlan0
sudo ip route add default dev wlx0013eff10409
```
### USB Web-Camera
Bus 001 Device 007: ID 0ac8:3500 Z-Star Microelectronics Corp. Full HD 1080P PC Camera
Live stream: 
```bash
sudo apt install build-essential cmake libjpeg-dev
git clone https://github.com/jacksonliam/mjpg-streamer.git
cd mjpg-streamer/mjpg-streamer-experimental
make
sudo make install
mjpg_streamer -i "/home/volodya/mjpg-streamer/mjpg-streamer-experimental/_build/plugins/input_uvc/input_uvc.so -d /dev/video0 -r 1280x720 -f 30" -o "/home/volodya/mjpg-streamer/mjpg-streamer-experimental/_build/plugins/output_http/output_http.so -p 8080" &
```
Video is available at url: `http://<IP-адрес вашего устройства>:8080/?action=stream`

### Bluetooth controller
You can use any controller you like, I use DualShock or 8bitDo. To pair a controller you need to know its MAC, you can find it by the name "Wireless controller" in the list of bluetooth devices then pair.
```bash
bluetoothctl
[bluetooth]# scan on
[bluetooth]# pair E4:17:D8:01:0B:7E
[bluetooth]# connect E4:17:D8:01:0B:7E
[bluetooth]# trust E4:17:D8:01:0B:7E
```
You can test controller using `jstest` (joystick debian package required)

## Web Interface
The RoverPi project includes a web-based remote control interface built on Flask and Socket.IO. This interface enables you to control the rover using any modern web browser on your computer or mobile device, with live video streaming and a virtual joystick.

### Key Features
- Stream live video feed from the robot’s camera.
- Control motors using a responsive virtual joystick.
- Real-time command updates using WebSockets.
Open your web browser and go to: `http://<robot-ip-address>:5000`






