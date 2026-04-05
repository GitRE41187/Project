"""Shared mutable state."""
from collections import deque

running_processes = {}
running_filename_by_user = {}
current_user = None
field_reset_position = (0, 0)

# Per-user console lines from subprocess stdout/stderr (ring buffer).
EXEC_LOG_MAX_LINES = 500
execution_log_by_user = {}


def append_execution_log(user_id, line: str) -> None:
    uid = str(user_id)
    if uid not in execution_log_by_user:
        execution_log_by_user[uid] = deque(maxlen=EXEC_LOG_MAX_LINES)
    execution_log_by_user[uid].append(line)


def clear_execution_log(user_id) -> None:
    uid = str(user_id)
    if uid in execution_log_by_user:
        execution_log_by_user[uid].clear()


def get_execution_log_lines(user_id):
    uid = str(user_id)
    d = execution_log_by_user.get(uid)
    return list(d) if d else []
