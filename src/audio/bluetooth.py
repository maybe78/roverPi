"""
Bluetooth speaker auto-reconnect daemon.
Runs in background, tries to connect every N seconds if speaker is offline.
"""

import logging
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger("rover.bluetooth")


class BluetoothSpeaker:
    def __init__(self, mac: str, reconnect_interval: int = 15):
        self._mac = mac
        self._interval = reconnect_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self._mac:
            logger.warning("BT_SPEAKER_MAC not set — bluetooth daemon disabled")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="BluetoothThread"
        )
        self._thread.start()
        logger.info(f"Bluetooth daemon started for {self._mac}")

    def stop(self) -> None:
        self._running = False

    def is_connected(self) -> bool:
        try:
            result = subprocess.run(
                ["bluetoothctl", "info", self._mac],
                capture_output=True, text=True, timeout=5
            )
            return "Connected: yes" in result.stdout
        except Exception:
            return False

    def connect(self) -> bool:
        try:
            result = subprocess.run(
                ["bluetoothctl", "connect", self._mac],
                capture_output=True, text=True, timeout=10
            )
            success = "Connection successful" in result.stdout
            if success:
                # set as default audio sink
                self._set_as_default_sink()
            return success
        except Exception as e:
            logger.debug(f"BT connect attempt failed: {e}")
            return False

    def _set_as_default_sink(self) -> None:
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                # bluez sinks contain the MAC (colons replaced by underscores)
                mac_fmt = self._mac.replace(":", "_")
                if mac_fmt in line:
                    sink_name = line.split()[1]
                    subprocess.run(
                        ["pactl", "set-default-sink", sink_name],
                        timeout=5
                    )
                    logger.info(f"Default audio sink: {sink_name}")
                    return
        except Exception as e:
            logger.debug(f"Could not set default sink: {e}")

    def _loop(self) -> None:
        while self._running:
            try:
                if not self.is_connected():
                    logger.info(f"Speaker disconnected, reconnecting {self._mac}...")
                    connected = self.connect()
                    if connected:
                        logger.info("Speaker connected")
                    else:
                        logger.debug("Reconnect failed, will retry")
            except Exception as e:
                logger.error(f"BT loop error: {e}")
            time.sleep(self._interval)
