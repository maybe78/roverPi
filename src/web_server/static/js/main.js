document.addEventListener('DOMContentLoaded', () => {
    // --- Константы и переменные ---
    const ROVER_IP = '192.168.0.38'; // IP вашего ровера
    const JOYSTICK_SEND_INTERVAL = 100; // Отправлять команду каждые 100 мс

    // WebRTC переменные
    let pc = null;
    const videoElement = document.getElementById('webrtc-video');
    const startButton = document.getElementById('start-button');
    const stopButton = document.getElementById('stop-button');
    const statusDiv = document.getElementById('connection-status');

    // Socket.IO и джойстик
    const socket = io();
    let joystickIntervalId = null;
    let lastStickStatus = { lx: 0, ly: 0 };
    const joystickContainer = document.getElementById('joystickDiv');

    // --- Инициализация джойстика ---
    const joy = new JoyStick('joystickDiv', {
        internalFillColor: '#444c5c',
        internalLineWidth: 3,
        internalStrokeColor: '#222933',
        externalLineWidth: 3,
        externalStrokeColor: '#0055ff',
        autoReturnToCenter: true,
        radius: 70
    }, function(stickData) {
        // Этот callback вызывается только при движении.
        // Мы просто сохраняем последнюю позицию.
        lastStickStatus.lx = parseFloat((stickData.x / 100).toFixed(2));
        lastStickStatus.ly = parseFloat((-stickData.y / 100).toFixed(2));
    });

    // --- Управление отправкой команд джойстика ---

    function startSendingJoystickData() {
        if (joystickIntervalId) return; // Не запускать, если уже запущен

        joystickIntervalId = setInterval(() => {
            // Каждые 100 мс отправляем последнее известное положение
            socket.emit('control', lastStickStatus);
        }, JOYSTICK_SEND_INTERVAL);
        console.log("Начата периодическая отправка данных джойстика.");
    }

    function stopSendingJoystickData() {
        if (joystickIntervalId) {
            clearInterval(joystickIntervalId);
            joystickIntervalId = null;
            // Отправляем финальную команду на остановку
            lastStickStatus = { lx: 0, ly: 0 };
            socket.emit('control', lastStickStatus);
            console.log("Остановлена отправка данных. Моторы в 0.");
        }
    }
    
    // Вешаем обработчики на контейнер джойстика
    joystickContainer.addEventListener('mousedown', startSendingJoystickData);
    joystickContainer.addEventListener('touchstart', startSendingJoystickData);

    joystickContainer.addEventListener('mouseup', stopSendingJoystickData);
    joystickContainer.addEventListener('touchend', stopSendingJoystickData);
    // Также на случай, если курсор "убежит" с джойстика
    document.addEventListener('mouseup', stopSendingJoystickData);
    document.addEventListener('touchend', stopSendingJoystickData);


    // --- Логика WebRTC ---
    async function startWebRTC() {
        if (pc) return;

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
                stopWebRTC();
            }
        };

        pc.addTransceiver('video', { direction: 'recvonly' });

        try {
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            const response = await fetch(`https://192.168.0.38:8443`, {
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

    // --- Socket.IO обработчики ---
    socket.on('connect', () => console.log('Connected to control server.'));
    socket.on('disconnect', () => console.log('Disconnected from control server.'));

    // --- Глобальные функции и автозапуск ---
    window.startWebRTC = startWebRTC;
    window.stopWebRTC = stopWebRTC;

    // Автоматический запуск видео при загрузке
    setTimeout(startWebRTC, 500);
});
