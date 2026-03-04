"""Code execution service."""
import os
import subprocess

from config import UPLOAD_FOLDER
from state import running_processes
from utils import validate_python_code


def run_user_code(user_id: str, file_path: str, allowed_imports: set) -> tuple:
    """Run user code in a subprocess. Returns (success, message)."""
    try:
        is_safe, message = validate_python_code(file_path, allowed_imports)
        if not is_safe:
            return False, message

        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(os.getcwd(), UPLOAD_FOLDER)

        process = subprocess.Popen(
            ['python', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.join(os.getcwd(), UPLOAD_FOLDER),
            env=env
        )
        running_processes[str(user_id)] = process
        return True, f"Code started for user {user_id}"
    except Exception as e:
        return False, f"Error running code: {str(e)}"


def stop_user_code(user_id) -> tuple:
    """Stop user code execution. Returns (success, message)."""
    uid = str(user_id)
    if uid in running_processes:
        process = running_processes[uid]
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            del running_processes[uid]
            return True, f"Code stopped for user {user_id}"
        except Exception as e:
            return False, f"Error stopping code: {str(e)}"
    return False, f"No running process found for user {user_id}"


def reset_field() -> tuple:
    """Reset field to start position. Returns (success, message)."""
    import state
    try:
        if state.current_user and state.current_user in running_processes:
            stop_user_code(state.current_user)
        print(f"Field reset to position {state.field_reset_position}")
        state.current_user = None
        return True, "Field reset to start position"
    except Exception as e:
        return False, f"Error resetting field: {str(e)}"
