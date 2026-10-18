"""Did a test run write the operator's files? (#892)

`tests/__init__.py` redirects the stores the suite is known to touch, but a new test
can reach a new one, and CI never noticed: its checkout has no `data/`. `ops test`
snapshots `data/` and `output/` before the run and fails, naming the files, when the run
created or changed any.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

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


@contextmanager
def without_dotenv(path: str = ".env") -> Iterator[list[str]]:
    """The environment without the values `.env` put there, for the length of a suite run (#1302).

    `ops` loads `.env`, and the suite it starts inherited the operator's settings: six tests
    failed in `ops all` on the operator's PC and passed in CI, which has no `.env`. A key whose
    value differs from the file's was set in the shell and stays. Restored afterwards, so the
    batch steps after the suite keep their configuration.
    """
    try:
        from dotenv import dotenv_values

        from_file = {k: v for k, v in dotenv_values(path).items() if v is not None}
    except Exception:
        from_file = {}
    removed = {k: os.environ[k] for k, v in from_file.items() if os.environ.get(k) == v}
    for key in removed:
        os.environ.pop(key, None)
    try:
        yield sorted(removed)
    finally:
        os.environ.update(removed)
