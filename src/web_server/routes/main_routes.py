from flask import Blueprint, render_template, jsonify
import psutil
import logging

logger = logging.getLogger('rover')
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Отдает главную HTML-страницу."""
    return render_template('index.html')

@main_bp.route('/status')
def status():
    """Простой статус для проверки работоспособности."""
    return {'status': 'ok', 'message': 'RoverPi Web Server is running'}

@main_bp.route('/system-status')
def system_status():
    """Возвращает статус системных ресурсов."""
    try:
        # Получаем системную информацию
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage('/')
        
        # Температура CPU (если доступна на Raspberry Pi)
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000.0
        except:
            temp = None
        
        return jsonify({
            "status": "success",
            "cpu": {
                "percent": round(cpu_percent, 1),
                "temperature": temp
            },
            "memory": {
                "total": memory.total,
                "used": memory.used,
                "available": memory.available,
                "percent": round(memory.percent, 1)
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": round(swap.percent, 1)
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": round((disk.used / disk.total) * 100, 1)
            }
        })
    
    except Exception as e:
        logger.error(f"Ошибка получения статуса системы: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500