from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import subprocess
import threading
import time
import psutil
import shutil
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'user_codes'
ALLOWED_EXTENSIONS = {'py'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global variables to track running processes
running_processes = {}
current_user = None
field_reset_position = (0, 0)  # Default start position

# Allowed imports for safety
ALLOWED_IMPORTS = {
    'math', 'random', 'time', 'datetime', 'json', 'os', 'sys',
    'numpy', 'pandas', 'matplotlib', 'requests', 'urllib',
    'collections', 'itertools', 'functools', 'operator'
}

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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'running_processes': len(running_processes),
        'current_user': current_user
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
            return jsonify({'error': 'user_id and file_path are required'}), 400
        
        # Copy file to user_codes directory
        user_filename = f"user_{user_id}.py"
        user_file_path = os.path.join(UPLOAD_FOLDER, user_filename)
        
        if os.path.exists(file_path):
            shutil.copy2(file_path, user_file_path)
            
            # Validate the code
            is_safe, message = validate_python_code(user_file_path)
            if not is_safe:
                os.remove(user_file_path)
                return jsonify({'error': f'Code validation failed: {message}'}), 400
            
            return jsonify({
                'message': 'Code uploaded successfully',
                'user_id': user_id,
                'filename': user_filename,
                'validation': message
            })
        else:
            return jsonify({'error': 'Source file not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/run', methods=['POST'])
def run_code():
    """Run user code"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Check if another user is currently running code
        if current_user and current_user != user_id:
            return jsonify({'error': f'User {current_user} is currently using the field'}), 409
        
        # Check if user has code uploaded
        user_file_path = os.path.join(UPLOAD_FOLDER, f"user_{user_id}.py")
        if not os.path.exists(user_file_path):
            return jsonify({'error': 'No code uploaded for this user'}), 404
        
        # Stop any existing process for this user
        if user_id in running_processes:
            stop_user_code(user_id)
        
        # Run the code
        success, message = run_user_code(user_id, user_file_path)
        
        if success:
            current_user = user_id
            return jsonify({
                'message': message,
                'user_id': user_id,
                'status': 'running'
            })
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        return jsonify({'error': f'Run failed: {str(e)}'}), 500

@app.route('/stop', methods=['POST'])
def stop_code():
    """Stop user code execution"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        success, message = stop_user_code(user_id)
        
        if success:
            if current_user == user_id:
                current_user = None
            return jsonify({
                'message': message,
                'user_id': user_id,
                'status': 'stopped'
            })
        else:
            return jsonify({'error': message}), 404
            
    except Exception as e:
        return jsonify({'error': f'Stop failed: {str(e)}'}), 500

@app.route('/reset', methods=['POST'])
def reset_field_endpoint():
    """Reset field to start position"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Only allow reset if user is currently active
        if current_user != user_id:
            return jsonify({'error': 'Only the current user can reset the field'}), 403
        
        success, message = reset_field()
        
        if success:
            return jsonify({
                'message': message,
                'user_id': user_id,
                'status': 'reset'
            })
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        return jsonify({'error': f'Reset failed: {str(e)}'}), 500

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
            'timestamp': datetime.now().isoformat()
        }
        
        if is_running:
            process = running_processes[user_id]
            status['process_status'] = process.poll()
            status['is_alive'] = process.poll() is None
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': f'Status check failed: {str(e)}'}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up old files and processes"""
    try:
        # Stop all running processes
        for user_id in list(running_processes.keys()):
            stop_user_code(user_id)
        
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
            'stopped_processes': len(running_processes)
        })
        
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

if __name__ == '__main__':
    print("Starting Raspberry Pi Field Control API...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Allowed imports: {ALLOWED_IMPORTS}")
    
    # Run cleanup on startup
    try:
        cleanup()
    except:
        pass
    
    app.run(host='0.0.0.0', port=5001, debug=True)
