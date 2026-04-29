"""
Thin wrapper around qik.py that adds graceful degradation.
If the serial port is unavailable, all calls are no-ops with a warning.
"""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logger = logging.getLogger("rover.motors")


class Motors:
    def __init__(self):
        self._ctrl = None
        try:
            from qik import MotorController
            self._ctrl = MotorController()
            logger.info("Motor controller initialised")
        except Exception as e:
            logger.error(f"Motor controller unavailable: {e}")

    @property
    def available(self) -> bool:
        return self._ctrl is not None

    def set_speed(self, left: int, right: int) -> None:
        if self._ctrl:
            self._ctrl.set_speed(left, right)

    def stop_all(self) -> None:
        if self._ctrl:
            self._ctrl.stop_all()

    def get_motor_current(self, motor_id: int):
        if self._ctrl:
            return self._ctrl.get_motor_current(motor_id)
        return None
