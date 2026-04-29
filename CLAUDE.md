# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RoverPi is a Raspberry Pi-based all-terrain robot controlled via Bluetooth gamepad (DualShock 4 / 8BitDo) or a browser-based virtual joystick, with live video over WebRTC. It runs as a `systemd` service on Raspberry Pi OS (Bookworm, arm64).

Hardware: Wild Thumper 4WD chassis, Pololu Qik 2s12v10 motor controller (serial `/dev/ttyUSB0` at 38400 baud), UVC USB camera (`/dev/video0`).

## Running the Application

On the Raspberry Pi, the service is started via systemd:
```bash
sudo systemctl start rover.service   # starts start_all.sh
sudo systemctl status rover.service
journalctl -u rover.service -f        # live logs
```

Manual start (for development):
```bash
source venv/bin/activate
cd src
python main.py
```

`start_all.sh` launches two processes:
1. `/home/volodya/pi-webrtc` — external binary for WebRTC video (WHEP, port 8080)
2. `python src/main.py` — Flask/Socket.IO control server (port 5000)

## Development Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Linting (configured via `.pylintrc`):
```bash
pylint src/
```

There are no automated tests. `src/MotorTest.py` and `src/OpenCVTest.py` are manual hardware test scripts.

## Architecture

### Control Flow (priority order in `main.py`)

The motor control loop runs in a background thread (`motor_control_loop`). On each 100ms tick:
1. **Gamepad (priority 1):** If a DualShock/8BitDo is connected via Bluetooth (`evdev`), its left stick axes drive the motors.
2. **Web interface (priority 2):** If no gamepad, uses the latest command from `WebCommands` (expires after 500ms).
3. **Stop:** If neither source has a valid command, motors are halted.

Joystick values are translated to differential (tank) drive by `utils.joystick_to_diff_control()`, which applies dead zone, exponential curve, and left/right mixing.

### Two Separate Backend Services

| Service | File | Port | Protocol |
|---|---|---|---|
| Motor control + web UI | `src/main.py` | 5000 | Flask + Socket.IO |
| Video stream | `/home/volodya/pi-webrtc` (external binary) | 8080 | WebRTC WHEP |

The browser (`src/static/js/main.js`) connects to **both**: Socket.IO on port 5000 for joystick commands, and HTTP POST to `http://192.168.0.38:8080` for the WebRTC SDP handshake. The rover IP is hardcoded in `main.js`.

### Key Modules

- **`src/main.py`** — Entry point. Owns the Flask app, Socket.IO server, motor control thread, and gamepad reconnect logic.
- **`src/qik.py`** — Serial driver for the Pololu Qik 2s12v10. Speed range is −127 to +127. Motor 0 = left side, Motor 1 = right side.
- **`src/dualshock4.py`** — `evdev`-based gamepad reader. Searches for devices named "Wireless Controller" or "8Bitdo". Handles disconnect/reconnect gracefully.
- **`src/utils.py`** — Pure math: dead zone, exponential curve (`CURVE_EXPONENT=1.6`), arcade-to-differential mixing.
- **`src/web_commands.py`** — Thread-safe shared state (`threading.Lock`) between the Socket.IO handler and the motor thread.
- **`src/webrtc_handler.py`** — An alternative `aiortc`-based WebRTC implementation (not used in the current `main.py`; kept for reference).
- **`src/app.py`** — An earlier, simpler version of the Flask app (not the active entry point).

### Web Frontend

- `src/templates/index.html` — Single-page UI with virtual joystick and WebRTC video element.
- `src/static/js/joystick.js` — Canvas joystick widget.
- `src/static/js/main.js` — Socket.IO control logic (throttled to 50ms) and WebRTC SDP negotiation.

## Important Notes

- The `venv/` directory is at the project root; `start_all.sh` references `/home/volodya/roverPi/venv/bin/python`.
- The `pi-webrtc` binary must be present at `/home/volodya/pi-webrtc` (downloaded separately, not in this repo).
- Serial port `/dev/ttyUSB0` must be accessible; the Qik controller requires Serial Port hardware enabled in `raspi-config` with login shell over serial **disabled**.
- The `rover.service` runs as user `volodya` with `WorkingDirectory=/home/volodya/roverPi/src`.
