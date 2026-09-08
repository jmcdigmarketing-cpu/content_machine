"""#609: import-time ratchet. Patch the clock in tests; do not network."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

from config.paths import ROOT_DIR

_DEFAULT_BUDGET_S = 5.0
_BUDGETS_S = {
    "core.chrome": 5.0,
}


def budget_for(module: str) -> float:
    return float(_BUDGETS_S.get(module, _DEFAULT_BUDGET_S))


def elapsed_over_budget(elapsed: float, budget_s: float) -> bool:
    return float(elapsed) > float(budget_s)


def measure_import(
    module: str,
    *,
    clock: Callable[[], float] = time.perf_counter,
    importer: Callable[[str], Any] = importlib.import_module,
) -> float:
    start = clock()
    importer(module)
    return clock() - start


def measure_import_fresh(module: str) -> float:
    """Time a real import in a new interpreter so the ratchet is not a warm cache."""
    code = (
        "import importlib, time\n"
        f"t = time.perf_counter()\n"
        f"importlib.import_module({module!r})\n"
        "print(time.perf_counter() - t)\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT_DIR + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT_DIR,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "import failed")
    return float((proc.stdout or "0").strip().split()[-1])
