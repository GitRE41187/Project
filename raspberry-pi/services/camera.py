"""Camera service."""
import base64
import threading

import cv2
import imutils


camera = None
camera_active = False
camera_lock = threading.Lock()


def init_camera() -> bool:
    """Initialize camera."""
    global camera, camera_active
    try:
        camera = cv2.VideoCapture(0)
        if camera.isOpened():
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_FPS, 30)
            camera_active = True
            return True
        return False
    except Exception as e:
        print(f"Camera initialization error: {str(e)}")
        return False


def release_camera():
    """Release camera resources."""
    global camera, camera_active
    with camera_lock:
        if camera is not None:
            camera.release()
            camera = None
        camera_active = False


def generate_frames():
    """Generate camera frames for streaming."""
    global camera, camera_active
    while camera_active:
        with camera_lock:
            if camera is None:
                break
            success, frame = camera.read()
            if not success:
                break
        frame = imutils.resize(frame, width=640)
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


def get_frame_jpeg_base64() -> str | None:
    """Grab one JPEG frame and return base64-encoded payload."""
    global camera, camera_active
    if not camera_active:
        return None
    with camera_lock:
        if camera is None:
            return None
        ok, frame = camera.read()
        if not ok:
            return None
    frame = imutils.resize(frame, width=640)
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
    if not ret:
        return None
    return base64.b64encode(buffer.tobytes()).decode('ascii')
