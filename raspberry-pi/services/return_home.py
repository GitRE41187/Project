"""Return home entry point: picks line following (primary) or retrace (backup).

The real work lives in return_home_line (IR line follow back to START) and
return_home_retrace (reverse motor-log replay). This module keeps the public
API used by code_runner: mark_home(), return_home(), script_uses_line_sensors().
"""
import json
import math
import os

from services import return_home_common as common
from services.return_home_line import (
    classify_feature,
    expected_return_features,
    line_log_path,
    load_line_events,
    return_home_line,
    script_uses_line_sensors,
)
from services.return_home_retrace import return_home_retrace

# Older names, kept for callers and tests that still import them from here.
_get_motor_pwm = common.get_motor_pwm
_effective_speeds = common.effective_speeds
_return_home_line = return_home_line
_return_home_retrace = return_home_retrace
_expected_return_features = expected_return_features
_classify_feature = classify_feature
_line_log_path = line_log_path
_load_line_events = load_line_events


def is_returning_home() -> bool:
    """True while a return-home routine is driving the motors."""
    return common.is_active()


def return_home_status() -> dict:
    """Snapshot for the agent `status` command: active, state, detail."""
    snap = common.status_snapshot()
    return {'active': snap['active'], 'state': snap['state'], 'detail': snap['detail']}


def cancel_return_home(owner=None) -> bool:
    """Ask a running return home to stop the motors. True if one was running."""
    return common.request_cancel(owner)


def _compute_pose(commands, speed_scale: float, wheel_base: float, duty3_inverted: bool):
    """Integrate differential drive kinematics over command log → (x, y, theta_rad)."""
    x, y, theta = 0.0, 0.0, 0.0
    for cmd in commands:
        motors = cmd.get('motors', [0, 0, 0, 0])
        dur = min(max(cmd.get('duration', 0), 0), 2.0)
        if dur <= 0:
            continue
        vl = _effective_speeds(motors, duty3_inverted)[0] * speed_scale
        vr = _effective_speeds(motors, duty3_inverted)[1] * speed_scale
        v = (vl + vr) / 2.0
        w = (vr - vl) / wheel_base
        if abs(w) < 1e-6:
            x += v * dur * math.cos(theta)
            y += v * dur * math.sin(theta)
        else:
            r = v / w
            dt = w * dur
            x += r * (math.sin(theta + dt) - math.sin(theta))
            y -= r * (math.cos(theta + dt) - math.cos(theta))
            theta = (theta + dt + math.pi) % (2 * math.pi) - math.pi
    return x, y, theta


def mark_home(log_path: str, line_log: str = '', log_fn=None):
    """Mark the robot's current position as 'home'.

    Call this once at the start of a run (before the Motor.py recording
    wrapper starts logging any movement commands). It resets/clears the
    motor log so that a later call to return_home() only reverses the
    motion recorded *after* this point, treating the current physical
    position as the new reference (0,0) point.

    Args:
        log_path: Path to the JSON motor log written by Motor.py wrapper.
        line_log: Optional path to the line-feature log written by line_events.
        log_fn:   Optional callback(str) for status messages.
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    for path, label in ((log_path, 'motor'), (line_log, 'line')):
        if not path:
            continue
        try:
            log_dir = os.path.dirname(os.path.abspath(path))
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except Exception as e:
            _log(f'[mark_home] could not reset {label} log: {e}')
    common.reset_status()
    _log('[mark_home] current position marked as home (logs reset)')


def return_home(log_path: str, log_fn=None, prefer_line: bool = False, owner=None):
    """Drive back to the starting position after a run.

    Mode is chosen by RETURN_HOME_MODE env/config:
      'line'    – U-turn, then follow the field line back to START (no fallback)
      'hybrid'  – line first when the run used the IR sensors (or
                  RETURN_HOME_LINE_FIRST), retrace if line mode cannot start;
                  otherwise short/straight → direct, complex → retrace, except
                  that an empty/truncated/long log first checks for a line
                  under the robot (HYBRID_LINE_PROBE)
      'retrace' – replay path in reverse
      'direct'  – odometry estimate then straight back

    Only one return home runs at a time; a second call while one is active is
    ignored so two routines never drive the motors together.

    Args:
        prefer_line: the finished script read the IR line sensors, so following
            the line back is likely to work (see script_uses_line_sensors).
        owner: user id that started the run, so only they can cancel it.
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    if not common.begin(owner):
        _log('[return_home] already running — ignoring duplicate request')
        return
    try:
        _dispatch(log_path, log_fn, _log, prefer_line)
    except Exception as e:
        _log(f'[return_home] error: {e}')
        common.set_status('failed', f'error: {e}', log_fn)
    finally:
        common.end()


