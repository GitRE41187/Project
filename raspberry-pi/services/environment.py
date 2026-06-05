"""Runtime environment: a dedicated virtual environment for user code plus
automatic dependency installation at upload time.

Goal: when code is uploaded, figure out which third-party packages it imports
and `pip install` them into an isolated venv *ahead of time*, so pressing Run
never dies with ModuleNotFoundError. The same venv is then used to run the
code, giving a lightweight, docker-like isolation that still sees the Pi's
system packages (RPi.GPIO, picamera, ...) via --system-site-packages.
"""
import ast
import os
import subprocess
import sys
import threading

from config import (
    PYTHON_EXE,
    VENV_DIR,
    RUN_SANDBOX,
    PIP_INDEX_URL,
    PIP_TIMEOUT,
    STATIC_CODES_DIR,
    UPLOAD_FOLDER,
    _PKG_DIR,
)

# Map an import name -> the pip package that actually provides it.
MODULE_TO_PACKAGE = {
    'cv2': 'opencv-python',
    'PIL': 'Pillow',
    'serial': 'pyserial',
    'yaml': 'PyYAML',
    'sklearn': 'scikit-learn',
    'skimage': 'scikit-image',
    'bs4': 'beautifulsoup4',
    'dotenv': 'python-dotenv',
    'Crypto': 'pycryptodome',
    'dateutil': 'python-dateutil',
    'mpl_toolkits': 'matplotlib',
    'matplotlib': 'matplotlib',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'requests': 'requests',
}

# Import names we must NOT try to install with pip: hardware/system packages
# (provided by the OS, visible through --system-site-packages) and the helper
# modules that ship alongside user code (Motor.py, ADC.py, ...).
RESERVED_MODULES = {
    'rpi', 'gpio', 'motor', 'adc', 'picamera', 'picamera2', 'smbus', 'smbus2',
    'spidev', 'gpiozero', 'board', 'busio', 'pigpio', 'adafruit_blinka',
}

_venv_lock = threading.Lock()


def _is_windows() -> bool:
    return os.name == 'nt'


def venv_python_path() -> str:
    """Path to the python interpreter inside the runtime venv."""
    if _is_windows():
        return os.path.join(VENV_DIR, 'Scripts', 'python.exe')
    return os.path.join(VENV_DIR, 'bin', 'python')


def _stdlib_names() -> set:
    names = set(getattr(sys, 'stdlib_module_names', set()))
    # Fallback list for Python < 3.10 where stdlib_module_names is absent.
    names.update({
        'math', 'random', 'time', 'datetime', 'json', 'os', 'sys', 're',
        'collections', 'itertools', 'functools', 'operator', 'urllib',
        'threading', 'subprocess', 'typing', 'asyncio', 'logging', 'pathlib',
        'string', 'io', 'base64', 'socket', 'struct', 'enum', 'abc', 'copy',
    })
    return names


def _local_module_names() -> set:
    """Top-level names of .py files that live next to user code, so we don't
    try to pip-install our own helper modules."""
    names = set()
    search_dirs = [_PKG_DIR, STATIC_CODES_DIR, os.path.join(_PKG_DIR, UPLOAD_FOLDER)]
    for d in search_dirs:
        try:
            for name in os.listdir(d):
                if name.endswith('.py'):
                    names.add(name[:-3].lower())
        except OSError:
            continue
    return names


