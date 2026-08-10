"""Code execution service."""
import os
import shutil
import subprocess
import threading
import time

from config import (
    UPLOAD_FOLDER,
    _PKG_DIR,
    RUN_SANDBOX,
    RUN_MEMORY_LIMIT_MB,
    RUN_CPU_SECONDS,
    DOCKER_IMAGE,
    DOCKER_MEMORY,
    DOCKER_CPUS,
    DOCKER_NETWORK,
    RETURN_HOME_ON_STOP,
)
from state import (
    running_processes,
    running_filename_by_user,
    append_execution_log,
    clear_execution_log,
)
from utils import validate_python_code
from services.environment import get_runtime_python, detect_imports, _installable_packages

_IS_POSIX = os.name == 'posix'


def _resource_limiter():
    """Return a preexec_fn that puts the child in its own process group and
    applies memory/CPU caps (POSIX only). Returns None on non-POSIX."""
    if not _IS_POSIX:
        return None

    def _apply():
        os.setsid()  # own process group, so we can kill children too
        try:
            import resource
            if RUN_MEMORY_LIMIT_MB and RUN_MEMORY_LIMIT_MB > 0:
                limit = RUN_MEMORY_LIMIT_MB * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            if RUN_CPU_SECONDS and RUN_CPU_SECONDS > 0:
                resource.setrlimit(resource.RLIMIT_CPU, (RUN_CPU_SECONDS, RUN_CPU_SECONDS))
        except Exception:
            pass

    return _apply


def _build_docker_command(uid, abs_script, script_dir):
    """Run user code inside a throwaway container. Code dir is mounted
    read-only; detected packages are installed at container start."""
    workdir = '/workspace'
    rel_script = os.path.basename(abs_script)
    packages = sorted(set(_installable_packages(detect_imports(abs_script)).values()))
    inner = ''
    if packages:
        inner += 'pip install --quiet --disable-pip-version-check ' + ' '.join(packages) + ' && '
    inner += f'python {rel_script}'
    return [
        'docker', 'run', '--rm', '--name', f'robot_run_{uid}',
        '--network', DOCKER_NETWORK,
        '--memory', DOCKER_MEMORY,
        '--cpus', DOCKER_CPUS,
        '-v', f'{script_dir}:{workdir}:ro',
        '-w', workdir,
        DOCKER_IMAGE,
        'bash', '-lc', inner,
    ]


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


def _watch_process(uid: str, process: subprocess.Popen, motor_log: str = ''):
    try:
        while process.poll() is None:
            time.sleep(0.15)
        code = process.returncode
    except Exception as e:
        append_execution_log(uid, f'[process] watch error: {e}')
        code = -1
    append_execution_log(uid, f'[process] exited with code {code}')
    import state as state_mod
    append_execution_log(uid, f'[debug] motor_log={motor_log!r}')
    if state_mod.running_processes.get(uid) is process:
        state_mod.running_processes.pop(uid, None)
        state_mod.running_filename_by_user.pop(uid, None)
        if state_mod.current_user == uid:
            state_mod.current_user = None

    # Return home: replay recorded motor commands in reverse
    if motor_log and state_mod.running_processes.get(uid) is None:
        from services.return_home import return_home
        return_home(motor_log, log_fn=lambda msg: append_execution_log(uid, msg))


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
        from config import EXTRA_PYTHONPATH
        path_parts = [script_dir, _PKG_DIR, user_codes_dir] + EXTRA_PYTHONPATH
        prev = env.get('PYTHONPATH', '').strip()
        if prev:
            path_parts.append(prev)
        env['PYTHONPATH'] = os.pathsep.join(path_parts)

        clear_execution_log(uid)

        motor_log = ''
        if RETURN_HOME_ON_STOP and RUN_SANDBOX != 'docker':
            motor_log = os.path.join(script_dir, '.motor_log.json')
            env['MOTOR_LOG_FILE'] = motor_log
            from services.return_home import mark_home
            mark_home(motor_log, log_fn=lambda msg: append_execution_log(uid, msg))

        sandbox = RUN_SANDBOX
        if sandbox == 'docker' and shutil.which('docker') is None:
            append_execution_log(uid, '[process] docker not found, falling back to venv sandbox')
            sandbox = 'venv'

        if sandbox == 'docker':
            cmd = _build_docker_command(uid, abs_script, script_dir)
            interpreter = DOCKER_IMAGE
        else:
            interpreter = get_runtime_python(lambda line: append_execution_log(uid, line))
            cmd = [interpreter, abs_script]

        append_execution_log(
            uid,
            f'[process] starting {os.path.basename(abs_script)} (sandbox={sandbox}, interpreter={interpreter}, cwd={script_dir})',
        )

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=script_dir,
            env=env,
            preexec_fn=_resource_limiter(),
        )
        running_processes[uid] = process
        running_filename_by_user[uid] = os.path.basename(file_path)

        threading.Thread(target=_stream_reader, args=(uid, process.stdout, 'stdout'), daemon=True).start()
        threading.Thread(target=_stream_reader, args=(uid, process.stderr, 'stderr'), daemon=True).start()
        threading.Thread(target=_watch_process, args=(uid, process, motor_log), daemon=True).start()

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
            _terminate(process)
            if RUN_SANDBOX == 'docker':
                try:
                    subprocess.run(['docker', 'rm', '-f', f'robot_run_{uid}'], capture_output=True, text=True)
                except OSError:
                    pass
            del running_processes[uid]
            running_filename_by_user.pop(uid, None)
            return True, f'Code stopped for user {user_id}'
        except Exception as e:
            return False, f'Error stopping code: {str(e)}'
    return False, f'No running process found for user {user_id}'


def _terminate(process: subprocess.Popen):
    """Stop a process and any children it spawned (process-group aware).

    Sends SIGINT first so Python scripts run their finally/KeyboardInterrupt
    handlers (e.g. GPIO.cleanup()). Falls back to SIGTERM then SIGKILL.
    """
    import signal

    def _signal_group(sig):
        if _IS_POSIX:
            try:
                os.killpg(os.getpgid(process.pid), sig)
                return
            except (ProcessLookupError, OSError):
                pass
        # Non-POSIX or no group: signal the process directly.
        try:
            if sig == signal.SIGKILL:
                process.kill()
            else:
                process.terminate()
        except OSError:
            pass

    # SIGINT → KeyboardInterrupt in Python → finally blocks run (e.g. GPIO.cleanup)
    if _IS_POSIX:
        _signal_group(signal.SIGINT)
        try:
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass

    # Fallback: SIGTERM
    _signal_group(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _signal_group(getattr(signal, 'SIGKILL', signal.SIGTERM))
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


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