def _dispatch(log_path, log_fn, _log, prefer_line):
    try:
        from config import RETURN_HOME_MODE
        mode = (RETURN_HOME_MODE or 'hybrid').strip().lower()
    except Exception:
        mode = 'hybrid'

    if 'finish' in load_line_events(log_path):
        common.set_status('finish_reached', 'run confirmed the FINISH pad', log_fn)

    if mode == 'line':
        if not return_home_line(log_path, log_fn):
            # retrace ทับหลังตามเส้นไม่ได้ อาจพารถออกนอกสนาม — โหมดนี้จึงหยุดเฉย ๆ
            common.set_status('failed', 'line mode could not start (GPIO busy or no line)', log_fn)
        return

    if mode == 'hybrid':
        if prefer_line or _line_first_enabled():
            why = 'script used the IR sensors' if prefer_line else 'RETURN_HOME_LINE_FIRST'
            _log(f'[return_home] hybrid trying line mode ({why})')
            if return_home_line(log_path, log_fn):
                return
            _log('[return_home] line mode could not start → fallback retrace')
            return_home_retrace(log_path, log_fn)
            return
        mode = _choose_hybrid_mode(log_path, log_fn=_log)
        _log(f'[return_home] hybrid selected mode={mode}')
        if mode == 'retrace' and _line_probe_wanted(log_path):
            # source scan missed IR use, or the log cannot be replayed faithfully;
            # return_home_line reads the sensors first and does not move if no line
            _log('[return_home] path unsuitable for retrace — checking for a line under the robot')
            if return_home_line(log_path, log_fn):
                return

    if mode == 'direct':
        _return_home_direct(log_path, log_fn)
    else:
        return_home_retrace(log_path, log_fn)


def _line_first_enabled() -> bool:
    try:
        from config import RETURN_HOME_LINE_FIRST
        return bool(RETURN_HOME_LINE_FIRST)
    except Exception:
        return False


def _line_probe_wanted(log_path: str) -> bool:
    """Retrace is a poor bet: no log, a truncated log, or a long line-follow style log."""
    try:
        from config import HYBRID_LINE_PROBE, HYBRID_LINE_PROBE_MIN_CMDS
    except Exception:
        HYBRID_LINE_PROBE, HYBRID_LINE_PROBE_MIN_CMDS = True, 40
    if not HYBRID_LINE_PROBE:
        return False
    truncated = False
    try:
        with open(log_path, encoding='utf-8') as f:
            raw = json.load(f)
        truncated = isinstance(raw, list) and any(
            isinstance(c, dict) and c.get('truncated') for c in raw
        )
    except Exception:
        pass
    n = len(_load_motion_commands(log_path))
    return n == 0 or truncated or n >= HYBRID_LINE_PROBE_MIN_CMDS


