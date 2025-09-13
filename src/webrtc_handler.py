import asyncio
import logging
import cv2
import threading
from aiortc import RTCPeerConnection, MediaStreamTrack, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import json

logger = logging.getLogger('webrtc')

class VideoTransformTrack(MediaStreamTrack):
    """
    Кастомный видео трек, который получает видео с камеры
    """
    kind = "video"

    def __init__(self):
        super().__init__()
        # Создаем MediaPlayer для /dev/video0
        try:
            # Пробуем разные варианты настроек камеры
            camera_options = {
                'video_size': '640x480',
                'framerate': '15',  # Уменьшаем framerate для стабильности
                'pixel_format': 'yuyv422'  # Добавляем формат пикселей
            }
            
            self.player = MediaPlayer('/dev/video0', format='v4l2', options=camera_options)
            
            if self.player.video:
                self.track = self.player.video
                logger.info("Camera /dev/video0 successfully initialized")
            else:
                raise Exception("No video track from camera")
                
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            try:
                # Fallback: пробуем без дополнительных опций
                self.player = MediaPlayer('/dev/video0', format='v4l2')
                if self.player.video:
                    self.track = self.player.video
                    logger.warning("Camera initialized with basic settings")
                else:
                    raise Exception("No video track from basic camera init")
            except Exception as e2:
                logger.error(f"Camera fallback also failed: {e2}")
                # Последний fallback на тестовый источник
                self.player = MediaPlayer('testsrc=size=640x480:rate=15', format='lavfi')
                self.track = self.player.video
                logger.warning("Using test source instead of camera")

    async def recv(self):
        """
        Получает кадр с камеры и возвращает его
        """
        try:
            frame = await self.track.recv()
            
            # Конвертируем в numpy array для обработки
            img = frame.to_ndarray(format="bgr24")
            
            # Добавляем метку времени для отладки
            timestamp = f'RoverPi - {asyncio.get_event_loop().time():.1f}'
            img = cv2.putText(img, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Создаем новый VideoFrame с обработанным изображением
            new_frame = VideoFrame.from_ndarray(img, format="bgr24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base
            
            return new_frame
            
        except Exception as e:
            logger.error(f"Error in recv: {e}")
            # В случае ошибки возвращаем черный кадр с текстом ошибки
            img = cv2.zeros((480, 640, 3), dtype=cv2.uint8)
            cv2.putText(img, f'Camera Error: {str(e)[:50]}', (10, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            return frame

    def stop(self):
        """Останавливает проигрыватель"""
        if hasattr(self, 'player') and self.player:
            try:
                self.player.stop()
            except Exception as e:
                logger.error(f"Error stopping player: {e}")


class WebRTCHandler:
    """
    Класс для обработки WebRTC соединений с правильным управлением event loop
    """
    
    def __init__(self):
        self.pcs = set()  # Множество активных соединений
        self.video_track = None
        self.loop = None
        self.loop_thread = None
        self.is_running = False
        
    def start_loop(self):
        """Запускает event loop в отдельном потоке"""
        if self.is_running:
            return
            
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.is_running = True
            logger.info("WebRTC event loop started")
            try:
                self.loop.run_forever()
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
            finally:
                self.is_running = False
                
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        # Ждем пока loop будет готов
        import time
        timeout = 5.0
        start_time = time.time()
        while not self.is_running and (time.time() - start_time) < timeout:
            time.sleep(0.1)
            
        if not self.is_running:
            raise RuntimeError("Failed to start WebRTC event loop")
        
    def create_offer(self, sdp_offer):
        """
        Обрабатывает SDP offer от клиента и возвращает answer
        """
        if not self.is_running:
            self.start_loop()
            
        future = asyncio.run_coroutine_threadsafe(
            self._async_create_offer(sdp_offer), self.loop
        )
        
        try:
            return future.result(timeout=10.0)  # 10 секунд таймаут
        except Exception as e:
            logger.error(f"Error in create_offer: {e}")
            raise
        
    async def _async_create_offer(self, sdp_offer):
        """
        Асинхронная версия создания offer - ИСПРАВЛЕННАЯ
        """
        try:
            # Создаем новое peer connection
            pc = RTCPeerConnection()
            self.pcs.add(pc)
            
            # Добавляем обработчик для отключения
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state is {pc.connectionState}")
                if pc.connectionState in ["closed", "failed"]:
                    self.pcs.discard(pc)
                    if hasattr(pc, '_video_track_instance'):
                        try:
                            pc._video_track_instance.stop()
                        except:
                            pass
                    
            # Добавляем обработчик для получения треков от клиента
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track received: {track.kind}")
            
            # ИСПРАВЛЕНИЕ: Добавляем видео трек ДО установки remote description
            video_track = VideoTransformTrack()
            pc._video_track_instance = video_track  # Сохраняем ссылку для очистки
            pc.addTrack(video_track)
            logger.info("Video track added BEFORE setRemoteDescription")
            
            # Теперь устанавливаем remote description
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=sdp_offer["sdp"], 
                type=sdp_offer["type"]
            ))
            
            # Проверяем трансиверы после установки remote description
            transceivers = pc.getTransceivers()
            logger.info(f"Found {len(transceivers)} transceivers after setRemoteDescription")
            
            for i, transceiver in enumerate(transceivers):
                logger.info(f"Transceiver {i}: kind={transceiver.kind}, direction={transceiver.direction}")
                
                # Убеждаемся что направление правильное для отправки видео
                if transceiver.kind == "video":
                    # Должно быть sendonly или sendrecv для отправки видео с сервера
                    logger.info(f"Video transceiver direction: {transceiver.direction}")
                    # Если направление recvonly, устанавливаем sendrecv
                    if hasattr(transceiver, 'direction') and transceiver.direction == 'recvonly':
                        transceiver.direction = 'sendrecv'
                        logger.info("Changed video transceiver direction to sendrecv")
            
            # Создаем answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            logger.info("WebRTC offer processed successfully")
            logger.info(f"Answer SDP preview: {answer.sdp[:500]}...")
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
            
        except Exception as e:
            logger.error(f"Error in _async_create_offer: {e}", exc_info=True)
            raise
    
    def shutdown(self):
        """Закрывает все соединения"""
        if not self.is_running:
            return
            
        try:
            # Планируем задачу закрытия в event loop
            future = asyncio.run_coroutine_threadsafe(
                self._async_shutdown(), self.loop
            )
            future.result(timeout=5.0)
            
            # Останавливаем event loop
            self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Ждем завершения потока
            if self.loop_thread and self.loop_thread.is_alive():
                self.loop_thread.join(timeout=2.0)
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            self.is_running = False
            logger.info("WebRTC handler shutdown complete")
        
    async def _async_shutdown(self):
        """Асинхронная версия shutdown"""
        # Останавливаем все video tracks
        for pc in list(self.pcs):
            if hasattr(pc, '_video_track_instance'):
                try:
                    pc._video_track_instance.stop()
                except:
                    pass
                    
        # Закрываем все peer connections
        coros = [pc.close() for pc in self.pcs]
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)
        self.pcs.clear()
