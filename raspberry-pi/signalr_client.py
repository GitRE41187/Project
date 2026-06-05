"""SignalR client - connect to backend ASP.NET hub."""
import base64
import logging
import os
import threading
import time
from datetime import datetime

from signalrcore.hub_connection_builder import HubConnectionBuilder

from config import (
    ROBOT_CAR_ID,
    ROBOT_CAR_NAME,
    ROBOT_CAR_IP,
    ROBOT_CAR_PORT,
    SERVER_URL,
    MAX_RECONNECT_ATTEMPTS,
    UPLOAD_FOLDER,
    ALLOWED_IMPORTS,
    AUTO_INSTALL_DEPENDENCIES,
    RESTRICT_INSTALL_TO_WHITELIST,
)
from state import (
    append_execution_log,
    clear_execution_log,
    get_execution_log_lines,
    running_filename_by_user,
    running_processes,
)
from utils import log_debug, validate_python_code
from user_scripts import (
    list_user_py_files,
    safe_py_filename,
    user_script_subdir,
    legacy_user_script_path,
    resolve_script_path,
    perform_move,
)

hub_connection = None
ws_connected = False
ws_reconnect_attempts = 0
last_connect_time = None
last_heartbeat_time = None
connection_lock = threading.Lock()
connecting_in_progress = False
camera_stream_thread_started = False


def get_hub_url():
    return f"{SERVER_URL.rstrip('/')}/hubs/robot"


def _emit_deploy_result(user_id: str, success: bool, message: str, filename: str = None):
    if hub_connection and ws_connected:
        payload = {'carId': ROBOT_CAR_ID, 'userId': user_id, 'success': success, 'message': message}
        if filename:
            payload['filename'] = filename
        hub_connection.send("DeployResult", [payload])


def _install_deps_for(user_id, file_path: str) -> dict:
    """Pre-install third-party packages imported by the uploaded file so the
    run never fails with ModuleNotFoundError. Streams progress to the user's
    execution log. Returns the install report (or None if disabled)."""
    if not AUTO_INSTALL_DEPENDENCIES:
        return None
    uid = str(user_id)
    try:
        from services.environment import install_dependencies
        return install_dependencies(
            file_path,
            allowed_imports=ALLOWED_IMPORTS,
            restrict_to_whitelist=RESTRICT_INSTALL_TO_WHITELIST,
            log_fn=lambda line: append_execution_log(uid, line),
        )
    except Exception as e:  # never block an upload on the installer
        append_execution_log(uid, f'[deps] dependency install error: {e}')
        return {'installed': [], 'skipped': [], 'failed': [], 'requested': [], 'error': str(e)}


def _emit_command_result(correlation_id: str, command: str, success: bool, status_code: int = 200, payload=None, error: str = None):
    if not hub_connection or not ws_connected:
        return
    result = {
        'correlationId': correlation_id,
        'carId': ROBOT_CAR_ID,
        'command': command,
        'success': success,
        'statusCode': status_code,
        'payload': payload or {},
        'respondedAt': datetime.utcnow().isoformat() + 'Z'
    }
    if error:
        result['error'] = error
    hub_connection.send("RobotCommandResult", [result])


