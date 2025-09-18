# web_server/routes/audio_routes.py

from flask import Blueprint, jsonify, current_app, request
import threading
import logging
import subprocess  
from functools import wraps

# Создаем Blueprint
audio_bp = Blueprint('audio', __name__)
logger = logging.getLogger('rover')

# Пути к предустановленным звукам
PRESET_SOUNDS = {
    "sound1": "media/police.mp3", 
    "sound2": "media/startup.mp3",
    "mic_placeholder": "media/juje.mp3"
}

# --- Локальное воспроизведение MP3 ---

@audio_bp.route('/play/<sound_name>', methods=['POST'])
def play_sound(sound_name):
    """
    Проигрывает предустановленный звук ЛОКАЛЬНО через pygame на Raspberry Pi.
    """
    if sound_name not in PRESET_SOUNDS:
        logger.warning(f"Запрошен неизвестный звук: {sound_name}")
        return jsonify({"status": "error", "message": "Sound not found"}), 404
    
    try:
        file_path = PRESET_SOUNDS[sound_name]
        audio_player = current_app.audio_player
        
        def play_async():
            try:
                audio_player.play(file_path)
                logger.info(f"Локальное воспроизведение на Raspberry Pi: {sound_name}")
            except Exception as e:
                logger.error(f"Ошибка воспроизведения {sound_name}: {e}")
        
        threading.Thread(target=play_async, daemon=True, name=f"AudioPlay-{sound_name}").start()
        
        return jsonify({
            "status": "success", 
            "message": f"Playing {sound_name} on Raspberry Pi",
            "file": file_path
        })
    
    except Exception as e:
        logger.error(f"Ошибка при запуске воспроизведения {sound_name}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@audio_bp.route('/stop', methods=['POST'])
def stop_audio():
    """
    Остановка локального воспроизведения на Raspberry Pi.
    """
    try:
        audio_player = current_app.audio_player
        audio_player.stop()
        logger.info("Локальное воспроизведение на Raspberry Pi остановлено")
        
        return jsonify({
            "status": "success", 
            "message": "Local playback stopped"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при остановке аудио: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Text-to-Speech ---

@audio_bp.route('/speak', methods=['POST'])
def speak_text():
    """
    Озвучивает текст через TTS на Raspberry Pi.
    """
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"status": "error", "message": "Text is required"}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({"status": "error", "message": "Text cannot be empty"}), 400
        
        # Ограничиваем длину текста
        if len(text) > 500:
            text = text[:500] + "..."
        
        # Получаем audio_player в основном потоке
        audio_player = current_app.audio_player
        
        def speak_async():
            try:
                # Останавливаем текущее воспроизведение
                if audio_player.is_playing():
                    audio_player.stop()
                
                # Озвучиваем через RHVoice (или замените на другой TTS)
                subprocess.run([
                    'bash', '-c', f'echo "{text}" | RHVoice-test -p alexander'
                ], check=True)
                                
                logger.info(f"TTS озвучил: '{text[:50]}...'")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Ошибка TTS: {e}")
            except Exception as e:
                logger.error(f"Ошибка async TTS: {e}")
        
        # Запускаем в отдельном потоке
        threading.Thread(target=speak_async, daemon=True, name="TTS-Thread").start()
        
        return jsonify({
            "status": "success", 
            "message": f"Speaking: {text[:50]}{'...' if len(text) > 50 else ''}",
            "text_length": len(text)
        })
    
    except Exception as e:
        logger.error(f"Ошибка TTS endpoint: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Статус ---

@audio_bp.route('/status', methods=['GET'])
def audio_status():
    """
    Получить статус аудио системы.
    """
    try:
        audio_player = current_app.audio_player
        
        pygame_status = {
            "is_playing": audio_player.is_playing()
        }
        
        return jsonify({
            "status": "success",
            "pygame": pygame_status,
            "available_sounds": list(PRESET_SOUNDS.keys())
        })
    
    except Exception as e:
        logger.error(f"Ошибка получения статуса аудио: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
