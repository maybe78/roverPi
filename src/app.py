from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from threading import Lock
from web_commands import WebCommands

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

# Thread-safe command storage object
web_commands = WebCommands()
thread_lock = Lock()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('control')
def handle_control(data):
    # Expecting dict with keys "lx", "ly"
    lx = float(data.get('lx', 0))
    ly = float(data.get('ly', 0))

    # Simple transform, invert Y axis
    left_speed = int(lx * 100)  # example scaling
    right_speed = int(ly * 100)

    # Save commands
    web_commands.set_speed(left_speed, right_speed)

    emit('ack', {'ls': left_speed, 'rs': right_speed})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)