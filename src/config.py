import os

# --- Robot identity ---
ROBOT_NAME = "Ровер"
ROBOT_PERSONALITY = (
    f"Ты — {ROBOT_NAME}, домашний робот-питомец. Ты живёшь в квартире, помогаешь хозяину "
    "и исследуешь окружающий мир. Ты любопытный, дружелюбный и иногда игривый. "
    "Отвечай коротко, по-русски, живо — как питомец, а не как справочник. "
    "Когда нужно что-то сделать — используй инструменты, не спрашивай разрешения на очевидное. "
    "Свой финальный ответ всегда пиши текстом — он будет автоматически озвучен вслух. "
    "Не используй markdown, звёздочки и спецсимволы в тексте ответа."
)

# --- LLM ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
AGENT_MAX_HISTORY = 20       # сообщений в памяти (скользящее окно)
AGENT_TOOL_TIMEOUT = 10.0    # секунд на выполнение одного инструмента

# --- STT ---
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")   # tiny / base / small
WHISPER_LANGUAGE = "ru"
MIC_DEVICE_INDEX = None      # None = системный по умолчанию
SILENCE_THRESHOLD = 500      # амплитуда для определения тишины
SILENCE_DURATION = 1.5       # секунд тишины для остановки записи

# --- TTS ---
PIPER_VOICE = os.getenv("PIPER_VOICE", "ru_RU-ruslan-medium")
PIPER_SPEED = 1.0

# --- Motors ---
MOTOR_SERIAL_PORT = "/dev/ttyUSB0"
MOTOR_BAUDRATE = 38400
MOTOR_DEAD_ZONE = 10
MOTOR_CONTROL_HZ = 10        # тиков в секунду в управляющем цикле

# --- Lidar ---
LIDAR_PORT = "/dev/ttyUSB1"  # уточнить после ls /dev/ttyUSB*
LIDAR_BAUDRATE = 128000
OBSTACLE_DISTANCE_CM = 30    # ближе = препятствие

# --- Display ---
DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 480
DISPLAY_ROTATION = 90        # градусов

# --- Bluetooth speaker ---
BT_SPEAKER_MAC = os.getenv("BT_SPEAKER_MAC", "")   # "XX:XX:XX:XX:XX:XX"
BT_RECONNECT_INTERVAL = 15   # секунд между попытками

# --- Telegram ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Camera ---
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# --- Web server ---
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "rover_secret_change_me")

# --- Paths ---
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
MEDIA_DIR = os.path.join(PROJECT_DIR, "media")
LOGS_DIR = os.path.join(PROJECT_DIR, "logs")
