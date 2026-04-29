"""
Mock audio subsystems for local development.

MockTTS   — uses macOS `say` if available, otherwise prints
MockSTT   — reads lines from stdin in a background thread
MockBT    — no-op
MockPlayer — no-op with logs
"""

import logging
import platform
import subprocess
import sys
import threading
from typing import Callable, Optional

logger = logging.getLogger("mock.audio")


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

class MockTTS:
    def __init__(self, **kwargs):
        self._use_say = (platform.system() == "Darwin" and
                         subprocess.run(["which", "say"],
                                        capture_output=True).returncode == 0)
        if self._use_say:
            logger.info("MockTTS: macOS `say` command available")
        else:
            logger.info("MockTTS: printing to console")

    def say(self, text: str) -> None:
        if self._use_say:
            threading.Thread(
                target=lambda: subprocess.run(
                    ["say", "-v", "Milena", text], timeout=30
                ),
                daemon=True,
            ).start()
        else:
            print(f"\n🤖 Rover: {text}\n", flush=True)
        logger.info(f"TTS: {text[:100]}")

    def say_sync(self, text: str) -> None:
        if self._use_say:
            subprocess.run(["say", "-v", "Milena", text], timeout=30)
        else:
            print(f"\n🤖 Rover: {text}\n", flush=True)


# ---------------------------------------------------------------------------
# STT  —  reads from stdin, sends each line to the agent
# ---------------------------------------------------------------------------

class MockSTT:
    def __init__(self, **kwargs):
        self._callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        logger.info("MockSTT: type commands in terminal (Enter to send)")

    def on_transcript(self, callback: Callable[[str], None]) -> None:
        self._callback = callback

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._stdin_loop, daemon=True, name="MockSTTThread"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _stdin_loop(self) -> None:
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  MOCK MODE — type a command and press Enter")
        print("  Examples: едь вперёд | осмотрись | как дела")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        while self._running:
            try:
                print(">>> ", end="", flush=True)
                line = sys.stdin.readline()
                if not line:
                    break
                text = line.strip()
                if text and self._callback:
                    logger.info(f"MockSTT input: {text}")
                    self._callback(text)
            except (EOFError, KeyboardInterrupt):
                break


# ---------------------------------------------------------------------------
# Bluetooth speaker
# ---------------------------------------------------------------------------

class MockBluetoothSpeaker:
    def __init__(self, **kwargs):
        logger.info("MockBluetooth: no-op")

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def connect(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Audio player
# ---------------------------------------------------------------------------

class MockAudioPlayer:
    def __init__(self):
        logger.info("MockAudioPlayer: no-op")

    def play(self, file_path: str) -> None:
        logger.info(f"AudioPlayer: would play {file_path}")

    def stop(self) -> None:
        pass

    def is_playing(self) -> bool:
        return False
