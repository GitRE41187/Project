"""Raspberry Pi Field Control API - main entry point."""
import os
import threading

from flask import Flask
from flask_cors import CORS

from config import (
    UPLOAD_FOLDER, ROBOT_CAR_ID, ROBOT_CAR_NAME, ROBOT_CAR_PORT, SERVER_URL,
    MAX_CONTENT_LENGTH,
)
from signalr_client import connect_to_server, disconnect_from_server, start_heartbeat_thread, start_camera_stream_thread
from routes.api import api_bp
from routes.camera_routes import camera_bp

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
CORS(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.register_blueprint(api_bp)
app.register_blueprint(camera_bp)


def start_reconnector_thread():
    print("ℹ️ Reconnector disabled; using SignalR automatic reconnect")


if __name__ == '__main__':
    print("🚀 Starting Raspberry Pi Field Control API...")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"🤖 Robot ID: {ROBOT_CAR_ID}")
    print(f"🏷️  Robot Name: {ROBOT_CAR_NAME}")
    print(f"🌐 Server URL: {SERVER_URL}")

    try:
        from routes.api import cleanup
        cleanup()
    except Exception:
        pass

    start_heartbeat_thread()
    start_camera_stream_thread()
    start_reconnector_thread()

    def connect_worker():
        print("🔄 Attempting to connect to main server...")
        connect_to_server()

    threading.Thread(target=connect_worker, daemon=True).start()

    try:
        app.run(host='0.0.0.0', port=ROBOT_CAR_PORT, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        disconnect_from_server()
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        disconnect_from_server()
