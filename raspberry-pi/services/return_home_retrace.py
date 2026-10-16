"""Backup return home: replay recorded motor commands in reverse.

Accuracy drifts with wheel slip and battery level, and nothing confirms the
robot actually reached START — use it only when line following is unavailable.
"""
import json
import os
import time

from services import return_home_common as common


def return_home_retrace(log_path: str, log_fn=None) -> bool:
    """Reverse every logged motor command. True when the full replay ran."""
    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        from config import RETRACE_MAX_SECS, RETRACE_MAX_DUTY
    except Exception:
        RETRACE_MAX_SECS, RETRACE_MAX_DUTY = 60.0, 4095

    if not os.path.isfile(log_path):
        _log('[return_home] no motor log, skipping')
        common.set_status('skipped', 'no motor log', log_fn)
        return False

    try:
        with open(log_path, encoding='utf-8') as f:
            commands = json.load(f)
    except Exception as e:
        _log(f'[return_home] could not read log: {e}')
        common.set_status('failed', 'unreadable motor log', log_fn)
        return False

    if not isinstance(commands, list):
        commands = []
    truncated = sum(
        int(c.get('truncated') or 0) for c in commands if isinstance(c, dict)
    )
    if truncated:
        _log(f'[return_home] log lost its first {truncated} commands — retrace covers only the last part')

    # Filter out stop commands (0,0,0,0) – no need to reverse them
    commands = [
        c for c in commands
        if isinstance(c, dict) and isinstance(c.get('motors'), list)
        and len(c['motors']) == 4 and any(v != 0 for v in c['motors'])
    ]
    if not commands:
        _log('[return_home] nothing to retrace')
        common.set_status('skipped', 'robot did not move', log_fn)
        return False

    pwm = common.get_motor_pwm()
    if pwm is None:
        _log('[return_home] Motor not found, skipping')
        common.set_status('failed', 'motor driver not found', log_fn)
        return False

    cap = max(0, min(int(RETRACE_MAX_DUTY), 4095))

    def _clamp(v):
        return max(-cap, min(cap, -v))

    common.set_status('retrace', f'{len(commands)} steps', log_fn)
    _log(f'[return_home] retracing {len(commands)} steps...')
    started = time.monotonic()
    outcome = 'retrace_done'
    try:
        for cmd in reversed(commands):
            if time.monotonic() - started > RETRACE_MAX_SECS:
                _log(f'[return_home] retrace exceeded {RETRACE_MAX_SECS:.0f}s — stopping')
                outcome = 'timeout'
                break
            pwm.setMotorModel(*[_clamp(v) for v in cmd['motors']])
            duration = min(max(cmd.get('duration', 0), 0), 2.0)  # cap each step at 2 s
            if not common.sleep_or_cancel(duration):
                outcome = 'cancelled'
                break
    except Exception as e:
        _log(f'[return_home] error during replay: {e}')
        outcome = 'failed'
    finally:
        try:
            pwm.setMotorModel(0, 0, 0, 0)
        except Exception:
            pass
        _log('[return_home] done')

    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
    except Exception:
        pass

    if outcome == 'retrace_done':
        detail = 'position not verified by sensors'
        if truncated:
            detail = 'partial path (log truncated), ' + detail
        common.set_status('retrace_done', detail, log_fn)
        return True
    common.set_status(outcome, 'retrace stopped early', log_fn)
    return False
