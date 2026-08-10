"""Quick test for return_home logic using a fake motor log (no hardware needed)."""
import json
import os
import shutil

# ---------------------------------------------------------------------------
# Inject a fake Motor module so _load_real_motor finds something in PYTHONPATH
# ---------------------------------------------------------------------------
calls = []

class _FakeMotor:
    class PWM:
        @staticmethod
        def setMotorModel(a, b, c, d):
            calls.append((a, b, c, d))

fake_motor = _FakeMotor()

# Patch _load_real_motor to return our fake without needing PYTHONPATH
import services.return_home as rh
rh._load_real_motor = lambda skip_dir: fake_motor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_log(tmp_dir, entries):
    path = os.path.join(tmp_dir, 'motor_log.json')
    with open(path, 'w') as f:
        json.dump(entries, f)
    return path


def run_test(name, entries, expected_calls):
    calls.clear()
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test_tmp')
    os.makedirs(tmp, exist_ok=True)
    try:
        path = make_log(tmp, entries)
        msgs = []
        rh.return_home(path, log_fn=msgs.append)
        ok = calls == expected_calls
        status = 'PASS' if ok else 'FAIL'
        print(f'[{status}] {name}')
        if not ok:
            print(f'       expected: {expected_calls}')
            print(f'       got:      {calls}')
        # Check log reset only if the file still exists (some Pi Motor versions may remove it)
        if os.path.isfile(path):
            with open(path) as f:
                content = json.load(f)
                assert content == [], f'log not reset after return, got: {content}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# 1. Single forward step → should replay as single backward step
run_test(
    'single forward step reversed',
    [{'motors': [1000, 1000, 1000, 1000], 'duration': 0.0}],
    [(-1000, -1000, -1000, -1000), (0, 0, 0, 0)],  # move + final stop
)

# 2. Two steps → replayed in reverse order
run_test(
    'two steps reversed in order',
    [
        {'motors': [1000, 1000, 1000, 1000], 'duration': 0.0},
        {'motors': [500, 500, -500, -500], 'duration': 0.0},
    ],
    [(-500, -500, 500, 500), (-1000, -1000, -1000, -1000), (0, 0, 0, 0)],
)

# 3. Stop-only log (all zeros) → nothing to retrace
run_test(
    'stop-only log skipped',
    [{'motors': [0, 0, 0, 0], 'duration': 0.0}],
    [],
)

# 4. Bad entry missing 'motors' key → ignored, should not crash
run_test(
    'malformed entry ignored',
    [{'duration': 0.0}, {'motors': [1000, 1000, 1000, 1000], 'duration': 0.0}],
    [(-1000, -1000, -1000, -1000), (0, 0, 0, 0)],
)

# 5. mark_home resets an existing log
def test_mark_home():
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test_tmp')
    os.makedirs(tmp, exist_ok=True)
    try:
        path = os.path.join(tmp, 'motor_log.json')
        with open(path, 'w') as f:
            json.dump([{'motors': [1, 2, 3, 4], 'duration': 0.1}], f)
        rh.mark_home(path)
        with open(path) as f:
            assert json.load(f) == [], 'mark_home did not clear log'
        print('[PASS] mark_home clears log')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

test_mark_home()

print('\nAll tests done.')
