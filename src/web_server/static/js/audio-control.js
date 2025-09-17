// static/js/audio-control.js

class AudioController {
    constructor() {
        // Состояние локального воспроизведения MP3 на Raspberry Pi
        this.isPlaying = false;
        this.currentSound = null;

        // Состояние WebRTC микрофона
        this.isMicStreaming = false;
        this.webrtcConnection = null;
        this.localStream = null;

        // Настройки
        this.baseUrl = '/audio';
        
        this.initializeButtons();
        console.log('AudioController инициализирован');
    }

    initializeButtons() {
        // Получаем ссылки на кнопки
        this.playSound1Btn = document.getElementById('playSound1');
        this.playSound2Btn = document.getElementById('playSound2');
        this.startMicBtn = document.getElementById('startMic');
        this.stopAllBtn = document.getElementById('stopAll');

        // Проверяем, что кнопки найдены
        if (!this.playSound1Btn || !this.playSound2Btn || !this.startMicBtn || !this.stopAllBtn) {
            console.error('Не все аудио-кнопки найдены в DOM!');
            return;
        }

        // Привязываем обработчики событий
        this.playSound1Btn.addEventListener('click', () => this.playSound('sound1'));
        this.playSound2Btn.addEventListener('click', () => this.playSound('sound2'));
        this.startMicBtn.addEventListener('click', () => this.toggleMicrophone());
        this.stopAllBtn.addEventListener('click', () => this.stopAll());

        console.log('Обработчики событий аудиокнопок привязаны');
    }

    async sendAudioCommand(endpoint, data = {}) {
        try {
            console.log(`Отправка команды на ${this.baseUrl}${endpoint}`);
            
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Ответ сервера:', result);
            return result;
        } catch (error) {
            console.error('Ошибка отправки аудио команды:', error);
            return { status: 'error', message: error.message };
        }
    }

    // --- Локальное воспроизведение MP3 ---

    async playSound(soundName) {
        console.log(`Воспроизведение MP3 на Raspberry Pi: ${soundName}`);
        
        // Останавливаем текущие MP3, но не WebRTC микрофон
        if (this.isPlaying) {
            await this.stopLocalPlayback();
        }

        try {
            const result = await this.sendAudioCommand(`/play/${soundName}`);
            
            if (result && result.status === 'success') {
                this.isPlaying = true;
                this.currentSound = soundName;
                this.updateButtonStates();
                console.log(`MP3 ${soundName} играет на Raspberry Pi`);
            } else {
                console.error(`Ошибка воспроизведения ${soundName}:`, result.message);
                this.showError(`Ошибка воспроизведения ${soundName}`);
            }
        } catch (error) {
            console.error(`Исключение при воспроизведении ${soundName}:`, error);
            this.showError(`Ошибка воспроизведения ${soundName}`);
        }
    }

    async stopLocalPlayback() {
        console.log('Остановка локального MP3 на Raspberry Pi');
        
        try {
            const result = await this.sendAudioCommand('/stop');
            
            if (result && result.status === 'success') {
                this.isPlaying = false;
                this.currentSound = null;
                console.log('Локальное воспроизведение остановлено');
            }
        } catch (error) {
            console.error('Ошибка остановки локального воспроизведения:', error);
        }
    }

    // --- WebRTC микрофон ---

    async toggleMicrophone() {
        if (this.isMicStreaming) {
            await this.stopMicrophoneStream();
        } else {
            await this.startMicrophoneStream();
        }
    }

