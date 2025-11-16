from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import subprocess
import threading
import time
import shutil
from datetime import datetime
import cv2
import imutils
import socketio
from typing import Tuple, Dict, Any

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'user_codes'
ALLOWED_EXTENSIONS = {'py'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Robot car configuration
ROBOT_CAR_ID = os.getenv('ROBOT_CAR_ID', 'robot-001')
ROBOT_CAR_NAME = os.getenv('ROBOT_CAR_NAME', 'Alpha Bot')
def get_local_ip():
    """Get the local IP address of the Raspberry Pi."""
    try:
        # Connect to a public DNS server to get the local IP (does not actually send data)
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

ROBOT_CAR_IP = os.getenv('ROBOT_CAR_IP', get_local_ip())
ROBOT_CAR_PORT = int(os.getenv('ROBOT_CAR_PORT', '5001'))
SERVER_URL = os.getenv('SERVER_URL', 'http://192.168.1.132:5000')

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global variables to track running processes
running_processes = {}
current_user = None
field_reset_position = (0, 0)  # Default start position

# Camera variables
camera = None
camera_active = False
camera_lock = threading.Lock()

# WebSocket connection
sio = socketio.Client()
ws_connected = False
ws_reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5
last_connect_time = None
last_heartbeat_time = None
connection_lock = threading.Lock()
connecting_in_progress = False

# Allowed imports for safety
ALLOWED_IMPORTS = {
    'math', 'random', 'time', 'datetime', 'json', 'os', 'sys',
    'numpy', 'pandas', 'matplotlib', 'requests', 'urllib',
    'collections', 'itertools', 'functools', 'operator'
}

# -------------------------
# Utilities & helpers
# -------------------------
def json_ok(payload: Dict[str, Any], status_code: int = 200):
    payload.setdefault('timestamp', datetime.now().isoformat())
    return jsonify(payload), status_code

def json_error(message: str, status_code: int = 400, **extra):
    pay = {'error': message, 'timestamp': datetime.now().isoformat()}
    if extra:
        pay.update(extra)
    return jsonify(pay), status_code

def log_debug(event: str, data: Dict[str, Any] = None):
    """Log and emit debug info to server for visibility in web UI."""
    try:
        stamp = datetime.now().isoformat()
        payload = {
            'carId': ROBOT_CAR_ID,
            'event': event,
            'data': data or {},
            'timestamp': stamp
        }
        print(f"[DEBUG {stamp}] {event}: {payload['data']}")
        if ws_connected:
            sio.emit('robot-debug', payload)
    except Exception as e:
        print(f"❌ Failed to emit debug: {e}")

# WebSocket event handlers
@sio.event
def connect():
    global ws_connected, ws_reconnect_attempts, last_connect_time
    print(f"✅ Connected to server: {SERVER_URL}")
    ws_connected = True
    ws_reconnect_attempts = 0
    last_connect_time = datetime.now().isoformat()
    
    # Register robot car with server
    sio.emit('robot-connect', {
        'carId': ROBOT_CAR_ID,
        'name': ROBOT_CAR_NAME,
        'ip': ROBOT_CAR_IP,
        'port': ROBOT_CAR_PORT
    })
    print(f"🤖 Robot car registered: {ROBOT_CAR_NAME} ({ROBOT_CAR_ID})")
    log_debug('robot-connected', {'name': ROBOT_CAR_NAME, 'ip': ROBOT_CAR_IP, 'port': ROBOT_CAR_PORT})

@sio.event
def disconnect():
    global ws_connected
    print(f"❌ Disconnected from server")
    ws_connected = False
    log_debug('robot-disconnected')

@sio.event
def connect_error(data):
    global ws_reconnect_attempts
    print(f"❌ Connection error: {data}")
    ws_reconnect_attempts += 1
    log_debug('robot-connect-error', {'error': str(data), 'attempts': ws_reconnect_attempts})

@sio.on('deploy-code')
def on_deploy_code(payload):
    """
    Handle server-initiated code deploy to this car.
    Expected payload: { userId: str|int, codeText?: str, filename?: str }
    """
    try:
        user_id = str(payload.get('userId') or 'unknown')
        code_text = payload.get('codeText')
        filename = payload.get('filename') or f"user_{user_id}.py"
        if not code_text:
            sio.emit('deploy-result', {
                'carId': ROBOT_CAR_ID,
                'userId': user_id,
                'success': False,
                'message': 'codeText is required'
            })
            return

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        user_file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(user_file_path, 'w', encoding='utf-8') as f:
            f.write(code_text)

        is_safe, message = validate_python_code(user_file_path)
        if not is_safe:
            try:
                os.remove(user_file_path)
            except:
                pass
            sio.emit('deploy-result', {
                'carId': ROBOT_CAR_ID,
                'userId': user_id,
                'success': False,
                'message': f'Validation failed: {message}'
            })
            log_debug('deploy-code-failed', {'userId': user_id, 'reason': message})
            return

        sio.emit('deploy-result', {
            'carId': ROBOT_CAR_ID,
            'userId': user_id,
            'success': True,
            'filename': filename,
            'message': 'Code deployed to car storage'
        })
        log_debug('deploy-code-success', {'userId': user_id, 'filename': filename})
    except Exception as e:
        sio.emit('deploy-result', {
            'carId': ROBOT_CAR_ID,
            'success': False,
            'message': f'Unhandled error: {str(e)}'
        })
        log_debug('deploy-code-error', {'error': str(e)})

def connect_to_server():
    """Connect to the main server via WebSocket"""
    global ws_connected, ws_reconnect_attempts, connecting_in_progress

    if ws_connected:
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

            print(f"🔄 Connecting to server: {SERVER_URL} (attempt {ws_reconnect_attempts + 1})")
            # Enable built-in auto-reconnect; avoid custom reconnector thread
            sio.connect(SERVER_URL, wait_timeout=10, transports=['websocket', 'polling'])
            return True
        except Exception as e:
            print(f"❌ Failed to connect to server: {e}")
            ws_reconnect_attempts += 1
            return False
        finally:
            connecting_in_progress = False

def disconnect_from_server():
    """Disconnect from the main server"""
    global ws_connected
    try:
        if ws_connected:
            sio.emit('robot-disconnect', {'carId': ROBOT_CAR_ID})
            sio.disconnect()
            ws_connected = False
            print("🔌 Disconnected from server")
    except Exception as e:
        print(f"❌ Error disconnecting from server: {e}")

def send_heartbeat():
    """Send heartbeat to server"""
    global ws_connected, last_heartbeat_time
    
    if not ws_connected:
        return False
    
    try:
        # Get system status
        battery_level = 85  # Simulate battery level
        position = field_reset_position
        status = 'idle'
        
        if current_user:
            status = 'in_use'
        
        sio.emit('robot-heartbeat', {
            'carId': ROBOT_CAR_ID,
            'status': status,
            'battery': battery_level,
            'position': position
        })
        last_heartbeat_time = datetime.now().isoformat()
        return True
    except Exception as e:
        print(f"❌ Failed to send heartbeat: {e}")
        return False

def start_heartbeat_thread():
    """Start heartbeat thread"""
    def heartbeat_worker():
        while True:
            try:
                if ws_connected:
                    send_heartbeat()
                time.sleep(30)  # Send heartbeat every 30 seconds
            except Exception as e:
                print(f"❌ Heartbeat error: {e}")
                time.sleep(5)
    
    heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    heartbeat_thread.start()
    print("💓 Heartbeat thread started")

def start_reconnector_thread():
    """Deprecated: rely on socketio auto-reconnect to avoid duplicate connections."""
    print("ℹ️ Reconnector disabled; using socketio auto-reconnect")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_python_code(file_path):
    """Validate Python code for safety"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for dangerous imports
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # Extract module name
                if line.startswith('import '):
                    module = line.split('import ')[1].split()[0].split('.')[0]
                else:
                    module = line.split('from ')[1].split()[0].split('.')[0]
                
                if module not in ALLOWED_IMPORTS:
                    return False, f"Import '{module}' is not allowed"
        
        # Check for dangerous functions
        dangerous_functions = ['eval', 'exec', 'open', 'file', '__import__']
        for func in dangerous_functions:
            if func in content:
                return False, f"Function '{func}' is not allowed"
        
        return True, "Code is safe"
    except Exception as e:
        return False, f"Error validating code: {str(e)}"

def run_user_code(user_id, file_path):
    """Run user code in a subprocess with restrictions"""
    try:
        # Validate code first
        is_safe, message = validate_python_code(file_path)
        if not is_safe:
            return False, message
        
        # Create a restricted environment
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(os.getcwd(), 'user_codes')
        
        # Run the code
        process = subprocess.Popen(
            ['python', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.join(os.getcwd(), 'user_codes'),
            env=env
        )
        
        running_processes[user_id] = process
        return True, f"Code started for user {user_id}"
        
    except Exception as e:
        return False, f"Error running code: {str(e)}"

def stop_user_code(user_id):
    """Stop user code execution"""
    if user_id in running_processes:
        process = running_processes[user_id]
        try:
            # Terminate the process
            process.terminate()
            
            # Wait for it to terminate gracefully
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                process.kill()
                process.wait()
            
            del running_processes[user_id]
            return True, f"Code stopped for user {user_id}"
        except Exception as e:
            return False, f"Error stopping code: {str(e)}"
    else:
        return False, f"No running process found for user {user_id}"

def reset_field():
    """Reset field to start position"""
    global current_user
    try:
        # Stop any running code
        if current_user and current_user in running_processes:
            stop_user_code(current_user)
        
        # Reset field position (simulate)
        print(f"Field reset to position {field_reset_position}")
        current_user = None
        return True, "Field reset to start position"
    except Exception as e:
        return False, f"Error resetting field: {str(e)}"

def init_camera():
    """Initialize camera"""
    global camera
    try:
        camera = cv2.VideoCapture(0)  # Use default camera (index 0)
        if camera.isOpened():
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_FPS, 30)
            return True
        else:
            return False
    except Exception as e:
        print(f"Camera initialization error: {str(e)}")
        return False

def release_camera():
    """Release camera resources"""
    global camera, camera_active
    with camera_lock:
        if camera is not None:
            camera.release()
            camera = None
        camera_active = False

def generate_frames():
    """Generate camera frames for streaming"""
    global camera, camera_active
    
    while camera_active:
        with camera_lock:
            if camera is None:
                break
            
            success, frame = camera.read()
            if not success:
                break
        
        # Resize frame for better performance
        frame = imutils.resize(frame, width=640)
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'running_processes': len(running_processes),
        'current_user': current_user,
        'camera_active': camera_active,
        'ws_connected': ws_connected,
        'robot_id': ROBOT_CAR_ID,
        'robot_name': ROBOT_CAR_NAME,
        'last_connect_time': last_connect_time,
        'last_heartbeat_time': last_heartbeat_time
    })

@app.route('/camera/start', methods=['POST'])
def start_camera():
    """Start camera streaming"""
    global camera_active
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Check if another user is currently using the camera
        if current_user and current_user != user_id:
            return jsonify({'error': f'User {current_user} is currently using the camera'}), 409
        
        with camera_lock:
            if camera_active:
                return jsonify({'error': 'Camera is already active'}), 409
            
            # Initialize camera
            if init_camera():
                camera_active = True
                current_user = user_id
                return jsonify({
                    'message': 'Camera started successfully',
                    'user_id': user_id,
                    'status': 'active'
                })
            else:
                return jsonify({'error': 'Failed to initialize camera'}), 500
                
    except Exception as e:
        return jsonify({'error': f'Start camera failed: {str(e)}'}), 500

@app.route('/camera/stop', methods=['POST'])
def stop_camera():
    """Stop camera streaming"""
    global camera_active, current_user
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Only allow stop if user is currently active
        if current_user != user_id:
            return jsonify({'error': 'Only the current user can stop the camera'}), 403
        
        release_camera()
        current_user = None
        
        return jsonify({
            'message': 'Camera stopped successfully',
            'user_id': user_id,
            'status': 'stopped'
        })
        
    except Exception as e:
        return jsonify({'error': f'Stop camera failed: {str(e)}'}), 500

@app.route('/camera/stream')
def camera_stream():
    """Camera streaming endpoint"""
    global camera_active
    
    if not camera_active:
        return "Camera not active", 404
    
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera/status', methods=['GET'])
def camera_status():
    """Get camera status"""
    return jsonify({
        'camera_active': camera_active,
        'current_user': current_user,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/upload_code', methods=['POST'])
def upload_code():
    """Upload and store user code"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        file_path = data.get('file_path')
        original_filename = data.get('original_filename')
        
        if not user_id or not file_path:
            return json_error('user_id and file_path are required', 400)
        
        # Copy file to user_codes directory
        user_filename = f"user_{user_id}.py"
        user_file_path = os.path.join(UPLOAD_FOLDER, user_filename)
        
        if os.path.exists(file_path):
            shutil.copy2(file_path, user_file_path)
            
            # Validate the code
            is_safe, message = validate_python_code(user_file_path)
            if not is_safe:
                os.remove(user_file_path)
                return json_error(f'Code validation failed: {message}', 400)
            
            # Notify server so it can store metadata to DB and mark car deployment
            if ws_connected:
                sio.emit('robot-code-uploaded', {
                    'carId': ROBOT_CAR_ID,
                    'userId': user_id,
                    'filename': user_filename,
                    'original': original_filename,
                    'size': os.path.getsize(user_file_path),
                    'timestamp': datetime.now().isoformat()
                })
            log_debug('code-uploaded', {'userId': user_id, 'filename': user_filename})

            return json_ok({
                'message': 'Code uploaded successfully',
                'user_id': user_id,
                'filename': user_filename,
                'validation': message
            })
        else:
            return json_error('Source file not found', 404)
            
    except Exception as e:
        return json_error(f'Upload failed: {str(e)}', 500)

@app.route('/run', methods=['POST'])
def run_code():
    """Run user code"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return json_error('user_id is required', 400)
        
        # Check if another user is currently running code
        if current_user and current_user != user_id:
            return json_error(f'User {current_user} is currently using the field', 409)
        
        # Check if user has code uploaded
        user_file_path = os.path.join(UPLOAD_FOLDER, f"user_{user_id}.py")
        if not os.path.exists(user_file_path):
            return json_error('No code uploaded for this user', 404)
        
        # Stop any existing process for this user
        if user_id in running_processes:
            stop_user_code(user_id)
        
        # Run the code
        success, message = run_user_code(user_id, user_file_path)
        
        if success:
            current_user = user_id
            log_debug('code-run-started', {'userId': user_id})
            if ws_connected:
                sio.emit('robot-status', {'carId': ROBOT_CAR_ID, 'status': 'running', 'userId': user_id})
            return json_ok({
                'message': message,
                'user_id': user_id,
                'status': 'running'
            })
        else:
            return json_error(message, 500)
            
    except Exception as e:
        return json_error(f'Run failed: {str(e)}', 500)

@app.route('/stop', methods=['POST'])
def stop_code():
    """Stop user code execution"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return json_error('user_id is required', 400)
        
        success, message = stop_user_code(user_id)
        
        if success:
            if current_user == user_id:
                current_user = None
            log_debug('code-run-stopped', {'userId': user_id})
            if ws_connected:
                sio.emit('robot-status', {'carId': ROBOT_CAR_ID, 'status': 'idle', 'userId': user_id})
            return json_ok({
                'message': message,
                'user_id': user_id,
                'status': 'stopped'
            })
        else:
            return json_error(message, 404)
            
    except Exception as e:
        return json_error(f'Stop failed: {str(e)}', 500)

@app.route('/reset', methods=['POST'])
def reset_field_endpoint():
    """Reset field to start position"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return json_error('user_id is required', 400)
        
        # Only allow reset if user is currently active
        if current_user != user_id:
            return json_error('Only the current user can reset the field', 403)
        
        success, message = reset_field()
        
        if success:
            log_debug('field-reset', {'userId': user_id})
            return json_ok({
                'message': message,
                'user_id': user_id,
                'status': 'reset'
            })
        else:
            return json_error(message, 500)
            
    except Exception as e:
        return json_error(f'Reset failed: {str(e)}', 500)

@app.route('/status/<int:user_id>', methods=['GET'])
def get_status(user_id):
    """Get execution status for a user"""
    try:
        is_running = user_id in running_processes
        is_current = current_user == user_id
        
        status = {
            'user_id': user_id,
            'is_running': is_running,
            'is_current_user': is_current,
            'current_user': current_user,
            'running_processes': list(running_processes.keys()),
            'timestamp': datetime.now().isoformat(),
            'ws_connected': ws_connected,
            'last_connect_time': last_connect_time,
            'last_heartbeat_time': last_heartbeat_time
        }
        
        if is_running:
            process = running_processes[user_id]
            status['process_status'] = process.poll()
            status['is_alive'] = process.poll() is None
        
        return jsonify(status)
        
    except Exception as e:
        return json_error(f'Status check failed: {str(e)}', 500)

# -------------------------
# Simple movement controls
# -------------------------
def perform_move(direction: str, duration: float = 0.5) -> Tuple[bool, str]:
    """
    Placeholder movement action. Replace with GPIO/motor driver commands.
    """
    try:
        allowed = {'front', 'back', 'left', 'right'}
        if direction not in allowed:
            return False, f'Invalid direction: {direction}'
        log_debug('move-command-received', {'direction': direction, 'duration': duration})
        # TODO: integrate actual motor control here
        time.sleep(min(max(duration, 0.1), 3.0))
        log_debug('move-command-completed', {'direction': direction})
        if ws_connected:
            sio.emit('robot-control-ack', {'carId': ROBOT_CAR_ID, 'direction': direction, 'duration': duration})
        return True, f'Move {direction} executed'
    except Exception as e:
        return False, f'Move error: {str(e)}'

@app.route('/control/front', methods=['POST'])
def control_front():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('front', duration)
    if ok:
        return json_ok({'message': msg})
    return json_error(msg, 400)

@app.route('/control/back', methods=['POST'])
def control_back():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('back', duration)
    if ok:
        return json_ok({'message': msg})
    return json_error(msg, 400)

@app.route('/control/left', methods=['POST'])
def control_left():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('left', duration)
    if ok:
        return json_ok({'message': msg})
    return json_error(msg, 400)

@app.route('/control/right', methods=['POST'])
def control_right():
    data = request.get_json(silent=True) or {}
    duration = float(data.get('duration', 0.5))
    ok, msg = perform_move('right', duration)
    if ok:
        return json_ok({'message': msg})
    return json_error(msg, 400)

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up old files and processes"""
    try:
        # Stop all running processes
        for user_id in list(running_processes.keys()):
            stop_user_code(user_id)
        
        # Stop camera if active
        if camera_active:
            release_camera()
        
        # Clean up old files (older than 24 hours)
        current_time = time.time()
        cleaned_files = 0
        
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > 24 * 3600:  # 24 hours
                    os.remove(file_path)
                    cleaned_files += 1
        
        return jsonify({
            'message': 'Cleanup completed',
            'cleaned_files': cleaned_files,
            'stopped_processes': len(running_processes),
            'camera_stopped': True
        })
        
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Starting Raspberry Pi Field Control API...")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"🔒 Allowed imports: {ALLOWED_IMPORTS}")
    print(f"🤖 Robot ID: {ROBOT_CAR_ID}")
    print(f"🏷️  Robot Name: {ROBOT_CAR_NAME}")
    print(f"🌐 Server URL: {SERVER_URL}")
    
    # Run cleanup on startup
    try:
        cleanup()
    except:
        pass
    
    # Start heartbeat thread
    start_heartbeat_thread()
    # Start reconnector thread
    start_reconnector_thread()
    
    # Connect to main server
    print("🔄 Attempting to connect to main server...")
    connect_to_server()
    
    try:
        app.run(host='0.0.0.0', port=ROBOT_CAR_PORT, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        disconnect_from_server()
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        disconnect_from_server()
