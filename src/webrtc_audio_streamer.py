# webrtc_audio_streamer.py

import asyncio
import logging
import uuid
from typing import Dict, Optional
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import threading
import time
import pygame

logger = logging.getLogger('rover.audio')

class WebRTCAudioReceiver:
    """
    Принимает аудио с браузера через WebRTC и воспроизводит его на Raspberry Pi.
    """
    def __init__(self):
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.is_receiving = False
        self.current_audio_track = None
        
        # Инициализируем pygame для воспроизведения принятого аудио
        pygame.mixer.pre_init(frequency=48000, size=-16, channels=2, buffer=1024)
        pygame.mixer.init()
        
    async def create_offer_for_microphone(self) -> dict:
        """
        Создает WebRTC offer для приема аудио с микрофона браузера.
        """
        connection_id = str(uuid.uuid4())
        pc = RTCPeerConnection()
        
        self.peer_connections[connection_id] = pc
        
        # Настраиваем обработчики событий
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"[{connection_id}] WebRTC состояние: {pc.connectionState}")
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                await self._cleanup_connection(connection_id)
        
        @pc.on("track")
        async def on_track(track):
            logger.info(f"[{connection_id}] Получен аудио трек от браузера")
            if track.kind == "audio":
                self.current_audio_track = track
                self.is_receiving = True
                # Здесь мы будем обрабатывать входящий аудиопоток
                asyncio.create_task(self._handle_incoming_audio(track))
        
        # Добавляем transceiver для приема аудио
        pc.addTransceiver("audio", direction="recvonly")
        
        # Создаем offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        return {
            "connection_id": connection_id,
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
    
    async def handle_answer(self, connection_id: str, answer_data: dict) -> bool:
        """
        Обрабатывает WebRTC answer от браузера.
        """
        if connection_id not in self.peer_connections:
            logger.error(f"Connection {connection_id} не найден")
            return False
        
        pc = self.peer_connections[connection_id]
        answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
        
        try:
            await pc.setRemoteDescription(answer)
            logger.info(f"[{connection_id}] WebRTC соединение для микрофона установлено")
            return True
        except Exception as e:
            logger.error(f"[{connection_id}] Ошибка установки answer: {e}")
            await self._cleanup_connection(connection_id)
            return False
    
    async def _handle_incoming_audio(self, track: MediaStreamTrack):
        """
        Обрабатывает входящий аудиопоток с микрофона браузера.
        """
        logger.info("Начинаем обработку аудио с микрофона браузера")
        
        try:
            while True:
                # Получаем аудио-фрейм
                frame = await track.recv()
                
                # Преобразуем аудио-фрейм в формат, подходящий для pygame
                # Здесь может потребоваться дополнительная обработка
                audio_data = frame.to_ndarray()
                
                # Воспроизводим через pygame или другой аудио-движок
                # Это упрощенный пример - в реальности нужна буферизация
                self._play_audio_data(audio_data)
                
        except Exception as e:
            logger.error(f"Ошибка обработки входящего аудио: {e}")
        finally:
            self.is_receiving = False
            logger.info("Обработка аудио с микрофона завершена")
    
    def _play_audio_data(self, audio_data):
        """
        Воспроизводит аудио-данные через динамики Raspberry Pi.
        """
        # Упрощенная реализация - в реальности нужна буферизация и конвертация
        # Возможно, лучше использовать PyAudio или другую библиотеку
        pass
    
    async def stop_microphone_stream(self, connection_id: str = None):
        """
        Останавливает прием аудио с микрофона.
        """
        if connection_id:
            await self._cleanup_connection(connection_id)
        else:
            connection_ids = list(self.peer_connections.keys())
            for conn_id in connection_ids:
                await self._cleanup_connection(conn_id)
            
            self.is_receiving = False
            self.current_audio_track = None
            logger.info("Прием аудио с микрофона остановлен")
    
    async def _cleanup_connection(self, connection_id: str):
        """
        Очищает ресурсы конкретного соединения.
        """
        if connection_id in self.peer_connections:
            pc = self.peer_connections[connection_id]
            await pc.close()
            del self.peer_connections[connection_id]
            logger.info(f"[{connection_id}] Соединение закрыто и удалено")
    
    def get_status(self) -> dict:
        """
        Возвращает статус приемника.
        """
        return {
            "is_receiving": self.is_receiving,
            "active_connections": len(self.peer_connections),
            "connection_ids": list(self.peer_connections.keys())
        }
    
    async def cleanup_all(self):
        """
        Полная очистка всех ресурсов.
        """
        await self.stop_microphone_stream()
        logger.info("WebRTCAudioReceiver полностью очищен")
