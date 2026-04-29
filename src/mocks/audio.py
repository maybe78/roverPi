"""
Mock audio for local development.

MockTTS    — macOS `say`, else prints to console
MockSTT    — real Whisper on microphone (if sounddevice available),
             falls back to stdin readline
MockBT     — no-op
MockPlayer — no-op with log
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
        self._mac = (platform.system() == "Darwin" and
                     subprocess.run(["which", "say"],
                                    capture_output=True).returncode == 0)
        engine = "macOS say" if self._mac else "console print"
        logger.info(f"MockTTS: {engine}")

    def say(self, text: str) -> None:
        if self._mac:
            threading.Thread(
                target=lambda: subprocess.run(
                    ["say", "-v", "Milena", text], timeout=30
                ), daemon=True,
            ).start()
        else:
            print(f"\n🤖  {text}\n", flush=True)
        logger.info(f"TTS → {text[:100]}")

    def say_sync(self, text: str) -> None:
        if self._mac:
            subprocess.run(["say", "-v", "Milena", text], timeout=30)
        else:
            print(f"\n🤖  {text}\n", flush=True)


# ---------------------------------------------------------------------------
# STT  —  real Whisper on mic, fallback to stdin
# ---------------------------------------------------------------------------

class MockSTT:
    """
    Tries to use faster-whisper + sounddevice for real voice input.
    Falls back to reading from stdin if hardware/deps are unavailable.
    """

    def __init__(self, model_size: str = "base", language: str = "ru",
                 **kwargs):
        self._callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._use_mic = self._check_mic()
        self._model = None
        self._model_size = model_size
        self._language = language

        if self._use_mic:
            self._load_model()

    def _check_mic(self) -> bool:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            inputs = [d for d in devices if d["max_input_channels"] > 0]
            if not inputs:
                logger.warning("MockSTT: no input devices found → stdin mode")
                return False
            logger.info(f"MockSTT: mic available ({inputs[0]['name']})")
            return True
        except Exception as e:
            logger.warning(f"MockSTT: sounddevice unavailable ({e}) → stdin mode")
            return False

    def _load_model(self) -> None:
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_size, device="cpu", compute_type="int8"
            )
            logger.info(f"MockSTT: Whisper '{self._model_size}' loaded — real voice input active")
        except Exception as e:
            logger.warning(f"MockSTT: Whisper load failed ({e}) → stdin mode")
            self._use_mic = False

    # ------------------------------------------------------------------

    def on_transcript(self, callback: Callable[[str], None]) -> None:
        self._callback = callback

    def start(self) -> None:
        self._running = True
        target = self._mic_loop if self._use_mic else self._stdin_loop
        self._thread = threading.Thread(
            target=target, daemon=True, name="MockSTTThread"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Microphone loop
    # ------------------------------------------------------------------

    def _mic_loop(self) -> None:
        import numpy as np
        import sounddevice as sd

        RATE    = 16000
        CHUNK   = 1024
        SILENCE = 400     # amplitude threshold
        SILENCE_CHUNKS = int(1.5 * RATE / CHUNK)

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  🎤  Voice input active — speak to the robot")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        buffer = []
        silence_count = 0
        recording = False

        def cb(indata, frames, time_info, status):
            nonlocal recording, silence_count, buffer
            audio = indata[:, 0]
            amp = np.abs(audio).mean() * 32768
            if amp > SILENCE:
                if not recording:
                    print("🔴 listening...", flush=True)
                recording = True
                silence_count = 0
                buffer.append(audio.copy())
            elif recording:
                buffer.append(audio.copy())
                silence_count += 1
                if silence_count >= SILENCE_CHUNKS:
                    data = list(buffer)
                    buffer.clear()
                    silence_count = 0
                    recording = False
                    threading.Thread(
                        target=self._transcribe, args=(data,),
                        daemon=True
                    ).start()

        with sd.InputStream(
            samplerate=RATE, channels=1, dtype="float32",
            blocksize=CHUNK, callback=cb,
        ):
            while self._running:
                sd.sleep(200)

    def _transcribe(self, buffer: list) -> None:
        import numpy as np
        try:
            audio = np.concatenate(buffer).astype(np.float32)
            segments, _ = self._model.transcribe(
                audio, language=self._language, beam_size=2, vad_filter=True
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            if text:
                print(f"🗣  {text}", flush=True)
                logger.info(f"Heard: {text}")
                if self._callback:
                    self._callback(text)
        except Exception as e:
            logger.error(f"Transcription error: {e}")

    # ------------------------------------------------------------------
    # Stdin fallback
    # ------------------------------------------------------------------

    def _stdin_loop(self) -> None:
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  ⌨️  No mic — type commands and press Enter")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        while self._running:
            try:
                print(">>> ", end="", flush=True)
                line = sys.stdin.readline()
                if not line:
                    break
                text = line.strip()
                if text and self._callback:
                    logger.info(f"Stdin: {text}")
                    self._callback(text)
            except (EOFError, KeyboardInterrupt):
                break


# ---------------------------------------------------------------------------

class MockBluetoothSpeaker:
    def __init__(self, **kwargs):
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def connect(self) -> bool:
        return True


class MockAudioPlayer:
    def __init__(self):
        pass

    def play(self, file_path: str) -> None:
        logger.info(f"AudioPlayer: would play {file_path}")

    def stop(self) -> None:
        pass

    def is_playing(self) -> bool:
        return False
