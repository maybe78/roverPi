from flask import Blueprint, render_template, current_app

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Отдает главную HTML-страницу."""
    return render_template('index.html')

@main_bp.route('/status')
def status():
    """Простой статус для проверки работоспособности."""
    return {'status': 'ok', 'message': 'RoverPi Web Server is running'}
