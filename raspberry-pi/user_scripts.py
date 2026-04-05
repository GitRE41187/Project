"""User .py file storage and coarse movement stub — consumed by the SignalR command handler only."""
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config import STATIC_CODES_DIR, UPLOAD_FOLDER, ROBOT_CAR_ID
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


def _is_path_under_dir(path: str, root: str) -> bool:
    try:
        p = os.path.abspath(path)
        r = os.path.abspath(root)
        return p == r or p.startswith(r + os.sep)
    except (OSError, ValueError):
        return False


def _read_static_codes_manifest() -> Dict[str, Dict[str, Any]]:
    path = os.path.join(STATIC_CODES_DIR, 'manifest.json')
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        entries = data.get('entries') if isinstance(data, dict) else None
        if not isinstance(entries, dict):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in entries.items():
            if isinstance(v, dict):
                out[str(k)] = v
        return out
    except Exception:
        return {}


def resolve_script_path(user_id, filename: Optional[str]) -> Optional[str]:
    uid = str(user_id)
    legacy = legacy_user_script_path(uid)
    if filename:
        base = safe_py_filename(filename)
        if base == os.path.basename(legacy) and os.path.isfile(legacy):
            return legacy
        candidate = os.path.join(user_script_subdir(uid), base)
        if os.path.isfile(candidate):
            return candidate
        static_candidate = os.path.join(STATIC_CODES_DIR, base)
        if _is_path_under_dir(static_candidate, STATIC_CODES_DIR) and os.path.isfile(static_candidate):
            return static_candidate
        return None
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

    manifest = _read_static_codes_manifest()
    if os.path.isdir(STATIC_CODES_DIR):
        for name in sorted(os.listdir(STATIC_CODES_DIR)):
            if not name.lower().endswith('.py') or name.startswith('_'):
                continue
            path = os.path.join(STATIC_CODES_DIR, name)
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
            stem = name[:-3] if name.lower().endswith('.py') else name
            meta = manifest.get(stem) or {}
            title = meta.get('title') if isinstance(meta.get('title'), str) else None
            desc = meta.get('description') if isinstance(meta.get('description'), str) else None
            row: dict = {
                "filename": name,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "source": "static_robot",
                "deletable": False,
                "staticId": stem,
            }
            if title:
                row["title"] = title
            if desc:
                row["description"] = desc
            out.append(row)
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
