"""
Hardware/service factory.

IS_MOCK is True when:
  - env var MOCK=1  (explicit)
  - running on non-Linux OS (Mac, Windows)

Usage:
  from factory import create_all
  hw = create_all()
  motors = hw.motors
  agent  = hw.agent
  ...
"""

import os
import platform
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("rover.factory")

IS_MOCK: bool = (
    os.getenv("MOCK", "0") == "1"
    or platform.system() != "Linux"
)


@dataclass
class RoverComponents:
    motors:     Any = None
    lidar:      Any = None
    display:    Any = None
    tts:        Any = None
    stt:        Any = None
    bt_speaker: Any = None
    audio_player: Any = None
    telegram:   Any = None
    agent:      Any = None
    web_commands: Any = None
    mock: bool = False


def create_all() -> RoverComponents:
    from config import (
        MOTOR_SERIAL_PORT, MOTOR_BAUDRATE,
        LIDAR_PORT, LIDAR_BAUDRATE, DISPLAY_ROTATION,
        PIPER_VOICE, PIPER_SPEED,
        WHISPER_MODEL, WHISPER_LANGUAGE, MIC_DEVICE_INDEX,
        BT_SPEAKER_MAC, BT_RECONNECT_INTERVAL,
        TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
        OLLAMA_MODEL,
    )
    from web_commands import WebCommands
    from agent.tools import build_registry
    from agent.agent import RoverAgent

    c = RoverComponents(mock=IS_MOCK)

    if IS_MOCK:
        logger.warning("━━━ MOCK MODE — no real hardware ━━━")
        from mocks.motors   import MockMotors
        from mocks.lidar    import MockLidar
        from mocks.audio    import MockTTS, MockSTT, MockBluetoothSpeaker, MockAudioPlayer
        from mocks.telegram import MockTelegram

        c.motors       = MockMotors()
        c.lidar        = MockLidar()
        c.tts          = MockTTS()
        c.stt          = MockSTT()
        c.bt_speaker   = MockBluetoothSpeaker()
        c.audio_player = MockAudioPlayer()
        c.telegram     = MockTelegram()

        # Display: real pygame window on desktop (skip fbcon)
        from hardware.display import FaceDisplay
        c.display = FaceDisplay(fb_device="", mock=True)

    else:
        logger.info("━━━ HARDWARE MODE ━━━")
        from hardware.motors  import Motors
        from hardware.lidar   import Lidar
        from hardware.display import FaceDisplay
        from audio.tts        import TTS
        from audio.stt        import STT
        from audio.bluetooth  import BluetoothSpeaker
        from audio.player     import AudioPlayer

        c.motors       = Motors()
        c.lidar        = Lidar(port=LIDAR_PORT, baudrate=LIDAR_BAUDRATE)
        c.display      = FaceDisplay(rotation=DISPLAY_ROTATION)
        c.tts          = TTS(voice=PIPER_VOICE, speed=PIPER_SPEED)
        c.stt          = STT(model_size=WHISPER_MODEL,
                             language=WHISPER_LANGUAGE,
                             device_index=MIC_DEVICE_INDEX)
        c.bt_speaker   = BluetoothSpeaker(mac=BT_SPEAKER_MAC,
                                          reconnect_interval=BT_RECONNECT_INTERVAL)
        c.audio_player = c.audio_player  # AudioPlayer()

        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            from services.telegram import TelegramBot
            c.telegram = TelegramBot(bot_token=TELEGRAM_TOKEN,
                                     default_chat_id=TELEGRAM_CHAT_ID)
        else:
            logger.warning("Telegram disabled (no token/chat_id)")

    # --- Agent is always real (talks to ollama) ---
    c.web_commands = WebCommands()
    registry = build_registry(
        motors=c.motors,
        lidar=c.lidar,
        display=c.display,
        tts=c.tts,
        camera=None,
        telegram=c.telegram,
    )
    c.agent = RoverAgent(
        tool_registry=registry,
        tts=c.tts,
        display=c.display,
    )

    return c
