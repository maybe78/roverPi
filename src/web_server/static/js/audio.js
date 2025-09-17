// static/js/audio-control.js

class AudioController {
    constructor() {
        this.isPlaying = false;
        this.isRecording = false;
        this.currentSound = null;
        this.baseUrl = '/audio'; // Префикс для аудио маршрутов
        this.initializeButtons();
        console.log('AudioController инициализирован');
    }

    initializeButtons() {
        this.playSound1Btn = document.getElementById('playSound1');
        this.playSound2Btn = document.getElementById('playSound2');
        this.startMicBtn = document.getElementById('startMic');
        this.stopAllBtn = document.getElementById('stopAll');

        this.playSound1Btn.addEventListener('click', () => this.playSound('sound1'));
        this.playSound2Btn.addEventListener('click', () => this.playSound('sound2'));
        this.startMicBtn.addEventListener('click', () => this.toggleMicrophone());
        this.stopAllBtn.addEventListener('click', () => this.stopAll());

        console.log('Обработчики событий аудиокнопок привязаны');
    }

    async sendAudioCommand(endpoint, data = {}) {
        try {
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

    async playSound(soundName) {
        console.log(`Попытка воспроизвести звук: ${soundName}`);
        
        if (this.isPlaying || this.isRecording) {
            await this.stopAll();
        }

        const result = await this.sendAudioCommand(`/play/${soundName}`);
        
        if (result && result.status === 'success') {
            this.isPlaying = true;
            this.currentSound = soundName;
            this.updateButtonStates();
            console.log(`Звук ${soundName} запущен`);
        } else {
            console.error(`Ошибка при воспроизведении ${soundName}:`, result.message);
        }
    }

    async toggleMicrophone() {
        if (this.isRecording) {
            await this.stopAll();
        } else {
            console.log('Запуск записи с микрофона (пока заглушка)');
            
            const result = await this.sendAudioCommand('/start_microphone');
            
            if (result && result.status === 'success') {
                this.isRecording = true;
                this.updateButtonStates();
                console.log('Запись с микрофона активирована (заглушка)');
            } else {
                console.error('Ошибка при запуске микрофона:', result.message);
            }
        }
    }

    async stopAll() {
        console.log('Остановка всех аудио процессов');
        
        const result = await this.sendAudioCommand('/stop');
        
        if (result && result.status === 'success') {
            this.isPlaying = false;
            this.isRecording = false;
            this.currentSound = null;
            this.updateButtonStates();
            console.log('Все аудио процессы остановлены');
        } else {
            console.error('Ошибка при остановке аудио:', result.message);
        }
    }

    updateButtonStates() {
        document.querySelectorAll('.audio-button').forEach(btn => {
            btn.classList.remove('playing', 'recording');
        });

        if (this.isRecording) {
            this.startMicBtn.classList.add('recording');
            this.startMicBtn.textContent = 'Запись...';
        } else {
            this.startMicBtn.textContent = 'Микрофон';
        }

        if (this.isPlaying && this.currentSound) {
            const btnId = this.currentSound === 'sound1' ? 'playSound1' : 'playSound2';
            const currentBtn = document.getElementById(btnId);
            if (currentBtn) {
                currentBtn.classList.add('playing');
            }
        }
    }

    getStatus() {
        return {
            isPlaying: this.isPlaying,
            isRecording: this.isRecording,
            currentSound: this.currentSound
        };
    }
}

document.addEventListener('DOMContentLoaded', function() {
    window.audioController = new AudioController();
    console.log('AudioController готов к использованию');
});
