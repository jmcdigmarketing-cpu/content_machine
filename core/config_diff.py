"""#447: channels.json fingerprint vs the last-run trace."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from config.paths import CHANNELS_FILE


def channels_fingerprint(path: str | None = None) -> str:
    target = Path(path or CHANNELS_FILE)
    data = target.read_bytes()
    return hashlib.sha256(data).hexdigest()


def diff_against(trace: dict[str, Any] | None) -> list[str]:
    current = channels_fingerprint()
    stored = str((trace or {}).get("channels_sha256") or "").strip()
    if not stored:
        return [f"channels.json sha256 {current[:12]} (no prior fingerprint)"]
    if stored == current:
        return [f"channels.json matches last run ({current[:12]})"]
    return [f"channels.json drifted vs last run ({stored[:12]} -> {current[:12]})"]
