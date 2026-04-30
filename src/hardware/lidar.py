"""
YDLIDAR X4-Pro driver wrapper.

Returns sector distances used by the agent's scan_surroundings() tool.
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
        self._scan: dict[int, float] = {}   # angle → distance_mm
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._connect()

    def _connect(self) -> None:
        try:
            import ydlidar, time
            ydlidar.os_init()
            time.sleep(0.5)  # let USB device settle after hotplug
            self._laser = ydlidar.CYdLidar()
            self._laser.setlidaropt(ydlidar.LidarPropSerialPort, self._port)
            self._laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, self._baudrate)
            self._laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
            self._laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
            self._laser.setlidaropt(ydlidar.LidarPropScanFrequency, 6.0)
            self._laser.setlidaropt(ydlidar.LidarPropSampleRate, 9)
            self._laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)
            if not self._laser.initialize():
                raise RuntimeError("Lidar initialize() failed")
            if not self._laser.turnOn():
                raise RuntimeError("Lidar turnOn() failed")
            logger.info(f"YDLIDAR ready on {self._port}")
            self._start_scan_thread()
        except ImportError:
            logger.warning("ydlidar SDK not installed — lidar disabled")
        except Exception as e:
            logger.error(f"Lidar init failed: {e}")
            self._laser = None

    def _start_scan_thread(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._scan_loop, daemon=True, name="LidarThread"
        )
        self._thread.start()

    def _scan_loop(self) -> None:
        import ydlidar
        scan = ydlidar.LaserScan()
        while self._running and self._laser:
            try:
                if self._laser.doProcessSimple(scan):
                    data = {}
                    for point in scan.points:
                        angle_deg = math.degrees(point.angle) % 360
                        if point.range > 0:
                            data[int(angle_deg)] = point.range * 1000  # → mm
                    with self._lock:
                        self._scan = data
            except Exception as e:
                logger.error(f"Lidar scan error: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._laser is not None

    def get_full_scan(self) -> dict:
        """Return full 360° scan {angle_deg: distance_mm}."""
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
                if start > end:          # wraps around 0 (e.g. front: 315–45)
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
        if self._laser:
            try:
                self._laser.turnOff()
                self._laser.disconnecting()
            except Exception:
                pass
