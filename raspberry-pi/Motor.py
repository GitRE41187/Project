"""Motor.py wrapper – proxies to the real Motor and records setMotorModel calls
when MOTOR_LOG_FILE env var is set, enabling the return-home feature."""
import atexit
import importlib.util
import os
import time

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.environ.get('MOTOR_LOG_FILE', '')
_MAX_COMMANDS = int(os.environ.get('MOTOR_LOG_MAX', '2000'))
_commands: list = []
_warn_no_hw = False

# Common Freenove install locations if EXTRA_PYTHONPATH is missing
_FALLBACK_MOTOR_DIRS = [
    os.path.expanduser('~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server'),
    '/home/huntrix/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server',
    '/home/pi/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server',
]


def _iter_motor_search_dirs():
    seen = set()
    for path in os.environ.get('PYTHONPATH', '').split(os.pathsep):
        if not path:
            continue
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(_PKG_DIR):
            continue
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        yield path
    for path in _FALLBACK_MOTOR_DIRS:
        if not path or not os.path.isdir(path):
            continue
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        yield path


def _load_real_motor_module():
    """Load motor module from PYTHONPATH / Freenove Server, skipping this wrapper."""
    for path in _iter_motor_search_dirs():
        for filename in ('Motor.py', 'motor.py'):
            candidate = os.path.join(path, filename)
            if not os.path.isfile(candidate):
                continue
            try:
                spec = importlib.util.spec_from_file_location('_real_Motor_module', candidate)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                print(f'[Motor] hardware driver loaded from {candidate}', flush=True)
                return mod
            except Exception as e:
                print(f'[Motor] failed loading {candidate}: {e}', flush=True)
                continue
    return None


_real_mod = _load_real_motor_module()
_real_pwm = None  # instantiated lazily on first setMotorModel call


def _get_real_pwm():
    """Lazily instantiate the hardware motor object so I2C init happens at first use."""
    global _real_pwm
    if _real_pwm is not None:
        return _real_pwm
    if _real_mod is None:
        return None
    if hasattr(_real_mod, 'PWM'):
        _real_pwm = _real_mod.PWM
        return _real_pwm
    import inspect
    _MOTOR_METHODS = ('setMotorModel', 'set_motor_model')
    candidates = ['Motor', 'Ordinary_Car', 'motor', 'MotorDriver']
    all_classes = [name for name, _ in inspect.getmembers(_real_mod, inspect.isclass)]
    for name in candidates + [c for c in all_classes if c not in candidates]:
        cls = getattr(_real_mod, name, None)
        if not isinstance(cls, type):
            continue
        method = next((m for m in _MOTOR_METHODS if hasattr(cls, m)), None)
        if method is None:
            continue
        try:
            _real_pwm = cls()
            return _real_pwm
        except Exception as e:
            print(f'[Motor] init {name} failed: {e}', flush=True)
            continue
    return None


def hardware_ok() -> bool:
    """True if the Freenove/hardware motor driver is available."""
    return _get_real_pwm() is not None


class _RecordingPWM:
    def setMotorModel(self, a, b, c, d):
        global _warn_no_hw
        if _LOG_FILE:
            now = time.time()
            if _commands:
                _commands[-1]['duration'] = now - _commands[-1]['_ts']
            _commands.append({'motors': [a, b, c, d], '_ts': now, 'duration': 0})
            if len(_commands) > _MAX_COMMANDS:
                _commands.pop(0)
        real = _get_real_pwm()
        if real is None:
            if not _warn_no_hw:
                print(
                    '[Motor] ERROR: no hardware driver — motors will not move.\n'
                    '[Motor] Set in ~/field-control/.env then restart app.py:\n'
                    '[Motor]   EXTRA_PYTHONPATH=/home/huntrix/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server',
                    flush=True,
                )
                _warn_no_hw = True
            return
        if hasattr(real, 'setMotorModel'):
            real.setMotorModel(a, b, c, d)
        elif hasattr(real, 'set_motor_model'):
            real.set_motor_model(a, b, c, d)


PWM = _RecordingPWM()


def _flush_log():
    if not _LOG_FILE or not _commands:
        return
    _commands[-1]['duration'] = time.time() - _commands[-1].get('_ts', time.time())
    data = [{'motors': c['motors'], 'duration': c['duration']} for c in _commands]
    try:
        from config import ODOMETRY_SPEED_SCALE, ODOMETRY_WHEEL_BASE, ODOMETRY_DUTY3_INVERTED
        import math
        x, y, theta = 0.0, 0.0, 0.0
        for cmd in data:
            motors = cmd['motors']
            dur = min(max(cmd.get('duration', 0), 0), 2.0)
            if dur <= 0:
                continue
            left = (motors[0] + motors[1]) / 2.0
            d3 = -motors[2] if ODOMETRY_DUTY3_INVERTED else motors[2]
            right = (d3 + motors[3]) / 2.0
            vl, vr = left * ODOMETRY_SPEED_SCALE, right * ODOMETRY_SPEED_SCALE
            v, w = (vl + vr) / 2.0, (vr - vl) / ODOMETRY_WHEEL_BASE
            if abs(w) < 1e-6:
                x += v * dur * math.cos(theta)
                y += v * dur * math.sin(theta)
            else:
                r, dt = v / w, w * dur
                x += r * (math.sin(theta + dt) - math.sin(theta))
                y -= r * (math.cos(theta + dt) - math.cos(theta))
                theta = (theta + dt + math.pi) % (2 * math.pi) - math.pi
        data.append({'pose': {'x': round(x, 4), 'y': round(y, 4), 'theta': round(theta, 4)}})
    except Exception:
        pass
    try:
        import json
        with open(_LOG_FILE, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
    except Exception:
        pass


atexit.register(_flush_log)
