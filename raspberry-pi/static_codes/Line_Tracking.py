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

# Field profile (จูนตามสนาม): เส้นตรง · โค้ง U · โค้ง S · เส้นประ · แผ่นจบกว้าง
# duty3 (right_upper) กลับขั้ว — รูปแบบเดียวกับ test.py / return_home
# กลับจุดเริ่ม: ใช้ agent RETURN_HOME_ON_STOP (services/return_home) — ไม่ retrace ในสคริปต์นี้


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
    """Follow field line: straight, S, U, dashed, wide finish.

    Tight curves: detect → brake/stop → slow in-place pivot until mid
    sensor locks the line again (better for short/narrow U ~12.5 cm).
    """
    current_cmd = None

    # โปรไฟล์รถใหญ่: โมเมนตัมสูง / เลี้ยวยาก → เข้าโค้งช้า + เบรกฆ่าความเร็ว + pivot แรง
    CRUISE = 650
    SOFT_INNER = 700
    SOFT_OUTER = 880
    PIVOT_SPEED = 1600
    PIVOT_FAST = 1900
    WIDE = 1000
    FINISH = 450
    STOP = (0, 0, 0, 0)

    # fmt: off
    forward_cmd = ( CRUISE, CRUISE, -CRUISE, CRUISE)
    slight_left  = ( SOFT_INNER, SOFT_INNER, -SOFT_OUTER, SOFT_OUTER)
    slight_right = ( SOFT_OUTER, SOFT_OUTER, -SOFT_INNER, SOFT_INNER)
    pivot_left   = (-PIVOT_SPEED, -PIVOT_SPEED, -PIVOT_SPEED,  PIVOT_SPEED)
    pivot_right  = ( PIVOT_SPEED,  PIVOT_SPEED,  PIVOT_SPEED, -PIVOT_SPEED)
    pivot_left_fast  = (-PIVOT_FAST, -PIVOT_FAST, -PIVOT_FAST,  PIVOT_FAST)
    pivot_right_fast = ( PIVOT_FAST,  PIVOT_FAST,  PIVOT_FAST, -PIVOT_FAST)
    finish_cmd   = ( FINISH, FINISH, -FINISH, FINISH)
    # fmt: on

    # แผ่นจบ: 0b111 ต้องค้าง ≥1 วิ ถึงจะจบ — สั้นกว่านั้นไม่เข้าโหมดจบ (ไปต่อตามเส้น)
    FINISH_HOLD_SEC = 1.0
    MIN_TRACK_BEFORE_FINISH = 2.0
    DASH_KEEP_FORWARD = 4.0
    WIDE_SEARCH_AFTER = 5.5
    LOST_GIVE_UP      = 14.0

    # รถใหญ่: เบรกนานขึ้นนิดเพื่อฆ่าโมเมนตัม แล้วหมุนแรง/นานกว่า
    CURVE_CONFIRM = 0.02       # เริ่มโค้งเร็ว (ตัวถังยื่น ต้องหันก่อน)
    BRAKE_TIME = 0.15          # ฆ่าความเร็วก่อนหมุน
    PIVOT_MAX = 2.0            # หมุนได้นานขึ้นให้ครบ U แคบ
    PIVOT_FAST_AFTER = 0.40

    # phase: 'follow' | 'brake' | 'pivot'
    phase = 'follow'
    pivot_dir = 0              # -1 left, +1 right
    phase_since = 0.0
    curve_hint_since = 0.0
    curve_hint_dir = 0
    last_search_cmd = slight_left
    lost_since = time.monotonic()
    all_on_since = 0.0
    finish_armed = False
    track_started = 0.0
    run_started = time.monotonic()
    last_log_t = 0.0

    print('[run] Large-robot curve: slow approach → brake → strong pivot')
    print('[run] Gap/dash → drive forward (no spin-back)')
    print('[run] Finish: 3 sensors must hold ≥1.0s (shorter = ignore)')
    print('[run] Waiting to lock onto line before finish is armed...')

    def _start_curve(direction, now):
        nonlocal phase, pivot_dir, phase_since, last_search_cmd
        phase = 'brake'
        pivot_dir = direction
        phase_since = now
        last_search_cmd = pivot_left if direction < 0 else pivot_right
        side = 'left' if direction < 0 else 'right'
        print(f'[run] Curve {side} — brake then slow pivot')

    while True:
        sensors = read_sensors()
        now = time.monotonic()

        if now - last_log_t > 1.0:
            print(
                f'[run] sensors={sensors:03b} phase={phase} '
                f'mid={bool(sensors & 0b010)}'
            )
            last_log_t = now

        if not finish_armed and sensors in (0b010, 0b110, 0b011, 0b100, 0b001):
            if track_started == 0.0:
                track_started = now
                print(f'[run] Line lock sensors={sensors:03b}')
            elif now - track_started >= MIN_TRACK_BEFORE_FINISH:
                finish_armed = True
                print('[run] Finish armed — wide pad will end the run')
        elif (
            not finish_armed
            and sensors == 0b111
            and track_started == 0.0
            and (now - run_started) < 1.5
        ):
            # ยังอยู่บนแผ่นสตาร์ท — ยังไม่นับว่า lock เส้น
            pass
        elif (
            not finish_armed
            and track_started != 0.0
            and (now - track_started) >= MIN_TRACK_BEFORE_FINISH
        ):
            finish_armed = True
            print('[run] Finish armed — wide pad will end the run')

        # --- finish: 3 sensors ต้องค้าง ≥1s — สั้นกว่านั้นไม่เข้าจบ ---
        if sensors == 0b111:
            phase = 'follow'
            if not finish_armed:
                all_on_since = 0.0
                cmd = finish_cmd
                lost_since = now
            else:
                if all_on_since == 0.0:
                    all_on_since = now
                    print('[run] 3-sensor — verifying (need ≥1.0s)')
                elif now - all_on_since >= FINISH_HOLD_SEC:
                    print('[run] Finish confirmed (≥1.0s) — ending run.')
                    PWM.setMotorModel(0, 0, 0, 0)
                    break
                cmd = finish_cmd
                lost_since = now

        else:
            if all_on_since != 0.0:
                held = now - all_on_since
                if held < FINISH_HOLD_SEC:
                    print(f'[run] 3-sensor only {held:.2f}s (<1s) — ignore, keep following')
                all_on_since = 0.0

            # --- active stop-then-pivot curve ---
            if phase == 'brake':
                cmd = STOP
                if now - phase_since >= BRAKE_TIME:
                    phase = 'pivot'
                    phase_since = now
                    print('[run] Pivot start')

            elif phase == 'pivot':
                elapsed = now - phase_since
                if sensors == 0b010 or sensors == 0b110 or sensors == 0b011:
                    phase = 'follow'
                    lost_since = now
                    curve_hint_dir = 0
                    print('[run] Mid locked — resume follow')
                    if sensors == 0b010:
                        cmd = forward_cmd
                    elif sensors == 0b110:
                        cmd = slight_left
                    else:
                        cmd = slight_right
                elif elapsed >= PIVOT_MAX:
                    phase = 'follow'
                    lost_since = now
                    print('[run] Pivot timeout — resume search')
                    cmd = last_search_cmd
                else:
                    lost_since = now
                    if elapsed >= PIVOT_FAST_AFTER:
                        cmd = pivot_left_fast if pivot_dir < 0 else pivot_right_fast
                    else:
                        cmd = pivot_left if pivot_dir < 0 else pivot_right
                    last_search_cmd = cmd

            # --- lost line ---
            elif sensors == 0b000:
                lost_dur = now - lost_since
                curve_hint_dir = 0
                if not finish_armed and (now - run_started) < 3.0:
                    cmd = forward_cmd
                elif lost_dur > LOST_GIVE_UP:
                    print('[run] No line for too long - stopping.')
                    break
                elif lost_dur < DASH_KEEP_FORWARD:
                    cmd = forward_cmd
                elif lost_dur < WIDE_SEARCH_AFTER:
                    cmd = slight_left if last_search_cmd[0] <= 0 else slight_right
                else:
                    sign = 1 if last_search_cmd[3] > 0 else -1
                    cmd = (-sign * WIDE, -sign * WIDE, -sign * WIDE, sign * WIDE)

            elif sensors == 0b010:
                lost_since = now
                curve_hint_dir = 0
                phase = 'follow'
                cmd = forward_cmd

            elif sensors in (0b110, 0b100):
                lost_since = now
                want = -1
                if curve_hint_dir != want:
                    curve_hint_dir = want
                    curve_hint_since = now
                    cmd = slight_left
                    last_search_cmd = slight_left
                elif now - curve_hint_since < CURVE_CONFIRM:
                    cmd = slight_left if sensors == 0b110 else pivot_left
                else:
                    _start_curve(want, now)
                    cmd = STOP

            elif sensors in (0b011, 0b001):
                lost_since = now
                want = 1
                if curve_hint_dir != want:
                    curve_hint_dir = want
                    curve_hint_since = now
                    cmd = slight_right
                    last_search_cmd = slight_right
                elif now - curve_hint_since < CURVE_CONFIRM:
                    cmd = slight_right if sensors == 0b011 else pivot_right
                else:
                    _start_curve(want, now)
                    cmd = STOP

            else:
                cmd = forward_cmd

        if cmd != current_cmd:
            current_cmd = cmd

        PWM.setMotorModel(*cmd)


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
    try:
        run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        try:
            PWM.setMotorModel(0, 0, 0, 0)
        except Exception:
            pass
        cleanup_gpio()
        print('Stopped.')
