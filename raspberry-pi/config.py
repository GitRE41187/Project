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
    'collections', 'itertools', 'functools', 'operator', 'Motor', 'ADC', 'GPIO', 'RPi.GPIO', 'RPi',
    'lgpio',
}

# --- Isolated run environment ("virtual", docker-like) ---------------------
# How uploaded user code is executed:
#   'venv'  -> dedicated virtual environment on the Pi (default; sees system
#              site-packages so RPi.GPIO / picamera still work, extra pip
#              packages get installed into the venv at upload time).
#   'docker'-> run inside a throwaway container (needs Docker on the host).
#   'none'  -> run with PYTHON_EXE directly (legacy behaviour).
RUN_SANDBOX = os.getenv('RUN_SANDBOX', 'venv').strip().lower()

# Extra paths to add to PYTHONPATH when running user code.
# ใช้สำหรับ hardware modules เช่น Motor.py, ADC.py ของ Freenove kit
# ตัวอย่าง: EXTRA_PYTHONPATH=/home/huntrix/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server
EXTRA_PYTHONPATH = [p for p in os.getenv('EXTRA_PYTHONPATH', '').split(':') if p.strip()]

# Dedicated virtual environment used to run user code.
VENV_DIR = os.getenv('VENV_DIR', os.path.join(_PKG_DIR, '.runtime-venv'))

# After a user script ends (or is stopped), drive the robot back to its approximate
# starting position by replaying recorded motor commands in reverse (dead reckoning).
RETURN_HOME_ON_STOP = os.getenv('RETURN_HOME_ON_STOP', 'false').strip().lower() in ('1', 'true', 'yes', 'on')

# 'hybrid'  = auto for learning platform (line → direct → retrace)
# 'retrace' = always replay path in reverse
# 'direct'  = always odometry then straight back
# 'line'    = reverse along the field line using the IR sensors (falls back to retrace)
RETURN_HOME_MODE = os.getenv('RETURN_HOME_MODE', 'hybrid').strip().lower()

# Hybrid thresholds: path is "simple" (use direct) only if ALL are within limits
HYBRID_MAX_TURN_SEGMENTS = int(os.getenv('HYBRID_MAX_TURN_SEGMENTS', '2'))
HYBRID_MAX_MOVE_TIME = float(os.getenv('HYBRID_MAX_MOVE_TIME', '4.0'))
HYBRID_MAX_DIST_M = float(os.getenv('HYBRID_MAX_DIST_M', '1.2'))
HYBRID_MAX_YAW_DEG = float(os.getenv('HYBRID_MAX_YAW_DEG', '60'))

# Line-following return: U-turn on the spot, then follow the line forward until
# the wide start pad. Hybrid tries it automatically when the finished script read
# the IR sensors; RETURN_HOME_LINE_FIRST=true forces it on every run.
RETURN_HOME_LINE_FIRST = os.getenv('RETURN_HOME_LINE_FIRST', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
LINE_IR_LEFT = int(os.getenv('LINE_IR_LEFT', '14'))
LINE_IR_MIDDLE = int(os.getenv('LINE_IR_MIDDLE', '15'))
LINE_IR_RIGHT = int(os.getenv('LINE_IR_RIGHT', '23'))
LINE_RETURN_SPEED = int(os.getenv('LINE_RETURN_SPEED', '650'))
LINE_RETURN_TURN_SPEED = int(os.getenv('LINE_RETURN_TURN_SPEED', '900'))
LINE_RETURN_PIVOT_SPEED = int(os.getenv('LINE_RETURN_PIVOT_SPEED', '1500'))
LINE_RETURN_MAX_SECS = float(os.getenv('LINE_RETURN_MAX_SECS', '30'))
# ช่วงแรกยังคร่อมแผ่นจบอยู่ — อย่านับว่าเป็นแผ่นเริ่ม
LINE_RETURN_IGNORE_PAD_SECS = float(os.getenv('LINE_RETURN_IGNORE_PAD_SECS', '2.0'))
LINE_RETURN_PAD_HOLD = float(os.getenv('LINE_RETURN_PAD_HOLD', '1.0'))
LINE_RETURN_LOST_GIVE_UP = float(os.getenv('LINE_RETURN_LOST_GIVE_UP', '2.5'))
# วิ่งเกินเวลานี้แล้วยังไม่ถึงแผ่นเริ่ม — ห้าม replay log ทับ (จะยิ่งเพี้ยน)
LINE_RETURN_NO_FALLBACK_AFTER = float(os.getenv('LINE_RETURN_NO_FALLBACK_AFTER', '2.5'))
# กลับหลังหัน: 0 = คำนวณจาก ODOMETRY_TURN_RATE/SCALE, >0 = กำหนดวินาทีเอง
LINE_RETURN_UTURN_SECS = float(os.getenv('LINE_RETURN_UTURN_SECS', '0'))
LINE_RETURN_UTURN_DIR = os.getenv('LINE_RETURN_UTURN_DIR', 'left').strip().lower()

# Odometry calibration (used only when RETURN_HOME_MODE=direct)
# ODOMETRY_SPEED_SCALE: meters per second per duty unit  (tune by measuring: at duty=2000 how fast in m/s?)
# ODOMETRY_WHEEL_BASE: distance (meters) between left and right wheel centres
# ODOMETRY_RETURN_SPEED: duty value used for both turning and driving back
# ODOMETRY_DUTY3_INVERTED: set true if right_upper_wheel is wired in reverse (Freenove quirk)
ODOMETRY_SPEED_SCALE = float(os.getenv('ODOMETRY_SPEED_SCALE', '0.00015'))  # m/s per duty unit
ODOMETRY_WHEEL_BASE = float(os.getenv('ODOMETRY_WHEEL_BASE', '0.14'))  # meters
ODOMETRY_RETURN_SPEED = int(os.getenv('ODOMETRY_RETURN_SPEED', '1500'))
ODOMETRY_DUTY3_INVERTED = os.getenv('ODOMETRY_DUTY3_INVERTED', 'true').strip().lower() in ('1', 'true', 'yes')
# Turn rate in rad/s at turn duty — calibrate by measuring time for 360° rotation
ODOMETRY_TURN_RATE = float(os.getenv('ODOMETRY_TURN_RATE', '3.21'))  # default ~184 °/s at duty=1500
# Scale turn duration: >1 = หมุนนานขึ้น (ถ้ารถใหญ่หมุนไม่พอ), <1 = หมุนสั้นลง (หมุนเกิน)
ODOMETRY_TURN_SCALE = float(os.getenv('ODOMETRY_TURN_SCALE', '1.0'))
# Duty ตอนหมุนกลับบ้าน (0 = ใช้ ODOMETRY_RETURN_SPEED) — รถใหญ่มักต้องสูงกว่าตอนวิ่งตรง
ODOMETRY_TURN_SPEED = int(os.getenv('ODOMETRY_TURN_SPEED', '0'))
# พักหลังหมุนก่อนวิ่งตรง (วินาที) — ช่วยให้หัวนิ่ง
ODOMETRY_TURN_SETTLE = float(os.getenv('ODOMETRY_TURN_SETTLE', '0.35'))

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
