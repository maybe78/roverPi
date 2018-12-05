# roverPi
6-wheel raspberypi robot written in Python

### Previous version based om Arduino Mega:
![photo](doc/roverph.jpg)

### Installation

Firstly need to setup a DualShock PS4 controller for rover control. Once paired it will be connected automatically.
####  Dualshock4 pairing
1. First of all install needed python3 bluetooth dependencies and debug util
```bash
sudo pip install python-evdev pyudev
sudo apt install joystick
```
.*2. To pair a controller you need to know its MAC, you can find it by the name "Wireless controller" in the list of bluetooth devices
```bash
sudo bluetoothctl << EOF
devices
EOF
```
3. Once MAC is known, just execute the following script passing an address as a param
```bash
sudo sh bluetooth-pair.sh
```
