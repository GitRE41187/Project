from Motor import *
import lgpio
import os
import time

# GPIO pins for the three infrared sensors (BCM)
# NOTE: BCM14/15 are also UART TX/RX. If serial console is enabled they stay
# "GPIO busy" forever — disable it via raspi-config (see setup_gpio hint).
IR_LEFT   = 14
IR_MIDDLE = 15
IR_RIGHT  = 23

_chip = None  # lgpio chip handle

# Records (command_tuple, duration_seconds) while running
_history: list = []

# Field profile (จูนตามสนาม): เส้นตรง · โค้ง U · โค้ง S · เส้นประ · แผ่นจบกว้าง
# duty3 (right_upper) กลับขั้ว — รูปแบบเดียวกับ test.py / return_home


def _kill_stale_line_tracking():
    """Kill other Line_Tracking.py processes still holding GPIO (not ourselves)."""
    mypid = os.getpid()
    # Avoid blocked builtins; shell excludes our pid.
    os.system(
        "ps -eo pid=,args= 2>/dev/null | "
        "grep -F 'Line_Tracking.py' | grep -v grep | "
        f"awk -v me={mypid} '$1 != me {{ print $1 }}' | "
        "xargs -r kill -9 >/dev/null 2>&1"
    )


def _force_release_gpiochips():
    """Release leftover userspace holders of the main gpiochip (consumer 'lg')."""
    _kill_stale_line_tracking()
    try:
        # Kill any process holding the main chip. Prefer sudo -n when allowed
        # (plain fuser often cannot signal another user's / root leftover).
        for name in ('gpiochip0', 'gpiochip4'):
            path = f'/dev/{name}'
            if not os.path.exists(path):
                continue
            os.system(
                f'command -v fuser >/dev/null 2>&1 && '
                f'(sudo -n fuser -k {path} || fuser -k {path}) >/dev/null 2>&1'
            )
    except Exception:
        pass
    time.sleep(0.8)


def cleanup_gpio():
    """Release IR pins and close the chip handle."""
    global _chip
    if _chip is None:
        return
    for pin in (IR_LEFT, IR_MIDDLE, IR_RIGHT):
        try:
            lgpio.gpio_free(_chip, pin)
        except Exception:
            pass
    try:
        lgpio.gpiochip_close(_chip)
    except Exception:
        pass
    _chip = None


def _primary_chip_num():
    """Return the main BCM GPIO chip number (never aux chips like gpiochip1)."""
    for num in (0, 4):
        path = f'/dev/gpiochip{num}'
        if os.path.exists(path):
            return num
    raise RuntimeError('No /dev/gpiochip0 (or gpiochip4) found')


def _try_claim_primary():
    """Claim IR pins on the primary chip and verify reads work."""
    num = _primary_chip_num()
    handle = lgpio.gpiochip_open(num)
    claimed = []
    try:
        for pin in (IR_LEFT, IR_MIDDLE, IR_RIGHT):
            try:
                lgpio.gpio_free(handle, pin)
            except Exception:
                pass
            try:
                lgpio.gpio_claim_input(handle, pin, 0)
            except Exception as e:
                raise RuntimeError(f'pin BCM{pin} on chip{num}: {e}') from e
            claimed.append(pin)
        # Reject wrong chips that accept claim then fail on read ("bad GPIO number").
        for pin in (IR_LEFT, IR_MIDDLE, IR_RIGHT):
            lgpio.gpio_read(handle, pin)
        return handle, num
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
        raise


def setup_gpio():
    global _chip
    cleanup_gpio()
    last_err = None

    for round_i in range(2):
        if round_i == 1:
            print('[gpio] still busy — killing stale holders and retrying...')
            _force_release_gpiochips()
        try:
            handle, num = _try_claim_primary()
            _chip = handle
            print(f'[gpio] IR pins claimed on /dev/gpiochip{num}')
            return
        except Exception as e:
            last_err = e
            _chip = None
            print(f'[gpio] {e}')

    msg = str(last_err or '')
    if 'busy' in msg.lower():
        print(
            '[gpio] Pins still held by lgpio (gpioinfo shows consumer "lg").\n'
            '[gpio] On the Pi run:\n'
            '[gpio]   sudo fuser -v /dev/gpiochip0\n'
            '[gpio]   sudo fuser -k /dev/gpiochip0\n'
            '[gpio]   gpioinfo gpiochip0 | grep -E "line +14:|line +15:|line +23:"'
        )
    raise last_err if last_err else RuntimeError('GPIO setup failed')


def read_sensors() -> int:
    """Fast multi-sample read for IR line sensors."""
    SENSOR_SAMPLES = 5
    SENSOR_SAMPLE_GAP = 0.001
    need = 3
    left = mid = right = 0
    for _ in range(SENSOR_SAMPLES):
        if lgpio.gpio_read(_chip, IR_LEFT):
            left += 1
        if lgpio.gpio_read(_chip, IR_MIDDLE):
            mid += 1
        if lgpio.gpio_read(_chip, IR_RIGHT):
            right += 1
        time.sleep(SENSOR_SAMPLE_GAP)
    state = 0
    if left >= need:
        state |= 0b100
    if mid >= need:
        state |= 0b010
    if right >= need:
        state |= 0b001
    return state


