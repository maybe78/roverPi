import asyncio
import logging
import threading
from aiortc import RTCPeerConnection, MediaStreamTrack, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import numpy as np
import weakref

logger = logging.getLogger('webrtc')

class SharedVideoSource:
    """
    Общий источник видео для всех клиентов
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.player = None
        self.track = None
        self.subscribers = set()
        self._stopped = False
        self._lock = threading.Lock()
        
        # Создаем единственный MediaPlayer
        try:
            camera_options = {
                'video_size': '640x480',
                'framerate': '15',
                'pixel_format': 'yuyv422'
            }
            
            self.player = MediaPlayer('/dev/video0', format='v4l2', options=camera_options)
            
            if self.player.video:
                self.track = self.player.video
                logger.info("Shared camera /dev/video0 successfully initialized")
            else:
                raise Exception("No video track from camera")
                
        except Exception as e:
            logger.error(f"Failed to initialize shared camera: {e}")
            try:
                self.player = MediaPlayer('/dev/video0', format='v4l2')
                if self.player.video:
                    self.track = self.player.video
                    logger.warning("Shared camera initialized with basic settings")
                else:
                    raise Exception("No video track from basic camera init")
            except Exception as e2:
                logger.error(f"Shared camera fallback also failed: {e2}")
                # Последний fallback на тестовый источник
                self.player = MediaPlayer('testsrc=size=640x480:rate=15', format='lavfi')
                self.track = self.player.video
                logger.warning("Using shared test source instead of camera")
        
        self._initialized = True
    
    def subscribe(self, video_track):
        """Подписывает видео трек на получение кадров"""
        with self._lock:
            self.subscribers.add(video_track)
            logger.info(f"Video track subscribed. Total subscribers: {len(self.subscribers)}")
    
    def unsubscribe(self, video_track):
        """Отписывает видео трек"""
        with self._lock:
            self.subscribers.discard(video_track)
            logger.info(f"Video track unsubscribed. Total subscribers: {len(self.subscribers)}")
            
            # Если больше нет подписчиков, можно остановить источник
            if len(self.subscribers) == 0:
                logger.info("No more subscribers, keeping source active for future connections")
    
    async def get_frame(self):
        """Получает кадр от общего источника"""
        if self._stopped or not self.track:
            # Возвращаем черный кадр если остановлен
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            # Красный текст "STOPPED"
            img[240:280, 250:390] = [0, 0, 255]
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            return frame
            
        try:
            frame = await self.track.recv()
            
            # Конвертируем в numpy array для обработки
            img = frame.to_ndarray(format="bgr24")
            
            # Добавляем индикатор количества клиентов
            with self._lock:
                client_count = len(self.subscribers)
            
            # Зеленый прямоугольник с количеством клиентов
            img[10:40, 10:200] = [0, 255, 0]
            
            # Создаем КОПИЮ кадра для каждого получателя
            # (важно, чтобы каждый трек получил свой кадр)
            new_frame = VideoFrame.from_ndarray(img.copy(), format="bgr24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base
            
            return new_frame
            
        except Exception as e:
            if not self._stopped:
                logger.error(f"Error getting shared frame: {e}")
            
            # В случае ошибки возвращаем черный кадр
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            img[240:280, 320:420] = [0, 0, 255]  # Красный прямоугольник
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            return frame
    
    def shutdown(self):
        """Останавливает общий источник"""
        self._stopped = True
        with self._lock:
            self.subscribers.clear()
            
        try:
            if self.track and hasattr(self.track, 'stop'):
                self.track.stop()
            
            # MediaPlayer освобождается при удалении ссылки
            self.player = None
            self.track = None
            logger.info("Shared video source stopped")
        except Exception as e:
            logger.error(f"Error stopping shared video source: {e}")


class VideoTransformTrack(MediaStreamTrack):
    """
    Видео трек, который получает кадры от общего источника
    """
    kind = "video"

    def __init__(self):
        super().__init__()
        self._stopped = False
        self.shared_source = SharedVideoSource()
        self.shared_source.subscribe(self)
        logger.info("VideoTransformTrack created and subscribed to shared source")

    async def recv(self):
        """
        Получает кадр от общего источника
        """
        if self._stopped:
            # Возвращаем черный кадр если остановлен
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            return frame
        
        return await self.shared_source.get_frame()

    def stop(self):
        """Останавливает трек"""
        self._stopped = True
        if hasattr(self, 'shared_source'):
            self.shared_source.unsubscribe(self)
        logger.info("VideoTransformTrack stopped and unsubscribed")


def fix_safari_sdp(sdp_text):
    """
    Исправляет SDP для совместимости с Safari/iOS
    """
    lines = sdp_text.split('\r\n')
    fixed_lines = []
    
    for line in lines:
        # Исправляем направления для Safari
        if line.startswith('a=') and ('recvonly' in line or 'sendonly' in line or 'sendrecv' in line or 'inactive' in line):
            # Safari иногда создает некорректные направления
            if 'recvonly' in line:
                fixed_lines.append('a=recvonly')
            elif 'sendonly' in line:
                fixed_lines.append('a=sendonly')
            elif 'sendrecv' in line:
                fixed_lines.append('a=sendrecv')
            elif 'inactive' in line:
                fixed_lines.append('a=inactive')
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    return '\r\n'.join(fixed_lines)


class WebRTCHandler:
    """
    Класс для обработки WebRTC соединений с поддержкой множественных клиентов
    """
    
    def __init__(self):
        self.pcs = set()
        self.loop = None
        self.loop_thread = None
        self.is_running = False
        self._shutdown_in_progress = False
        
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
        if self._shutdown_in_progress:
            raise RuntimeError("WebRTC handler is shutting down")
            
        if not self.is_running:
            self.start_loop()
            
        future = asyncio.run_coroutine_threadsafe(
            self._async_create_offer(sdp_offer), self.loop
        )
        
        try:
            return future.result(timeout=10.0)
        except Exception as e:
            logger.error(f"Error in create_offer: {e}")
            raise
        
    async def _async_create_offer(self, sdp_offer):
        """
        Асинхронная версия создания offer с поддержкой множественных клиентов
        """
        if self._shutdown_in_progress:
            raise RuntimeError("Shutdown in progress")
            
        try:
            # Увеличиваем лимит для множественных клиентов
            if len(self.pcs) > 10:
                logger.warning("Too many peer connections, rejecting new connection")
                raise RuntimeError("Too many connections")
                
            # Конфигурация
            ice_servers = [RTCIceServer(urls=['stun:stun.l.google.com:19302'])]
            configuration = RTCConfiguration(iceServers=ice_servers)
            pc = RTCPeerConnection(configuration=configuration)
            self.pcs.add(pc)
            
            logger.info(f"New peer connection created. Total connections: {len(self.pcs)}")
            
            # Добавляем обработчик для отключения
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state is {pc.connectionState}")
                if pc.connectionState in ["closed", "failed"]:
                    await self._cleanup_pc(pc)
                    
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track received: {track.kind}")
            
            # Создаем отдельный видео трек для каждого клиента
            video_track = VideoTransformTrack()
            pc._video_track_instance = video_track
            pc.addTrack(video_track)
            logger.info("Video track added for new client")
            
            # Исправляем SDP и устанавливаем remote description
            fixed_sdp = fix_safari_sdp(sdp_offer["sdp"])
            
            logger.info("Setting remote description...")
            remote_desc = RTCSessionDescription(
                sdp=fixed_sdp,
                type=sdp_offer["type"]
            )
            await pc.setRemoteDescription(remote_desc)
            
            # Проверяем трансиверы
            transceivers = pc.getTransceivers()
            logger.info(f"Found {len(transceivers)} transceivers after setRemoteDescription")
            
            for i, transceiver in enumerate(transceivers):
                logger.info(f"Transceiver {i}: kind={transceiver.kind}, direction={transceiver.direction}")
                
                if transceiver.kind == "video":
                    logger.info(f"Video transceiver direction: {transceiver.direction}")
                    if hasattr(transceiver, 'direction') and transceiver.direction == 'recvonly':
                        transceiver.direction = 'sendrecv'
                        logger.info("Changed video transceiver direction to sendrecv")
            
            # Создаем answer
            logger.info("Creating answer...")
            answer = await pc.createAnswer()
            
            # Исправляем answer SDP
            fixed_answer_sdp = fix_safari_sdp(answer.sdp)
            fixed_answer = RTCSessionDescription(
                sdp=fixed_answer_sdp,
                type=answer.type
            )
            
            await pc.setLocalDescription(fixed_answer)
            
            logger.info(f"WebRTC offer processed successfully. Active connections: {len(self.pcs)}")
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
            
        except Exception as e:
            logger.error(f"Error in _async_create_offer: {e}", exc_info=True)
            if 'pc' in locals():
                await self._cleanup_pc(pc)
            raise
    
    async def _cleanup_pc(self, pc):
        """Безопасная очистка peer connection"""
        try:
            self.pcs.discard(pc)
            logger.info(f"Peer connection removed. Remaining connections: {len(self.pcs)}")
            
            if hasattr(pc, '_video_track_instance'):
                pc._video_track_instance.stop()
                
            if pc.connectionState != 'closed':
                await pc.close()
                
        except Exception as e:
            logger.error(f"Error cleaning up PC: {e}")
    
    def shutdown(self):
        """Закрывает все соединения и общий источник видео"""
        if self._shutdown_in_progress or not self.is_running:
            logger.info("Shutdown already in progress or not running")
            return
            
        self._shutdown_in_progress = True
        logger.info("Starting WebRTC shutdown...")
        
        try:
            # Сначала останавливаем общий источник видео
            shared_source = SharedVideoSource()
            shared_source.shutdown()
            
            # Затем закрываем все peer connections
            future = asyncio.run_coroutine_threadsafe(
                self._async_shutdown(), self.loop
            )
            future.result(timeout=5.0)  # Увеличиваем таймаут
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            # Принудительно останавливаем event loop
            if self.loop and self.is_running:
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            self.is_running = False
            logger.info("WebRTC handler shutdown complete")
        
    async def _async_shutdown(self):
        """Асинхронная версия shutdown"""
        logger.info(f"Shutting down {len(self.pcs)} peer connections...")
        
        # Создаем копию множества для безопасной итерации
        pcs_copy = list(self.pcs)
        self.pcs.clear()
        
        # Останавливаем все видео треки
        for pc in pcs_copy:
            if hasattr(pc, '_video_track_instance'):
                try:
                    pc._video_track_instance.stop()
                except Exception as e:
                    logger.error(f"Error stopping video track: {e}")
        
        # Даем время на остановку треков
        await asyncio.sleep(0.5)
                    
        # Закрываем все peer connections параллельно
        if pcs_copy:
            close_tasks = []
            for pc in pcs_copy:
                if pc.connectionState != 'closed':
                    close_tasks.append(pc.close())
            
            if close_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*close_tasks, return_exceptions=True),
                        timeout=3.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for peer connections to close")
        
        logger.info("All peer connections cleaned up")
