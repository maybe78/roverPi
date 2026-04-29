import logging
import time

logger = logging.getLogger("mock.motors")

_ARROWS = {
    (1, 1):   "⬆ forward",
    (-1, -1): "⬇ backward",
    (1, -1):  "↩ turn right",
    (-1, 1):  "↪ turn left",
    (0, 0):   "■ stop",
}


def _sign(v):
    if v > 5:  return 1
    if v < -5: return -1
    return 0


class MockMotors:
    available = True

    def __init__(self):
        self._last_desc = None
        logger.info("MockMotors ready")

    def set_speed(self, left: int, right: int) -> None:
        arrow = _ARROWS.get((_sign(left), _sign(right)), "↔ mixed")
        desc = f"{arrow}  L={left:+4d}  R={right:+4d}"
        if desc != self._last_desc:          # only log on change
            logger.info(f"Motors  {desc}")
            self._last_desc = desc

    def stop_all(self) -> None:
        if self._last_desc != "■ stop":
            logger.info("Motors  ■ stop")
            self._last_desc = "■ stop"

    def get_motor_current(self, motor_id: int):
        return 0.0
