// Этот скрипт будет управлять кнопками аудиопанели

document.addEventListener('DOMContentLoaded', () => {
    // Убедимся, что DOM полностью загружен, прежде чем навешивать события

    /**
     * Отправляет POST-запрос на указанный эндпоинт на сервере.
     * @param {string} endpoint - URL-адрес для запроса (например, '/audio/stop').
     */
    function sendAudioCommand(endpoint) {
        console.log(`Отправка аудио-команды на: ${endpoint}`);
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                // Если сервер ответил ошибкой, выводим ее
                throw new Error(`Сетевой ответ не был успешным: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Ответ сервера:', data);
        })
        .catch(error => {
            console.error('Произошла ошибка при отправке аудио-команды:', error);
        });
    }

    // Находим кнопки по их ID и назначаем им действия
    const playSound1Btn = document.getElementById('playSound1');
    const playSound2Btn = document.getElementById('playSound2');
    const startMicBtn = document.getElementById('startMic');
    const stopAllAudioBtn = document.getElementById('stopAllAudio');

    if (playSound1Btn) {
        playSound1Btn.onclick = () => sendAudioCommand('/audio/play/police');
    }
    
    if (playSound2Btn) {
        playSound2Btn.onclick = () => sendAudioCommand('/audio/play/sound2');
    }
    
    if (startMicBtn) {
        // Пока для микрофона используем заглушку, которая проиграет файл на сервере
        startMicBtn.onclick = () => sendAudioCommand('/audio/play/mic_placeholder');
    }
    
    if (stopAllAudioBtn) {
        stopAllAudioBtn.onclick = () => sendAudioCommand('/audio/stop');
    }
});
