"""Camera routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify, Response

import state
from services.camera import camera_active, init_camera, release_camera, generate_frames
from utils import log_debug

camera_bp = Blueprint('camera', __name__)


@camera_bp.route('/camera/start', methods=['POST'])
def start_camera():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        if state.current_user and state.current_user != str(user_id):
            return jsonify({'error': f'User {state.current_user} is currently using the camera'}), 409

        if camera_active:
            return jsonify({'error': 'Camera is already active'}), 409

        if init_camera():
            state.current_user = str(user_id)
            log_debug('camera-started', {'userId': user_id})
            return jsonify({
                'message': 'Camera started successfully',
                'user_id': user_id,
                'status': 'active'
            })
        return jsonify({'error': 'Failed to initialize camera'}), 500
    except Exception as e:
        return jsonify({'error': f'Start camera failed: {str(e)}'}), 500


@camera_bp.route('/camera/stop', methods=['POST'])
def stop_camera():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        if state.current_user != str(user_id):
            return jsonify({'error': 'Only the current user can stop the camera'}), 403

        release_camera()
        state.current_user = None
        log_debug('camera-stopped', {'userId': user_id})
        return jsonify({
            'message': 'Camera stopped successfully',
            'user_id': user_id,
            'status': 'stopped'
        })
    except Exception as e:
        return jsonify({'error': f'Stop camera failed: {str(e)}'}), 500


@camera_bp.route('/camera/stream')
def camera_stream():
    if not camera_active:
        return "Camera not active", 404
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_bp.route('/camera/status', methods=['GET'])
def camera_status():
    return jsonify({
        'camera_active': camera_active,
        'current_user': state.current_user,
        'timestamp': datetime.now().isoformat()
    })
