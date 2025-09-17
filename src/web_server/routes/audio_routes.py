from flask import Blueprint, jsonify, current_app
import threading
import logging

audio_bp = Blueprint('audio', __name__)
logger = logging.getLogger('rover')

# Пути к предустановленным звукам
PRESET_SOUNDS = {
    "sound1": "media/police.mp3",  # Замените на ваши пути
    "sound2": "media/startup.mp3",
    "mic_placeholder": "media/juje.mp3"  # Используем существующий файл как заглушку
}

@audio_bp.route('/play/<sound_name>', methods=['POST'])
def play_sound(sound_name):
    """
    Проигрывает предустановленный звук.
    """
    if sound_name not in PRESET_SOUNDS:
        logger.warning(f"Запрошен неизвестный звук: {sound_name}")
        return jsonify({"status": "error", "message": "Sound not found"}), 404
    
    try:
        file_path = PRESET_SOUNDS[sound_name]
        audio_player = current_app.audio_player
        
        # Запускаем в отдельном потоке, чтобы не блокировать сервер
        def play_async():
            try:
                audio_player.play(file_path)
                logger.info(f"Запущено воспроизведение: {sound_name}")
            except Exception as e:
                logger.error(f"Ошибка воспроизведения {sound_name}: {e}")
        
        threading.Thread(target=play_async, daemon=True, name=f"AudioPlay-{sound_name}").start()
        
        return jsonify({
            "status": "success", 
            "message": f"Playing {sound_name}",
            "file": file_path
        })
    
    except Exception as e:
        logger.error(f"Ошибка при запуске воспроизведения {sound_name}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@audio_bp.route('/start_microphone', methods=['POST'])
def start_microphone():
    """
    Запуск записи с микрофона (пока заглушка).
    """
    try:
        # Пока используем заглушку - проигрываем файл police.mp3
        file_path = PRESET_SOUNDS["mic_placeholder"]
        audio_player = current_app.audio_player
        
        def play_mic_placeholder():
            try:
                audio_player.play(file_path)
                logger.info("Запущена заглушка микрофона (police.mp3)")
            except Exception as e:
                logger.error(f"Ошибка заглушки микрофона: {e}")
        
        threading.Thread(target=play_mic_placeholder, daemon=True, name="AudioMic-Placeholder").start()
        
        return jsonify({
            "status": "success", 
            "message": "Microphone started (placeholder mode)",
            "file": file_path
        })
    
    except Exception as e:
        logger.error(f"Ошибка запуска микрофона: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@audio_bp.route('/stop', methods=['POST'])
def stop_audio():
    """
    Остановка всех аудио процессов.
    """
    try:
        audio_player = current_app.audio_player
        audio_player.stop()
        logger.info("Все аудио процессы остановлены")
        
        return jsonify({
            "status": "success", 
            "message": "All audio processes stopped"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при остановке аудио: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@audio_bp.route('/status', methods=['GET'])
def audio_status():
    """
    Получить статус аудио системы.
    """
    try:
        audio_player = current_app.audio_player
        is_playing = audio_player.is_playing()
        
        return jsonify({
            "status": "success",
            "is_playing": is_playing,
            "available_sounds": list(PRESET_SOUNDS.keys())
        })
    
    except Exception as e:
        logger.error(f"Ошибка получения статуса аудио: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
