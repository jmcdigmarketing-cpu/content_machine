"""Signals the operator chose to stop running, with the evidence (#574).

`ops signal-audit` (#575) shows which signals never feed the script. Retiring one is
the operator's call (decisions §19): `ops signal-audit --skip news --note "..."`
records it here with the audit's evidence and the date, per channel; `--unskip`
removes it. `apis/register_signals._skip_signals` unions these with
`CONTENT_SKIP_SIGNALS`, so discovery, fan-out and fact enrichment all leave the signal
out, and the health block names it. Nothing is ever added here automatically.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.runs.signal_skips")

SKIPS_FILE = os.path.join(DATA_DIR, "signal_skips.json")
_lock = threading.Lock()


def load_skips() -> dict[str, dict[str, dict[str, Any]]]:
    """{channel: {signal: {since, note, evidence}}}; {} when unreadable."""
    try:
        with open(SKIPS_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def skipped_for(channel_id: str) -> dict[str, dict[str, Any]]:
    entry = load_skips().get(channel_id)
    return entry if isinstance(entry, dict) else {}


def _save(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SKIPS_FILE) or ".", exist_ok=True)
    tmp = f"{SKIPS_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    os.replace(tmp, SKIPS_FILE)


def skip(channel_id: str, signal: str, *, evidence: str, note: str = "") -> None:
    name = signal.strip().lower()
    with _lock:
        data = load_skips()
        data.setdefault(channel_id, {})[name] = {
            "since": date.today().isoformat(),
            "evidence": evidence,
            "note": note.strip(),
        }
        _save(data)


def unskip(channel_id: str, signal: str) -> bool:
    """True when the signal was skipped and now is not."""
    name = signal.strip().lower()
    with _lock:
        data = load_skips()
        removed = data.get(channel_id, {}).pop(name, None) is not None
        if removed:
            _save(data)
    return removed
