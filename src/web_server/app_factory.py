from flask import Flask
from flask_socketio import SocketIO
from webrtc_audio_streamer import WebRTCAudioReceiver  # <-- Исправлен импорт


def create_app(web_commands, audio_player, config=None):
    """
    Фабрика для создания Flask приложения с необходимыми компонентами.
    """
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = config.get('secret_key', 'a_very_secret_key_for_rover') if config else 'a_very_secret_key_for_rover'
    
    # Создаем SocketIO экземпляр
    socketio = SocketIO(
        app, 
        async_mode='threading',
        engineio_logger=False,
        socketio_logger=False,
    )
    
    # Создаем WebRTC приемник для микрофона
    webrtc_receiver = WebRTCAudioReceiver()  # <-- Исправлено название
    
    # Передаем зависимости в контекст приложения
    app.web_commands = web_commands
    app.audio_player = audio_player
    app.webrtc_receiver = webrtc_receiver  # <-- Исправлено название
    app.socketio = socketio
    
    # Регистрируем blueprints
    from .routes.main_routes import main_bp
    from .routes.audio_routes import audio_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(audio_bp, url_prefix='/audio')
    
    # Регистрируем SocketIO обработчики
    register_socketio_handlers(socketio, web_commands)
    
    return app, socketio


def register_socketio_handlers(socketio, web_commands):
    """
    Регистрирует обработчики SocketIO событий.
    Это сохраняет вашу текущую логику управления моторами.
    """
    import logging
    from threading import Lock
    
    logger = logging.getLogger('rover')
    thread_count_lock = Lock()
    active_threads = 0
    
    @socketio.on('control')
    def handle_control(data):
        """
        ВАЖНО: Сохраняем точно вашу логику управления моторами!
        """
        nonlocal active_threads
        with thread_count_lock:
            if active_threads > 20:
                logger.warning(f"Слишком много команд управления, сбрасываем. Потоков: {active_threads}")
                return
            active_threads += 1
        
        try:
            lx = float(data.get('lx', 0.0))
            ly = float(data.get('ly', 0.0))

            scaled_x = int(lx * 127)
            scaled_y = int(ly * 127)

            # Импортируем utils здесь, чтобы избежать циклических импортов
            import utils
            ls, rs = utils.joystick_to_diff_control(scaled_x, scaled_y, 10)  # dead_zone = 10
            web_commands.set_speed(ls, rs)
            logger.debug(f"Команда с веба: L={ls}, R={rs}")

        except (ValueError, TypeError) as e:
            logger.error(f"Некорректные данные от веб-клиента: {e}")
        finally:
            with thread_count_lock:
                active_threads -= 1

    @socketio.on('connect')
    def handle_connect():
        """Обработчик подключения нового клиента."""
        logger.info("Клиент подключился к веб-интерфейсу управления.")
