import logging
import random
import threading
import time

logger = logging.getLogger("mock.lidar")


class MockLidar:
    """
    Returns randomised sector distances.
    Call set_obstacle(sector, distance_mm) to simulate a wall.
    """
    available = True

    _SECTORS = ("front", "right", "back", "left")

    def __init__(self):
        self._obstacles: dict[str, int] = {}
        logger.info("MockLidar ready (randomised distances)")

    def set_obstacle(self, sector: str, distance_mm: int) -> None:
        """Simulate a wall in a given sector (test helper)."""
        self._obstacles[sector] = distance_mm
        logger.debug(f"Obstacle set: {sector} = {distance_mm} mm")

    def clear_obstacles(self) -> None:
        self._obstacles.clear()

    def get_nearest_by_sector(self) -> dict:
        result = {}
        for s in self._SECTORS:
            if s in self._obstacles:
                result[s] = self._obstacles[s]
            else:
                result[s] = random.randint(400, 3000)
        logger.info(f"Lidar scan: {result}")
        return result

    def get_nearest_distance(self) -> int:
        return min(self.get_nearest_by_sector().values())

    def is_obstacle_ahead(self, threshold_mm: int = 300) -> bool:
        return self.get_nearest_by_sector()["front"] < threshold_mm

    def stop(self) -> None:
        pass
