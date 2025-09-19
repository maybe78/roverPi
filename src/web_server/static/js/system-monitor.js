// static/js/system-monitor.js

class SystemMonitor {
    constructor() {
        this.updateInterval = null;
        this.isActive = false;
    }
    
    start() {
        if (this.isActive) return;
        
        this.isActive = true;
        this.updateSystemStats();
        
        // Обновляем каждые 2 секунды
        this.updateInterval = setInterval(() => {
            this.updateSystemStats();
        }, 2000);
        
        console.log('System monitor started');
    }
    
    stop() {
        if (!this.isActive) return;
        
        this.isActive = false;
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        console.log('System monitor stopped');
    }
    
    async updateSystemStats() {
        try {
            const response = await fetch('/system-status');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateUI(data);
            }
            
        } catch (error) {
            console.error('Ошибка получения системного статуса:', error);
        }
    }
    
    updateUI(data) {
        // CPU
        this.updateProgressBar('cpu', data.cpu.percent);
        this.updateText('cpu-percent', `${data.cpu.percent}%`);
        
        // Memory
        this.updateProgressBar('memory', data.memory.percent);
        this.updateText('memory-percent', `${data.memory.percent}%`);
        this.updateText('memory-text', 
            `${this.formatBytes(data.memory.used)} / ${this.formatBytes(data.memory.total)}`);
        
        // Swap
        this.updateProgressBar('swap', data.swap.percent);
        this.updateText('swap-percent', `${data.swap.percent}%`);
        this.updateText('swap-text', 
            `${this.formatBytes(data.swap.used)} / ${this.formatBytes(data.swap.total)}`);
        
        // Temperature
        if (data.cpu.temperature) {
            this.updateText('temperature', `🌡️ ${data.cpu.temperature.toFixed(1)}°C`);
        }
    }
    
    updateProgressBar(id, percent) {
        const bar = document.getElementById(`${id}-bar`);
        if (bar) {
            bar.style.width = `${Math.min(percent, 100)}%`;
        }
    }
    
    updateText(id, text) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = text;
        }
    }
    
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

// Инициализация после загрузки DOM
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        window.systemMonitor = new SystemMonitor();
        window.systemMonitor.start();
        console.log('System monitor готов');
    }, 500);
});
