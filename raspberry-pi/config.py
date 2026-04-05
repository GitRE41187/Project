"""Configuration and constants."""
import os

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv()
except Exception:
    # Keep working even if python-dotenv is not installed in current interpreter.
    pass


def get_local_ip():
    """Get the local IP address of the Raspberry Pi."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


UPLOAD_FOLDER = 'user_codes'

# Built-in scripts shipped with the Pi app (same folder as in repo: raspberry-pi/static_codes).
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_CODES_DIR = os.path.normpath(os.path.join(_PKG_DIR, 'static_codes'))
# Local Flask /health only (tiny JSON); limit kept for consistency if extended later.
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(15 * 1024 * 1024)))

ROBOT_CAR_ID = os.getenv('ROBOT_CAR_ID', 'robot-001')
ROBOT_CAR_NAME = os.getenv('ROBOT_CAR_NAME', 'Alpha Bot')
ROBOT_CAR_IP = os.getenv('ROBOT_CAR_IP', get_local_ip())

# Local HTTP port (Flask /health only). Same value is sent to the hub for display.
ROBOT_CAR_PORT = int(os.getenv('ROBOT_CAR_PORT', os.getenv('PORT', '5001')))

# Backend base URL; SignalR hub is {SERVER_URL}/hubs/robot. Alias: BACKEND_URL
SERVER_URL = os.getenv('SERVER_URL', os.getenv('BACKEND_URL', 'http://127.0.0.1:5000'))

MAX_RECONNECT_ATTEMPTS = 5

# Interpreter used to run user / uploaded scripts on the Pi (use python3 on Raspberry Pi OS).
PYTHON_EXE = os.getenv('PYTHON_EXE', os.getenv('PYTHON', 'python3'))

ALLOWED_IMPORTS = {
    'math', 'random', 'time', 'datetime', 'json', 'os', 'sys',
    'numpy', 'pandas', 'matplotlib', 'requests', 'urllib',
    'collections', 'itertools', 'functools', 'operator', 'Motor', 'ADC', 'GPIO', 'RPi.GPIO', 'RPi'
}
