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


def return_home(log_path: str, log_fn=None, prefer_line: bool = False):
    """Read motor log and drive back to starting position.

    Mode is chosen by RETURN_HOME_MODE env/config:
      'retrace' – replay path in reverse
      'direct'  – odometry estimate then straight back
      'line'    – U-turn, then follow the field line forward back to the start pad
      'hybrid'  – auto: try line first when the run used the IR sensors, else
                  short/straight → direct, complex (U/S/messy) → retrace
                  (recommended for learning / trial-and-error runs)

    Args:
        prefer_line: the finished script read the IR line sensors, so following
            the line back is likely to work (see script_uses_line_sensors).
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
        if prefer_line or _line_first_enabled():
            why = 'script used the IR sensors' if prefer_line else 'RETURN_HOME_LINE_FIRST'
            _log(f'[return_home] hybrid trying line mode ({why})')
            if _return_home_line(log_path, log_fn):
                return
        mode = _choose_hybrid_mode(log_path, log_fn=_log)
        _log(f'[return_home] hybrid selected mode={mode}')

    if mode == 'line':
        if _return_home_line(log_path, log_fn):
            return
        # ตามเส้นกลับไม่สำเร็จ (ไม่เจอเส้น/ไม่มี GPIO) — ใช้ log ย้อนกลับแทน
        _log('[return_home] line mode failed → fallback retrace')
        _return_home_retrace(log_path, log_fn)
    elif mode == 'direct':
        _return_home_direct(log_path, log_fn)
    else:
        _return_home_retrace(log_path, log_fn)


def _line_first_enabled() -> bool:
    try:
        from config import RETURN_HOME_LINE_FIRST
        return bool(RETURN_HOME_LINE_FIRST)
    except Exception:
        return False


def script_uses_line_sensors(script_path: str) -> bool:
    """True when the script reads the IR line sensors, so it ran on the line field.

    Detected by source scan: a GPIO read call plus at least two of the three IR
    pin numbers. Students write their own sensor code, so match on the pins
    rather than on any particular helper name.
    """
    try:
        from config import LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT
    except Exception:
        LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT = 14, 15, 23

    try:
        with open(script_path, encoding='utf-8', errors='replace') as f:
            src = f.read()
    except Exception:
        return False

    reads_gpio = any(
        token in src for token in
        ('gpio_read', 'gpio_claim_input', 'read_sensors', 'GPIO.input', 'input(')
    )
    if not reads_gpio:
        return False

    import re
    pins_found = sum(
        1 for pin in (LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT)
        if re.search(rf'(?<![\w.]){pin}(?![\w.])', src)
    )
    return pins_found >= 2


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


def _ir_open():
    """Claim the 3 IR line sensors. Returns (lgpio, handle, pins) or None."""
    try:
        import lgpio
    except Exception:
        return None
    try:
        from config import (
            LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT,
        )
    except Exception:
        LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT = 14, 15, 23

    pins = (LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT)
    for num in (0, 4):
        if not os.path.exists(f'/dev/gpiochip{num}'):
            continue
        try:
            handle = lgpio.gpiochip_open(num)
        except Exception:
            continue
        claimed = []
        try:
            for pin in pins:
                try:
                    lgpio.gpio_free(handle, pin)
                except Exception:
                    pass
                lgpio.gpio_claim_input(handle, pin, 0)
                claimed.append(pin)
            for pin in pins:
                lgpio.gpio_read(handle, pin)  # wrong chip accepts claim but fails here
            return lgpio, handle, pins
        except Exception:
            for pin in claimed:
                try:
                    lgpio.gpio_free(handle, pin)
                except Exception:
                    pass
            try:
                lgpio.gpiochip_close(handle)
            except Exception:
                pass
    return None


def _ir_close(lgpio_mod, handle, pins):
    for pin in pins:
        try:
            lgpio_mod.gpio_free(handle, pin)
        except Exception:
            pass
    try:
        lgpio_mod.gpiochip_close(handle)
    except Exception:
        pass


def _ir_read(lgpio_mod, handle, pins) -> int:
    """Multi-sample read → bitmask (left=0b100, mid=0b010, right=0b001)."""
    samples = 5
    votes = [0, 0, 0]
    for _ in range(samples):
        for i, pin in enumerate(pins):
            try:
                if lgpio_mod.gpio_read(handle, pin):
                    votes[i] += 1
            except Exception:
                pass
        time.sleep(0.002)
    need = samples // 2 + 1
    state = 0
    if votes[0] >= need:
        state |= 0b100
    if votes[1] >= need:
        state |= 0b010
    if votes[2] >= need:
        state |= 0b001
    return state


def _return_home_line(log_path: str, log_fn=None) -> bool:
    """U-turn on the spot, then follow the line forward back to the start pad.

    Driving forward keeps the IR array ahead of the wheels (same geometry the
    line-tracking script is tuned for), which steers far more stably than
    reversing. Stops when the wide start pad (all 3 sensors) is held long enough.

    Returns True when the run is handled (pad reached, or the robot already
    drove far enough that a log-based replay would overshoot), False when the
    caller should fall back to a log-based mode.
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        from config import (
            LINE_RETURN_SPEED, LINE_RETURN_TURN_SPEED, LINE_RETURN_PIVOT_SPEED,
            LINE_RETURN_MAX_SECS, LINE_RETURN_IGNORE_PAD_SECS,
            LINE_RETURN_PAD_HOLD, LINE_RETURN_LOST_GIVE_UP,
            LINE_RETURN_NO_FALLBACK_AFTER, LINE_RETURN_UTURN_SECS,
            LINE_RETURN_UTURN_DIR, ODOMETRY_TURN_RATE, ODOMETRY_TURN_SCALE,
            ODOMETRY_DUTY3_INVERTED,
        )
    except Exception:
        LINE_RETURN_SPEED, LINE_RETURN_TURN_SPEED, LINE_RETURN_PIVOT_SPEED = 650, 900, 1500
        LINE_RETURN_MAX_SECS, LINE_RETURN_IGNORE_PAD_SECS = 30.0, 2.0
        LINE_RETURN_PAD_HOLD, LINE_RETURN_LOST_GIVE_UP = 1.0, 2.5
        LINE_RETURN_NO_FALLBACK_AFTER = 2.5
        LINE_RETURN_UTURN_SECS, LINE_RETURN_UTURN_DIR = 0.0, 'left'
        ODOMETRY_TURN_RATE, ODOMETRY_TURN_SCALE = 3.21, 1.0
        ODOMETRY_DUTY3_INVERTED = True

    ir = _ir_open()
    if ir is None:
        # สคริปต์ผู้ใช้อาจยังปล่อย GPIO ไม่เสร็จ — รอสั้น ๆ แล้วลองอีกครั้ง
        time.sleep(0.5)
        ir = _ir_open()
    if ir is None:
        _log('[return_home_line] IR sensors unavailable (GPIO busy?)')
        return False
    lgpio_mod, handle, pins = ir

    pwm = _get_motor_pwm()
    if pwm is None:
        _ir_close(lgpio_mod, handle, pins)
        _log('[return_home_line] Motor not found')
        return False

    # ยังไม่ขยับอะไร: ถ้าใต้ท้องรถไม่มีเส้น/แผ่นเลย โหมดนี้ไม่มีอะไรให้ตาม
    if _ir_read(lgpio_mod, handle, pins) == 0b000:
        _ir_close(lgpio_mod, handle, pins)
        _log('[return_home_line] no line under the robot — skipping line mode')
        return False

    def _cmd(left, right):
        """Build a 4-motor tuple from effective left/right duty."""
        if ODOMETRY_DUTY3_INVERTED:
            return (left, left, -right, right)
        return (left, left, right, right)

    S = LINE_RETURN_SPEED
    T = LINE_RETURN_TURN_SPEED
    P = LINE_RETURN_PIVOT_SPEED
    forward = _cmd(S, S)
    soft_left = _cmd(S, T)       # เบนซ้ายนุ่ม ๆ (ล้อขวาเร็วกว่า)
    soft_right = _cmd(T, S)
    pivot_left = _cmd(-P, P)
    pivot_right = _cmd(P, -P)
    STOP = (0, 0, 0, 0)

    turn_rate = ODOMETRY_TURN_RATE if ODOMETRY_TURN_RATE > 0 else 3.21
    turn_scale = ODOMETRY_TURN_SCALE if ODOMETRY_TURN_SCALE > 0 else 1.0
    uturn_secs = LINE_RETURN_UTURN_SECS
    if uturn_secs <= 0:
        uturn_secs = math.pi / turn_rate * turn_scale
    uturn_cmd = pivot_right if str(LINE_RETURN_UTURN_DIR).lower() == 'right' else pivot_left

    started = time.monotonic()
    pad_since = 0.0
    lost_since = 0.0
    last_turn = soft_left
    last_log = 0.0
    reached = False
    BRAKE_TIME = 0.15
    PIVOT_MAX = 2.0
    phase = 'follow'
    phase_since = 0.0
    pivot_dir = 0

    try:
        _log(f'[return_home_line] U-turn {LINE_RETURN_UTURN_DIR} for {uturn_secs:.2f}s')
        pwm.setMotorModel(*STOP)
        time.sleep(0.15)
        pwm.setMotorModel(*uturn_cmd)
        time.sleep(uturn_secs)
        pwm.setMotorModel(*STOP)
        time.sleep(0.25)

        follow_started = time.monotonic()
        lost_since = follow_started
        _log('[return_home_line] following the line forward to the start pad')

        while True:
            sensors = _ir_read(lgpio_mod, handle, pins)
            now = time.monotonic()
            elapsed = now - follow_started

            if now - last_log > 1.0:
                _log(
                    f'[return_home_line] sensors={sensors:03b} '
                    f'phase={phase} t={elapsed:.1f}s'
                )
                last_log = now

            if now - started > LINE_RETURN_MAX_SECS:
                _log('[return_home_line] timeout — stopping')
                break

            if sensors == 0b111:
                lost_since = now
                phase = 'follow'
                # ช่วงแรกยังคร่อมแผ่นจบอยู่ — ยังไม่นับว่าถึงแผ่นเริ่ม
                if elapsed < LINE_RETURN_IGNORE_PAD_SECS:
                    pad_since = 0.0
                    cmd = forward
                else:
                    if pad_since == 0.0:
                        pad_since = now
                        _log('[return_home_line] wide pad — verifying start')
                    elif now - pad_since >= LINE_RETURN_PAD_HOLD:
                        _log('[return_home_line] start pad reached — stop')
                        reached = True
                        break
                    cmd = forward
            elif phase == 'brake':
                pad_since = 0.0
                lost_since = now
                cmd = STOP
                if now - phase_since >= BRAKE_TIME:
                    phase = 'pivot'
                    phase_since = now
            elif phase == 'pivot':
                pad_since = 0.0
                lost_since = now
                if sensors in (0b010, 0b110, 0b011):
                    phase = 'follow'
                    cmd = forward
                elif now - phase_since >= PIVOT_MAX:
                    phase = 'follow'
                    cmd = last_turn
                else:
                    cmd = pivot_left if pivot_dir < 0 else pivot_right
                    last_turn = cmd
            elif sensors == 0b010:
                pad_since = 0.0
                lost_since = now
                cmd = forward
            elif sensors in (0b110, 0b100):
                pad_since = 0.0
                lost_since = now
                if sensors == 0b110:
                    cmd = soft_left
                    last_turn = cmd
                else:
                    # เส้นหลุดไปข้างเดียว = โค้งแคบ → เบรกแล้วหมุนอยู่กับที่
                    phase, phase_since, pivot_dir = 'brake', now, -1
                    cmd = STOP
            elif sensors in (0b011, 0b001):
                pad_since = 0.0
                lost_since = now
                if sensors == 0b011:
                    cmd = soft_right
                    last_turn = cmd
                else:
                    phase, phase_since, pivot_dir = 'brake', now, 1
                    cmd = STOP
            else:  # 0b000 — เส้นประหรือหลุดเส้น
                pad_since = 0.0
                lost = now - lost_since
                if lost >= LINE_RETURN_LOST_GIVE_UP:
                    _log(f'[return_home_line] line lost {lost:.1f}s — give up')
                    break
                cmd = forward if lost < 0.8 else last_turn

            pwm.setMotorModel(*cmd)
    except Exception as e:
        _log(f'[return_home_line] error: {e}')
    finally:
        try:
            pwm.setMotorModel(*STOP)
        except Exception:
            pass
        _ir_close(lgpio_mod, handle, pins)

    drove = time.monotonic() - started
    if reached:
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except Exception:
            pass
        _log('[return_home_line] done')
        return True

    # หมุนกลับ/วิ่งไปไกลแล้วแต่ไม่เจอแผ่นเริ่ม — replay log ทับจะยิ่งเพี้ยน
    if drove >= LINE_RETURN_NO_FALLBACK_AFTER:
        _log(f'[return_home_line] stopped after {drove:.1f}s — skipping log replay')
        return True
    return False


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