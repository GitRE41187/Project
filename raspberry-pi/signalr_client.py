"""SignalR client - connect to backend ASP.NET hub."""
import logging
import threading
import time
from datetime import datetime

from signalrcore.hub_connection_builder import HubConnectionBuilder

from config import (
    ROBOT_CAR_ID, ROBOT_CAR_NAME, ROBOT_CAR_IP, ROBOT_CAR_PORT,
    SERVER_URL, MAX_RECONNECT_ATTEMPTS, UPLOAD_FOLDER
)
from utils import log_debug, validate_python_code


hub_connection = None
ws_connected = False
ws_reconnect_attempts = 0
last_connect_time = None
last_heartbeat_time = None
connection_lock = threading.Lock()
connecting_in_progress = False

from state import current_user, field_reset_position
from config import ALLOWED_IMPORTS


def get_hub_url():
    return f"{SERVER_URL.rstrip('/')}/hubs/robot"


def _emit_deploy_result(user_id: str, success: bool, message: str, filename: str = None):
    if hub_connection and ws_connected:
        payload = {'carId': ROBOT_CAR_ID, 'userId': user_id, 'success': success, 'message': message}
        if filename:
            payload['filename'] = filename
        hub_connection.send("DeployResult", [payload])


def _on_deploy_code(args):
    """Handle server-initiated DeployCode. args = [userId, codeText, filename]"""
    try:
        user_id = str(args[0] if args else 'unknown')
        code_text = args[1] if len(args) > 1 else None
        filename = args[2] if len(args) > 2 else f"user_{user_id}.py"
        if not code_text:
            _emit_deploy_result(user_id, False, 'codeText is required')
            return

        import os
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

        _emit_deploy_result(user_id, True, 'Code deployed to car storage', filename)
        log_debug('deploy-code-success', {'userId': user_id, 'filename': filename}, hub_connection, ws_connected)
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
