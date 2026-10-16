"""Quick test for return_home logic using a fake motor log (no hardware needed)."""
import json
import os
import shutil
import sys
import threading
import time

calls = []
failures = []


class _FakeMotor:
    class PWM:
        @staticmethod
        def setMotorModel(a, b, c, d):
            calls.append((a, b, c, d))


# Patch the motor lookup so no Freenove library / PYTHONPATH is needed
import config
from services import return_home_common as common
import services.return_home as rh
import services.return_home_retrace as rh_retrace

common.get_motor_pwm = lambda: _FakeMotor.PWM

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test_tmp')


def check(name, ok, detail=''):
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    if not ok:
        failures.append(name)
        if detail:
            print(f'       {detail}')


def make_log(entries, name='.motor_log.json'):
    os.makedirs(TMP, exist_ok=True)
    path = os.path.join(TMP, name)
    with open(path, 'w') as f:
        json.dump(entries, f)
    return path


def run_test(name, entries, expected_calls):
    """Drive the retrace path directly: hybrid mode selection is covered separately."""
    calls.clear()
    try:
        path = make_log(entries)
        rh._return_home_retrace(path, log_fn=lambda m: None)
        check(name, calls == expected_calls, f'expected {expected_calls}, got {calls}')
        # The log is only cleared once a replay actually ran
        if expected_calls and os.path.isfile(path):
            with open(path) as f:
                check(f'{name}: log reset', json.load(f) == [])
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


# ---------------------------------------------------------------------------
# Retrace
# ---------------------------------------------------------------------------
run_test(
    'single forward step reversed',
    [{'motors': [1000, 1000, 1000, 1000], 'duration': 0.0}],
    [(-1000, -1000, -1000, -1000), (0, 0, 0, 0)],  # move + final stop
)
run_test(
    'two steps reversed in order',
    [
        {'motors': [1000, 1000, 1000, 1000], 'duration': 0.0},
        {'motors': [500, 500, -500, -500], 'duration': 0.0},
    ],
    [(-500, -500, 500, 500), (-1000, -1000, -1000, -1000), (0, 0, 0, 0)],
)
run_test('stop-only log skipped', [{'motors': [0, 0, 0, 0], 'duration': 0.0}], [])
run_test(
    'malformed entry ignored',
    [{'duration': 0.0}, {'motors': [1000, 1000, 1000, 1000], 'duration': 0.0}],
    [(-1000, -1000, -1000, -1000), (0, 0, 0, 0)],
)


def test_retrace_duty_clamp():
    prev = config.RETRACE_MAX_DUTY
    config.RETRACE_MAX_DUTY = 800
    try:
        run_test(
            'retrace clamps duty to RETRACE_MAX_DUTY',
            [{'motors': [2000, 2000, -2000, 300], 'duration': 0.0}],
            [(-800, -800, 800, -300), (0, 0, 0, 0)],
        )
    finally:
        config.RETRACE_MAX_DUTY = prev


def test_retrace_cancel():
    """Stop during a long replay step must halt the motors promptly."""
    calls.clear()
    path = make_log([{'motors': [1000, 1000, 1000, 1000], 'duration': 2.0}])
    try:
        assert common.begin('u1')
        threading.Timer(0.2, lambda: common.request_cancel('u1')).start()
        t0 = time.monotonic()
        ok = rh_retrace.return_home_retrace(path, log_fn=lambda m: None)
        took = time.monotonic() - t0
        common.end()
        check('retrace cancel stops early', not ok and took < 1.0, f'ok={ok} took={took:.2f}s')
        check('retrace cancel ends with motors stopped', calls[-1:] == [(0, 0, 0, 0)], str(calls))
        check('retrace cancel status', common.status_snapshot()['state'] == 'cancelled',
              common.status_snapshot()['state'])
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


test_retrace_duty_clamp()
test_retrace_cancel()


