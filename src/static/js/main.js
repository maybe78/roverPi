document.addEventListener('DOMContentLoaded', () => {
    // WebRTC переменные
    let pc = null;
    let localVideo = document.getElementById('webrtc-video');
    let startButton = document.getElementById('start-button');
    let stopButton = document.getElementById('stop-button');
    let statusDiv = document.getElementById('connection-status');

    // Socket.IO
    const socket = io();

    // Throttling для команд джойстика
    let lastCommandTime = 0;
    const COMMAND_THROTTLE = 50; // 50ms между командами (20 FPS)
    let lastCommand = { lx: 0, ly: 0 };

    // Джойстик с throttling
    const joy = new JoyStick('joystickDiv', {
        internalFillColor: '#444c5c',
        internalLineWidth: 3,
        internalStrokeColor: '#222933',
        externalLineWidth: 3,
        externalStrokeColor: '#0055ff',
        autoReturnToCenter: true,
        autoReturnSpeed: 15,
        radius: 70
    }, function(stickData) {
        const now = Date.now();
        
        const lx = parseFloat((stickData.x / 100).toFixed(2));
        const ly = parseFloat((-stickData.y / 100).toFixed(2));

        // Проверяем throttling и изменения
        if ((now - lastCommandTime) >= COMMAND_THROTTLE && 
            (Math.abs(lx - lastCommand.lx) > 0.01 || Math.abs(ly - lastCommand.ly) > 0.01)) {
            
            socket.emit('control', { lx, ly });
            console.log(`Sending control: lx=${lx}, ly=${ly}`);
            
            lastCommandTime = now;
            lastCommand = { lx, ly };
        }
    });

    function isIOSDevice() {
        return /iPad|iPhone|iPod/.test(navigator.userAgent);
    }
    
    // WebRTC функции
    function createPeerConnection() {
        const config = {
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
            sdpSemantics: 'unified-plan',
            bundlePolicy: 'max-bundle',
            rtcpMuxPolicy: 'require'
        };


        pc = new RTCPeerConnection(config);

        pc.ontrack = function(event) {
            console.log('Received track:', event.track.kind, 'readyState:', event.track.readyState);
            console.log('Event streams:', event.streams);
            
            if (event.track.kind === 'video') {
                // ИСПРАВЛЕНИЕ: Правильная установка srcObject
                localVideo.srcObject = event.streams[0]; // Берем первый поток
                updateStatus('Подключено', true);
                
                localVideo.play().then(() => {
                    console.log('Video started playing');
                }).catch(e => {
                    console.error('Error playing video:', e);
                });
                
                // Дополнительные обработчики для отладки
                event.track.onended = () => console.log('Track ended');
                event.track.onmute = () => console.log('Track muted');
                event.track.onunmute = () => {
                    console.log('Track unmuted');
                    localVideo.play().catch(e => console.error('Error playing video after unmute:', e));
                };
            }
        };

        pc.onconnectionstatechange = function() {
            console.log('Connection state:', pc.connectionState);
            
            switch(pc.connectionState) {
                case 'connected':
                    updateStatus('Подключено', true);
                    // Проверяем есть ли видео поток
                    if (localVideo.srcObject) {
                        console.log('Video stream exists, trying to play');
                        localVideo.play().catch(e => console.error('Error playing video on connect:', e));
                    }
                    break;
                case 'connecting':
                    updateStatus('Подключение...', false);
                    break;
                case 'disconnected':
                case 'failed':
                case 'closed':
                    updateStatus('Отключено', false);
                    break;
            }
        };

        pc.oniceconnectionstatechange = function() {
            console.log('ICE connection state:', pc.iceConnectionState);
        };

        return pc;
    }

    async function startWebRTC() {
        try {
            startButton.disabled = true;
            updateStatus('Инициализация...', false);

            pc = createPeerConnection();
            const offerOptions = {
                offerToReceiveVideo: true,
                offerToReceiveAudio: false
            };
            
            if (isIOSDevice()) {
                console.log('Detected iOS device, using special configuration');
                // Для iOS явно добавляем трансивер
                pc.addTransceiver('video', {direction: 'recvonly'});
            }
            const offer = await pc.createOffer({
                offerToReceiveVideo: true,
                offerToReceiveAudio: false
            });
            
            await pc.setLocalDescription(offer);

            console.log('Offer SDP (first 500 chars):', offer.sdp.substring(0, 500));
            console.log('User agent:', navigator.userAgent);

            const response = await fetch('/offer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'User-Agent': navigator.userAgent
                },
                body: JSON.stringify({
                    sdp: offer.sdp,
                    type: offer.type
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
            }

            const answer = await response.json();
            
            if (answer.error) {
                throw new Error(answer.error);
            }

            console.log('Answer SDP (first 500 chars):', answer.sdp.substring(0, 500));

            await pc.setRemoteDescription(new RTCSessionDescription(answer));
            
            stopButton.disabled = false;
            updateStatus('Подключение...', false);

        } catch (error) {
            console.error('Error starting WebRTC:', error);
            updateStatus('Ошибка подключения', false);
            startButton.disabled = false;
        }
    }

    function stopWebRTC() {
        if (pc) {
            pc.close();
            pc = null;
        }
        
        localVideo.srcObject = null;
        updateStatus('Отключено', false);
        
        startButton.disabled = false;
        stopButton.disabled = true;
    }

    function updateStatus(text, connected) {
        statusDiv.textContent = text;
        statusDiv.className = connected ? 'connected' : '';
    }

    // Обработчики для остановки движения с debouncing
    let stopTimeout = null;
    
    function stopMovement() {
        // Очищаем предыдущий таймаут
        if (stopTimeout) {
            clearTimeout(stopTimeout);
        }
        
        // Устанавливаем новый таймаут
        stopTimeout = setTimeout(() => {
            socket.emit('control', { lx: 0.0, ly: 0.0 });
            console.log('Force stop on touch end');
            lastCommand = { lx: 0, ly: 0 };
        }, 100); // 100ms задержка для debouncing
    }

    document.addEventListener('touchend', stopMovement);
    document.addEventListener('mouseup', stopMovement);

    // Socket.IO обработчики
    socket.on('connect', function() {
        console.log('Connected to server');
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
    });

    // Глобальные функции для кнопок
    window.startWebRTC = startWebRTC;
    window.stopWebRTC = stopWebRTC;

    // Автоматический запуск WebRTC при загрузке страницы
    setTimeout(startWebRTC, 1000);
});
