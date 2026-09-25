"""UTF-8 output for headless entry points (#767).

`main.py` already reconfigures stdout for its art. The headless paths did not, and a
redirected Windows stdout - `> log.txt`, a pipe, Task Scheduler - is cp1252: the first
live `auto_generate --all-angles` run (2026-09-17) died on the cadence line's check mark
before discovery. The nightly `ops overnight` task would have died the same way.
"""

from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    """Write UTF-8 to stdout/stderr, replacing anything unencodable. Never raises."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
