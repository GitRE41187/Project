"""Record the line features a run drives over, so return home can retrace by counting.

A script calls record() with the raw IR bitmask every loop. Sustained sensor
patterns are collapsed into events (curve, gap, pad), which return_home replays
in reverse: counting features is drift-free, unlike multiplying time by speed.

Enabled by the LINE_LOG_FILE env var, which the agent sets before a run — the
module is inert otherwise, so scripts can import it on any machine.
"""
import atexit
import json
import os
import time

LOG_FILE = os.environ.get('LINE_LOG_FILE', '')

# Sensor bitmask: left=0b100, middle=0b010, right=0b001
CURVE_LEFT = 0b100
CURVE_RIGHT = 0b001
PAD = 0b111
LOST = 0b000

# ต้องเห็นรูปแบบเดิมค้างเท่านี้ก่อนจึงนับเป็น event — กัน noise และการกระพริบ
HOLD_CURVE = 0.05
HOLD_GAP = 0.35
HOLD_PAD = 0.30

_events: list = []
_pattern = None
_pattern_since = 0.0
_pattern_logged = False


def _classify(sensors: int):
    """Map a bitmask to an event name, or None when it carries no feature."""
    if sensors == PAD:
        return 'pad'
    if sensors == LOST:
        return 'gap'
    if sensors == CURVE_LEFT:
        return 'curve_left'
    if sensors == CURVE_RIGHT:
        return 'curve_right'
    return None


def record(sensors: int) -> None:
    """Feed one sensor reading. Safe to call every loop; never raises."""
    if not LOG_FILE:
        return
    global _pattern, _pattern_since, _pattern_logged
    try:
        name = _classify(sensors)
        now = time.monotonic()

        if name != _pattern:
            _pattern = name
            _pattern_since = now
            _pattern_logged = False
            return
        if name is None or _pattern_logged:
            return

        hold = HOLD_PAD if name == 'pad' else (HOLD_GAP if name == 'gap' else HOLD_CURVE)
        if now - _pattern_since < hold:
            return

        _pattern_logged = True
        _events.append({'event': name, 'at': round(now - _start, 3)})
        print(f'[line_events] {name} (#{len(_events)})', flush=True)
        flush()
    except Exception:
        pass


def mark(name: str) -> None:
    """Record a named milestone immediately (e.g. 'finish' once the script confirms it)."""
    if not LOG_FILE:
        return
    try:
        _events.append({'event': str(name), 'at': round(time.monotonic() - _start, 3)})
        print(f'[line_events] {name} (#{len(_events)})', flush=True)
        flush()
    except Exception:
        pass


def events() -> list:
    return list(_events)


def flush() -> None:
    """Write the event list so the agent can read it after the run exits."""
    if not LOG_FILE:
        return
    try:
        tmp = LOG_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(_events, fh)
        os.replace(tmp, LOG_FILE)
    except Exception:
        pass


_start = time.monotonic()
atexit.register(flush)