# ---------------------------------------------------------------------------
# mark_home
# ---------------------------------------------------------------------------
def test_mark_home():
    try:
        path = make_log([{'motors': [1, 2, 3, 4], 'duration': 0.1}])
        common.set_status('at_start')
        rh.mark_home(path)
        with open(path) as f:
            check('mark_home clears log', json.load(f) == [])
        check('mark_home resets status to idle', common.status_snapshot()['state'] == 'idle')
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


test_mark_home()


# ---------------------------------------------------------------------------
# Dispatcher: which module runs for each mode
# ---------------------------------------------------------------------------
def dispatch(mode, line_result, prefer_line=False, line_events=None, entries=None):
    """Run return_home() with both modules stubbed. Returns (order of calls, final state)."""
    order = []
    orig = rh.return_home_line, rh.return_home_retrace, config.RETURN_HOME_MODE

    def fake_line(path, log_fn=None):
        order.append('line')
        order.append('active' if rh.is_returning_home() else 'inactive')
        return line_result

    def fake_retrace(path, log_fn=None):
        order.append('retrace')
        common.set_status('retrace_done')
        return True

    rh.return_home_line, rh.return_home_retrace = fake_line, fake_retrace
    config.RETURN_HOME_MODE = mode
    try:
        if entries is None:
            entries = [{'motors': [1000, 1000, -1000, 1000], 'duration': 0.5}] * 10
        path = make_log(entries)
        if line_events is not None:
            make_log([{'event': e, 'at': 0} for e in line_events], '.line_log.json')
        states = []
        rh.return_home(path, log_fn=lambda m: states.append(m), prefer_line=prefer_line, owner='u1')
        return order, common.status_snapshot()['state'], states
    finally:
        rh.return_home_line, rh.return_home_retrace, config.RETURN_HOME_MODE = orig
        shutil.rmtree(TMP, ignore_errors=True)


def test_dispatch():
    order, state, _ = dispatch('line', line_result=False)
    check('line mode: no retrace when line cannot start', order == ['line', 'active'], str(order))
    check('line mode: reports failed', state == 'failed', state)

    order, _, _ = dispatch('line', line_result=True)
    check('line mode: line handled', order == ['line', 'active'], str(order))

    order, _, _ = dispatch('hybrid', line_result=True, prefer_line=True)
    check('hybrid+IR: line handled, no retrace', order == ['line', 'active'], str(order))

    order, state, _ = dispatch('hybrid', line_result=False, prefer_line=True)
    check('hybrid+IR: retrace backup when line cannot start',
          order == ['line', 'active', 'retrace'], str(order))
    check('hybrid+IR: backup status', state == 'retrace_done', state)

    order, _, _ = dispatch('hybrid', line_result=True, prefer_line=False)
    check('hybrid without IR: line skipped', 'line' not in order, str(order))

    order, _, _ = dispatch('retrace', line_result=True, prefer_line=True)
    check('retrace mode: retrace only', order == ['retrace'], str(order))

    _, _, msgs = dispatch('line', line_result=True, line_events=['curve_left', 'finish'])
    check('finish marker reported', any('status=finish_reached' in m for m in msgs), str(msgs))

    check('not active after return_home returns', not rh.is_returning_home())

    # Probe: scan missed the IR, but the log is unsuitable for retrace
    zigzag = [{'motors': [1000, 1000, -m, m], 'duration': 0.1}
              for m in [600, 1200] * 25]
    order, _, _ = dispatch('hybrid', line_result=True, entries=zigzag)
    check('probe: long line-follow log tries line', order == ['line', 'active'], str(order))

    order, _, _ = dispatch('hybrid', line_result=False, entries=zigzag)
    check('probe: no line under robot falls back to retrace',
          order == ['line', 'active', 'retrace'], str(order))

    order, _, _ = dispatch('hybrid', line_result=True, entries=[])
    check('probe: empty log tries line', order == ['line', 'active'], str(order))

    order, _, _ = dispatch('hybrid', line_result=True, entries=zigzag[:10] + [{'truncated': 5}])
    check('probe: truncated log tries line', order == ['line', 'active'], str(order))

    prev = config.HYBRID_LINE_PROBE
    config.HYBRID_LINE_PROBE = False
    try:
        order, _, _ = dispatch('hybrid', line_result=True, entries=zigzag)
        check('probe disabled: retrace only', order == ['retrace'], str(order))
    finally:
        config.HYBRID_LINE_PROBE = prev