def _on_robot_command_request(args):
    try:
        req = args[0] if args else {}
        correlation_id = str(req.get('correlationId') or req.get('CorrelationId') or '')
        command = str(req.get('command') or req.get('Command') or '')
        payload = req.get('payload') if req.get('payload') is not None else req.get('Payload')
        payload = payload if isinstance(payload, dict) else {}
        if not correlation_id or not command:
            return

        import state
        from services.code_runner import run_user_code, stop_user_code, reset_field
        from services.camera import camera_active, init_camera, release_camera

        if command == 'list_files':
            user_id = payload.get('user_id')
            if user_id is None or str(user_id) == '':
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            files = list_user_py_files(user_id)
            _emit_command_result(correlation_id, command, True, 200, payload={'user_id': user_id, 'files': files})
            return

        if command == 'upload_code':
            user_id = payload.get('user_id')
            content_b64 = payload.get('content_base64')
            original_filename = payload.get('original_filename') or 'script.py'
            if user_id is None or str(user_id) == '':
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            if not content_b64:
                _emit_command_result(correlation_id, command, False, 400, error='content_base64 is required')
                return
            user_dir = user_script_subdir(user_id)
            os.makedirs(user_dir, exist_ok=True)
            safe_name = safe_py_filename(original_filename)
            dest = os.path.join(user_dir, safe_name)
            try:
                raw = base64.b64decode(content_b64)
            except Exception:
                _emit_command_result(correlation_id, command, False, 400, error='Invalid content_base64')
                return
            with open(dest, 'wb') as f:
                f.write(raw)
            is_safe, message = validate_python_code(dest, ALLOWED_IMPORTS)
            if not is_safe:
                try:
                    os.remove(dest)
                except Exception:
                    pass
                _emit_command_result(correlation_id, command, False, 400, error=f'Code validation failed: {message}')
                return
            deps = _install_deps_for(user_id, dest)
            result_payload = {
                'message': 'Code uploaded successfully',
                'user_id': user_id,
                'filename': safe_name,
                'validation': message,
            }
            if deps is not None:
                result_payload['dependencies'] = deps
                if deps.get('failed'):
                    result_payload['message'] = (
                        'Code uploaded, but some packages failed to install: '
                        + ', '.join(deps['failed'])
                    )
            _emit_command_result(correlation_id, command, True, 200, payload=result_payload)
            return

        if command == 'delete_file':
            user_id = payload.get('user_id')
            filename = payload.get('filename')
            if user_id is None or str(user_id) == '' or not filename:
                _emit_command_result(correlation_id, command, False, 400, error='user_id and filename are required')
                return
            base = safe_py_filename(filename)
            legacy = legacy_user_script_path(user_id)
            if base == os.path.basename(legacy) and os.path.isfile(legacy):
                os.remove(legacy)
                _emit_command_result(correlation_id, command, True, 200, payload={'message': 'File deleted', 'filename': base})
                return
            path = os.path.join(user_script_subdir(user_id), base)
            if os.path.isfile(path):
                os.remove(path)
                _emit_command_result(correlation_id, command, True, 200, payload={'message': 'File deleted', 'filename': base})
                return
            _emit_command_result(correlation_id, command, False, 404, error='File not found')
            return

        if command == 'run':
            user_id = payload.get('user_id')
            filename = payload.get('filename')
            if not user_id:
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            if state.current_user and state.current_user != str(user_id):
                append_execution_log(
                    str(user_id),
                    f'[error] Field in use by user {state.current_user}',
                )
                _emit_command_result(correlation_id, command, False, 409, error=f'User {state.current_user} is currently using the field')
                return
            user_file_path = resolve_script_path(user_id, filename)
            if not user_file_path:
                append_execution_log(str(user_id), '[error] No code file found for this user')
                _emit_command_result(correlation_id, command, False, 404, error='No code file found for this user')
                return
            uid = str(user_id)
            if uid in running_processes:
                stop_user_code(uid)
            ok, msg = run_user_code(uid, user_file_path, ALLOWED_IMPORTS)
            if not ok:
                append_execution_log(str(user_id), f'[error] {msg}')
                _emit_command_result(correlation_id, command, False, 500, error=msg)
                return
            state.current_user = uid
            _emit_command_result(correlation_id, command, True, 200, payload={'message': msg, 'status': 'running', 'user_id': user_id})
            return

        if command == 'stop':
            user_id = payload.get('user_id')
            if not user_id:
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            ok, msg = stop_user_code(user_id)
            if ok and state.current_user == str(user_id):
                state.current_user = None
            if not ok:
                _emit_command_result(correlation_id, command, False, 404, error=msg)
                return
            _emit_command_result(correlation_id, command, True, 200, payload={'message': msg, 'status': 'stopped', 'user_id': user_id})
            return

        if command == 'reset':
            user_id = payload.get('user_id')
            if not user_id:
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            if state.current_user != str(user_id):
                _emit_command_result(correlation_id, command, False, 403, error='Only the current user can reset the field')
                return
            ok, msg = reset_field()
            if not ok:
                _emit_command_result(correlation_id, command, False, 500, error=msg)
                return
            _emit_command_result(correlation_id, command, True, 200, payload={'message': msg, 'status': 'reset', 'user_id': user_id})
            return

        if command == 'status':
            user_id = payload.get('user_id')
            uid = str(user_id)
            p = running_processes.get(uid)
            if p is not None and p.poll() is not None:
                running_processes.pop(uid, None)
                running_filename_by_user.pop(uid, None)
                if state.current_user == uid:
                    state.current_user = None
                p = None
            is_running = p is not None and p.poll() is None
            _emit_command_result(correlation_id, command, True, 200, payload={
                'user_id': user_id,
                'is_running': is_running,
                'is_current_user': state.current_user == uid,
                'current_user': state.current_user,
                'running_processes': list(running_processes.keys()),
                'running_filename': (running_filename_by_user.get(uid) if is_running else None),
                'timestamp': datetime.now().isoformat(),
                'process_status': (p.poll() if p else None),
                'is_alive': (p.poll() is None if p else False)
            })
            return

        if command == 'execution_log':
            user_id = payload.get('user_id')
            if user_id is None or str(user_id) == '':
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            lines = get_execution_log_lines(user_id)
            _emit_command_result(correlation_id, command, True, 200, payload={'user_id': user_id, 'lines': lines})
            return

        if command == 'execution_log_clear':
            user_id = payload.get('user_id')
            if user_id is None or str(user_id) == '':
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            clear_execution_log(user_id)
            _emit_command_result(correlation_id, command, True, 200, payload={'user_id': user_id, 'message': 'Execution log cleared'})
            return

        if command == 'camera_start':
            user_id = payload.get('user_id')
            if not user_id:
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            if state.current_user and state.current_user != str(user_id):
                _emit_command_result(correlation_id, command, False, 409, error=f'User {state.current_user} is currently using the camera')
                return
            if camera_active:
                _emit_command_result(correlation_id, command, False, 409, error='Camera is already active')
                return
            if not init_camera():
                _emit_command_result(correlation_id, command, False, 500, error='Failed to initialize camera')
                return
            state.current_user = str(user_id)
            _emit_command_result(correlation_id, command, True, 200, payload={'message': 'Camera started successfully', 'status': 'active'})
            return

        if command == 'camera_stop':
            user_id = payload.get('user_id')
            if not user_id:
                _emit_command_result(correlation_id, command, False, 400, error='user_id is required')
                return
            if state.current_user != str(user_id):
                _emit_command_result(correlation_id, command, False, 403, error='Only the current user can stop the camera')
                return
            release_camera()
            state.current_user = None
            _emit_command_result(correlation_id, command, True, 200, payload={'message': 'Camera stopped successfully', 'status': 'stopped'})
            return

        if command == 'camera_status':
            _emit_command_result(correlation_id, command, True, 200, payload={
                'camera_active': camera_active,
                'current_user': state.current_user,
                'timestamp': datetime.now().isoformat()
            })
            return

        if command == 'move':
            direction = payload.get('direction')
            duration = float(payload.get('duration', 0.5))
            ok, msg = perform_move(direction, duration)
            if not ok:
                _emit_command_result(correlation_id, command, False, 400, error=msg)
                return
            _emit_command_result(correlation_id, command, True, 200, payload={'message': msg})
            return

        _emit_command_result(correlation_id, command, False, 400, error=f'Unsupported command: {command}')
    except Exception as e:
        try:
            req = args[0] if args else {}
            cid = str(req.get('correlationId') or req.get('CorrelationId') or '')
            cmd = str(req.get('command') or req.get('Command') or 'unknown')
            _emit_command_result(cid, cmd, False, 500, error=f'Unhandled command error: {str(e)}')
        except Exception:
            pass


