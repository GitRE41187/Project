"""Replay recorded motor commands in reverse to approximately return home."""
import json
import math
import os
import time


def _get_motor_pwm():
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


def _effective_speeds(motors, duty3_inverted: bool):
    """Convert raw motor values to (left_eff, right_eff) duty units for differential drive."""
    left = (motors[0] + motors[1]) / 2.0
    d3 = -motors[2] if duty3_inverted else motors[2]
    right = (d3 + motors[3]) / 2.0
    return left, right


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


def mark_home(log_path: str, log_fn=None):
    """Mark the robot's current position as 'home'.

    Call this once at the start of a run (before the Motor.py recording
    wrapper starts logging any movement commands). It resets/clears the
    motor log so that a later call to return_home() only reverses the
    motion recorded *after* this point, treating the current physical
    position as the new reference (0,0) point.

    Args:
        log_path: Path to the JSON motor log written by Motor.py wrapper.
        log_fn:   Optional callback(str) for status messages.
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        log_dir = os.path.dirname(os.path.abspath(log_path))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        _log('[mark_home] current position marked as home (log reset)')
    except Exception as e:
        _log(f'[mark_home] could not reset log: {e}')


def return_home(log_path: str, log_fn=None):
    """Read motor log and drive back to starting position.

    Mode is chosen by RETURN_HOME_MODE env/config:
      'retrace' – replay path in reverse
      'direct'  – odometry estimate then straight back
      'hybrid'  – auto: short/straight → direct, complex (U/S/messy) → retrace
                  (recommended for learning / trial-and-error runs)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        from config import RETURN_HOME_MODE
        mode = (RETURN_HOME_MODE or 'hybrid').strip().lower()
    except Exception:
        mode = 'hybrid'

    if mode == 'hybrid':
        mode = _choose_hybrid_mode(log_path, log_fn=_log)
        _log(f'[return_home] hybrid selected mode={mode}')

    if mode == 'direct':
        _return_home_direct(log_path, log_fn)
    else:
        _return_home_retrace(log_path, log_fn)


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


def _return_home_retrace(log_path: str, log_fn=None):
    def _log(msg):
        if log_fn:
            log_fn(msg)

    if not os.path.isfile(log_path):
        _log('[return_home] no motor log, skipping')
        return

    try:
        with open(log_path, encoding='utf-8') as f:
            commands = json.load(f)
    except Exception as e:
        _log(f'[return_home] could not read log: {e}')
        return

    # Filter out stop commands (0,0,0,0) – no need to reverse them
    commands = [c for c in commands if isinstance(c.get('motors'), list) and len(c['motors']) == 4 and any(v != 0 for v in c['motors'])]
    if not commands:
        _log('[return_home] nothing to retrace')
        return

    # Load the Motor wrapper PWM (handles Freenove motor.py detection automatically)
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # services/../
    pwm = _get_motor_pwm()
    if pwm is None:
        _log('[return_home] Motor not found, skipping')
        return

    _log(f'[return_home] retracing {len(commands)} steps...')
    try:
        for cmd in reversed(commands):
            inverted = [-v for v in cmd['motors']]
            pwm.setMotorModel(*inverted)
            duration = min(max(cmd.get('duration', 0), 0), 2.0)  # cap each step at 2 s
            time.sleep(duration)
    except Exception as e:
        _log(f'[return_home] error during replay: {e}')
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
        return
    try:
        with open(log_path, encoding='utf-8') as f:
            commands = json.load(f)
    except Exception as e:
        _log(f'[return_home_direct] could not read log: {e}')
        return

    commands = [c for c in commands if isinstance(c.get('motors'), list) and len(c['motors']) == 4]

    # Use pre-computed pose from Motor wrapper if available (last entry has 'pose' key)
    raw = json.load(open(log_path, encoding='utf-8')) if os.path.isfile(log_path) else []
    pose_entry = next((e for e in reversed(raw) if 'pose' in e), None)
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
        return

    pwm = _get_motor_pwm()
    if pwm is None:
        _log('[return_home_direct] Motor not found, skipping')
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

    try:
        # Step 1: rotate to face home
        angle_to_home = math.atan2(-y, -x)
        delta_angle = (angle_to_home - theta + math.pi) % (2 * math.pi) - math.pi
        turn_time = (abs(delta_angle) / turn_rate * turn_scale) if turn_rate > 0 else 0
        if turn_time > 0.08:
            _log(
                f'[return_home_direct] rotating {math.degrees(delta_angle):.1f}° '
                f'({turn_time:.2f}s, scale={turn_scale:.2f}, duty={TS})'
            )
            pwm.setMotorModel(0, 0, 0, 0)
            time.sleep(0.12)  # kill forward momentum before pivot (large robot)
            pwm.setMotorModel(*(turn_left_cmd if delta_angle > 0 else turn_right_cmd))
            time.sleep(turn_time)
            pwm.setMotorModel(0, 0, 0, 0)
            if settle > 0:
                time.sleep(settle)

        # Step 2: drive straight to home
        drive_time = distance / forward_speed if forward_speed > 0 else 0
        _log(f'[return_home_direct] driving {distance:.3f}m ({drive_time:.2f}s)')
        pwm.setMotorModel(*forward_cmd)
        time.sleep(drive_time)

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