def test_no_overlap():
    """A second return_home while one is running must not touch the motors."""
    assert common.begin('u1')
    try:
        order, _, msgs = dispatch('hybrid', line_result=True, prefer_line=True)
        check('duplicate return_home ignored', order == [], str(order))
        check('duplicate return_home logged', any('already running' in m for m in msgs), str(msgs))
    finally:
        common.end()


def test_cancel_ownership():
    assert common.begin('u1')
    try:
        check('other user cannot cancel', not rh.cancel_return_home('u2'))
        check('owner can cancel', rh.cancel_return_home('u1') and common.cancelled())
    finally:
        common.end()
    check('cancel flag cleared after end', not common.cancelled())
    check('cancel when idle is a no-op', not rh.cancel_return_home('u1'))


test_dispatch()
test_no_overlap()
test_cancel_ownership()


# ---------------------------------------------------------------------------
# code_runner: no new run while returning, Stop cancels return home
# ---------------------------------------------------------------------------
def test_code_runner_guards():
    try:
        import services.code_runner as cr
    except Exception as e:
        print(f'[SKIP] code_runner guards (import failed: {e})')
        return
    assert common.begin('u1')
    try:
        ok, msg = cr.run_user_code('u1', __file__, set())
        check('run refused while returning home', not ok and 'returning home' in msg, msg)
        ok, msg = cr.stop_user_code('u1')
        check('stop cancels return home', ok and common.cancelled(), msg)
    finally:
        common.end()
    ok, _ = cr.stop_user_code('u1')
    check('stop with nothing running still reports not found', not ok)


test_code_runner_guards()


# ---------------------------------------------------------------------------
# Line follow loop with a scripted fake IR array
# ---------------------------------------------------------------------------
import services.return_home_line as rh_line


class _FakeIR:
    """Sensor bitmask as a function of time since the follow phase began."""
    def __init__(self, script):
        self.script = script          # list of (until_secs, bitmask); last one holds
        self.t0 = None
        self.closed = False

    def bits(self):
        if self.t0 is None:
            self.t0 = time.monotonic()
        t = time.monotonic() - self.t0
        for until, b in self.script:
            if t < until:
                return b
        return self.script[-1][1]


def run_line(script, overrides=None, cancel_after=None, line_events=None):
    fake = _FakeIR(script)
    saved = {}
    fast = {
        'LINE_RETURN_UTURN_SECS': 0.05, 'LINE_RETURN_IGNORE_PAD_SECS': 0.2,
        'LINE_RETURN_PAD_HOLD': 0.2, 'LINE_RETURN_MAX_SECS': 3.0,
        'LINE_RETURN_LOST_GIVE_UP': 0.5, 'LINE_RETURN_NO_FALLBACK_AFTER': 0.3,
    }
    fast.update(overrides or {})
    for k, v in fast.items():
        saved[k] = getattr(config, k)
        setattr(config, k, v)
    orig = rh_line._ir_open, rh_line._ir_read, rh_line._ir_close
    rh_line._ir_open = lambda: ('lg', 'h', (14, 15, 23))
    rh_line._ir_read = lambda *a: fake.bits()
    rh_line._ir_close = lambda *a: setattr(fake, 'closed', True)
    calls.clear()
    msgs = []
    try:
        path = make_log([{'motors': [1000, 1000, -1000, 1000], 'duration': 0.5}])
        if line_events is not None:
            make_log([{'event': e, 'at': 0} for e in line_events], '.line_log.json')
        assert common.begin('u1')
        if cancel_after is not None:
            threading.Timer(cancel_after, lambda: common.request_cancel('u1')).start()
        handled = rh_line.return_home_line(path, log_fn=msgs.append)
        state = common.status_snapshot()['state']
        common.end()
        return handled, state, list(calls), fake.closed, msgs
    finally:
        rh_line._ir_open, rh_line._ir_read, rh_line._ir_close = orig
        for k, v in saved.items():
            setattr(config, k, v)
        shutil.rmtree(TMP, ignore_errors=True)


