"""
RoverPi — entry point.

Run normally:   python main.py
Run mock mode:  MOCK=1 python main.py   (or on non-Linux automatically)
"""

import logging
import os
import sys
import signal
import threading
from time import sleep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from factory import create_all, IS_MOCK

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rover.main")

shutdown_event = threading.Event()


def main():
    logger.info(f"=== RoverPi starting {'[MOCK]' if IS_MOCK else '[HARDWARE]'} ===")
    os.makedirs(config.LOGS_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Build all components via factory
    # ------------------------------------------------------------------
    c = create_all()

    c.lidar.start()          # start AFTER factory so Whisper loads without GIL contention
    c.display.start()
    c.display.set_state("idle")
    c.bt_speaker.start()

    # ------------------------------------------------------------------
    # Wire STT → Agent
    # ------------------------------------------------------------------
    def on_speech(text: str):
        logger.info(f"Voice input: {text}")
        c.display.set_state("listening")
        c.agent.submit(text)

    c.stt.on_transcript(on_speech)
    c.stt.start()
    c.agent.start()

    # ------------------------------------------------------------------
    # Telegram: receive text commands, reply with TTS + text
    # ------------------------------------------------------------------
    if c.telegram:
        def on_telegram_message(text: str):
            logger.info(f"Telegram input: {text}")
            c.display.set_state("listening")
            c.agent.submit(text)

        c.telegram.start_polling(on_telegram_message)

    # Greet on startup (ollama already ready from start_all.sh)
    threading.Timer(
        1.0,
        lambda: c.agent.submit(
            "Ты только что включился. Поприветствуй хозяина одной короткой фразой."
        ),
    ).start()

    # ------------------------------------------------------------------
    # Start pi-webrtc camera after lidar is up (avoid USB contention at boot)
    # ------------------------------------------------------------------
    if not IS_MOCK:
        def start_webrtc():
            import subprocess
            # Wait until lidar has data or 60s timeout
            for _ in range(60):
                if c.lidar.available:
                    break
                sleep(1)
            webrtc_cmd = [
                "/home/volodya/pi-webrtc",
                "--camera=v4l2:0", "--v4l2-format=h264",
                "--fps=15", "--width=640", "--height=480",
                "--use-whep", "--http-port=8080",
                "--uid=rover-camera", "--no-audio", "--hw-accel",
            ]
            log_path = os.path.join(config.LOGS_DIR, "pi-webrtc.log")
            with open(log_path, "a") as lf:
                subprocess.Popen(webrtc_cmd, stdout=lf, stderr=lf)
            logger.info("pi-webrtc started")

        threading.Thread(target=start_webrtc, daemon=True, name="WebRTCThread").start()

    # ------------------------------------------------------------------
    # Radar feed loop — pushes lidar scan to display at ~10 Hz
    # ------------------------------------------------------------------
    def radar_loop():
        while not shutdown_event.is_set():
            try:
                if hasattr(c.lidar, "get_full_scan"):
                    scan = c.lidar.get_full_scan()
                    c.display.update_radar(scan)
            except Exception as e:
                logger.debug(f"Radar loop error: {e}")
            sleep(0.1)

    threading.Thread(
        target=radar_loop, daemon=True, name="RadarThread"
    ).start()

    # ------------------------------------------------------------------
    # Motor control loop  (gamepad > web)
    # ------------------------------------------------------------------
    pad = None
    if not IS_MOCK:
        try:
            import dualshock4
            pad = dualshock4.DualShock(config.MOTOR_DEAD_ZONE)
        except Exception as e:
            logger.warning(f"Gamepad unavailable: {e}")

    def motor_loop():
        import utils
        try:
            from evdev._ecodes import ABS_X, ABS_Y
        except ImportError:
            ABS_X = ABS_Y = None

        while not shutdown_event.is_set():
            try:
                if pad and ABS_X and pad.is_connected():
                    keys = pad.read_events()
                    if ABS_X in keys and ABS_Y in keys:
                        ls, rs = utils.joystick_to_diff_control(
                            keys[ABS_X], keys[ABS_Y], config.MOTOR_DEAD_ZONE
                        )
                    else:
                        ls, rs = 0, 0
                    c.motors.set_speed(ls, rs)
                else:
                    web_ls, web_rs = c.web_commands.get_speed()
                    if web_ls is not None:
                        c.motors.set_speed(web_ls, web_rs)
                    else:
                        c.motors.stop_all()

                if pad and not pad.is_connected():
                    pad.connect()

            except Exception as e:
                logger.error(f"Motor loop error: {e}")

            sleep(1.0 / config.MOTOR_CONTROL_HZ)

        c.motors.stop_all()

    threading.Thread(
        target=motor_loop, daemon=True, name="MotorThread"
    ).start()

    # ------------------------------------------------------------------
    # Web server
    # ------------------------------------------------------------------
    from flask import Flask, render_template
    from flask_socketio import SocketIO
    import utils

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = config.WEB_SECRET_KEY
    app.audio_player = c.audio_player
    socketio = SocketIO(app, async_mode="threading",
                        engineio_logger=False, socketio_logger=False)

    @app.route("/")
    def index():
        return render_template("index.html")

    @socketio.on("control")
    def handle_control(data):
        lx = float(data.get("lx", 0.0))
        ly = float(data.get("ly", 0.0))
        ls, rs = utils.joystick_to_diff_control(
            int(lx * 127), int(ly * 127), config.MOTOR_DEAD_ZONE
        )
        c.web_commands.set_speed(ls, rs)

    @socketio.on("voice_command")
    def handle_voice_command(data):
        text = data.get("text", "").strip()
        if text:
            c.agent.submit(text)

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------
    def shutdown(sig=None, frame=None):
        logger.info("Shutting down...")
        shutdown_event.set()
        c.agent.stop()
        c.stt.stop()
        if c.telegram:
            c.telegram.stop_polling()
        c.bt_speaker.stop()
        c.lidar.stop()
        c.display.stop()
        c.motors.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info(f"Web UI → http://{config.WEB_HOST}:{config.WEB_PORT}")

    # ------------------------------------------------------------------
    # macOS: pygame MUST run on the main thread (Cocoa restriction).
    # In that case Flask runs in a background thread instead.
    # On Linux (Pi): Flask is on main thread, pygame in background thread.
    # ------------------------------------------------------------------
    if c.display.needs_main_thread:
        flask_thread = threading.Thread(
            target=lambda: socketio.run(
                app, host=config.WEB_HOST, port=config.WEB_PORT,
                allow_unsafe_werkzeug=True
            ),
            daemon=True,
            name="FlaskThread",
        )
        flask_thread.start()
        try:
            c.display.run()          # blocks main thread — this is correct on macOS
        except (KeyboardInterrupt, SystemExit):
            shutdown()
    else:
        c.display.start()            # background thread on Pi
        try:
            socketio.run(app, host=config.WEB_HOST, port=config.WEB_PORT,
                         allow_unsafe_werkzeug=True)
        except (KeyboardInterrupt, SystemExit):
            shutdown()


if __name__ == "__main__":
    main()