def run():
    """Follow field line: straight, S-curves, U-turns, dashed gaps, wide finish pad.

    Straight-line rule: while middle sensor sees the line → drive forward.
    Only steer hard when middle is offline (tight U / lost edge).
    """
    _history.clear()
    current_cmd = None
    segment_start = time.monotonic()

    CRUISE = 750
    # เส้นตรง: แก้เบามาก (ความเร็วใกล้กัน) — กันส่าย
    SOFT_INNER = 780
    SOFT_OUTER = 950
    # โค้ง U สั้น 12.5cm: pivot ตั้งแต่เข้าปากโค้ง (left+mid) ไม่รอ left-only
    U_SPEED = 1750
    U_BOOST = 2000
    U_ENTRY = 1500          # แรงตอนเจอ left+mid / right+mid
    WIDE = 900
    FINISH = 550

    # fmt: off
    forward_cmd = ( CRUISE, CRUISE, -CRUISE, CRUISE)
    slight_left  = ( SOFT_INNER, SOFT_INNER, -SOFT_OUTER, SOFT_OUTER)
    slight_right = ( SOFT_OUTER, SOFT_OUTER, -SOFT_INNER, SOFT_INNER)
    sharp_left   = (-U_SPEED, -U_SPEED, -U_SPEED,  U_SPEED)
    sharp_right  = ( U_SPEED,  U_SPEED,  U_SPEED, -U_SPEED)
    entry_left   = (-U_ENTRY, -U_ENTRY, -U_ENTRY,  U_ENTRY)
    entry_right  = ( U_ENTRY,  U_ENTRY,  U_ENTRY, -U_ENTRY)
    finish_cmd   = ( FINISH, FINISH, -FINISH, FINISH)
    # fmt: on

    END_HOLD_TIME = 2.5
    FINISH_GRACE  = 0.35
    MIN_TRACK_BEFORE_FINISH = 2.0
    DASH_KEEP_FORWARD = 4.0
    U_COMMIT_TIME     = 1.35   # หมุนต่อหลังเซ็นเซอร์หลุดใน U สั้น
    U_ENTRY_ESCALATE  = 0.06   # left+mid ค้างสั้นๆ → เข้าโหมด U ทันที
    WIDE_SEARCH_AFTER = 5.5
    LOST_GIVE_UP      = 14.0
    U_BOOST_AFTER = 0.08

    last_search_cmd = slight_left
    last_was_sharp  = False
    u_commit_until  = 0.0
    sharp_since     = 0.0
    curve_side      = 0        # -1 ซ้าย, +1 ขวา
    curve_since     = 0.0
    lost_since      = time.monotonic()
    all_on_since    = 0.0
    finish_seen_at  = 0.0
    finish_armed    = False
    track_started   = 0.0
    run_started     = time.monotonic()
    last_log_t      = 0.0

    print('[run] Short U 12.5cm: pivot from curve entry')
    print('[run] Gap/dash → drive forward (no spin-back)')
    print('[run] Waiting to lock onto line before finish is armed...')

    while True:
        sensors = read_sensors()
        now = time.monotonic()

        if now - last_log_t > 1.0:
            print(f'[run] sensors={sensors:03b} mid={bool(sensors & 0b010)} u_commit={now < u_commit_until}')
            last_log_t = now

        if not finish_armed and sensors in (0b010, 0b110, 0b011, 0b100, 0b001):
            if track_started == 0.0:
                track_started = now
                print(f'[run] Line lock sensors={sensors:03b}')
            elif now - track_started >= MIN_TRACK_BEFORE_FINISH:
                finish_armed = True
                print('[run] Finish armed — wide pad will stop the run')
        elif not finish_armed and sensors in (0b000, 0b111):
            track_started = 0.0

        if sensors == 0b111:
            if not finish_armed:
                all_on_since = 0.0
                cmd = forward_cmd
                lost_since = now
                last_was_sharp = False
                u_commit_until = 0.0
                curve_side = 0
            else:
                finish_seen_at = now
                sharp_since = 0.0
                if all_on_since == 0.0:
                    all_on_since = now
                    print('[run] Finish zone detected — creeping into pad...')
                elif now - all_on_since >= END_HOLD_TIME:
                    print('[run] Finish pad held - stopping.')
                    break
                cmd = finish_cmd
                last_was_sharp = False
                u_commit_until = 0.0
                curve_side = 0
                lost_since = now

        elif finish_armed and all_on_since != 0.0 and (now - finish_seen_at) <= FINISH_GRACE:
            if now - all_on_since >= END_HOLD_TIME:
                print('[run] Finish pad held - stopping.')
                break
            cmd = finish_cmd
            lost_since = now

        elif sensors == 0b000:
            all_on_since = 0.0
            lost_dur = now - lost_since
            if not finish_armed and (now - run_started) < 3.0:
                cmd = forward_cmd
            elif lost_dur > LOST_GIVE_UP:
                print('[run] No line for too long - stopping.')
                break
            elif now < u_commit_until:
                # กำลังหมุน U สั้น — เซ็นเซอร์หลุดแล้วให้หมุนต่อ ห้ามพุ่งตรง
                cmd = last_search_cmd
            elif lost_dur < DASH_KEEP_FORWARD:
                cmd = forward_cmd
            elif lost_dur < WIDE_SEARCH_AFTER:
                cmd = slight_left if last_search_cmd[0] <= 0 else slight_right
            else:
                sign = 1 if last_search_cmd[3] > 0 else -1
                cmd = (-sign * WIDE, -sign * WIDE, -sign * WIDE, sign * WIDE)

        elif sensors == 0b010:
            # กลางอย่างเดียว → ตรง; จบโหมด U
            all_on_since = 0.0
            lost_since = now
            last_was_sharp = False
            u_commit_until = 0.0
            sharp_since = 0.0
            curve_side = 0
            cmd = forward_cmd

        elif sensors == 0b110:
            # ปากโค้งซ้าย — U สั้นมักหลุดก่อน left-only ต้อง pivot ตั้งแต่จุดนี้
            all_on_since = 0.0
            lost_since = now
            if curve_side != -1:
                curve_since = now
                curve_side = -1
            if now - curve_since >= U_ENTRY_ESCALATE:
                if not last_was_sharp:
                    print('[run] Short U entry — pivot left')
                last_was_sharp = True
                u_commit_until = now + U_COMMIT_TIME
                cmd = entry_left
                last_search_cmd = sharp_left
            else:
                cmd = slight_left
                last_search_cmd = slight_left

        elif sensors == 0b011:
            all_on_since = 0.0
            lost_since = now
            if curve_side != 1:
                curve_since = now
                curve_side = 1
            if now - curve_since >= U_ENTRY_ESCALATE:
                if not last_was_sharp:
                    print('[run] Short U entry — pivot right')
                last_was_sharp = True
                u_commit_until = now + U_COMMIT_TIME
                cmd = entry_right
                last_search_cmd = sharp_right
            else:
                cmd = slight_right
                last_search_cmd = slight_right

        elif sensors == 0b100:
            all_on_since = 0.0
            lost_since = now
            curve_side = -1
            if not last_was_sharp:
                sharp_since = now
                print('[run] Tight U — pivot left')
            last_was_sharp = True
            u_commit_until = now + U_COMMIT_TIME
            if sharp_since == 0.0:
                sharp_since = now
            if now - sharp_since >= U_BOOST_AFTER:
                s = U_BOOST
                cmd = (-s, -s, -s, s)
            else:
                cmd = sharp_left
            last_search_cmd = cmd

        elif sensors == 0b001:
            all_on_since = 0.0
            lost_since = now
            curve_side = 1
            if not last_was_sharp:
                sharp_since = now
                print('[run] Tight U — pivot right')
            last_was_sharp = True
            u_commit_until = now + U_COMMIT_TIME
            if sharp_since == 0.0:
                sharp_since = now
            if now - sharp_since >= U_BOOST_AFTER:
                s = U_BOOST
                cmd = (s, s, s, -s)
            else:
                cmd = sharp_right
            last_search_cmd = cmd

        else:
            cmd = forward_cmd

        if cmd != current_cmd:
            if current_cmd is not None:
                _history.append((current_cmd, now - segment_start))
            current_cmd = cmd
            segment_start = now

        PWM.setMotorModel(*cmd)

    if current_cmd is not None:
        _history.append((current_cmd, time.monotonic() - segment_start))


