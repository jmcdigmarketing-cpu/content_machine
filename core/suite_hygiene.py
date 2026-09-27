"""Did a test run write the operator's files? (#892)

`tests/__init__.py` redirects the stores the suite is known to touch, but a new test
can reach a new one, and CI never noticed: its checkout has no `data/`. `ops test`
snapshots `data/` and `output/` before the run and fails, naming the files, when the run
created or changed any.
"""

from __future__ import annotations

import os

WATCHED = ("data", "output")


def snapshot(dirs) -> dict[str, float]:
    """{path: mtime} for every file under `dirs`; a missing folder contributes nothing."""
    seen: dict[str, float] = {}
    for root in dirs:
        for folder, _subdirs, files in os.walk(root):
            for name in files:
                path = os.path.join(folder, name)
                try:
                    seen[path] = os.stat(path).st_mtime
                except OSError:
                    continue
    return seen


def changed(before: dict[str, float], after: dict[str, float]) -> list[str]:
    """Files created or modified between two snapshots, sorted."""
    return sorted(path for path, mtime in after.items() if before.get(path) != mtime)
