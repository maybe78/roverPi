import asyncio
import logging
import threading
from aiortc import RTCPeerConnection, MediaStreamTrack, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import atexit
import time
import gc
import weakref
import psutil
import os

logger = logging.getLogger('webrtc')

class MemoryManager:
    """
    Агрессивное управление памятью для предотвращения утечек
    """
    def __init__(self):
        self.last_cleanup = time.time()
        self.frame_count = 0
        self.cleanup_interval = 5.0  # Каждые 5 секунд
        self.force_cleanup_interval = 30.0  # Каждые 30 секунд принудительная очистка
        self.last_force_cleanup = time.time()
        
    def should_cleanup(self):
        """Проверяет нужна ли очистка памяти"""
        current_time = time.time()
        self.frame_count += 1
        
        # Обычная очистка каждые 5 секунд или каждые 100 кадров
        if (current_time - self.last_cleanup > self.cleanup_interval or 
            self.frame_count > 100):
            self.last_cleanup = current_time
            self.frame_count = 0
            return True
            
        return False
    
    def should_force_cleanup(self):
        """Проверяет нужна ли принудительная очистка"""
        current_time = time.time()
        if current_time - self.last_force_cleanup > self.force_cleanup_interval:
            self.last_force_cleanup = current_time
            return True
        return False
    
    def cleanup_memory(self):
        """Обычная очистка памяти"""
        try:
            gc.collect()
            logger.debug("Memory cleanup completed")
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
    
    def force_cleanup_memory(self):
        """Принудительная агрессивная очистка памяти"""
        try:
            # Принудительная сборка мусора несколько раз
            for _ in range(3):
                gc.collect()
            
            # Получаем информацию о памяти
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            logger.info(f"Force cleanup: Memory usage: {memory_mb:.1f} MB")
            
            # Если памяти используется больше 400MB - логируем предупреждение
            if memory_mb > 400:
                logger.warning(f"High memory usage detected: {memory_mb:.1f} MB")
                
        except Exception as e:
            logger.error(f"Error during force memory cleanup: {e}")