def return_to_start():
    if not _history:
        print('[return] No path recorded.')
        return
    MAX_RETURN_SECS = 4.0  # must finish before SIGTERM (5s timeout in _terminate)
    deadline = time.monotonic() + MAX_RETURN_SECS
    print(f'[return] Retracing {len(_history)} segments (max {MAX_RETURN_SECS}s)...')
    for cmd, duration in reversed(_history):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        PWM.setMotorModel(*tuple(-v for v in cmd))
        time.sleep(min(duration, remaining))
    PWM.setMotorModel(0, 0, 0, 0)
    print('[return] Done.')


if __name__ == '__main__':
    print('Program is starting ...')
    setup_gpio()
    try:
        from Motor import hardware_ok
        if hardware_ok():
            print('[motor] hardware OK — short kick')
            PWM.setMotorModel(1200, 1200, -1200, 1200)
            time.sleep(0.25)
            PWM.setMotorModel(0, 0, 0, 0)
        else:
            print('[motor] HARDWARE MISSING — robot will not move (see EXTRA_PYTHONPATH)')
    except Exception as e:
        print(f'[motor] probe failed: {e}')
    _finished = False
    try:
        run()
        _finished = True
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        if _finished and _history:
            try:
                return_to_start()
            except BaseException:
                pass
        try:
            PWM.setMotorModel(0, 0, 0, 0)
        except Exception:
            pass
        cleanup_gpio()
        print('Stopped.')
