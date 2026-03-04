"""Utility functions."""
from datetime import datetime
from flask import jsonify
from typing import Dict, Any

from config import UPLOAD_FOLDER, ROBOT_CAR_ID


def json_ok(payload: Dict[str, Any], status_code: int = 200):
    payload.setdefault('timestamp', datetime.now().isoformat())
    return jsonify(payload), status_code


def json_error(message: str, status_code: int = 400, **extra):
    pay = {'error': message, 'timestamp': datetime.now().isoformat()}
    if extra:
        pay.update(extra)
    return jsonify(pay), status_code


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'py'}


def validate_python_code(file_path: str, allowed_imports: set) -> tuple:
    """Validate Python code for safety. Returns (is_safe, message)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                if line.startswith('import '):
                    module = line.split('import ')[1].split()[0].split('.')[0]
                else:
                    module = line.split('from ')[1].split()[0].split('.')[0]
                if module not in allowed_imports:
                    return False, f"Import '{module}' is not allowed"

        dangerous_functions = ['eval', 'exec', 'open', 'file', '__import__']
        for func in dangerous_functions:
            if func in content:
                return False, f"Function '{func}' is not allowed"

        return True, "Code is safe"
    except Exception as e:
        return False, f"Error validating code: {str(e)}"


def log_debug(event: str, data: Dict[str, Any] = None, hub_conn=None, ws_conn=False):
    """Log and emit debug info to server."""
    try:
        stamp = datetime.now().isoformat()
        payload = {
            'carId': ROBOT_CAR_ID,
            'event': event,
            'data': data or {},
            'timestamp': stamp
        }
        print(f"[DEBUG {stamp}] {event}: {payload['data']}")
        if ws_conn and hub_conn:
            hub_conn.send("RobotDebug", [payload])
    except Exception as e:
        print(f"❌ Failed to emit debug: {e}")
