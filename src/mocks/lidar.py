"""
Mock lidar — simulates a room with walls and a moving obstacle.
get_full_scan() returns a realistic 360° point cloud.
"""

import logging
import math
import random
import time
import threading

logger = logging.getLogger("mock.lidar")

_SECTORS = {
    "front": (315, 45),
    "right": (45, 135),
    "back":  (135, 225),
    "left":  (225, 315),
}

# Room dimensions (mm): robot is at origin, walls at these distances per angle
_ROOM_W = 3500   # half-width  (left/right walls)
_ROOM_D = 4000   # half-depth  (front/back walls)


class MockLidar:
    available = True

    def __init__(self):
        self._forced: dict[str, int] = {}   # sector overrides for testing
        self._start_time = time.time()
        logger.info("MockLidar ready  (simulated room 7×8 m)")

    # ------------------------------------------------------------------
    # Full 360° scan — used by radar visualisation
    # ------------------------------------------------------------------

    def get_full_scan(self) -> dict[int, float]:
        """
        Returns {angle_deg: distance_mm} for 0..359.
        Simulates a rectangular room + one moving obstacle.
        """
        t = time.time() - self._start_time
        scan = {}

        # Moving obstacle: slow circle around the robot
        obs_angle = (t * 20) % 360          # degrees/sec
        obs_dist  = 900 + math.sin(t * 0.3) * 300   # 600–1200 mm
        obs_width = 18                       # angular half-width

        for a in range(360):
            rad = math.radians(a)

            # Ray-cast against rectangular room
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            d_wall = _ray_rect(cos_a, sin_a, _ROOM_W, _ROOM_D)

            # Check obstacle
            diff = abs(_angle_diff(a, obs_angle))
            if diff < obs_width:
                blend = 1.0 - (diff / obs_width)
                d_obs = obs_dist * (1.0 - 0.15 * blend)
                d = min(d_wall, d_obs)
            else:
                d = d_wall

            # Add small noise
            d += random.gauss(0, 15)
            scan[a] = max(80, d)

        return scan

    # ------------------------------------------------------------------
    # Sector summary (used by agent tool)
    # ------------------------------------------------------------------

    def get_nearest_by_sector(self) -> dict:
        scan = self.get_full_scan()
        result = {}
        for sector, (start, end) in _SECTORS.items():
            if sector in self._forced:
                result[sector] = self._forced[sector]
                continue
            distances = []
            for angle, dist in scan.items():
                if start > end:
                    if angle >= start or angle <= end:
                        distances.append(dist)
                else:
                    if start <= angle <= end:
                        distances.append(dist)
            result[sector] = int(min(distances)) if distances else -1
        logger.info(f"Lidar sectors: { {k: v for k, v in result.items()} }")
        return result

    def get_nearest_distance(self) -> int:
        return min(self.get_nearest_by_sector().values())

    def is_obstacle_ahead(self, threshold_mm: int = 300) -> bool:
        return self.get_nearest_by_sector()["front"] < threshold_mm

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def set_obstacle(self, sector: str, distance_mm: int) -> None:
        self._forced[sector] = distance_mm

    def clear_obstacles(self) -> None:
        self._forced.clear()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


# ---------------------------------------------------------------------------

def _ray_rect(cx: float, cy: float, hw: float, hd: float) -> float:
    """Distance from origin to rectangle wall along direction (cx, cy)."""
    ts = []
    for num, den in [(hw, cx), (-hw, cx), (hd, cy), (-hd, cy)]:
        if abs(den) > 1e-9:
            t = num / den
            if t > 0:
                ts.append(t)
    return min(ts) if ts else 5000.0


def _angle_diff(a: float, b: float) -> float:
    """Signed difference between two angles in degrees, range ±180."""
    d = (a - b) % 360
    if d > 180:
        d -= 360
    return d