    async startMicrophoneStream() {
        try {
            console.log('Запрос доступа к микрофону...');
            
            // Запрашиваем доступ к микрофону
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 48000
                },
                video: false
            });

            console.log('Доступ к микрофону получен');

            // Создаем WebRTC соединение
            this.webrtcConnection = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });

            // Добавляем аудио-трек в соединение
            const audioTrack = this.localStream.getAudioTracks()[0];
            this.webrtcConnection.addTrack(audioTrack, this.localStream);

            this.webrtcConnection.onconnectionstatechange = () => {
                console.log('WebRTC состояние:', this.webrtcConnection.connectionState);
                if (this.webrtcConnection.connectionState === 'connected') {
                    this.isMicStreaming = true;
                    this.updateButtonStates();
                    console.log('Микрофон транслируется на Raspberry Pi');
                } else if (['disconnected', 'failed', 'closed'].includes(this.webrtcConnection.connectionState)) {
                    this.isMicStreaming = false;
                    this.updateButtonStates();
                }
            };

            // Получаем offer от сервера
            const offerResponse = await this.sendAudioCommand('/webrtc/microphone-offer');

            if (offerResponse.status !== 'success') {
                throw new Error(offerResponse.message);
            }

            // Устанавливаем remote description
            await this.webrtcConnection.setRemoteDescription({
                type: offerResponse.type,
                sdp: offerResponse.sdp
            });

            // Создаем answer
            const answer = await this.webrtcConnection.createAnswer();
            await this.webrtcConnection.setLocalDescription(answer);

            // Отправляем answer на сервер
            const answerResponse = await this.sendAudioCommand('/webrtc/microphone-answer', {
                connection_id: offerResponse.connection_id,
                sdp: answer.sdp,
                type: answer.type
            });

            if (answerResponse.status !== 'success') {
                throw new Error(answerResponse.message);
            }

            console.log('WebRTC соединение для микрофона установлено');

        } catch (error) {
            console.error('Ошибка запуска микрофона:', error);
            this.showError('Ошибка доступа к микрофону');
            await this.stopMicrophoneStream();
        }
    }

    async stopMicrophoneStream() {
        console.log('Остановка трансляции микрофона');

        // Останавливаем локальный поток
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }

        // Закрываем WebRTC соединение
        if (this.webrtcConnection) {
            this.webrtcConnection.close();
            this.webrtcConnection = null;
        }

        // Уведомляем сервер
        try {
            await this.sendAudioCommand('/webrtc/microphone-stop');
        } catch (error) {
            console.error('Ошибка уведомления сервера об остановке микрофона:', error);
        }

        this.isMicStreaming = false;
        this.updateButtonStates();
        console.log('Трансляция микрофона остановлена');
    }

    // --- Общее управление ---

    async stopAll() {
        console.log('Остановка всех аудио процессов');
        
        // Останавливаем локальное воспроизведение MP3
        if (this.isPlaying) {
            await this.stopLocalPlayback();
        }

        // Останавливаем трансляцию микрофона
        if (this.isMicStreaming) {
            await this.stopMicrophoneStream();
        }

        this.updateButtonStates();
        console.log('Все аудио процессы остановлены');
    }

    updateButtonStates() {
        // Убираем все активные состояния
        document.querySelectorAll('.audio-button').forEach(btn => {
            btn.classList.remove('playing', 'recording');
        });

        // Показываем состояние MP3
        if (this.isPlaying && this.currentSound) {
            const btnId = this.currentSound === 'sound1' ? 'playSound1' : 'playSound2';
            const currentBtn = document.getElementById(btnId);
            if (currentBtn) {
                currentBtn.classList.add('playing');
            }
        }

        // Показываем состояние микрофона
        if (this.isMicStreaming) {
            this.startMicBtn.classList.add('recording');
            this.startMicBtn.textContent = 'Стрим идет...';
        } else {
            this.startMicBtn.textContent = 'Микрофон';
        }
    }

    showError(message) {
        console.error(message);
        
        // Временно меняем текст кнопки стоп для индикации ошибки
        const originalText = this.stopAllBtn.textContent;
        this.stopAllBtn.textContent = 'Ошибка!';
        this.stopAllBtn.style.backgroundColor = '#ff4444';
        
        setTimeout(() => {
            this.stopAllBtn.textContent = originalText;
            this.stopAllBtn.style.backgroundColor = '';
        }, 2000);
    }

    // --- Статус и отладка ---

    getStatus() {
        return {
            // Локальное MP3
            isPlaying: this.isPlaying,
            currentSound: this.currentSound,
            // WebRTC микрофон
            isMicStreaming: this.isMicStreaming,
            webrtcConnected: this.webrtcConnection?.connectionState === 'connected'
        };
    }

    async getServerStatus() {
        try {
            const response = await fetch(`${this.baseUrl}/status`);
            if (response.ok) {
                const status = await response.json();
                console.log('Статус сервера:', status);
                return status;
            }
        } catch (error) {
            console.error('Ошибка получения статуса сервера:', error);
        }
        return null;
    }
}

// Инициализация после загрузки DOM
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализация AudioController...');
    
    setTimeout(() => {
        window.audioController = new AudioController();
        console.log('AudioController готов к использованию');
        
        // Получить начальный статус с сервера
        window.audioController.getServerStatus();
    }, 100);
});
