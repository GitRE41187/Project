"""Primary return home: U-turn at FINISH, then follow the field line forward to START.

Driving forward keeps the IR array ahead of the wheels (same geometry the
line-tracking script is tuned for), which steers far more stably than reversing.

START and FINISH both read 0b111, so the sensors alone cannot tell them apart.
A pad only counts as START after LINE_RETURN_IGNORE_PAD_SECS (leaving FINISH),
after the landmarks logged on the way out have been met in reverse order, and
after it is held for LINE_RETURN_PAD_HOLD (twice that while landmarks remain).
The stop is reported as `at_start` only when a landmark log existed and every
landmark was matched; otherwise it is `pad_reached` (START not verified).
"""
import json
import math
import os
import re
import time

from services import return_home_common as common

_MIRRORED_FEATURE = {'curve_left': 'curve_right', 'curve_right': 'curve_left'}
# Events in the line log that bookend the field rather than mark a spot along it.
_NON_LANDMARKS = ('pad', 'finish')


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

    pins_found = sum(
        1 for pin in (LINE_IR_LEFT, LINE_IR_MIDDLE, LINE_IR_RIGHT)
        if re.search(rf'(?<![\w.]){pin}(?![\w.])', src)
    )
    return pins_found >= 2


def line_log_path(motor_log_path: str) -> str:
    """The line-feature log lives next to the motor log, written by line_events."""
    return os.path.join(os.path.dirname(os.path.abspath(motor_log_path)), '.line_log.json')


def load_line_events(motor_log_path: str) -> list:
    """Feature names recorded while driving out, in order."""
    path = line_log_path(motor_log_path)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [
        e['event'] for e in raw
        if isinstance(e, dict) and isinstance(e.get('event'), str)
    ]


def expected_return_features(events: list) -> list:
    """Features the robot should meet on the way back.

    Pads are dropped (they bookend the field, not landmarks along it), the order
    is reversed, and curves swap hands because the robot now drives the other way.
    """
    feats = [e for e in events if e not in _NON_LANDMARKS]
    return [_MIRRORED_FEATURE.get(f, f) for f in reversed(feats)]


def classify_feature(sensors: int):
    """Bitmask → feature name, matching what line_events records during a run."""
    if sensors == 0b111:
        return 'pad'
    if sensors == 0b000:
        return 'gap'
    if sensors == 0b100:
        return 'curve_left'
    if sensors == 0b001:
        return 'curve_right'
    return None


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


