# web_server/routes/audio_routes.py

from flask import Blueprint, jsonify, current_app, request
import threading
import logging
import asyncio
from functools import wraps

# СНАЧАЛА создаем Blueprint
audio_bp = Blueprint('audio', __name__)
logger = logging.getLogger('rover')

# Пути к предустановленным звукам
PRESET_SOUNDS = {
    "sound1": "media/police.mp3", 
    "sound2": "media/startup.mp3",
    "mic_placeholder": "media/juje.mp3"
}

def async_route(f):
    """
    Декоратор для выполнения async функций в Flask роутах.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(f(*args, **kwargs))
    
    return wrapper

# --- Локальное воспроизведение MP3 (существующие маршруты) ---

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

@audio_bp.route('/start_microphone', methods=['POST'])
def start_microphone():
    """
    Запуск записи с микрофона (пока заглушка для локального воспроизведения).
    """
    try:
        file_path = PRESET_SOUNDS["mic_placeholder"]
        audio_player = current_app.audio_player
        
        def play_mic_placeholder():
            try:
                audio_player.play(file_path)
                logger.info("Запущена заглушка микрофона (локально на Raspberry Pi)")
            except Exception as e:
                logger.error(f"Ошибка заглушки микрофона: {e}")
        
        threading.Thread(target=play_mic_placeholder, daemon=True, name="AudioMic-Placeholder").start()
        
        return jsonify({
            "status": "success", 
            "message": "Microphone placeholder started (local mode)",
            "file": file_path
        })
    
    except Exception as e:
        logger.error(f"Ошибка запуска микрофона: {e}")
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

# --- WebRTC маршруты для микрофона ---

@audio_bp.route('/webrtc/microphone-offer', methods=['POST'])
@async_route
async def webrtc_microphone_offer():
    """
    Создает WebRTC offer для приема аудио с микрофона браузера.
    """
    try:
        webrtc_receiver = current_app.webrtc_receiver
        offer_data = await webrtc_receiver.create_offer_for_microphone()
        
        logger.info("WebRTC offer для микрофона создан")
        return jsonify({
            "status": "success",
            "connection_id": offer_data["connection_id"],
            "sdp": offer_data["sdp"],
            "type": offer_data["type"]
        })
    
    except Exception as e:
        logger.error(f"Ошибка создания WebRTC offer для микрофона: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@audio_bp.route('/webrtc/microphone-answer', methods=['POST'])
@async_route
async def webrtc_microphone_answer():
    """
    Обрабатывает WebRTC answer для микрофона.
    """
    try:
        data = request.get_json()
        if not data or not all(key in data for key in ['connection_id', 'sdp', 'type']):
            return jsonify({
                "status": "error", 
                "message": "Missing required parameters (connection_id, sdp, type)"
            }), 400
        
        webrtc_receiver = current_app.webrtc_receiver
        success = await webrtc_receiver.handle_answer(
            data['connection_id'], 
            {"sdp": data['sdp'], "type": data['type']}
        )
        
        if success:
            logger.info(f"WebRTC соединение для микрофона установлено: {data['connection_id']}")
            return jsonify({"status": "success", "message": "Microphone stream connected"})
        else:
            return jsonify({"status": "error", "message": "Failed to connect microphone"}), 500
            
    except Exception as e:
        logger.error(f"Ошибка обработки WebRTC answer для микрофона: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@audio_bp.route('/webrtc/microphone-stop', methods=['POST'])
@async_route
async def webrtc_microphone_stop():
    """
    Останавливает прием аудио с микрофона.
    """
    try:
        webrtc_receiver = current_app.webrtc_receiver
        await webrtc_receiver.stop_microphone_stream()
        
        logger.info("Прием аудио с микрофона остановлен")
        return jsonify({"status": "success", "message": "Microphone stream stopped"})
    
    except Exception as e:
        logger.error(f"Ошибка остановки микрофона: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Общие информационные маршруты ---

@audio_bp.route('/status', methods=['GET'])
def audio_status():
    """
    Получить общий статус всех аудио систем.
    """
    try:
        audio_player = current_app.audio_player
        webrtc_receiver = current_app.webrtc_receiver
        
        pygame_status = {
            "is_playing": audio_player.is_playing()
        }
        
        webrtc_status = webrtc_receiver.get_status()
        
        return jsonify({
            "status": "success",
            "pygame": pygame_status,
            "webrtc": webrtc_status,
            "available_sounds": list(PRESET_SOUNDS.keys())
        })
    
    except Exception as e:
        logger.error(f"Ошибка получения статуса аудио: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
