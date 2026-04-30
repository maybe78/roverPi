"""
Speech-to-text via faster-whisper.
Listens on microphone, detects voice activity, returns transcribed text.
"""

import logging
import threading
import queue
import numpy as np
from typing import Optional, Callable

logger = logging.getLogger("rover.stt")

SAMPLE_RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 500
SILENCE_CHUNKS = int(1.5 * SAMPLE_RATE / CHUNK)  # ~1.5 sec of silence
WAKE_WORD = "рома"
WAKE_TIMEOUT = 10.0  # seconds to stay active after wake word


class STT:
    def __init__(self, model_size: str = "base", language: str = "ru",
                 device_index: Optional[int] = None):
        self._language = language
        self._device_index = device_index
        self._model = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._result_queue: queue.Queue[str] = queue.Queue()
        self._callback: Optional[Callable[[str], None]] = None
        self._active = False
        self._wake_timer: Optional[threading.Timer] = None
        self._load_model(model_size)

    def _load_model(self, model_size: str) -> None:
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",   # faster on Pi
                local_files_only=True, # skip HF network check, use cache
            )
            logger.info(f"Whisper model '{model_size}' loaded")
        except ImportError:
            logger.warning("faster-whisper not installed — STT disabled")
        except Exception as e:
            logger.error(f"STT model load failed: {e}")

    # ------------------------------------------------------------------

    def on_transcript(self, callback: Callable[[str], None]) -> None:
        """Register callback invoked with each recognised phrase."""
        self._callback = callback

    def start(self) -> None:
        if not self._model:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="STTThread"
        )
        self._thread.start()
        logger.info("STT listening started")

    def stop(self) -> None:
        self._running = False
        if self._wake_timer:
            self._wake_timer.cancel()

    def _deactivate(self) -> None:
        self._active = False
        self._wake_timer = None
        logger.info("Wake word timeout — back to standby")

    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice not installed — STT disabled")
            return

        logger.info("Microphone open, listening...")
        buffer = []
        silence_count = 0
        recording = False

        def callback(indata, frames, time_info, status):
            nonlocal recording, silence_count, buffer
            audio = indata[:, 0]
            amplitude = np.abs(audio).mean() * 32768

            if amplitude > SILENCE_THRESHOLD:
                recording = True
                silence_count = 0
                buffer.append(audio.copy())
            elif recording:
                buffer.append(audio.copy())
                silence_count += 1
                if silence_count >= SILENCE_CHUNKS:
                    self._transcribe(buffer)
                    buffer = []
                    silence_count = 0
                    recording = False

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK,
                device=self._device_index,
                callback=callback,
            )
        except Exception as e:
            logger.error(f"Microphone unavailable: {e} — STT disabled")
            return

        with stream:
            while self._running:
                sd.sleep(100)

    def _transcribe(self, buffer: list) -> None:
        try:
            audio = np.concatenate(buffer).astype(np.float32)
            segments, _ = self._model.transcribe(
                audio,
                language=self._language,
                beam_size=2,
                vad_filter=True,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            if not text:
                return

            logger.info(f"Heard: {text}")
            lower = text.lower()

            if WAKE_WORD in lower:
                if self._wake_timer:
                    self._wake_timer.cancel()
                idx = lower.find(WAKE_WORD)
                command = text[idx + len(WAKE_WORD):].strip(" ,!?.")
                if command:
                    logger.info(f"Wake+command: {command}")
                    if self._callback:
                        self._callback(command)
                else:
                    self._active = True
                    self._wake_timer = threading.Timer(WAKE_TIMEOUT, self._deactivate)
                    self._wake_timer.daemon = True
                    self._wake_timer.start()
                    logger.info("Wake word heard — waiting for command...")
            elif self._active:
                self._active = False
                if self._wake_timer:
                    self._wake_timer.cancel()
                    self._wake_timer = None
                logger.info(f"Command: {text}")
                if self._callback:
                    self._callback(text)
            else:
                logger.info("(standby)")
        except Exception as e:
            logger.error(f"Transcription error: {e}")
