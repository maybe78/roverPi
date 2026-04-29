"""
Text-to-speech via piper.
Falls back to RHVoice (espeak) if piper is unavailable.
"""

import logging
import subprocess
import threading
import shutil
import os
from typing import Optional

logger = logging.getLogger("rover.tts")


class TTS:
    def __init__(self, voice: str = "ru_RU-ruslan-medium", speed: float = 1.0):
        self._voice = voice
        self._speed = speed
        self._engine = self._detect_engine()
        self._lock = threading.Lock()

    def _detect_engine(self) -> str:
        # RHVoice first — confirmed working on this Pi with 'alexander' voice
        if shutil.which("RHVoice-test"):
            logger.info("TTS engine: RHVoice (alexander)")
            return "rhvoice"
        if shutil.which("piper"):
            logger.info("TTS engine: piper")
            return "piper"
        if shutil.which("espeak-ng"):
            logger.info("TTS engine: espeak-ng (fallback)")
            return "espeak"
        logger.warning("No TTS engine found — speech disabled")
        return "none"

    def say(self, text: str) -> None:
        if not text or self._engine == "none":
            return
        threading.Thread(
            target=self._speak, args=(text,), daemon=True, name="TTSThread"
        ).start()

    def say_sync(self, text: str) -> None:
        """Blocking version — waits for speech to finish."""
        if not text or self._engine == "none":
            return
        with self._lock:
            self._speak(text)

    def _speak(self, text: str) -> None:
        text = text.strip().replace('"', "'")
        try:
            if self._engine == "piper":
                self._piper(text)
            elif self._engine == "rhvoice":
                self._rhvoice(text)
            elif self._engine == "espeak":
                self._espeak(text)
        except Exception as e:
            logger.error(f"TTS error: {e}")

    def _piper(self, text: str) -> None:
        from config import LOGS_DIR
        model_dir = os.path.expanduser("~/.local/share/piper")
        model_path = os.path.join(model_dir, f"{self._voice}.onnx")
        if not os.path.isfile(model_path):
            logger.error(f"Piper model not found: {model_path}")
            self._espeak(text)
            return
        cmd = (
            f'echo "{text}" | piper --model "{model_path}" '
            f'--length_scale {1.0/self._speed:.2f} --output-raw | '
            f'aplay -r 22050 -f S16_LE -t raw -'
        )
        subprocess.run(cmd, shell=True, timeout=30)

    def _rhvoice(self, text: str) -> None:
        # Same command confirmed working on this Pi
        subprocess.run(
            ["bash", "-c", f'echo "{text}" | RHVoice-test -p alexander'],
            timeout=30,
        )


    def _espeak(self, text: str) -> None:
        subprocess.run(
            ["espeak-ng", "-v", "ru", "-s", "150", text],
            timeout=30,
        )
