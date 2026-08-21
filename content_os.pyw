# Content OS operator launcher (no console flash).
# Start Menu shortcut target: pythonw.exe content_os.pyw
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.win_notify import run_tray  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_tray(stay=True))