class SharedVideoSource:
    """
    Источник видео с агрессивным управлением памятью
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
        self.subscribers = weakref.WeakSet()  # ВАЖНО: Используем WeakSet!
        self._stopped = False
        self._lock = threading.Lock()
        self._shutdown_called = False
        self.memory_manager = MemoryManager()
        self.last_frame = None  # Кэшируем последний кадр
        
        # КРИТИЧЕСКИЕ настройки для предотвращения утечек памяти
        try:
            camera_options = {
                'video_size': '640x480',
                'framerate': '15',
                'pixel_format': 'yuyv422',
                'thread_queue_size': '1',     # ВАЖНО: Минимальный размер очереди
                'buffer_size': '1',           # ВАЖНО: Минимальный буфер
                'fflags': '+nobuffer+fastseek+flush_packets',  # Агрессивные флаги очистки
                'avioflags': 'direct',        # Прямой доступ без буферизации
            }
            
            self.player = MediaPlayer('/dev/video0', format='v4l2', options=camera_options)
            
            if self.player.video:
                self.track = self.player.video
                logger.info("Camera initialized with memory-optimized settings")
            else:
                raise Exception("No video track from camera")
                
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            try:
                # Fallback с минимальными настройками
                self.player = MediaPlayer('/dev/video0', format='v4l2', 
                                        options={'fflags': '+nobuffer', 'buffer_size': '1'})
                if self.player.video:
                    self.track = self.player.video
                    logger.warning("Camera initialized with basic memory-safe settings")
                else:
                    raise Exception("No video track from fallback")
            except Exception as e2:
                logger.error(f"Camera fallback failed: {e2}")
                self.player = MediaPlayer('testsrc=size=640x480:rate=15', format='lavfi',
                                        options={'fflags': '+nobuffer'})
                self.track = self.player.video
                logger.warning("Using test source")
        
        self._initialized = True
        atexit.register(self._emergency_cleanup)
    
    def subscribe(self, video_track):
        """Подписывает видео трек на получение кадров"""
        if self._stopped:
            return False
            
        with self._lock:
            self.subscribers.add(video_track)
            logger.info(f"Video track subscribed. Total subscribers: {len(self.subscribers)}")
        return True
    
    def unsubscribe(self, video_track):
        """Отписывает видео трек"""
        with self._lock:
            # WeakSet автоматически удаляет мертвые ссылки
            logger.info(f"Video track unsubscribed. Total subscribers: {len(self.subscribers)}")
    
    async def get_frame(self):
        """
        Получение кадров с агрессивным управлением памятью
        """
        if self._stopped or not self.track:
            return self.last_frame
            
        try:
            # Получаем новый кадр
            frame = await self.track.recv()
            
            # ВАЖНО: Явно освобождаем предыдущий кадр
            if self.last_frame is not None:
                del self.last_frame
            
            self.last_frame = frame
            
            # Проверяем нужна ли очистка памяти
            if self.memory_manager.should_cleanup():
                self.memory_manager.cleanup_memory()
            
            # Принудительная очистка при необходимости
            if self.memory_manager.should_force_cleanup():
                self.memory_manager.force_cleanup_memory()
            
            return frame
            
        except Exception as e:
            if not self._stopped:
                logger.error(f"Error getting frame: {e}")
            return self.last_frame
    
    def _emergency_cleanup(self):
        """Экстренная очистка при завершении программы"""
        if not self._shutdown_called:
            logger.warning("Emergency cleanup of shared video source")
            self._stopped = True
            self._cleanup_resources()
    
    def _cleanup_resources(self):
        """Очистка всех ресурсов"""
        try:
            # Очищаем кэшированный кадр
            if self.last_frame is not None:
                del self.last_frame
                self.last_frame = None
            
            # Очищаем track
            if self.track:
                self.track = None
                
            # Очищаем player - ОСТОРОЖНО!
            if self.player:
                try:
                    # НЕ вызываем stop() - это может вызвать segfault
                    self.player = None
                except Exception as e:
                    logger.error(f"Error cleaning player: {e}")
            
            # Принудительная очистка памяти
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")
    
    def safe_shutdown(self):
        """Безопасная остановка"""
        if self._shutdown_called:
            return
            
        self._shutdown_called = True
        self._stopped = True
        
        with self._lock:
            self.subscribers.clear()
        
        self._cleanup_resources()
        logger.info("Shared video source shutdown with memory cleanup")

class MemoryEfficientVideoTrack(MediaStreamTrack):
    """
    Видео трек с контролем памяти
    """
    kind = "video"

    def __init__(self):
        super().__init__()
        self._stopped = False
        self.shared_source = SharedVideoSource()
        self.frame_cache = None
        
        if not self.shared_source.subscribe(self):
            logger.error("Failed to subscribe to shared video source")
        else:
            logger.info("MemoryEfficientVideoTrack created")

    async def recv(self):
        """
        Получение кадра с освобождением предыдущего
        """
        if self._stopped:
            return None
        
        # Освобождаем предыдущий кэшированный кадр
        if self.frame_cache is not None:
            del self.frame_cache
            self.frame_cache = None
        
        # Получаем новый кадр
        frame = await self.shared_source.get_frame()
        self.frame_cache = frame
        
        return frame

    def stop(self):
        """Останавливает трек с очисткой памяти"""
        if not self._stopped:
            self._stopped = True
            
            # Очищаем кэш кадра
            if self.frame_cache is not None:
                del self.frame_cache
                self.frame_cache = None
                
            if hasattr(self, 'shared_source'):
                self.shared_source.unsubscribe(self)
            
            logger.info("MemoryEfficientVideoTrack stopped and cleaned")

def fix_safari_sdp(sdp_text):
    """Исправляет SDP для совместимости с Safari/iOS"""
    lines = sdp_text.split('\r\n')
    fixed_lines = []
    
    for line in lines:
        if line.startswith('a=') and ('recvonly' in line or 'sendonly' in line or 'sendrecv' in line or 'inactive' in line):
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

class MemoryOptimizedWebRTCHandler:
    """
    WebRTC handler с предотвращением утечек памяти
    """
    
    def __init__(self):
        self.pcs = weakref.WeakSet()  # ВАЖНО: Используем WeakSet!
        self.loop = None
        self.loop_thread = None
        self.is_running = False
        self._shutdown_in_progress = False
        
    def start_loop(self):
        if self.is_running:
            return
            
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.is_running = True
            logger.info("Memory-optimized WebRTC event loop started")
            try:
                self.loop.run_forever()
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
            finally:
                self.is_running = False
                
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        import time
        timeout = 5.0
        start_time = time.time()
        while not self.is_running and (time.time() - start_time) < timeout:
            time.sleep(0.1)
            
        if not self.is_running:
            raise RuntimeError("Failed to start WebRTC event loop")
        
    def create_offer(self, sdp_offer):
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
        Создание offer с контролем памяти
        """
        if self._shutdown_in_progress:
            raise RuntimeError("Shutdown in progress")
            
        try:
            # Строгий лимит соединений для экономии памяти
            if len(self.pcs) > 2:
                logger.warning("Too many peer connections for memory optimization")
                raise RuntimeError("Too many connections")
            
            # Конфигурация
            ice_servers = [RTCIceServer(urls=['stun:stun.l.google.com:19302'])]
            configuration = RTCConfiguration(iceServers=ice_servers)
            pc = RTCPeerConnection(configuration=configuration)
            self.pcs.add(pc)
            
            logger.info(f"New memory-optimized peer connection. Total: {len(self.pcs)}")
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state is {pc.connectionState}")
                if pc.connectionState in ["closed", "failed"]:
                    await self._cleanup_pc(pc)
                    
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track received: {track.kind}")
            
            # Создаем memory-efficient видео трек
            video_track = MemoryEfficientVideoTrack()
            pc._video_track_instance = video_track
            pc.addTrack(video_track)
            logger.info("Memory-efficient video track added")
            
            # Исправляем SDP
            fixed_sdp = fix_safari_sdp(sdp_offer["sdp"])
            
            logger.info("Setting remote description...")
            remote_desc = RTCSessionDescription(
                sdp=fixed_sdp,
                type=sdp_offer["type"]
            )
            await pc.setRemoteDescription(remote_desc)
            
            # Проверяем трансиверы
            transceivers = pc.getTransceivers()
            
            for i, transceiver in enumerate(transceivers):
                if transceiver.kind == "video":
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
            
            logger.info(f"Memory-optimized WebRTC offer processed. Active connections: {len(self.pcs)}")
            
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
        """Очистка peer connection с освобождением памяти"""
        try:
            logger.info(f"Cleaning up peer connection. Remaining: {len(self.pcs)}")
            
            if hasattr(pc, '_video_track_instance'):
                pc._video_track_instance.stop()
                del pc._video_track_instance
                
            if pc.connectionState != 'closed':
                await pc.close()
            
            # Принудительная очистка памяти после закрытия соединения
            gc.collect()
                
        except Exception as e:
            logger.error(f"Error cleaning up PC: {e}")
    
    def shutdown(self):
        """Shutdown с полной очисткой памяти"""
        if self._shutdown_in_progress or not self.is_running:
            logger.info("Shutdown already in progress or not running")
            return
            
        self._shutdown_in_progress = True
        logger.info("Starting memory-safe WebRTC shutdown...")
        
        try:
            # Останавливаем общий источник видео
            shared_source = SharedVideoSource()
            shared_source.safe_shutdown()
            
            # Закрываем peer connections
            if self.loop and self.is_running:
                future = asyncio.run_coroutine_threadsafe(
                    self._async_shutdown(), self.loop
                )
                future.result(timeout=3.0)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            if self.loop and self.is_running:
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            self.is_running = False
            
            # Принудительная очистка памяти в конце
            gc.collect()
            logger.info("Memory-safe WebRTC handler shutdown complete")
        
    async def _async_shutdown(self):
        """Быстрое закрытие с очисткой памяти"""
        logger.info(f"Shutting down {len(self.pcs)} peer connections with memory cleanup...")
        
        # WeakSet автоматически очистится от мертвых ссылок
        pcs_copy = list(self.pcs)
        self.pcs.clear()
        
        for pc in pcs_copy:
            if hasattr(pc, '_video_track_instance'):
                try:
                    pc._video_track_instance.stop()
                    del pc._video_track_instance
                except Exception as e:
                    logger.error(f"Error stopping video track: {e}")
        
        # Быстрое закрытие соединений
        if pcs_copy:
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
                    logger.warning("Memory-safe shutdown timeout")
        
        # Принудительная очистка памяти
        for _ in range(3):
            gc.collect()
        
        logger.info("All peer connections cleaned up with memory optimization")

# В main.py замените:
# webrtc_handler = WebRTCHandler()
# на:
# webrtc_handler = MemoryOptimizedWebRTCHandler()
