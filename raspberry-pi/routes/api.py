"""API routes - health, upload, run, stop, reset, control, cleanup."""
import os
import shutil
import time
from datetime import datetime
from typing import Tuple

from flask import Blueprint, request, jsonify, Response

from config import (
    UPLOAD_FOLDER, ROBOT_CAR_ID, ROBOT_CAR_NAME,
    ALLOWED_IMPORTS, MAX_RECONNECT_ATTEMPTS
)
from state import running_processes, current_user
from utils import json_ok, json_error, validate_python_code, log_debug
from services.code_runner import run_user_code, stop_user_code, reset_field
from services.camera import camera_active, release_camera

api_bp = Blueprint('api', __name__)


def _get_signalr():
    from signalr_client import hub_connection, ws_connected, last_connect_time, last_heartbeat_time
    return hub_connection, ws_connected, last_connect_time, last_heartbeat_time


@api_bp.route('/health', methods=['GET'])
def health_check():
    hub, ws, lct, lht = _get_signalr()
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'running_processes': len(running_processes),
        'current_user': current_user,
        'camera_active': camera_active,
        'ws_connected': ws,
        'robot_id': ROBOT_CAR_ID,
        'robot_name': ROBOT_CAR_NAME,
        'last_connect_time': lct,
        'last_heartbeat_time': lht
    })


@api_bp.route('/upload_code', methods=['POST'])
def upload_code():
    hub, ws, _, _ = _get_signalr()
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        file_path = data.get('file_path')
        original_filename = data.get('original_filename')

        if not user_id or not file_path:
            return json_error('user_id and file_path are required', 400)

        user_filename = f"user_{user_id}.py"
        user_file_path = os.path.join(UPLOAD_FOLDER, user_filename)

        if os.path.exists(file_path):
            shutil.copy2(file_path, user_file_path)
            is_safe, message = validate_python_code(user_file_path, ALLOWED_IMPORTS)
            if not is_safe:
                os.remove(user_file_path)
                return json_error(f'Code validation failed: {message}', 400)

            if ws and hub:
                hub.send("RobotCodeUploaded", [{
                    'carId': ROBOT_CAR_ID, 'userId': user_id, 'filename': user_filename,
                    'original': original_filename, 'size': os.path.getsize(user_file_path),
                    'timestamp': datetime.now().isoformat()
                }])
            log_debug('code-uploaded', {'userId': user_id, 'filename': user_filename}, hub, ws)

            return json_ok({'message': 'Code uploaded successfully', 'user_id': user_id, 'filename': user_filename, 'validation': message})
        return json_error('Source file not found', 404)
    except Exception as e:
        return json_error(f'Upload failed: {str(e)}', 500)


@api_bp.route('/run', methods=['POST'])
def run_code():
    import state
    hub, ws, _, _ = _get_signalr()
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return json_error('user_id is required', 400)
        if current_user and current_user != user_id:
            return json_error(f'User {current_user} is currently using the field', 409)

        user_file_path = os.path.join(UPLOAD_FOLDER, f"user_{user_id}.py")
        if not os.path.exists(user_file_path):
            return json_error('No code uploaded for this user', 404)
        uid = str(user_id)
        if uid in running_processes:
            stop_user_code(uid)

        success, message = run_user_code(uid, user_file_path, ALLOWED_IMPORTS)
        if success:
            state.current_user = str(user_id)
            log_debug('code-run-started', {'userId': user_id}, hub, ws)
            if ws and hub:
                uid = int(user_id) if str(user_id).isdigit() else None
                hub.send("RobotStatus", [ROBOT_CAR_ID, 'running', uid])
            return json_ok({'message': message, 'user_id': user_id, 'status': 'running'})
        return json_error(message, 500)
    except Exception as e:
        return json_error(f'Run failed: {str(e)}', 500)


