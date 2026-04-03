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
ALLOWED_EXTENSIONS = {'py'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
# Flask / Werkzeug: max JSON body (base64 upload from ASP.NET)
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(15 * 1024 * 1024)))

ROBOT_CAR_ID = os.getenv('ROBOT_CAR_ID', 'robot-001')
ROBOT_CAR_NAME = os.getenv('ROBOT_CAR_NAME', 'Alpha Bot')
ROBOT_CAR_IP = os.getenv('ROBOT_CAR_IP', get_local_ip())

# Backward compatible:
# - Preferred: ROBOT_CAR_PORT
# - Legacy: PORT
ROBOT_CAR_PORT = int(os.getenv('ROBOT_CAR_PORT', os.getenv('PORT', '5001')))

# Preferred for ASP.NET backend integration:
# - SERVER_URL=http://<backend-host>:5000
# Alias accepted: BACKEND_URL
SERVER_URL = os.getenv('SERVER_URL', os.getenv('BACKEND_URL', 'http://127.0.0.1:5000'))

MAX_RECONNECT_ATTEMPTS = 5
ALLOWED_IMPORTS = {
    'math', 'random', 'time', 'datetime', 'json', 'os', 'sys',
    'numpy', 'pandas', 'matplotlib', 'requests', 'urllib',
    'collections', 'itertools', 'functools', 'operator'
}
