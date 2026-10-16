"""Shared pieces for the return-home modules: motor access, status and cancellation.

Must not import the other return_home* modules — they all import this one.
"""
import os
import threading
import time

# Only one return-home routine may drive the motors at a time.
_lock = threading.Lock()
_cancel = threading.Event()
_status = {'active': False, 'state': 'idle', 'detail': '', 'owner': None, 'at': 0.0}
_status_lock = threading.Lock()

# Outcome states that end a return-home attempt (shown after it stops).
FINAL_STATES = ('at_start', 'pad_reached', 'retrace_done', 'direct_done', 'timeout', 'failed', 'cancelled', 'skipped')


def get_motor_pwm():
    """Load PWM from the Motor wrapper, ensuring Freenove path is on PYTHONPATH."""
    try:
        import importlib.util
        import sys
        from config import EXTRA_PYTHONPATH

        # Inject hardware library paths so Motor wrapper can find motor.py
        extra = [p for p in EXTRA_PYTHONPATH if p]
        for p in reversed(extra):
            if p not in sys.path:
                sys.path.insert(0, p)
        if extra:
            prev = os.environ.get('PYTHONPATH', '')
            os.environ['PYTHONPATH'] = os.pathsep.join(extra) + (os.pathsep + prev if prev else '')

        pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        motor_path = os.path.join(pkg_dir, 'Motor.py')
        spec = importlib.util.spec_from_file_location('_Motor_wrapper', motor_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.PWM
    except Exception:
        return None


def effective_speeds(motors, duty3_inverted: bool):
    """Convert raw motor values to (left_eff, right_eff) duty units for differential drive."""
    left = (motors[0] + motors[1]) / 2.0
    d3 = -motors[2] if duty3_inverted else motors[2]
    right = (d3 + motors[3]) / 2.0
    return left, right


def drive_cmd(left, right, duty3_inverted: bool) -> tuple:
    """Build a 4-motor tuple from effective left/right duty."""
    if duty3_inverted:
        return (left, left, -right, right)
    return (left, left, right, right)


def set_status(state: str, detail: str = '', log_fn=None):
    """Publish the current return-home phase (agent `status` command + execution log)."""
    with _status_lock:
        _status['state'] = state
        _status['detail'] = detail
        _status['at'] = time.time()
    if log_fn:
        log_fn(f'[return_home] status={state}' + (f' ({detail})' if detail else ''))


def status_snapshot() -> dict:
    with _status_lock:
        return dict(_status)


def reset_status():
    with _status_lock:
        if not _status['active']:
            _status.update(state='idle', detail='', owner=None, at=time.time())


def begin(owner=None) -> bool:
    """Claim the motors for return home. False when another routine already holds them."""
    if not _lock.acquire(blocking=False):
        return False
    _cancel.clear()
    with _status_lock:
        _status.update(active=True, owner=owner, state='starting', detail='', at=time.time())
    return True


def end():
    with _status_lock:
        _status['active'] = False
    _cancel.clear()
    _lock.release()


def is_active() -> bool:
    with _status_lock:
        return bool(_status['active'])


def request_cancel(owner=None) -> bool:
    """Ask the running routine to stop. owner=None cancels regardless of who started it."""
    with _status_lock:
        if not _status['active']:
            return False
        if owner is not None and _status['owner'] not in (None, str(owner)):
            return False
    _cancel.set()
    return True


def cancelled() -> bool:
    return _cancel.is_set()


def sleep_or_cancel(secs: float) -> bool:
    """Sleep up to secs; returns False early if cancel was requested."""
    end_at = time.monotonic() + max(0.0, secs)
    while True:
        if _cancel.is_set():
            return False
        left = end_at - time.monotonic()
        if left <= 0:
            return True
        time.sleep(min(0.05, left))
