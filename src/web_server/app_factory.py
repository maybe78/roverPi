from flask import Flask
from flask_socketio import SocketIO
import pygame

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

    # Передаем зависимости в контекст приложения
    app.web_commands = web_commands
    app.audio_player = audio_player
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
    """
    import logging
    from threading import Lock
    import base64
    import tempfile
    import subprocess
    import os
    
    logger = logging.getLogger('rover')
    thread_count_lock = Lock()
    active_threads = 0
    
    @socketio.on('control')
    def handle_control(data):
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

            import utils
            ls, rs = utils.joystick_to_diff_control(scaled_x, scaled_y, 10)
            web_commands.set_speed(ls, rs)
            logger.debug(f"Команда с веба: L={ls}, R={rs}")

        except (ValueError, TypeError) as e:
            logger.error(f"Некорректные данные от веб-клиента: {e}")
        finally:
            with thread_count_lock:
                active_threads -= 1

    @socketio.on('connect')
    def handle_connect():
        logger.info("Клиент подключился к веб-интерфейсу управления.")
    
    # обработчики для WebSocket аудио
    @socketio.on('start_microphone')
    def handle_start_microphone():
        """Начинает прослушивание аудио с микрофона."""
        logger.info("Клиент начал передачу аудио с микрофона через WebSocket")
        socketio.emit('microphone_status', {'status': 'started'})
    
    @socketio.on('audio_data')
    def handle_audio_data(data):
        """Правильная обработка разных аудио форматов."""
        try:
            audio_data = base64.b64decode(data['audio'])
            data_size = len(audio_data)
            
            logger.debug(f"Получены аудио данные: {data_size} байт")
            
            # Определяем формат по заголовку
            if audio_data[:4] == b'OggS':
                suffix = '.ogg'
            elif audio_data[:4] == b'RIFF':
                suffix = '.wav'  
            elif audio_data[:4] == b'\x1a\x45\xdf\xa3':
                suffix = '.webm'
            else:
                suffix = '.webm'  # По умолчанию
                
            logger.debug(f"Определен формат: {suffix}")
            
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as input_file, \
                tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
                
                input_file.write(audio_data)
                input_file.flush()
                
                try:
                    # Конвертируем в WAV для надежного воспроизведения
                    result = subprocess.run([
                        'ffmpeg', '-hide_banner', '-loglevel', 'error',
                        '-i', input_file.name,
                        '-f', 'wav',
                        '-acodec', 'pcm_s16le',  # 16-bit PCM
                        '-ar', '22050',          # Понизим частоту для скорости
                        '-ac', '1',              # Моно
                        '-y', output_file.name
                    ], capture_output=True, timeout=3)
                    
                    if result.returncode == 0:
                        # Воспроизводим конвертированный WAV
                        subprocess.run(['aplay', '-q', output_file.name], 
                                    capture_output=True, timeout=2)
                        logger.debug(f"Успешно воспроизведен {suffix} -> WAV")
                    else:
                        logger.debug(f"ffmpeg ошибка: {result.stderr.decode()}")
                        
                except subprocess.TimeoutExpired:
                    logger.debug("Timeout при обработке аудио")
                except Exception as e:
                    logger.debug(f"Ошибка: {e}")
                finally:
                    # Удаляем временные файлы
                    try:
                        os.unlink(input_file.name)
                        os.unlink(output_file.name)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Критическая ошибка аудио: {e}")

    @socketio.on('stop_microphone')
    def handle_stop_microphone():
        """Останавливает прослушивание аудио."""
        logger.info("Клиент остановил передачу аудио с микрофона")
        # Остановим все pygame воспроизведение
        try:
            pygame.mixer.music.stop()
        except:
            pass
        socketio.emit('microphone_status', {'status': 'stopped'})