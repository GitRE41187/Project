"""Raspberry Pi robot agent: SignalR to backend + optional local /health for ops."""
import os
import threading
import time

from flask import Flask, jsonify

from config import UPLOAD_FOLDER, ROBOT_CAR_ID, ROBOT_CAR_NAME, ROBOT_CAR_PORT, SERVER_URL, MAX_CONTENT_LENGTH
from signalr_client import connect_to_server, disconnect_from_server, start_heartbeat_thread, start_camera_stream_thread
from state import running_processes
from services.code_runner import stop_user_code
from services.camera import camera_active, release_camera

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def startup_cleanup():
    """Reset leftover processes and uploaded files from a previous run."""
    for uid in list(running_processes.keys()):
        stop_user_code(uid)
    if camera_active:
        release_camera()
    now = time.time()
    cleaned = 0
    if not os.path.isdir(UPLOAD_FOLDER):
        return cleaned
    for name in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, name)
        if os.path.isfile(path) and now - os.path.getmtime(path) > 24 * 3600:
            try:
                os.remove(path)
                cleaned += 1
            except OSError:
                pass
    return cleaned


@app.route("/health", methods=["GET"])
def health():
    from signalr_client import hub_connection, ws_connected, last_connect_time, last_heartbeat_time

    return jsonify({
        "status": "OK",
        "role": "robot-agent",
        "robot_id": ROBOT_CAR_ID,
        "robot_name": ROBOT_CAR_NAME,
        "server_url": SERVER_URL,
        "ws_connected": ws_connected,
        "running_subprocesses": len(running_processes),
        "camera_active": camera_active,
        "last_connect_time": last_connect_time,
        "last_heartbeat_time": last_heartbeat_time,
    })


if __name__ == "__main__":
    print("🚀 Robot agent (SignalR) + local health")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"🤖 Robot ID: {ROBOT_CAR_ID} | {ROBOT_CAR_NAME}")
    print(f"🌐 Backend (SignalR): {SERVER_URL}")

    try:
        startup_cleanup()
    except Exception:
        pass

    start_heartbeat_thread()
    start_camera_stream_thread()

    def connect_worker():
        print("🔄 Connecting to backend hub...")
        connect_to_server()

    threading.Thread(target=connect_worker, daemon=True).start()

    try:
        app.run(host="0.0.0.0", port=ROBOT_CAR_PORT, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        disconnect_from_server()
    except Exception as e:
        print(f"❌ Error: {e}")
        disconnect_from_server()
