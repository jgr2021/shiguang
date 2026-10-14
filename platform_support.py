"""Small OS adapters shared by the desktop UI."""
import os
from pathlib import Path
import subprocess
import sys


def open_path(path):
    path = str(Path(path).resolve())
    if sys.platform == 'win32':
        os.startfile(path)
    else:
        subprocess.Popen(['/usr/bin/open' if sys.platform == 'darwin' else 'xdg-open', path],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wheel_units(event):
    delta = getattr(event, 'delta', 0)
    if not delta:
        return 0
    if sys.platform == 'darwin':
        return -max(-10, min(10, int(delta) or (1 if delta > 0 else -1)))
    return -int(delta / 120) or (-1 if delta > 0 else 1)


def prepare_cli_environment():
    # Finder launches apps with a minimal PATH. Do not run shell startup scripts.
    if sys.platform == 'darwin':
        paths = os.environ.get('PATH', '').split(os.pathsep)
        for value in ['/opt/homebrew/bin', '/usr/local/bin', str(Path.home() / '.local/bin')]:
            if value not in paths:
                paths.append(value)
        os.environ['PATH'] = os.pathsep.join(p for p in paths if p)
