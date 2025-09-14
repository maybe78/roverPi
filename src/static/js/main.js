document.addEventListener('DOMContentLoaded', () => {
    // --- Переменные для нового WebRTC ---
    let pc = null;
    const videoElement = document.getElementById('webrtc-video');
    const startButton = document.getElementById('start-button');
    const stopButton = document.getElementById('stop-button');
    const statusDiv = document.getElementById('connection-status');
    const ROVER_IP = '192.168.0.38'; // IP вашего ровера

    // --- Socket.IO для управления ---
    const socket = io();

    let lastCommandTime = 0;
    const COMMAND_THROTTLE = 50;
    let lastCommand = { lx: 0, ly: 0 };

    const joy = new JoyStick('joystickDiv', {
        internalFillColor: '#444c5c',
        internalLineWidth: 3,
        internalStrokeColor: '#222933',
        externalLineWidth: 3,
        externalStrokeColor: '#0055ff',
        autoReturnToCenter: true,
        radius: 70
    }, function(stickData) {
        const now = Date.now();
        const lx = parseFloat((stickData.x / 100).toFixed(2));
        const ly = parseFloat((-stickData.y / 100).toFixed(2));

        if ((now - lastCommandTime) >= COMMAND_THROTTLE && 
            (Math.abs(lx - lastCommand.lx) > 0.01 || Math.abs(ly - lastCommand.ly) > 0.01)) {
            
            socket.emit('control', { lx, ly });
            lastCommandTime = now;
            lastCommand = { lx, ly };
        }
    });

    // --- НОВЫЙ КОД ДЛЯ WEBRTC ---
    async function startWebRTC() {
        if (pc) return; // Не запускаем, если уже запущено

        console.log('Starting WebRTC connection...');
        updateStatus('Подключение...', false);
        startButton.disabled = true;
        
        pc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });

        pc.ontrack = (event) => {
            console.log('Video track received:', event.track);
            if (videoElement && event.streams && event.streams[0]) {
                videoElement.srcObject = event.streams[0];
            }
        };

        pc.onconnectionstatechange = () => {
            console.log('WebRTC State:', pc.connectionState);
            if (pc.connectionState === 'connected') {
                updateStatus('Подключено', true);
                stopButton.disabled = false;
            } else if (['disconnected', 'failed', 'closed'].includes(pc.connectionState)) {
                updateStatus('Отключено', false);
                stopWebRTC(); // Автоматически очищаем
            }
        };

        pc.addTransceiver('video', { direction: 'recvonly' });

        try {
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            // Отправляем offer на pi-webrtc WHEP endpoint
            const response = await fetch(`http://192.168.0.38:8080`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: offer.sdp
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error ${response.status}: ${errorText}`);
            }

            const answerSdp = await response.text();
            await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

        } catch (e) {
            console.error('Failed to start WebRTC:', e);
            updateStatus('Ошибка видео', false);
            stopWebRTC();
        }
    }

    function stopWebRTC() {
        if (pc) {
            pc.close();
            pc = null;
        }
        if (videoElement) {
            videoElement.srcObject = null;
        }
        updateStatus('Отключено', false);
        startButton.disabled = false;
        stopButton.disabled = true;
        console.log('WebRTC connection closed.');
    }

    function updateStatus(text, connected) {
        statusDiv.textContent = text;
        statusDiv.className = connected ? 'connected' : '';
    }

    // Обработчик остановки движения
    let stopTimeout = null;
    function stopMovement() {
        clearTimeout(stopTimeout);
        stopTimeout = setTimeout(() => {
            socket.emit('control', { lx: 0.0, ly: 0.0 });
        }, 100);
    }
    document.addEventListener('touchend', stopMovement);
    document.addEventListener('mouseup', stopMovement);

    // Socket.IO обработчики
    socket.on('connect', () => console.log('Connected to control server.'));
    socket.on('disconnect', () => console.log('Disconnected from control server.'));

    // Привязываем функции к кнопкам
    window.startWebRTC = startWebRTC;
    window.stopWebRTC = stopWebRTC;
    
    // Автоматический запуск видео при загрузке
    setTimeout(startWebRTC, 500);
});
