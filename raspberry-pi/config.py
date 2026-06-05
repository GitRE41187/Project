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

# Interpreter used to bootstrap the runtime (create the venv, etc). Use python3 on Raspberry Pi OS.
PYTHON_EXE = os.getenv('PYTHON_EXE', os.getenv('PYTHON', 'python3'))

ALLOWED_IMPORTS = {
    'math', 'random', 'time', 'datetime', 'json', 'os', 'sys',
    'numpy', 'pandas', 'matplotlib', 'requests', 'urllib',
    'collections', 'itertools', 'functools', 'operator', 'Motor', 'ADC', 'GPIO', 'RPi.GPIO', 'RPi'
}

# --- Isolated run environment ("virtual", docker-like) ---------------------
# How uploaded user code is executed:
#   'venv'  -> dedicated virtual environment on the Pi (default; sees system
#              site-packages so RPi.GPIO / picamera still work, extra pip
#              packages get installed into the venv at upload time).
#   'docker'-> run inside a throwaway container (needs Docker on the host).
#   'none'  -> run with PYTHON_EXE directly (legacy behaviour).
RUN_SANDBOX = os.getenv('RUN_SANDBOX', 'venv').strip().lower()

# Dedicated virtual environment used to run user code.
VENV_DIR = os.getenv('VENV_DIR', os.path.join(_PKG_DIR, '.runtime-venv'))

# Install missing third-party packages found in uploaded code at upload time
# (so they are ready before the user presses Run, instead of failing mid-run).
AUTO_INSTALL_DEPENDENCIES = os.getenv('AUTO_INSTALL_DEPENDENCIES', 'true').strip().lower() in ('1', 'true', 'yes', 'on')

# Only auto-install packages whose top-level import name is in ALLOWED_IMPORTS
# (keeps the security whitelist meaningful). Set to false to install anything
# the code imports (relies on the sandbox for safety).
RESTRICT_INSTALL_TO_WHITELIST = os.getenv('RESTRICT_INSTALL_TO_WHITELIST', 'true').strip().lower() in ('1', 'true', 'yes', 'on')

# Optional pip mirror + timeout for slow links (e.g. on a Pi behind a proxy).
PIP_INDEX_URL = os.getenv('PIP_INDEX_URL', '').strip()
PIP_TIMEOUT = int(os.getenv('PIP_TIMEOUT', '120'))

# Resource caps for a single user run (POSIX only; ignored on Windows dev box).
RUN_MEMORY_LIMIT_MB = int(os.getenv('RUN_MEMORY_LIMIT_MB', '512'))   # 0 = unlimited
RUN_CPU_SECONDS = int(os.getenv('RUN_CPU_SECONDS', '0'))            # 0 = unlimited

# Docker backend tuning (only used when RUN_SANDBOX == 'docker').
DOCKER_IMAGE = os.getenv('DOCKER_IMAGE', 'python:3.11-slim')
DOCKER_MEMORY = os.getenv('DOCKER_MEMORY', '512m')
DOCKER_CPUS = os.getenv('DOCKER_CPUS', '1')
# 'none' disables network inside the container; 'bridge' allows it.
DOCKER_NETWORK = os.getenv('DOCKER_NETWORK', 'none')