def detect_imports(file_path: str) -> set:
    """Return the set of top-level module names imported by a python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (OSError, SyntaxError, ValueError):
        return set()

    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            # Skip relative imports (from . import x) -> node.level > 0.
            if node.level == 0 and node.module:
                modules.add(node.module.split('.')[0])
    return modules


def ensure_venv(log_fn=None) -> str:
    """Create the runtime venv if needed and return its python path. Falls back
    to PYTHON_EXE if the venv can't be created."""
    def log(msg):
        if log_fn:
            log_fn(msg)

    py = venv_python_path()
    if os.path.isfile(py):
        return py

    with _venv_lock:
        if os.path.isfile(py):
            return py
        log(f'[env] creating runtime virtual environment at {VENV_DIR}')
        try:
            subprocess.run(
                [PYTHON_EXE, '-m', 'venv', '--system-site-packages', VENV_DIR],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            detail = getattr(e, 'stderr', '') or str(e)
            log(f'[env] venv creation failed, falling back to system python: {detail}')
            return PYTHON_EXE
        # Make sure pip is usable inside the venv.
        try:
            subprocess.run(
                [py, '-m', 'pip', '--version'],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, OSError):
            try:
                subprocess.run([py, '-m', 'ensurepip', '--upgrade'], capture_output=True, text=True)
            except OSError:
                pass
        log('[env] runtime virtual environment ready')
        return py


def get_runtime_python(log_fn=None) -> str:
    """Interpreter that should run user code, honouring RUN_SANDBOX."""
    if RUN_SANDBOX == 'none':
        return PYTHON_EXE
    # 'docker' still needs a local python only as a fallback; the runner handles
    # the docker command itself. For 'venv' (default) we build/return the venv.
    if RUN_SANDBOX == 'venv':
        return ensure_venv(log_fn)
    return PYTHON_EXE


def _module_available(python_exe: str, module: str) -> bool:
    try:
        result = subprocess.run(
            [python_exe, '-c', f'import importlib.util,sys; sys.exit(0 if importlib.util.find_spec({module!r}) else 1)'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _installable_packages(modules: set, allowed_imports=None, restrict_to_whitelist=False) -> dict:
    """Map import names -> pip package, filtering out stdlib / local / system
    modules and (optionally) anything outside the import whitelist."""
    stdlib = _stdlib_names()
    local = _local_module_names()
    allowed_lower = {str(a).split('.')[0].lower() for a in (allowed_imports or set())}

    targets = {}
    for mod in modules:
        low = mod.lower()
        if not mod or low in stdlib or low in local or low in RESERVED_MODULES:
            continue
        if restrict_to_whitelist and allowed_lower and low not in allowed_lower:
            # Not allowed and not auto-installable; leave it for validation to reject.
            continue
        targets[mod] = MODULE_TO_PACKAGE.get(mod, mod)
    return targets


def install_dependencies(file_path: str, allowed_imports=None, restrict_to_whitelist=False, log_fn=None) -> dict:
    """Detect imports in `file_path` and install the missing third-party
    packages into the runtime venv. Returns a report dict."""
    def log(msg):
        if log_fn:
            log_fn(msg)

    report = {'installed': [], 'skipped': [], 'failed': [], 'requested': []}

    if RUN_SANDBOX == 'docker':
        # Dependencies are installed inside the container at run time instead.
        report['note'] = 'docker sandbox: dependencies installed in container at run'
        return report

    python_exe = get_runtime_python(log_fn)

    modules = detect_imports(file_path)
    targets = _installable_packages(modules, allowed_imports, restrict_to_whitelist)
    report['requested'] = sorted(set(targets.values()))

    if not targets:
        log('[deps] no third-party packages required')
        return report

    env = os.environ.copy()
    base_cmd = [python_exe, '-m', 'pip', 'install', '--disable-pip-version-check', '--timeout', str(PIP_TIMEOUT)]
    if PIP_INDEX_URL:
        base_cmd += ['--index-url', PIP_INDEX_URL]

    for module, package in sorted(targets.items()):
        if _module_available(python_exe, module):
            report['skipped'].append(package)
            log(f'[deps] {package} already available, skipping')
            continue
        log(f'[deps] installing {package} ...')
        try:
            result = subprocess.run(
                base_cmd + [package],
                capture_output=True,
                text=True,
                env=env,
                timeout=max(PIP_TIMEOUT * 3, 300),
            )
        except subprocess.TimeoutExpired:
            report['failed'].append(package)
            log(f'[deps] {package} install timed out')
            continue
        except OSError as e:
            report['failed'].append(package)
            log(f'[deps] {package} install error: {e}')
            continue

        if result.returncode == 0:
            report['installed'].append(package)
            log(f'[deps] {package} installed')
        else:
            report['failed'].append(package)
            tail = (result.stderr or result.stdout or '').strip().splitlines()[-3:]
            log(f'[deps] {package} install failed: {" ".join(tail)}')

    return report
