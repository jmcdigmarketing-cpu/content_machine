# Content OS - the app window, no console (#982).
# Start Menu / Desktop shortcut target: pythonw.exe content_os.pyw  (py -m scripts.ops shortcut)
#   content_os.pyw          the app: Home, New video, Review, Queue, Costs, Studio, Brand
#   content_os.pyw --chip   the old quota chip
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

if __name__ == "__main__":
    if "--chip" in sys.argv:
        from core.win_notify import run_tray

        raise SystemExit(run_tray(stay=True))
    import config.settings  # noqa: F401  (loads .env)
    from desktop.launch import launch

    raise SystemExit(launch())