@api_bp.route('/stop', methods=['POST'])
def stop_code():
    import state
    hub, ws, _, _ = _get_signalr()
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return json_error('user_id is required', 400)
        success, message = stop_user_code(user_id)
        if success:
            if state.current_user == str(user_id):
                state.current_user = None
            log_debug('code-run-stopped', {'userId': user_id}, hub, ws)
            if ws and hub:
                uid = int(user_id) if str(user_id).isdigit() else None
                hub.send("RobotStatus", [ROBOT_CAR_ID, 'idle', uid])
            return json_ok({'message': message, 'user_id': user_id, 'status': 'stopped'})
        return json_error(message, 404)
    except Exception as e:
        return json_error(f'Stop failed: {str(e)}', 500)


@api_bp.route('/reset', methods=['POST'])
def reset_field_endpoint():
    hub, ws, _, _ = _get_signalr()
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return json_error('user_id is required', 400)
        if current_user != user_id:
            return json_error('Only the current user can reset the field', 403)
        success, message = reset_field()
        if success:
            log_debug('field-reset', {'userId': user_id}, hub, ws)
            return json_ok({'message': message, 'user_id': user_id, 'status': 'reset'})
        return json_error(message, 500)
    except Exception as e:
        return json_error(f'Reset failed: {str(e)}', 500)


@api_bp.route('/status/<int:user_id>', methods=['GET'])
def get_status(user_id):
    hub, ws, lct, lht = _get_signalr()
    try:
        uid = str(user_id)
        is_running = uid in running_processes
        is_current = current_user == uid
        status = {
            'user_id': user_id, 'is_running': is_running, 'is_current_user': is_current,
            'current_user': current_user, 'running_processes': list(running_processes.keys()),
            'timestamp': datetime.now().isoformat(), 'ws_connected': ws,
            'last_connect_time': lct, 'last_heartbeat_time': lht
        }
        if is_running:
            p = running_processes.get(uid)
            if p:
                status['process_status'] = p.poll()
                status['is_alive'] = p.poll() is None
        return jsonify(status)
    except Exception as e:
        return json_error(f'Status check failed: {str(e)}', 500)


def perform_move(direction: str, duration: float = 0.5) -> Tuple[bool, str]:
    hub, ws, _, _ = _get_signalr()
    try:
        allowed = {'front', 'back', 'left', 'right'}
        if direction not in allowed:
            return False, f'Invalid direction: {direction}'
        log_debug('move-command-received', {'direction': direction, 'duration': duration}, hub, ws)
        import time
        time.sleep(min(max(duration, 0.1), 3.0))
        log_debug('move-command-completed', {'direction': direction}, hub, ws)
        if ws and hub:
            hub.send("RobotDebug", [{'carId': ROBOT_CAR_ID, 'event': 'robot-control-ack', 'direction': direction, 'duration': duration}])
        return True, f'Move {direction} executed'
    except Exception as e:
        return False, f'Move error: {str(e)}'


@api_bp.route('/control/front', methods=['POST'])
def control_front():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('front', duration)
    return json_ok({'message': msg}) if ok else json_error(msg, 400)


@api_bp.route('/control/back', methods=['POST'])
def control_back():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('back', duration)
    return json_ok({'message': msg}) if ok else json_error(msg, 400)


@api_bp.route('/control/left', methods=['POST'])
def control_left():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('left', duration)
    return json_ok({'message': msg}) if ok else json_error(msg, 400)


@api_bp.route('/control/right', methods=['POST'])
def control_right():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('right', duration)
    return json_ok({'message': msg}) if ok else json_error(msg, 400)


@api_bp.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        for uid in list(running_processes.keys()):
            stop_user_code(uid)
        if camera_active:
            release_camera()
        current_time = time.time()
        cleaned_files = 0
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                if current_time - os.path.getmtime(file_path) > 24 * 3600:
                    os.remove(file_path)
                    cleaned_files += 1
        return jsonify({
            'message': 'Cleanup completed', 'cleaned_files': cleaned_files,
            'stopped_processes': len(running_processes), 'camera_stopped': True
        })
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500