def return_home_line(log_path: str, log_fn=None) -> bool:
    """U-turn on the spot, then follow the line forward back to the start pad.

    Returns True when the run is handled (pad reached, cancelled, or the robot
    already drove far enough that a log-based replay would overshoot), False
    when the robot has not moved and the caller may fall back to retrace.
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

    pwm = common.get_motor_pwm()
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
        return common.drive_cmd(left, right, ODOMETRY_DUTY3_INVERTED)

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
    outcome = 'failed'
    outcome_detail = ''
    BRAKE_TIME = 0.15
    PIVOT_MAX = 2.0
    phase = 'follow'
    phase_since = 0.0
    pivot_dir = 0

    # นับ landmark ที่บันทึกไว้ตอนวิ่งออกไป ย้อนลำดับกลับ — ไม่ drift เหมือนจับเวลา
    events_out = load_line_events(log_path)
    expected = expected_return_features(events_out)
    feat_pattern = None
    feat_since = 0.0
    feat_counted = False
    HOLD_CURVE, HOLD_GAP, HOLD_PAD = 0.05, 0.35, 0.30
    if expected:
        _log(f'[return_home_line] expecting {len(expected)} landmarks back: {expected}')
    else:
        _log('[return_home_line] no landmark log — will stop at the first wide pad')

    try:
        common.set_status('line_uturn', f'{LINE_RETURN_UTURN_DIR} {uturn_secs:.2f}s', log_fn)
        _log(f'[return_home_line] U-turn {LINE_RETURN_UTURN_DIR} for {uturn_secs:.2f}s')
        pwm.setMotorModel(*STOP)
        uturn_ok = common.sleep_or_cancel(0.15)
        if uturn_ok:
            pwm.setMotorModel(*uturn_cmd)
            uturn_ok = common.sleep_or_cancel(uturn_secs)
        pwm.setMotorModel(*STOP)
        if uturn_ok:
            uturn_ok = common.sleep_or_cancel(0.25)

        follow_started = time.monotonic()
        lost_since = follow_started
        if uturn_ok:
            common.set_status('line_following', 'heading to START', log_fn)
            _log('[return_home_line] following the line forward to the start pad')
        else:
            outcome = 'cancelled'

        while uturn_ok:
            if common.cancelled():
                _log('[return_home_line] cancel requested — stopping')
                outcome = 'cancelled'
                break

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
                outcome, outcome_detail = 'timeout', f'no START pad within {LINE_RETURN_MAX_SECS:.0f}s'
                break

            # ไล่ landmark ที่ผ่าน: ต้องเห็นรูปแบบค้างเท่ากับตอนบันทึกจึงนับ
            feature = classify_feature(sensors)
            if feature != feat_pattern:
                feat_pattern, feat_since, feat_counted = feature, now, False
            elif feature is not None and not feat_counted and expected:
                hold = HOLD_PAD if feature == 'pad' else (
                    HOLD_GAP if feature == 'gap' else HOLD_CURVE
                )
                if now - feat_since >= hold and elapsed >= LINE_RETURN_IGNORE_PAD_SECS:
                    feat_counted = True
                    if feature == expected[0]:
                        expected.pop(0)
                        _log(f'[return_home_line] landmark {feature} — {len(expected)} left')
                    else:
                        # ไม่ตรงลำดับ (เซ็นเซอร์พลาด/รถออกนอกเส้น) — ข้ามไปหาตัวถัดไป
                        _log(
                            f'[return_home_line] saw {feature}, expected {expected[0]}'
                            ' — resyncing'
                        )
                        if feature in expected:
                            del expected[:expected.index(feature) + 1]

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
                    else:
                        held = now - pad_since
                        # ยัง counted ไม่หมดแปลว่าอาจเป็นแผ่นกลางทาง — ต้องค้างนานกว่าจึงเชื่อ
                        need = LINE_RETURN_PAD_HOLD if not expected else LINE_RETURN_PAD_HOLD * 2
                        if held >= need:
                            if expected:
                                _log(
                                    f'[return_home_line] pad held {held:.1f}s with'
                                    f' {len(expected)} landmarks unmet — accepting as start'
                                )
                                outcome_detail = f'{len(expected)} landmarks unmet'
                            _log('[return_home_line] start pad reached — stop')
                            reached = True
                            outcome = 'at_start'
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
                    outcome_detail = f'line lost {lost:.1f}s'
                    break
                cmd = forward if lost < 0.8 else last_turn

            pwm.setMotorModel(*cmd)
    except Exception as e:
        _log(f'[return_home_line] error: {e}')
        outcome, outcome_detail = 'failed', f'error: {e}'
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
        # Without a landmark log (student scripts) any wide pad looks like START.
        if events_out and not expected:
            common.set_status('at_start', 'landmarks matched', log_fn)
        else:
            common.set_status(
                'pad_reached',
                outcome_detail or 'no landmark log — START not verified',
                log_fn,
            )
        _log('[return_home_line] done')
        return True

    if outcome == 'cancelled':
        common.set_status('cancelled', 'stopped by user', log_fn)
        return True

    # หมุนกลับ/วิ่งไปไกลแล้วแต่ไม่เจอแผ่นเริ่ม — replay log ทับจะยิ่งเพี้ยน
    if drove >= LINE_RETURN_NO_FALLBACK_AFTER:
        _log(f'[return_home_line] stopped after {drove:.1f}s — skipping log replay')
        common.set_status(outcome, outcome_detail or 'START not confirmed', log_fn)
        return True
    return False