def test_line_loop():
    # pre-check read, then line, then START pad held
    handled, state, mcalls, closed, msgs = run_line([(0.6, 0b010), (99, 0b111)])
    check('line: pad without landmark log is not claimed as START',
          handled and state == 'pad_reached', f'{handled} {state}')
    check('line: motors stopped and IR released', mcalls[-1] == (0, 0, 0, 0) and closed)
    check('line: U-turn is a left pivot', (-1500, -1500, -1500, 1500) in mcalls, str(mcalls[:4]))
    check('line: phases reported',
          any('status=line_uturn' in m for m in msgs) and any('status=line_following' in m for m in msgs))

    # out: curve_left then FINISH → back: expect curve_right before the pad
    handled, state, _, _, _ = run_line(
        [(0.8, 0b010), (1.0, 0b001), (1.3, 0b010), (99, 0b111)],
        line_events=['pad', 'curve_left', 'pad', 'finish'],
    )
    check('line: landmarks matched reports at_start', handled and state == 'at_start', f'{handled} {state}')

    handled, state, _, _, msgs = run_line(
        [(0.8, 0b010), (99, 0b111)],
        line_events=['curve_left', 'finish'],
    )
    check('line: unmet landmarks reports pad_reached', handled and state == 'pad_reached', f'{handled} {state}')
    check('line: unmet count in status detail',
          common.status_snapshot()['detail'] == '1 landmarks unmet', common.status_snapshot()['detail'])

    handled, _, mcalls, closed, _ = run_line([(99, 0b000)])
    check('line: no line under robot - not handled, motors untouched',
          not handled and mcalls == [] and closed, f'{handled} {mcalls}')

    handled, state, mcalls, closed, _ = run_line([(99, 0b010)], cancel_after=0.4)
    check('line: Stop cancels follow, no retrace afterwards',
          handled and state == 'cancelled' and mcalls[-1] == (0, 0, 0, 0) and closed, f'{handled} {state}')

    handled, state, mcalls, _, _ = run_line([(99, 0b010)], overrides={'LINE_RETURN_MAX_SECS': 0.6})
    check('line: timeout stops and skips replay',
          handled and state == 'timeout' and mcalls[-1] == (0, 0, 0, 0), f'{handled} {state}')

    handled, state, _, _, _ = run_line([(0.6, 0b010), (99, 0b000)])
    check('line: lost line gives up as failed', handled and state == 'failed', f'{handled} {state}')


test_line_loop()


# ---------------------------------------------------------------------------
# Landmarks
# ---------------------------------------------------------------------------
def test_expected_return_features():
    cases = [
        ('pads dropped', ['pad', 'curve_left', 'pad'], ['curve_right']),
        ('finish marker dropped', ['curve_left', 'pad', 'finish'], ['curve_right']),
        ('order reversed', ['curve_left', 'gap'], ['gap', 'curve_right']),
        ('curves mirrored', ['curve_right', 'curve_right'], ['curve_left', 'curve_left']),
        ('empty log', [], []),
    ]
    for name, events, expected in cases:
        got = rh._expected_return_features(events)
        check(f'expected_return_features: {name}', got == expected, f'expected {expected}, got {got}')


def test_line_event_classify():
    cases = [(0b111, 'pad'), (0b000, 'gap'), (0b100, 'curve_left'),
             (0b001, 'curve_right'), (0b010, None), (0b110, None)]
    bad = [(bits, rh._classify_feature(bits), want) for bits, want in cases
           if rh._classify_feature(bits) != want]
    check('classify_feature matches line_events', not bad, str(bad))


