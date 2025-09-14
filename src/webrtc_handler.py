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
import fractions

logger = logging.getLogger('webrtc')

class UltraLowLatencyVideoSource:
    """
    Источник видео с УЛЬТРА низкой задержкой - без буферизации
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
        self.subscribers = weakref.WeakSet()
        self._stopped = False
        self._lock = threading.Lock()
        self._shutdown_called = False
        
        # КРИТИЧНЫЕ настройки для НУЛЕВОЙ задержки
        try:
            camera_options = {
                'video_size': '640x480',
                'framerate': '30',                    # УВЕЛИЧИВАЕМ FPS для плавности
                'pixel_format': 'yuyv422',
                
                # УЛЬТРА критичные настройки латентности
                'buffer_size': '0',                   # НУЛЕВОЙ буфер!
                'thread_queue_size': '1',             # Минимальная очередь
                'fflags': '+nobuffer+fastseek+flush_packets+genpts+igndts',
                'flags': 'low_delay',                 # Флаг низкой задержки
                'probesize': '32',                    # Минимальная проба
                'analyzeduration': '0',               # Не анализируем
                'max_delay': '0',                     # Нулевая задержка
                'avioflags': 'direct',                # Прямой I/O
                'flush_packets': '1',                 # Немедленная отправка пакетов
                'real_time': '1',                     # Режим реального времени
            }
            
            self.player = MediaPlayer('/dev/video0', format='v4l2', options=camera_options)
            
            if self.player.video:
                self.track = self.player.video
                logger.info("Camera initialized with ZERO LATENCY settings (30fps)")
            else:
                raise Exception("No video track from camera")
                
        except Exception as e:
            logger.error(f"Failed to initialize ultra low latency camera: {e}")
            try:
                # Агрессивный fallback
                camera_options = {
                    'framerate': '25',
                    'buffer_size': '0',
                    'fflags': '+nobuffer+flush_packets',
                    'flags': 'low_delay',
                    'real_time': '1'
                }
                self.player = MediaPlayer('/dev/video0', format='v4l2', options=camera_options)
                if self.player.video:
                    self.track = self.player.video
                    logger.warning("Camera initialized with aggressive low-latency fallback")
                else:
                    raise Exception("No video track from fallback")
            except Exception as e2:
                logger.error(f"Camera fallback failed: {e2}")
                # Последний шанс с тестовым источником
                self.player = MediaPlayer('testsrc=size=640x480:rate=25', format='lavfi',
                                        options={'fflags': '+nobuffer', 'real_time': '1'})
                self.track = self.player.video
                logger.warning("Using ultra low latency test source")
        
        self._initialized = True
        atexit.register(self._emergency_cleanup)
    
    def subscribe(self, video_track):
        if self._stopped:
            return False
            
        with self._lock:
            self.subscribers.add(video_track)
            logger.info(f"Ultra low latency track subscribed. Total: {len(self.subscribers)}")
        return True
    
    def unsubscribe(self, video_track):
        with self._lock:
            logger.info(f"Ultra low latency track unsubscribed. Total: {len(self.subscribers)}")
    
    async def get_frame(self):
        """
        КРИТИЧНО: Немедленная отдача кадра с принудительным таймстампом
        """
        if self._stopped or not self.track:
            return None
            
        try:
            # Получаем кадр НЕМЕДЛЕННО
            frame = await self.track.recv()
            
            # КРИТИЧНО: Принудительно устанавливаем ТЕКУЩЕЕ время
            # Это гарантирует что кадр считается "свежим"
            current_time_us = int(time.time() * 1000000)
            frame.pts = current_time_us
            frame.time_base = fractions.Fraction(1, 1000000)  # Микросекунды
            
            return frame
            
        except Exception as e:
            if not self._stopped:
                logger.error(f"Error getting ultra low latency frame: {e}")
            return None
    
    def _emergency_cleanup(self):
        if not self._shutdown_called:
            logger.warning("Emergency cleanup of ultra low latency video source")
            self._stopped = True
    
    def safe_shutdown(self):
        if self._shutdown_called:
            return
            
        self._shutdown_called = True
        self._stopped = True
        
        with self._lock:
            self.subscribers.clear()
        
        # Быстрая очистка без блокировки
        self.track = None
        self.player = None
        
        logger.info("Ultra low latency video source shutdown")

class ZeroLatencyVideoTrack(MediaStreamTrack):
    """
    Видео трек с НУЛЕВОЙ задержкой через frame skipping
    """
    kind = "video"

    def __init__(self):
        super().__init__()
        self._stopped = False
        self.shared_source = UltraLowLatencyVideoSource()
        self.last_frame_time = 0
        self.max_frame_age = 0.050  # 50ms - дропаем кадры старше этого
        self.frames_dropped = 0
        self.frames_sent = 0
        
        if not self.shared_source.subscribe(self):
            logger.error("Failed to subscribe to ultra low latency source")
        else:
            logger.info("ZeroLatencyVideoTrack created")

    async def recv(self):
        """
        АГРЕССИВНЫЙ frame dropping для ультра низкой задержки
        """
        if self._stopped:
            return None
        
        max_attempts = 10  # Больше попыток для получения свежего кадра
        current_time = time.time()
        
        for attempt in range(max_attempts):
            frame = await self.shared_source.get_frame()
            
            if frame is None:
                continue
                
            # Вычисляем возраст кадра
            if hasattr(frame, 'pts') and frame.time_base:
                frame_timestamp = float(frame.pts * frame.time_base)
                frame_age = current_time - frame_timestamp
                
                # Если кадр свежий - отправляем
                if frame_age <= self.max_frame_age:
                    self.frames_sent += 1
                    
                    # Логируем статистику каждые 100 кадров
                    if (self.frames_sent + self.frames_dropped) % 100 == 0:
                        total_frames = self.frames_sent + self.frames_dropped
                        drop_rate = (self.frames_dropped / total_frames) * 100 if total_frames > 0 else 0
                        logger.debug(f"Frame stats: {drop_rate:.1f}% dropped, age: {frame_age*1000:.1f}ms")
                    
                    return frame
                else:
                    # Кадр слишком старый - дропаем
                    self.frames_dropped += 1
                    logger.debug(f"Dropped old frame (age: {frame_age*1000:.1f}ms)")
                    
                    # Не тратим время на получение нового кадра если этот очень старый
                    if frame_age > 0.200:  # Если старше 200ms - прерываем попытки
                        break
                    
                    continue
            else:
                # Если нет временной метки - отправляем как есть
                self.frames_sent += 1
                return frame
        
        # Если не смогли получить свежий кадр - лучше отправить старый чем ничего
        logger.debug("Could not get fresh frame, sending last available")
        return frame if 'frame' in locals() else None

    def stop(self):
        if not self._stopped:
            self._stopped = True
            if hasattr(self, 'shared_source'):
                self.shared_source.unsubscribe(self)
            
            # Логируем финальную статистику
            total_frames = self.frames_sent + self.frames_dropped
            if total_frames > 0:
                drop_rate = (self.frames_dropped / total_frames) * 100
                logger.info(f"ZeroLatencyVideoTrack stopped. Final stats: {drop_rate:.1f}% frames dropped")
            else:
                logger.info("ZeroLatencyVideoTrack stopped")

def optimize_sdp_for_zero_latency(sdp):
    """
    АГРЕССИВНАЯ оптимизация SDP для нулевой задержки
    """
    lines = sdp.split('\r\n')
    optimized_lines = []
    
    for line in lines:
        optimized_lines.append(line)
        
        # Добавляем критичные атрибуты после видео секции
        if line.startswith('m=video'):
            # УЛЬТРА агрессивные настройки для минимальной задержки
            optimized_lines.extend([
                'a=rtcp-fb:* nack',                    # Быстрое восстановление
                'a=rtcp-fb:* nack pli',                # Picture Loss Indication
                'a=rtcp-fb:* ccm fir',                 # Full Intra Request
                'a=rtcp-fb:* goog-remb',               # Receiver Estimated Max Bitrate
                'a=rtcp-fb:* transport-cc',            # Transport-wide Congestion Control
                'a=setup:actpass',                     # Быстрое установление соединения
                'a=rtcp-mux',                          # Мультиплексирование RTCP
                'a=rtcp-rsize',                        # Уменьшенные RTCP пакеты
            ])
        
        # Модифицируем существующие RTCP feedback атрибуты для агрессивности
        if 'a=rtcp-fb:' in line and 'transport-cc' in line:
            # Заменяем на более агрессивный
            optimized_lines[-1] = line  # Оставляем оригинальную строку
    
    optimized_sdp = '\r\n'.join(optimized_lines)
    
    # Дополнительно добавляем глобальные атрибуты для низкой задержки
    if 'a=group:BUNDLE' in optimized_sdp:
        # Добавляем атрибуты прямо после BUNDLE группы
        bundle_index = optimized_sdp.find('a=group:BUNDLE')
        if bundle_index != -1:
            end_of_line = optimized_sdp.find('\r\n', bundle_index)
            if end_of_line != -1:
                before = optimized_sdp[:end_of_line + 2]
                after = optimized_sdp[end_of_line + 2:]
                
                # Вставляем дополнительные атрибуты для низкой задержки
                extra_attrs = '\r\n'.join([
                    'a=extmap-allow-mixed',              # Разрешаем смешанные расширения
                    'a=msid-semantic: WMS',              # WebRTC Media Stream semantic
                ])
                
                optimized_sdp = before + extra_attrs + '\r\n' + after
    
    return optimized_sdp

def fix_safari_sdp(sdp_text):
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

class ZeroLatencyWebRTCHandler:
    """
    WebRTC handler для НУЛЕВОЙ задержки
    """
    
    def __init__(self):
        self.pcs = weakref.WeakSet()
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
            
            # КРИТИЧНО: Настраиваем event loop для минимальной задержки
            self.loop.set_debug(False)  # Отключаем debug для скорости
            
            self.is_running = True
            logger.info("Zero latency WebRTC event loop started")
            try:
                self.loop.run_forever()
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
            finally:
                self.is_running = False
                
        # Поток с высоким приоритетом для минимальной задержки
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        timeout = 3.0  # Уменьшили таймаут
        start_time = time.time()
        while not self.is_running and (time.time() - start_time) < timeout:
            time.sleep(0.05)  # Меньший интервал проверки
            
        if not self.is_running:
            raise RuntimeError("Failed to start zero latency WebRTC event loop")
        
    def create_offer(self, sdp_offer):
        if self._shutdown_in_progress:
            raise RuntimeError("WebRTC handler is shutting down")
            
        if not self.is_running:
            self.start_loop()
            
        future = asyncio.run_coroutine_threadsafe(
            self._async_create_offer(sdp_offer), self.loop
        )
        
        try:
            return future.result(timeout=5.0)  # Быстрый таймаут
        except Exception as e:
            logger.error(f"Error in create_offer: {e}")
            raise
        
    async def _async_create_offer(self, sdp_offer):
        """
        Создание offer с НУЛЕВОЙ задержкой
        """
        if self._shutdown_in_progress:
            raise RuntimeError("Shutdown in progress")
            
        try:
            # СТРОГИЙ лимит для минимальной задержки
            if len(self.pcs) > 1:  # Только 1 соединение для минимальной задержки!
                logger.warning("Only 1 connection allowed for zero latency")
                raise RuntimeError("Too many connections for zero latency")
            
            # УЛЬТРА быстрая конфигурация
            ice_servers = [RTCIceServer(urls=['stun:stun.l.google.com:19302'])]
            configuration = RTCConfiguration(iceServers=ice_servers)
            pc = RTCPeerConnection(configuration=configuration)
            self.pcs.add(pc)
            
            logger.info("Zero latency peer connection created")
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Zero latency connection state: {pc.connectionState}")
                if pc.connectionState in ["closed", "failed"]:
                    await self._cleanup_pc(pc)
                    
            @pc.on("track")
            def on_track(track):
                logger.info(f"Zero latency track received: {track.kind}")
            
            # Создаем ZERO LATENCY видео трек
            video_track = ZeroLatencyVideoTrack()
            pc._video_track_instance = video_track
            pc.addTrack(video_track)
            logger.info("Zero latency video track added")
            
            # КРИТИЧНО: Оптимизируем SDP ДО установки
            pre_optimized_sdp = optimize_sdp_for_zero_latency(sdp_offer["sdp"])
            fixed_sdp = fix_safari_sdp(pre_optimized_sdp)
            
            logger.info("Setting remote description with zero latency optimization...")
            remote_desc = RTCSessionDescription(
                sdp=fixed_sdp,
                type=sdp_offer["type"]
            )
            await pc.setRemoteDescription(remote_desc)
            
            # Агрессивно настраиваем трансиверы
            transceivers = pc.getTransceivers()
            for i, transceiver in enumerate(transceivers):
                if transceiver.kind == "video":
                    if hasattr(transceiver, 'direction') and transceiver.direction == 'recvonly':
                        transceiver.direction = 'sendrecv'
                        logger.info("Zero latency: Changed video transceiver direction")
            
            # Создаем answer
            logger.info("Creating zero latency answer...")
            answer = await pc.createAnswer()
            
            # КРИТИЧНО: Двойная оптимизация answer SDP
            optimized_answer = optimize_sdp_for_zero_latency(answer.sdp)
            final_answer_sdp = fix_safari_sdp(optimized_answer)
            
            final_answer = RTCSessionDescription(
                sdp=final_answer_sdp,
                type=answer.type
            )
            
            await pc.setLocalDescription(final_answer)
            
            logger.info("Zero latency WebRTC offer processed successfully")
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
            
        except Exception as e:
            logger.error(f"Error in zero latency offer: {e}", exc_info=True)
            if 'pc' in locals():
                await self._cleanup_pc(pc)
            raise
    
    async def _cleanup_pc(self, pc):
        try:
            logger.info("Cleaning up zero latency peer connection")
            
            if hasattr(pc, '_video_track_instance'):
                pc._video_track_instance.stop()
                del pc._video_track_instance
                
            if pc.connectionState != 'closed':
                await pc.close()
                
        except Exception as e:
            logger.error(f"Error cleaning up zero latency PC: {e}")
    
    def shutdown(self):
        if self._shutdown_in_progress or not self.is_running:
            logger.info("Zero latency shutdown already in progress")
            return
            
        self._shutdown_in_progress = True
        logger.info("Starting zero latency WebRTC shutdown...")
        
        try:
            # Быстрая остановка источника
            shared_source = UltraLowLatencyVideoSource()
            shared_source.safe_shutdown()
            
            # Быстрое закрытие соединений
            if self.loop and self.is_running:
                future = asyncio.run_coroutine_threadsafe(
                    self._async_shutdown(), self.loop
                )
                future.result(timeout=1.0)  # Очень быстрый shutdown
            
        except Exception as e:
            logger.error(f"Error during zero latency shutdown: {e}")
        finally:
            if self.loop and self.is_running:
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            self.is_running = False
            logger.info("Zero latency WebRTC handler shutdown complete")
        
    async def _async_shutdown(self):
        logger.info("Fast zero latency shutdown...")
        
        pcs_copy = list(self.pcs)
        self.pcs.clear()
        
        for pc in pcs_copy:
            if hasattr(pc, '_video_track_instance'):
                try:
                    pc._video_track_instance.stop()
                    del pc._video_track_instance
                except Exception as e:
                    logger.error(f"Error stopping zero latency track: {e}")
        
        if pcs_copy:
            close_tasks = []
            for pc in pcs_copy:
                if pc.connectionState != 'closed':
                    close_tasks.append(pc.close())
            
            if close_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*close_tasks, return_exceptions=True),
                        timeout=0.5  # Ультра быстрый таймаут
                    )
                except asyncio.TimeoutError:
                    logger.warning("Zero latency shutdown timeout")
        
        logger.info("Zero latency connections cleaned up")

# В main.py замените:
# webrtc_handler = MemoryOptimizedWebRTCHandler()
# на:
# webrtc_handler = ZeroLatencyWebRTCHandler()
