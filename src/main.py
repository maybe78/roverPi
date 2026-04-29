"""
RoverPi — main entry point.

Startup sequence:
  1. Load config
  2. Init hardware (motors, lidar, display) — failures are non-fatal
  3. Init audio (BT speaker daemon, TTS, STT)
  4. Init services (Telegram)
  5. Build agent tool registry
  6. Start agent background thread
  7. Wire STT → agent
  8. Start web server (Flask/Socket.IO) in main thread
  9. Start motor control loop thread (gamepad > agent > web priority)
"""

import logging
import os
import sys
import signal
import threading
from time import sleep

# Make src/ importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from web_commands import WebCommands

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rover.main")

shutdown_event = threading.Event()


def main():
    logger.info("=== RoverPi starting ===")
    os.makedirs(config.LOGS_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Hardware
    # ------------------------------------------------------------------
    from hardware.motors import Motors
    from hardware.lidar import Lidar
    from hardware.display import FaceDisplay

    motors = Motors()
    lidar = Lidar(port=config.LIDAR_PORT, baudrate=config.LIDAR_BAUDRATE)
    display = FaceDisplay(rotation=config.DISPLAY_ROTATION)
    display.start()
    display.set_state("idle")

    # ------------------------------------------------------------------
    # 2. Audio
    # ------------------------------------------------------------------
    from audio.bluetooth import BluetoothSpeaker
    from audio.tts import TTS
    from audio.stt import STT
    from audio.player import AudioPlayer

    bt_speaker = BluetoothSpeaker(
        mac=config.BT_SPEAKER_MAC,
        reconnect_interval=config.BT_RECONNECT_INTERVAL,
    )
    bt_speaker.start()

    tts = TTS(voice=config.PIPER_VOICE, speed=config.PIPER_SPEED)
    stt = STT(
        model_size=config.WHISPER_MODEL,
        language=config.WHISPER_LANGUAGE,
        device_index=config.MIC_DEVICE_INDEX,
    )
    audio_player = AudioPlayer()

    # ------------------------------------------------------------------
    # 3. Services
    # ------------------------------------------------------------------
    telegram = None
    if config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
        from services.telegram import TelegramBot
        telegram = TelegramBot(
            bot_token=config.TELEGRAM_TOKEN,
            default_chat_id=config.TELEGRAM_CHAT_ID,
        )
        logger.info("Telegram bot initialised")
    else:
        logger.warning("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID not set — Telegram disabled")

    # ------------------------------------------------------------------
    # 4. Agent
    # ------------------------------------------------------------------
    from agent.tools import build_registry
    from agent.agent import RoverAgent

    registry = build_registry(
        motors=motors,
        lidar=lidar,
        display=display,
        tts=tts,
        camera=None,      # object detector — add later
        telegram=telegram,
    )

    agent = RoverAgent(tool_registry=registry, tts=tts, display=display)

    # Wire STT → agent
    def on_speech(text: str):
        logger.info(f"Voice input: {text}")
        display.set_state("listening")
        agent.submit(text)

    stt.on_transcript(on_speech)
    stt.start()
    agent.start()

    # Greet on startup
    threading.Timer(
        3.0,
        lambda: agent.submit("Робот только что включился. Поприветствуй хозяина коротко.")
    ).start()

    # ------------------------------------------------------------------
    # 5. Motor control loop
    # ------------------------------------------------------------------
    from evdev._ecodes import ABS_X, ABS_Y
    import dualshock4
    import utils

    web_commands = WebCommands()

    try:
        pad = dualshock4.DualShock(config.MOTOR_DEAD_ZONE)
        logger.info("Gamepad initialised")
    except Exception as e:
        logger.warning(f"Gamepad unavailable: {e}")
        pad = None

    def motor_loop():
        while not shutdown_event.is_set():
            try:
                if pad and pad.is_connected():
                    keys = pad.read_events()
                    if ABS_X in keys and ABS_Y in keys:
                        ls, rs = utils.joystick_to_diff_control(
                            keys[ABS_X], keys[ABS_Y], config.MOTOR_DEAD_ZONE
                        )
                    else:
                        ls, rs = 0, 0
                    motors.set_speed(ls, rs)
                else:
                    web_ls, web_rs = web_commands.get_speed()
                    if web_ls is not None:
                        motors.set_speed(web_ls, web_rs)
                    else:
                        motors.stop_all()

                if pad and not pad.is_connected():
                    pad.connect()

            except Exception as e:
                logger.error(f"Motor loop error: {e}")

            sleep(1.0 / config.MOTOR_CONTROL_HZ)

        motors.stop_all()

    motor_thread = threading.Thread(
        target=motor_loop, daemon=True, name="MotorThread"
    )
    motor_thread.start()

    # ------------------------------------------------------------------
    # 6. Web server
    # ------------------------------------------------------------------
    from flask import Flask, render_template
    from flask_socketio import SocketIO
    import utils as math_utils

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = config.WEB_SECRET_KEY
    app.audio_player = audio_player
    app.tts = tts
    socketio = SocketIO(app, async_mode="threading",
                        engineio_logger=False, socketio_logger=False)

    @app.route("/")
    def index():
        return render_template("index.html")

    @socketio.on("control")
    def handle_control(data):
        lx = float(data.get("lx", 0.0))
        ly = float(data.get("ly", 0.0))
        ls, rs = math_utils.joystick_to_diff_control(
            int(lx * 127), int(ly * 127), config.MOTOR_DEAD_ZONE
        )
        web_commands.set_speed(ls, rs)

    @socketio.on("voice_command")
    def handle_voice_command(data):
        """Accept typed/voice commands from web UI."""
        text = data.get("text", "").strip()
        if text:
            agent.submit(text)

    # ------------------------------------------------------------------
    # 7. Graceful shutdown
    # ------------------------------------------------------------------
    def shutdown(sig=None, frame=None):
        logger.info("Shutdown signal received")
        shutdown_event.set()
        agent.stop()
        stt.stop()
        bt_speaker.stop()
        lidar.stop()
        display.stop()
        motors.stop_all()
        logger.info("Shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info(f"Web server on http://{config.WEB_HOST}:{config.WEB_PORT}")
    try:
        socketio.run(app, host=config.WEB_HOST, port=config.WEB_PORT,
                     allow_unsafe_werkzeug=True)
    except (KeyboardInterrupt, SystemExit):
        shutdown()


if __name__ == "__main__":
    main()
