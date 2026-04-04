"""User .py file storage and coarse movement stub — consumed by the SignalR command handler only."""
import os
import re
import time
from datetime import datetime
from typing import List, Optional, Tuple

from config import UPLOAD_FOLDER, ROBOT_CAR_ID
from utils import log_debug


def user_script_subdir(user_id) -> str:
    return os.path.join(UPLOAD_FOLDER, f"user_{user_id}")


def safe_py_filename(original_filename: str) -> str:
    base = os.path.basename(original_filename or "script.py")
    if not base.lower().endswith(".py"):
        base = (base.rsplit(".", 1)[0] if "." in base else base) + ".py"
    stem = base[:-3]
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem).strip("_") or "script"
    return safe_stem + ".py"


def legacy_user_script_path(user_id) -> str:
    return os.path.join(UPLOAD_FOLDER, f"user_{user_id}.py")


def resolve_script_path(user_id, filename: Optional[str]) -> Optional[str]:
    uid = str(user_id)
    legacy = legacy_user_script_path(uid)
    if filename:
        base = safe_py_filename(filename)
        if base == os.path.basename(legacy) and os.path.isfile(legacy):
            return legacy
        candidate = os.path.join(user_script_subdir(uid), base)
        return candidate if os.path.isfile(candidate) else None
    if os.path.isfile(legacy):
        return legacy
    sub = user_script_subdir(uid)
    if os.path.isdir(sub):
        py_files = sorted(
            f for f in os.listdir(sub)
            if f.lower().endswith(".py") and os.path.isfile(os.path.join(sub, f))
        )
        if len(py_files) == 1:
            return os.path.join(sub, py_files[0])
    return None


def list_user_py_files(user_id) -> List[dict]:
    uid = str(user_id)
    out: List[dict] = []
    sub = user_script_subdir(uid)
    if os.path.isdir(sub):
        for name in sorted(os.listdir(sub)):
            path = os.path.join(sub, name)
            if os.path.isfile(path) and name.lower().endswith(".py"):
                st = os.stat(path)
                out.append({
                    "filename": name,
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                })
    legacy = legacy_user_script_path(uid)
    if os.path.isfile(legacy):
        st = os.stat(legacy)
        out.append({
            "filename": os.path.basename(legacy),
            "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "legacy": True,
        })
    return out


def perform_move(direction: str, duration: float = 0.5) -> Tuple[bool, str]:
    try:
        from signalr_client import hub_connection, ws_connected

        allowed = {"front", "back", "left", "right"}
        if direction not in allowed:
            return False, f"Invalid direction: {direction}"
        log_debug(
            "move-command-received",
            {"direction": direction, "duration": duration},
            hub_connection,
            ws_connected,
        )
        time.sleep(min(max(duration, 0.1), 3.0))
        log_debug("move-command-completed", {"direction": direction}, hub_connection, ws_connected)
        if ws_connected and hub_connection:
            hub_connection.send("RobotDebug", [{
                "carId": ROBOT_CAR_ID,
                "event": "robot-control-ack",
                "direction": direction,
                "duration": duration,
            }])
        return True, f"Move {direction} executed"
    except Exception as e:
        return False, f"Move error: {str(e)}"
