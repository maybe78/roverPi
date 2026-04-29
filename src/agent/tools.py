"""
Tool registry for the rover agent.

Each tool is a plain function decorated with @tool(schema).
The registry collects them and exposes schemas to ollama + dispatches calls.
"""

import os
import time
import logging
import subprocess
import threading
from typing import Any, Callable

logger = logging.getLogger("rover.tools")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[Callable, dict]] = {}

    def register(self, func: Callable, schema: dict) -> None:
        self._tools[schema["function"]["name"]] = (func, schema)
        logger.debug(f"Tool registered: {schema['function']['name']}")

    def schemas(self) -> list[dict]:
        return [schema for _, schema in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> Any:
        if name not in self._tools:
            return f"[error] unknown tool: {name}"
        func, _ = self._tools[name]
        try:
            logger.info(f"Tool call: {name}({arguments})")
            result = func(**arguments)
            logger.info(f"Tool result: {name} → {str(result)[:120]}")
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            return f"[error] {name}: {e}"


# ---------------------------------------------------------------------------
# Builder — creates a registry bound to all robot subsystems
# ---------------------------------------------------------------------------

def build_registry(
    motors=None,
    lidar=None,
    display=None,
    tts=None,
    camera=None,
    telegram=None,
) -> ToolRegistry:
    """
    Bind hardware references into closures and register all tools.
    Any hardware that is None gets a stub that returns a polite error.
    """
    reg = ToolRegistry()

    # --- helpers ---
    def _require(hw, name):
        if hw is None:
            return f"[{name} недоступен]"
        return None

    # -----------------------------------------------------------------------
    # Movement
    # -----------------------------------------------------------------------

    def move(direction: str, speed: int = 60, duration: float = 1.0) -> str:
        err = _require(motors, "моторы")
        if err:
            return err
        direction = direction.lower()
        spd = max(0, min(int(speed), 127))
        dur = max(0.1, min(float(duration), 10.0))

        if direction == "forward":
            motors.set_speed(spd, spd)
        elif direction == "backward":
            motors.set_speed(-spd, -spd)
        elif direction == "left":
            motors.set_speed(-spd, spd)
        elif direction == "right":
            motors.set_speed(spd, -spd)
        else:
            return f"[error] неизвестное направление: {direction}"

        time.sleep(dur)
        motors.stop_all()
        return f"Движение {direction} {dur}с на скорости {spd}"

    reg.register(move, {
        "type": "function",
        "function": {
            "name": "move",
            "description": "Двигать робота. Направления: forward, backward, left, right.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["forward", "backward", "left", "right"]},
                    "speed":     {"type": "integer", "description": "Скорость 1–127, по умолчанию 60"},
                    "duration":  {"type": "number",  "description": "Время движения в секундах"},
                },
                "required": ["direction"],
            },
        },
    })

    # -----------------------------------------------------------------------

    def stop() -> str:
        err = _require(motors, "моторы")
        if err:
            return err
        motors.stop_all()
        return "Стоп."

    reg.register(stop, {
        "type": "function",
        "function": {
            "name": "stop",
            "description": "Остановить все моторы немедленно.",
            "parameters": {"type": "object", "properties": {}},
        },
    })

    # -----------------------------------------------------------------------
    # Sensing
    # -----------------------------------------------------------------------

    def scan_surroundings() -> dict:
        err = _require(lidar, "лидар")
        if err:
            return {"error": err}
        return lidar.get_nearest_by_sector()

    reg.register(scan_surroundings, {
        "type": "function",
        "function": {
            "name": "scan_surroundings",
            "description": (
                "Сканировать пространство вокруг лидаром. "
                "Возвращает расстояния (мм) по секторам: front, back, left, right."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    })

    # -----------------------------------------------------------------------

    def capture_photo() -> str:
        """Capture a frame and optionally run object detection."""
        import cv2
        from config import CAMERA_INDEX
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            return "[камера недоступна]"
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "[не удалось получить кадр]"

        # run object detection if available
        if camera is not None:
            try:
                labels = camera.detect(frame)
                if labels:
                    return "На фото: " + ", ".join(labels)
                return "Ничего особенного на фото."
            except Exception as e:
                return f"[ошибка детекции: {e}]"
        return "Фото сделано (детектор не подключён)."

    reg.register(capture_photo, {
        "type": "function",
        "function": {
            "name": "capture_photo",
            "description": "Сделать снимок с камеры и описать что на нём видно.",
            "parameters": {"type": "object", "properties": {}},
        },
    })

    # -----------------------------------------------------------------------

    def get_status() -> dict:
        import psutil
        return {
            "cpu_percent":  psutil.cpu_percent(interval=0.5),
            "ram_percent":  psutil.virtual_memory().percent,
            "ram_used_mb":  psutil.virtual_memory().used // 1024 // 1024,
            "temperature_c": _read_cpu_temp(),
            "disk_free_gb": psutil.disk_usage("/").free // 1024 // 1024 // 1024,
        }

    reg.register(get_status, {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Получить состояние системы: CPU, RAM, температура, место на диске.",
            "parameters": {"type": "object", "properties": {}},
        },
    })

    # -----------------------------------------------------------------------
    # Communication
    # -----------------------------------------------------------------------
    # NOTE: speak() is intentionally NOT a tool.
    # The agent's text response is always auto-spoken by the agent loop.
    # Having speak() as a tool caused double TTS (tool call + auto-speak).
    # -----------------------------------------------------------------------

    def send_notification(message: str, with_photo: bool = False) -> str:
        err = _require(telegram, "Telegram")
        if err:
            return err
        if with_photo:
            return str(telegram.capture_and_send_photo(caption=message))
        return str(telegram.send_text_message(message))

    reg.register(send_notification, {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Отправить уведомление хозяину в Telegram. Можно приложить фото с камеры.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message":    {"type": "string", "description": "Текст уведомления"},
                    "with_photo": {"type": "boolean", "description": "Приложить фото с камеры"},
                },
                "required": ["message"],
            },
        },
    })

    # -----------------------------------------------------------------------
    # Display
    # -----------------------------------------------------------------------

    def set_expression(emotion: str) -> str:
        known = ["idle", "listening", "thinking", "speaking",
                 "happy", "surprised", "angry", "sad"]
        if emotion not in known:
            return f"[неизвестная эмоция: {emotion}. Доступны: {known}]"
        err = _require(display, "дисплей")
        if err:
            return err
        display.set_state(emotion)
        return f"Выражение: {emotion}"

    reg.register(set_expression, {
        "type": "function",
        "function": {
            "name": "set_expression",
            "description": "Сменить выражение лица на дисплее.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion": {
                        "type": "string",
                        "enum": ["idle", "listening", "thinking", "speaking",
                                 "happy", "surprised", "angry", "sad"],
                    },
                },
                "required": ["emotion"],
            },
        },
    })

    # -----------------------------------------------------------------------
    # Self-modification
    # -----------------------------------------------------------------------

    def read_source_file(filename: str) -> str:
        from config import SRC_DIR
        path = os.path.normpath(os.path.join(SRC_DIR, filename))
        if not path.startswith(SRC_DIR):
            return "[error] выход за пределы src/ запрещён"
        if not os.path.isfile(path):
            return f"[error] файл не найден: {filename}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content

    reg.register(read_source_file, {
        "type": "function",
        "function": {
            "name": "read_source_file",
            "description": "Прочитать исходный файл робота (из папки src/).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string",
                                 "description": "Относительный путь внутри src/, например 'agent/agent.py'"},
                },
                "required": ["filename"],
            },
        },
    })

    # -----------------------------------------------------------------------

    def modify_source_file(filename: str, content: str, reason: str = "") -> str:
        from config import SRC_DIR, PROJECT_DIR
        path = os.path.normpath(os.path.join(SRC_DIR, filename))
        if not path.startswith(SRC_DIR):
            return "[error] выход за пределы src/ запрещён"

        # backup
        backup = path + ".bak"
        if os.path.isfile(path):
            import shutil
            shutil.copy2(path, backup)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        # git commit
        try:
            msg = f"robot self-modify: {filename}" + (f" — {reason}" if reason else "")
            subprocess.run(["git", "-C", PROJECT_DIR, "add", path], check=True, timeout=10)
            subprocess.run(["git", "-C", PROJECT_DIR, "commit", "-m", msg],
                           check=True, timeout=10)
        except subprocess.CalledProcessError as e:
            logger.warning(f"git commit skipped: {e}")

        return f"Файл {filename} обновлён. Бэкап: {os.path.basename(backup)}"

    reg.register(modify_source_file, {
        "type": "function",
        "function": {
            "name": "modify_source_file",
            "description": (
                "Изменить исходный файл робота. "
                "Старая версия сохраняется как .bak. Изменение фиксируется в git."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Путь внутри src/"},
                    "content":  {"type": "string", "description": "Новое содержимое файла целиком"},
                    "reason":   {"type": "string", "description": "Зачем вносится изменение"},
                },
                "required": ["filename", "content"],
            },
        },
    })

    # -----------------------------------------------------------------------

    def restart_service() -> str:
        logger.warning("Agent requested service restart")
        threading.Timer(2.0, lambda: subprocess.run(
            ["sudo", "systemctl", "restart", "rover.service"], timeout=10
        )).start()
        return "Перезапуск через 2 секунды..."

    reg.register(restart_service, {
        "type": "function",
        "function": {
            "name": "restart_service",
            "description": "Перезапустить systemd-сервис робота (применить изменения кода).",
            "parameters": {"type": "object", "properties": {}},
        },
    })

    return reg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_cpu_temp() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000, 1)
    except Exception:
        return 0.0
