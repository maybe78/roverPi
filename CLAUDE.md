# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RoverPi is a Raspberry Pi 5 (8 GB) based autonomous robot-pet. It moves, sees, hears, speaks, and makes decisions using an on-device LLM. Controlled via browser (mobile) or voice commands.

**Hardware:**
- Wild Thumper 4WD chassis, Pololu Qik 2s12v10 motor controller (`/dev/ttyUSB1`, 38400 baud)
- YDLIDAR X4-Pro (`/dev/ttyUSB0`, 128000 baud)
- USB webcam with microphone (`/dev/video0`)
- SPI color display 480×320 landscape, RGB565 (`/dev/fb0`)
- Bluetooth speaker H-PS1000 (MAC `41:42:E0:C6:CC:DB`)
- Bluetooth gamepad 8BitDo NES30 Pro

## Running

**On Pi (hardware mode):**
```bash
cd /home/volodya/roverPi
source venv/bin/activate
python src/main.py
```

**Local development (mock mode — auto-detected on non-Linux):**
```bash
source myenv/bin/activate
MOCK=1 python src/main.py   # or just: python src/main.py  (on macOS)
```

Mock opens a pygame desktop window (face + radar), uses macOS `say` for TTS, real Whisper mic input or stdin fallback.

**Systemd service:**
```bash
sudo systemctl start rover.service
journalctl -u rover.service -f
```

## Prerequisites on Pi

```bash
# LLM
ollama serve &
ollama pull qwen2.5:3b

# TTS — RHVoice already installed, voice: alexander
# STT — faster-whisper installed in venv

# Config
cat /home/volodya/roverPi/.env   # TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BT_SPEAKER_MAC etc.
```

## Architecture (branch: `autonomous`)

```
src/
├── main.py          — entry point; wires everything, starts Flask + threads
├── config.py        — all settings; reads from .env in project root
├── factory.py       — creates real or mock components based on IS_MOCK flag
│
├── agent/
│   ├── agent.py     — RoverAgent: ollama tool-calling loop, sliding history window
│   └── tools.py     — tool registry (move, scan, capture_photo, send_notification,
│                       set_expression, read/modify_source_file, restart_service)
│
├── hardware/
│   ├── motors.py    — wrapper over qik.py with graceful degradation
│   ├── lidar.py     — YDLIDAR X4-Pro; get_full_scan() → {angle: mm}
│   └── display.py   — pygame face animation + lidar radar; 480×320 landscape split:
│                       left 240px = face, right 240px = radar
├── audio/
│   ├── stt.py       — faster-whisper on mic, VAD, sends text to agent queue
│   ├── tts.py       — RHVoice (primary) → piper → espeak-ng fallback chain
│   ├── bluetooth.py — BT speaker auto-reconnect daemon
│   └── player.py    — pygame MP3 player
│
├── mocks/           — drop-in replacements for all hardware (no Pi needed)
│   ├── motors.py    — logs with direction arrows, only on state change
│   ├── lidar.py     — simulates a 7×8 m room + moving obstacle
│   ├── audio.py     — MockTTS (macOS say), MockSTT (real Whisper or stdin)
│   └── telegram.py  — prints to console instead of sending
│
├── services/
│   └── telegram.py  — Telegram Bot API: send text, photo, capture+send
│
└── vision/          — placeholder for object detector (OpenCV, from telegram branch)
```

## Agent Tool Calling Flow

```
voice/text input → STT → agent.submit(text)
  → display: "thinking"
  → ollama.chat(qwen2.5:3b, history, tools)
  → if tool_calls: execute → append results → loop (max 8 rounds)
  → final text response → display: "speaking" → TTS → display: "idle"
```

**Available tools:** `move`, `stop`, `scan_surroundings`, `capture_photo`, `get_status`, `send_notification`, `set_expression`, `read_source_file`, `modify_source_file`, `restart_service`

**Note:** `speak()` is NOT a tool — final LLM text response is always auto-spoken. This prevents double TTS.

## Display Layout

```
┌────────────┬────────────┐
│            │   RADAR    │  480×320 landscape (/dev/fb0, RGB565)
│    FACE    │  (lidar    │
│ (240×320)  │  top-down) │  Left: pygame face animation (240×320)
│            │  240×320   │  Right: 360° lidar point cloud, robot arrow at center
└────────────┴────────────┘
```

Face states: `idle`, `listening`, `thinking`, `speaking`, `happy`, `surprised`, `angry`, `sad`

## Key Config Values (Pi)

| Setting | Value |
|---|---|
| Lidar port | `/dev/ttyUSB0` |
| Motor port | `/dev/ttyUSB1` |
| Display fb | `/dev/fb0` |
| Display size | 480×320 |
| TTS engine | RHVoice `alexander` voice |
| LLM | `qwen2.5:3b` via ollama |
| STT | `faster-whisper` base model |
| BT speaker | H-PS1000, `41:42:E0:C6:CC:DB` |

## macOS / Pi Threading Difference

macOS Cocoa requires pygame on the **main thread**. On macOS mock mode: Flask runs in a daemon thread, pygame blocks main thread. On Pi: pygame in background thread, Flask on main thread. Controlled by `display.needs_main_thread` property.
