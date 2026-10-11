"""One upload-worker pass with no console window (#1130).

What the `ContentMachine\\UploadWorker` scheduled task runs every few minutes
(`py -m scripts.ops worker-task --install`). It sets the working folder to the repo, so `.env`
and `data/` resolve as they do in a terminal, and appends what the worker prints to
`data/logs/worker_task.log` - under `pythonw` there is no console to print to.
"""

import os
import runpy
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data", "logs", "worker_task.log")


def main() -> None:
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8", errors="replace") as log:
        sys.stdout = sys.stderr = log
        print(f"--- {datetime.now().isoformat(timespec='seconds')} worker pass")
        sys.argv = ["jobs.worker"]
        try:
            runpy.run_module("jobs.worker", run_name="__main__")
        except SystemExit as stop:
            print(f"exit {stop.code}")
        except Exception as exc:
            print(f"worker pass failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