def test_line_events_mark():
    import importlib
    log = make_log([], '.line_log.json')
    prev = os.environ.get('LINE_LOG_FILE')
    os.environ['LINE_LOG_FILE'] = log
    try:
        import line_events
        importlib.reload(line_events)
        line_events.mark('finish')
        line_events.flush()
        with open(log) as f:
            names = [e['event'] for e in json.load(f)]
        check('line_events.mark writes finish', names == ['finish'], str(names))
    finally:
        if prev is None:
            os.environ.pop('LINE_LOG_FILE', None)
        else:
            os.environ['LINE_LOG_FILE'] = prev
        shutil.rmtree(TMP, ignore_errors=True)


def test_motor_recorder():
    """Repeats merge into one entry; periodic flush survives a kill that skips atexit."""
    import subprocess
    os.makedirs(TMP, exist_ok=True)
    log = os.path.join(TMP, '.motor_log.json')
    child = (
        'import os, time\n'
        'import Motor\n'
        'for _ in range(50): Motor.PWM.setMotorModel(1000, 1000, -1000, 1000)\n'
        'time.sleep(0.25)\n'
        'for v in (1, 2, 3, 4): Motor.PWM.setMotorModel(v, v, v, v)\n'
        'Motor.PWM.setMotorModel(900, 900, -900, 900)\n'
        'time.sleep(0.5)\n'
        'os._exit(0)\n'   # like SIGKILL: atexit never runs
    )
    env = dict(os.environ, MOTOR_LOG_FILE=log, MOTOR_LOG_FLUSH_SECS='0.1', MOTOR_LOG_MAX='3')
    try:
        subprocess.run([sys.executable, '-c', child], cwd=os.path.dirname(os.path.abspath(__file__)),
                       env=env, capture_output=True, timeout=20)
        with open(log) as f:
            data = json.load(f)
        motors = [d['motors'] for d in data if 'motors' in d]
        check('recorder: log written without atexit', bool(motors), str(data))
        check('recorder: keeps newest commands within MOTOR_LOG_MAX',
              motors == [[3, 3, 3, 3], [4, 4, 4, 4], [900, 900, -900, 900]], str(motors))
        check('recorder: marks truncation', {'truncated': 3} in data, str(data))
        check('recorder: running command duration grows between flushes',
              data[2]['duration'] >= 0.3, str(data[2]))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    child_merge = (
        'import os, time\n'
        'import Motor\n'
        'for _ in range(50): Motor.PWM.setMotorModel(1000, 1000, -1000, 1000)\n'
        'Motor.PWM.setMotorModel(0, 0, 0, 0)\n'
    )
    os.makedirs(TMP, exist_ok=True)
    env['MOTOR_LOG_MAX'] = '2000'
    try:
        subprocess.run([sys.executable, '-c', child_merge], cwd=os.path.dirname(os.path.abspath(__file__)),
                       env=env, capture_output=True, timeout=20)
        with open(log) as f:
            motors = [d['motors'] for d in json.load(f) if 'motors' in d]
        check('recorder: identical repeats merged', motors == [[1000, 1000, -1000, 1000], [0, 0, 0, 0]], str(motors))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def test_retrace_truncated_warning():
    msgs = []
    try:
        path = make_log([{'motors': [1000, 1000, 1000, 1000], 'duration': 0.0}, {'truncated': 7}])
        rh_retrace.return_home_retrace(path, log_fn=msgs.append)
        check('retrace warns on truncated log', any('first 7 commands' in m for m in msgs), str(msgs))
        check('retrace status mentions partial path',
              common.status_snapshot()['detail'].startswith('partial path'), common.status_snapshot()['detail'])
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


test_expected_return_features()
test_line_event_classify()
test_line_events_mark()
test_motor_recorder()
test_retrace_truncated_warning()

print(f'\nAll tests done. {len(failures)} failed.')
sys.exit(1 if failures else 0)
