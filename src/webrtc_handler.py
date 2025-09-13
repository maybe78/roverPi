import asyncio
import logging
import threading
from aiortc import RTCPeerConnection, MediaStreamTrack, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import numpy as np
import re

logger = logging.getLogger('webrtc')

class VideoTransformTrack(MediaStreamTrack):
    """
    Кастомный видео трек, который получает видео с камеры
    """
    kind = "video"

    def __init__(self):
        super().__init__()
        self.player = None
        self.track = None
        self._stopped = False
        
        # Создаем MediaPlayer для /dev/video0
        try:
            camera_options = {
                'video_size': '640x480',
                'framerate': '15',
                'pixel_format': 'yuyv422'
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
        if self._stopped or not self.track:
            # Возвращаем черный кадр если остановлен
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            return frame
            
        try:
            frame = await self.track.recv()
            
            # Конвертируем в numpy array для обработки
            img = frame.to_ndarray(format="bgr24")
            
            # Простая обработка без OpenCV
            # Добавляем зеленый прямоугольник в углу как индикатор
            img[10:40, 10:150] = [0, 255, 0]  # Зеленый прямоугольник
            
            # Создаем новый VideoFrame с обработанным изображением
            new_frame = VideoFrame.from_ndarray(img, format="bgr24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base
            
            return new_frame
            
        except Exception as e:
            if not self._stopped:
                logger.error(f"Error in recv: {e}")
            
            # В случае ошибки возвращаем черный кадр
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            # Красный прямоугольник для обозначения ошибки
            img[240:280, 320:420] = [0, 0, 255]
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            return frame

    def stop(self):
        """Останавливает проигрыватель"""
        self._stopped = True
        try:
            if self.track and hasattr(self.track, 'stop'):
                self.track.stop()
            
            self.player = None
            self.track = None
            logger.info("Video player resources released")
        except Exception as e:
            logger.error(f"Error stopping player: {e}")

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
    Класс для обработки WebRTC соединений с поддержкой iOS
    """
    
    def __init__(self):
        self.pcs = set()
        self.video_track = None
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
        Асинхронная версия создания offer с упрощенной конфигурацией
        """
        if self._shutdown_in_progress:
            raise RuntimeError("Shutdown in progress")
            
        try:
            # Ограничиваем количество одновременных соединений
            if len(self.pcs) > 5:
                logger.warning("Too many peer connections, rejecting new connection")
                raise RuntimeError("Too many connections")
                
            # ИСПРАВЛЕНИЕ: Упрощенная конфигурация без проблемных опций
            ice_servers = [RTCIceServer(urls=['stun:stun.l.google.com:19302'])]
            configuration = RTCConfiguration(iceServers=ice_servers)
            pc = RTCPeerConnection(configuration=configuration)
            self.pcs.add(pc)
            
            # Добавляем обработчик для отключения
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state is {pc.connectionState}")
                if pc.connectionState in ["closed", "failed"]:
                    await self._cleanup_pc(pc)
                    
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track received: {track.kind}")
            
            # Добавляем видео трек ДО установки remote description (как раньше)
            video_track = VideoTransformTrack()
            pc._video_track_instance = video_track
            pc.addTrack(video_track)
            logger.info("Video track added BEFORE setRemoteDescription")
            
            # ВАЖНО: Исправляем SDP перед установкой
            fixed_sdp = fix_safari_sdp(sdp_offer["sdp"])
            
            logger.info("Setting remote description...")
            logger.debug(f"Original SDP type: {sdp_offer['type']}")
            
            # Устанавливаем remote description с исправленным SDP
            remote_desc = RTCSessionDescription(
                sdp=fixed_sdp,
                type=sdp_offer["type"]
            )
            await pc.setRemoteDescription(remote_desc)
            
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
            logger.info("Creating answer...")
            answer = await pc.createAnswer()
            
            # Исправляем answer SDP для iOS
            fixed_answer_sdp = fix_safari_sdp(answer.sdp)
            fixed_answer = RTCSessionDescription(
                sdp=fixed_answer_sdp,
                type=answer.type
            )
            
            await pc.setLocalDescription(fixed_answer)
            
            logger.info("WebRTC offer processed successfully")
            logger.info(f"Answer SDP preview: {answer.sdp[:500]}...")
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
            
        except Exception as e:
            logger.error(f"Error in _async_create_offer: {e}", exc_info=True)
            # Очищаем PC при ошибке
            if 'pc' in locals():
                await self._cleanup_pc(pc)
            raise
    
    async def _cleanup_pc(self, pc):
        """Безопасная очистка peer connection"""
        try:
            self.pcs.discard(pc)
            
            if hasattr(pc, '_video_track_instance'):
                pc._video_track_instance.stop()
                
            if pc.connectionState != 'closed':
                await pc.close()
                
        except Exception as e:
            logger.error(f"Error cleaning up PC: {e}")
    
    def shutdown(self):
        """Закрывает все соединения"""
        if self._shutdown_in_progress or not self.is_running:
            logger.info("Shutdown already in progress or not running")
            return
            
        self._shutdown_in_progress = True
        logger.info("Starting WebRTC shutdown...")
        
        try:
            # Планируем задачу закрытия в event loop
            future = asyncio.run_coroutine_threadsafe(
                self._async_shutdown(), self.loop
            )
            future.result(timeout=3.0)
            
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
                    
        # Закрываем все peer connections с таймаутом
        close_tasks = []
        for pc in pcs_copy:
            if pc.connectionState != 'closed':
                close_tasks.append(pc.close())
        
        if close_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for peer connections to close")
        
        logger.info("All peer connections cleaned up")