def _on_deploy_code(args):
    """Handle server-initiated DeployCode. args = [userId, codeText, filename]"""
    try:
        user_id = str(args[0] if args else 'unknown')
        code_text = args[1] if len(args) > 1 else None
        filename = args[2] if len(args) > 2 else f"user_{user_id}.py"
        if not code_text:
            _emit_deploy_result(user_id, False, 'codeText is required')
            return

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        user_file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(user_file_path, 'w', encoding='utf-8') as f:
            f.write(code_text)

        is_safe, message = validate_python_code(user_file_path, ALLOWED_IMPORTS)
        if not is_safe:
            try:
                os.remove(user_file_path)
            except Exception:
                pass
            _emit_deploy_result(user_id, False, f'Validation failed: {message}')
            log_debug('deploy-code-failed', {'userId': user_id, 'reason': message}, hub_connection, ws_connected)
            return

        deps = _install_deps_for(user_id, user_file_path)
        msg = 'Code deployed to car storage'
        if deps and deps.get('failed'):
            msg += ' (some packages failed: ' + ', '.join(deps['failed']) + ')'
        _emit_deploy_result(user_id, True, msg, filename)
        log_debug('deploy-code-success', {'userId': user_id, 'filename': filename, 'dependencies': deps}, hub_connection, ws_connected)
    except Exception as e:
        _emit_deploy_result(str(args[0]) if args else 'unknown', False, f'Unhandled error: {str(e)}')
        log_debug('deploy-code-error', {'error': str(e)}, hub_connection, ws_connected)