def _load_motion_commands(log_path: str):
    """Load motor log entries that have a 4-motor command (ignore pose-only rows)."""
    if not os.path.isfile(log_path):
        return []
    try:
        with open(log_path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [
        c for c in raw
        if isinstance(c, dict)
        and isinstance(c.get('motors'), list)
        and len(c['motors']) == 4
        and any(v != 0 for v in c['motors'])
    ]


def _path_stats(commands, duty3_inverted: bool, speed_scale: float, wheel_base: float):
    """Summarize path complexity for hybrid mode selection."""
    turn_segments = 0
    turn_time = 0.0
    move_time = 0.0
    duty_turn_eps = 250.0  # |left-right| above this ≈ turning
    for cmd in commands:
        motors = cmd.get('motors', [0, 0, 0, 0])
        dur = min(max(float(cmd.get('duration', 0) or 0), 0), 2.0)
        if dur <= 0:
            continue
        left, right = _effective_speeds(motors, duty3_inverted)
        if abs(left) < 30 and abs(right) < 30:
            continue
        move_time += dur
        if abs(left - right) >= duty_turn_eps:
            turn_segments += 1
            turn_time += dur
    x, y, theta = _compute_pose(commands, speed_scale, wheel_base, duty3_inverted)
    return {
        'turn_segments': turn_segments,
        'turn_time': turn_time,
        'move_time': move_time,
        'dist': math.hypot(x, y),
        'abs_yaw_deg': abs(math.degrees(theta)),
        'n_cmds': len(commands),
    }


def _choose_hybrid_mode(log_path: str, log_fn=None) -> str:
    """Pick direct for short/straight runs; retrace for complex student paths."""
    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        from config import (
            ODOMETRY_DUTY3_INVERTED, ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE,
            HYBRID_MAX_TURN_SEGMENTS, HYBRID_MAX_MOVE_TIME,
            HYBRID_MAX_DIST_M, HYBRID_MAX_YAW_DEG,
        )
    except Exception:
        ODOMETRY_DUTY3_INVERTED, ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE = True, 0.00015, 0.14
        HYBRID_MAX_TURN_SEGMENTS, HYBRID_MAX_MOVE_TIME = 2, 4.0
        HYBRID_MAX_DIST_M, HYBRID_MAX_YAW_DEG = 1.2, 60.0

    commands = _load_motion_commands(log_path)
    if not commands:
        _log('[return_home] hybrid: empty log → retrace (no-op)')
        return 'retrace'

    stats = _path_stats(
        commands, ODOMETRY_DUTY3_INVERTED, ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE,
    )
    _log(
        f'[return_home] hybrid stats: cmds={stats["n_cmds"]} '
        f'turns={stats["turn_segments"]} move={stats["move_time"]:.1f}s '
        f'dist≈{stats["dist"]:.2f}m yaw≈{stats["abs_yaw_deg"]:.0f}°'
    )

    simple = (
        stats['turn_segments'] <= HYBRID_MAX_TURN_SEGMENTS
        and stats['move_time'] <= HYBRID_MAX_MOVE_TIME
        and stats['dist'] <= HYBRID_MAX_DIST_M
        and stats['abs_yaw_deg'] <= HYBRID_MAX_YAW_DEG
    )
    return 'direct' if simple else 'retrace'


def _return_home_direct(log_path: str, log_fn=None):
    """Estimate robot position via odometry, then navigate straight back to origin."""
    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        from config import (
            ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE,
            ODOMETRY_RETURN_SPEED, ODOMETRY_DUTY3_INVERTED, ODOMETRY_TURN_RATE,
            ODOMETRY_TURN_SCALE, ODOMETRY_TURN_SPEED, ODOMETRY_TURN_SETTLE,
        )
    except Exception:
        ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE = 0.00015, 0.14
        ODOMETRY_RETURN_SPEED, ODOMETRY_DUTY3_INVERTED = 1500, True
        ODOMETRY_TURN_RATE = 3.21
        ODOMETRY_TURN_SCALE, ODOMETRY_TURN_SPEED, ODOMETRY_TURN_SETTLE = 1.0, 0, 0.35

    if not os.path.isfile(log_path):
        _log('[return_home_direct] no motor log, skipping')
        common.set_status('skipped', 'no motor log', log_fn)
        return
    try:
        with open(log_path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as e:
        _log(f'[return_home_direct] could not read log: {e}')
        common.set_status('failed', 'unreadable motor log', log_fn)
        return
    if not isinstance(raw, list):
        raw = []

    commands = [
        c for c in raw
        if isinstance(c, dict) and isinstance(c.get('motors'), list) and len(c['motors']) == 4
    ]

    # Use pre-computed pose from Motor wrapper if available (last entry has 'pose' key)
    pose_entry = next((e for e in reversed(raw) if isinstance(e, dict) and 'pose' in e), None)
    if pose_entry:
        x = pose_entry['pose']['x']
        y = pose_entry['pose']['y']
        theta = pose_entry['pose']['theta']
        _log(f'[return_home_direct] using saved pose: x={x:.3f}m y={y:.3f}m')
    else:
        x, y, theta = _compute_pose(commands, ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE, ODOMETRY_DUTY3_INVERTED)
    distance = math.hypot(x, y)
    _log(f'[return_home_direct] estimated pos: x={x:.3f}m y={y:.3f}m dist={distance:.3f}m')

    if distance < 0.02:
        _log('[return_home_direct] already at home')
        common.set_status('skipped', 'odometry says already home', log_fn)
        return

    pwm = _get_motor_pwm()
    if pwm is None:
        _log('[return_home_direct] Motor not found, skipping')
        common.set_status('failed', 'motor driver not found', log_fn)
        return
    S = ODOMETRY_RETURN_SPEED
    TS = ODOMETRY_TURN_SPEED if ODOMETRY_TURN_SPEED > 0 else S
    # Turn-in-place and forward commands, accounting for duty3 wiring
    if ODOMETRY_DUTY3_INVERTED:
        turn_left_cmd  = (-TS, -TS, -TS,  TS)
        turn_right_cmd = ( TS,  TS,  TS, -TS)
        forward_cmd    = ( S,  S, -S,  S)
    else:
        turn_left_cmd  = (-TS, -TS,  TS,  TS)
        turn_right_cmd = ( TS,  TS, -TS, -TS)
        forward_cmd    = ( S,  S,  S,  S)

    turn_rate = ODOMETRY_TURN_RATE
    forward_speed = S * ODOMETRY_SPEED_SCALE
    turn_scale = ODOMETRY_TURN_SCALE if ODOMETRY_TURN_SCALE > 0 else 1.0
    settle = max(0.0, ODOMETRY_TURN_SETTLE)

    common.set_status('direct', f'{distance:.2f}m by odometry', log_fn)
    finished = False
    try:
        # Step 1: rotate to face home
        angle_to_home = math.atan2(-y, -x)
        delta_angle = (angle_to_home - theta + math.pi) % (2 * math.pi) - math.pi
        turn_time = (abs(delta_angle) / turn_rate * turn_scale) if turn_rate > 0 else 0
        ok = True
        if turn_time > 0.08:
            _log(
                f'[return_home_direct] rotating {math.degrees(delta_angle):.1f}° '
                f'({turn_time:.2f}s, scale={turn_scale:.2f}, duty={TS})'
            )
            pwm.setMotorModel(0, 0, 0, 0)
            ok = common.sleep_or_cancel(0.12)  # kill forward momentum before pivot (large robot)
            if ok:
                pwm.setMotorModel(*(turn_left_cmd if delta_angle > 0 else turn_right_cmd))
                ok = common.sleep_or_cancel(turn_time)
            pwm.setMotorModel(0, 0, 0, 0)
            if ok and settle > 0:
                ok = common.sleep_or_cancel(settle)

        # Step 2: drive straight to home
        if ok:
            drive_time = distance / forward_speed if forward_speed > 0 else 0
            _log(f'[return_home_direct] driving {distance:.3f}m ({drive_time:.2f}s)')
            pwm.setMotorModel(*forward_cmd)
            ok = common.sleep_or_cancel(drive_time)
        finished = ok

    except Exception as e:
        _log(f'[return_home_direct] error: {e}')
    finally:
        try:
            pwm.setMotorModel(0, 0, 0, 0)
        except Exception:
            pass
        _log('[return_home_direct] done')

    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
    except Exception:
        pass

    if finished:
        common.set_status('direct_done', 'position not verified by sensors', log_fn)
    elif common.cancelled():
        common.set_status('cancelled', 'stopped by user', log_fn)
    else:
        common.set_status('failed', 'direct drive error', log_fn)
