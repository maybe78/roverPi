"""
YDLIDAR X4-Pro driver wrapper.

Initialization runs in a background thread and retries indefinitely — the
robot starts up immediately even if the lidar takes a few extra seconds to
spin up.  Once running, the scan thread auto-reconnects on disconnect.

Sectors: front (315–45°), right (45–135°), back (135–225°), left (225–315°).
"""

import logging
import threading
import math
from typing import Optional

logger = logging.getLogger("rover.lidar")

SECTORS = {
    "front": (315, 45),
    "right": (45, 135),
    "back":  (135, 225),
    "left":  (225, 315),
}


class Lidar:
    def __init__(self, port: str, baudrate: int = 128000):
        self._port = port
        self._baudrate = baudrate
        self._laser = None
        self._scan: dict[int, float] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._start_bg_thread()

    def _start_bg_thread(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._lidar_loop, daemon=True, name="LidarThread"
        )
        self._thread.start()

    def _lidar_loop(self) -> None:
        """Background loop: init → scan → reconnect on error."""
        import ydlidar, time
        attempt = 0

        while self._running:
            attempt += 1
            laser = None

            # --- initialise (exact legacy/lidar.py settings) ---
            try:
                laser = ydlidar.CYdLidar()
                laser.setlidaropt(ydlidar.LidarPropSerialPort, self._port)
                laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, self._baudrate)
                laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
                laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
                laser.setlidaropt(ydlidar.LidarPropScanFrequency, 6.0)
                laser.setlidaropt(ydlidar.LidarPropSampleRate, 9)
                laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)

                if not laser.initialize():
                    logger.warning(f"Lidar initialize() failed (attempt {attempt}), retry in 5s")
                    try:
                        laser.disconnecting()
                    except Exception:
                        pass
                    time.sleep(5)
                    continue

                # Retry turnOn() on the same object — do NOT recreate between retries
                turned_on = False
                for ton in range(1, 4):
                    if laser.turnOn():
                        turned_on = True
                        break
                    logger.warning(f"Lidar turnOn {ton}/3 failed, retry in 3s")
                    laser.turnOff()
                    time.sleep(3)

                if not turned_on:
                    logger.warning(f"Lidar init attempt {attempt} failed, full reset in 5s")
                    try:
                        laser.turnOff()
                        laser.disconnecting()
                    except Exception:
                        pass
                    time.sleep(5)
                    continue

            except ImportError:
                logger.warning("ydlidar SDK not installed — lidar disabled")
                return
            except Exception as e:
                logger.error(f"Lidar init error (attempt {attempt}): {e}, retry in 5s")
                time.sleep(5)
                continue

            logger.info(f"YDLIDAR ready on {self._port} (attempt {attempt})")
            with self._lock:
                self._laser = laser

            # --- scan ---
            scan_obj = ydlidar.LaserScan()
            while self._running:
                time.sleep(0)  # yield GIL so other Python threads can run
                try:
                    if laser.doProcessSimple(scan_obj):
                        data = {}
                        for point in scan_obj.points:
                            angle_deg = math.degrees(point.angle) % 360
                            if point.range > 0:
                                data[int(angle_deg)] = point.range * 1000  # m → mm
                        with self._lock:
                            self._scan = data
                except Exception as e:
                    logger.error(f"Lidar scan error: {e}")
                    break

            # scan loop exited — disconnect and retry
            with self._lock:
                self._laser = None
            try:
                laser.turnOff()
                laser.disconnecting()
            except Exception:
                pass

            if self._running:
                logger.info("Lidar disconnected, reconnecting in 3s...")
                time.sleep(3)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._laser is not None

    def get_full_scan(self) -> dict:
        """Return latest 360° scan {angle_deg: distance_mm}."""
        with self._lock:
            return dict(self._scan)

    def get_nearest_by_sector(self) -> dict:
        """Return nearest distance (mm) per sector. -1 = no reading."""
        with self._lock:
            scan = dict(self._scan)

        result = {}
        for sector, (start, end) in SECTORS.items():
            distances = []
            for angle, dist in scan.items():
                if start > end:
                    if angle >= start or angle <= end:
                        distances.append(dist)
                else:
                    if start <= angle <= end:
                        distances.append(dist)
            result[sector] = int(min(distances)) if distances else -1

        return result

    def get_nearest_distance(self) -> int:
        """Overall nearest obstacle distance in mm, -1 if unavailable."""
        with self._lock:
            if not self._scan:
                return -1
            return int(min(self._scan.values()))

    def is_obstacle_ahead(self, threshold_mm: int = 300) -> bool:
        sectors = self.get_nearest_by_sector()
        front = sectors.get("front", -1)
        return 0 < front < threshold_mm

    def stop(self) -> None:
        self._running = False
        with self._lock:
            laser = self._laser
            self._laser = None
        if laser:
            try:
                laser.turnOff()
                laser.disconnecting()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5.0)
