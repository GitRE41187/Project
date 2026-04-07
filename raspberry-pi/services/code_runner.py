"""Code execution service."""
import os
import subprocess
import threading
import time

from config import UPLOAD_FOLDER, PYTHON_EXE, _PKG_DIR
from state import (
    running_processes,
    running_filename_by_user,
    append_execution_log,
    clear_execution_log,
)
from utils import validate_python_code


def _stream_reader(uid: str, stream, label: str):
    try:
        for line in iter(stream.readline, ''):
            if line == '':
                break
            append_execution_log(uid, f'[{label}] {line.rstrip()}')
    except Exception as e:
        append_execution_log(uid, f'[{label}] <read error: {e}>')
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _watch_process(uid: str, process: subprocess.Popen):
    try:
        while process.poll() is None:
            time.sleep(0.15)
        code = process.returncode
    except Exception as e:
        append_execution_log(uid, f'[process] watch error: {e}')
        code = -1
    append_execution_log(uid, f'[process] exited with code {code}')
    import state as state_mod
    if state_mod.running_processes.get(uid) is process:
        state_mod.running_processes.pop(uid, None)
        state_mod.running_filename_by_user.pop(uid, None)
        if state_mod.current_user == uid:
            state_mod.current_user = None


def run_user_code(user_id: str, file_path: str, allowed_imports: set) -> tuple:
    """Run user code in a subprocess. Returns (success, message)."""
    uid = str(user_id)
    try:
        is_safe, message = validate_python_code(file_path, allowed_imports)
        if not is_safe:
            append_execution_log(uid, f'[validation] {message}')
            return False, message

        abs_script = os.path.abspath(file_path)
        script_dir = os.path.dirname(abs_script)
        user_codes_dir = os.path.join(_PKG_DIR, UPLOAD_FOLDER)

        env = os.environ.copy()
        # Same as: cd <script_dir> && python3 Light.py — plus project root on PYTHONPATH for Motor.py, ADC.py, etc.
        path_parts = [script_dir, _PKG_DIR, user_codes_dir]
        prev = env.get('PYTHONPATH', '').strip()
        if prev:
            path_parts.append(prev)
        env['PYTHONPATH'] = os.pathsep.join(path_parts)

        clear_execution_log(uid)
        append_execution_log(
            uid,
            f'[process] starting {os.path.basename(abs_script)} (interpreter={PYTHON_EXE}, cwd={script_dir})',
        )

        process = subprocess.Popen(
            [PYTHON_EXE, abs_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=script_dir,
            env=env,
        )
        running_processes[uid] = process
        running_filename_by_user[uid] = os.path.basename(file_path)

        threading.Thread(target=_stream_reader, args=(uid, process.stdout, 'stdout'), daemon=True).start()
        threading.Thread(target=_stream_reader, args=(uid, process.stderr, 'stderr'), daemon=True).start()
        threading.Thread(target=_watch_process, args=(uid, process), daemon=True).start()

        return True, f'Code started for user {user_id}'
    except Exception as e:
        append_execution_log(uid, f'[error] {str(e)}')
        return False, f'Error running code: {str(e)}'


def stop_user_code(user_id) -> tuple:
    """Stop user code execution. Returns (success, message)."""
    uid = str(user_id)
    if uid in running_processes:
        process = running_processes[uid]
        try:
            append_execution_log(uid, '[process] stop requested')
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            del running_processes[uid]
            running_filename_by_user.pop(uid, None)
            return True, f'Code stopped for user {user_id}'
        except Exception as e:
            return False, f'Error stopping code: {str(e)}'
    return False, f'No running process found for user {user_id}'


def reset_field() -> tuple:
    """Reset field to start position. Returns (success, message)."""
    import state
    try:
        if state.current_user and state.current_user in running_processes:
            stop_user_code(state.current_user)
        print(f'Field reset to position {state.field_reset_position}')
        state.current_user = None
        return True, 'Field reset to start position'
    except Exception as e:
        return False, f'Error resetting field: {str(e)}'