def _build_hub():
    global hub_connection
    url = get_hub_url()
    hub_connection = HubConnectionBuilder()\
        .with_url(url, options={"verify_ssl": False})\
        .configure_logging(logging.WARNING)\
        .with_automatic_reconnect({
            "type": "raw",
            "keep_alive_interval": 15,
            "reconnect_interval": 5,
            "max_attempts": MAX_RECONNECT_ATTEMPTS
        }).build()

    def on_open():
        global ws_connected, ws_reconnect_attempts, last_connect_time
        ws_connected = True
        ws_reconnect_attempts = 0
        last_connect_time = datetime.now().isoformat()
        hub_connection.send("RobotConnect", [ROBOT_CAR_ID, ROBOT_CAR_NAME, ROBOT_CAR_IP, ROBOT_CAR_PORT])
        print(f"🤖 Robot car registered: {ROBOT_CAR_NAME} ({ROBOT_CAR_ID})")
        log_debug('robot-connected', {'name': ROBOT_CAR_NAME, 'ip': ROBOT_CAR_IP, 'port': ROBOT_CAR_PORT}, hub_connection, ws_connected)

    def on_close():
        global ws_connected
        ws_connected = False
        print("❌ Disconnected from server")

    def on_error(data):
        global ws_reconnect_attempts
        print(f"❌ Connection error: {data}")
        ws_reconnect_attempts += 1
        log_debug('robot-connect-error', {'error': str(data), 'attempts': ws_reconnect_attempts}, hub_connection, ws_connected)

    hub_connection.on_open(on_open)
    hub_connection.on_close(on_close)
    hub_connection.on_error(on_error)
    hub_connection.on("DeployCode", _on_deploy_code)
    hub_connection.on("RobotCommandRequest", _on_robot_command_request)
    return hub_connection


def connect_to_server():
    global ws_connected, ws_reconnect_attempts, connecting_in_progress, hub_connection
    if ws_connected and hub_connection:
        return True
    with connection_lock:
        if ws_connected or connecting_in_progress:
            return ws_connected
        connecting_in_progress = True
        try:
            if ws_reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                print(f"❌ Max reconnection attempts reached ({MAX_RECONNECT_ATTEMPTS})")
                connecting_in_progress = False
                return False
            print(f"🔄 Connecting to server: {get_hub_url()} (attempt {ws_reconnect_attempts + 1})")
            _build_hub()
            hub_connection.start()
            return True
        except Exception as e:
            print(f"❌ Failed to connect to server: {e}")
            ws_reconnect_attempts += 1
            return False
        finally:
            connecting_in_progress = False


def disconnect_from_server():
    global ws_connected, hub_connection
    try:
        if ws_connected and hub_connection:
            hub_connection.stop()
            ws_connected = False
            print("🔌 Disconnected from server")
    except Exception as e:
        print(f"❌ Error disconnecting from server: {e}")


def send_heartbeat():
    global ws_connected, last_heartbeat_time
    if not ws_connected or not hub_connection:
        return False
    try:
        from state import current_user, field_reset_position
        battery_level = 85
        position = list(field_reset_position) if field_reset_position else [0, 0]
        status = 'in_use' if current_user else 'idle'
        hub_connection.send("RobotHeartbeat", [ROBOT_CAR_ID, status, battery_level, position])
        last_heartbeat_time = datetime.now().isoformat()
        return True
    except Exception as e:
        print(f"❌ Failed to send heartbeat: {e}")
        return False


def start_heartbeat_thread():
    def worker():
        while True:
            try:
                if ws_connected:
                    send_heartbeat()
                time.sleep(30)
            except Exception as e:
                print(f"❌ Heartbeat error: {e}")
                time.sleep(5)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("💓 Heartbeat thread started")


def start_camera_stream_thread():
    global camera_stream_thread_started
    if camera_stream_thread_started:
        return
    camera_stream_thread_started = True

    def worker():
        from services.camera import camera_active, get_frame_jpeg_base64
        while True:
            try:
                if ws_connected and camera_active:
                    frame_b64 = get_frame_jpeg_base64()
                    if frame_b64 and hub_connection:
                        hub_connection.send("RobotCameraFrame", [{
                            'carId': ROBOT_CAR_ID,
                            'timestamp': datetime.utcnow().isoformat() + 'Z',
                            'contentType': 'image/jpeg',
                            'imageBase64': frame_b64
                        }])
                time.sleep(0.25)
            except Exception:
                time.sleep(1)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("📷 Camera stream thread started")
