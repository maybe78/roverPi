// static/js/audio-control.js

class AudioController {
    constructor() {
        // Состояние локального воспроизведения MP3 на Raspberry Pi
        this.isPlaying = false;
        this.currentSound = null;

        // Настройки
        this.baseUrl = '/audio';
        
        this.initializeButtons();
        console.log('AudioController инициализирован');
    }

    initializeButtons() {
        // Получаем ссылки на кнопки
        this.playSound1Btn = document.getElementById('playSound1');
        this.playSound2Btn = document.getElementById('playSound2');
        this.stopAllBtn = document.getElementById('stopAll');
        this.ttsInput = document.getElementById('ttsInput');
        this.speakBtn = document.getElementById('speakBtn');

        console.log('TTS элементы:', this.ttsInput, this.speakBtn);
        console.log('ttsInput найден:', !!this.ttsInput);
        console.log('speakBtn найден:', !!this.speakBtn);

        // Проверяем, что основные кнопки найдены
        if (!this.playSound1Btn || !this.playSound2Btn || !this.stopAllBtn) {
            console.error('Не все аудио-кнопки найдены в DOM!');
            return;
        }

        // TTS обработчики
        if (this.speakBtn && this.ttsInput) {
            console.log('✅ Привязываем TTS обработчики');
            
            this.speakBtn.addEventListener('click', () => {
                const text = this.ttsInput.value;
                console.log('🔊 TTS кнопка нажата, текст:', text);
                if (text.trim()) {
                    this.speakText(text);
                    this.ttsInput.value = ''; // Очищаем поле
                } else {
                    console.log('❌ Текст пустой');
                }
            });
            
            // Enter для озвучивания
            this.ttsInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    console.log('⌨️ Enter нажат в TTS поле');
                    this.speakBtn.click();
                }
            });
        } else {
            console.error('❌ TTS элементы не найдены в DOM!');
        }
        
        // Привязываем обработчики событий
        this.playSound1Btn.addEventListener('click', () => this.playSound('sound1'));
        this.playSound2Btn.addEventListener('click', () => this.playSound('sound2'));
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
        
        // Останавливаем текущие MP3
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

    // --- Text-to-Speech ---

    async speakText(text) {
        if (!text || !text.trim()) {
            console.error('Нельзя озвучить пустой текст');
            return;
        }
        
        try {
            console.log(`Озвучиваем текст: "${text}"`);
            
            const result = await this.sendAudioCommand('/speak', { text: text.trim() });
            
            if (result && result.status === 'success') {
                console.log('TTS запущен на Raspberry Pi');
                // Можно добавить визуальную индикацию
            } else {
                console.error('Ошибка TTS:', result.message);
                this.showError('Ошибка озвучивания');
            }
        } catch (error) {
            console.error('Исключение TTS:', error);
            this.showError('Ошибка озвучивания');
        }
    }

    // --- Общее управление ---

    async stopAll() {
        console.log('Остановка всех аудио процессов');
        
        // Останавливаем локальное воспроизведение MP3
        if (this.isPlaying) {
            await this.stopLocalPlayback();
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
            isPlaying: this.isPlaying,
            currentSound: this.currentSound
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
