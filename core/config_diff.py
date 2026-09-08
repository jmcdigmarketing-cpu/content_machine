"""#447: channels.json fingerprint vs the last-run trace. #687: .env shape, never values."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from config.paths import CHANNELS_FILE, ROOT_DIR

ENV_EXAMPLE_FILE = Path(ROOT_DIR) / ".env.example"


def channels_fingerprint(path: str | None = None) -> str:
    target = Path(path or CHANNELS_FILE)
    data = target.read_bytes()
    return hashlib.sha256(data).hexdigest()


def env_example_keys(path: str | Path | None = None) -> list[str]:
    target = Path(path or ENV_EXAMPLE_FILE)
    names: list[str] = []
    seen: set[str] = set()
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def env_canonical(
    *,
    environ: dict[str, str] | None = None,
    example_path: str | Path | None = None,
) -> str:
    """Presence/shape only. Never includes secret values."""
    src = environ if environ is not None else os.environ
    lines = []
    for name in env_example_keys(example_path):
        if name not in src:
            state = "missing"
        elif not str(src.get(name) or "").strip():
            state = "empty"
        else:
            state = "set"
        lines.append(f"{name}={state}")
    return "\n".join(lines)


def env_fingerprint(
    *,
    environ: dict[str, str] | None = None,
    example_path: str | Path | None = None,
) -> str:
    return hashlib.sha256(
        env_canonical(environ=environ, example_path=example_path).encode()
    ).hexdigest()


def diff_against(trace: dict[str, Any] | None) -> list[str]:
    current = channels_fingerprint()
    stored = str((trace or {}).get("channels_sha256") or "").strip()
    if not stored:
        lines = [f"channels.json sha256 {current[:12]} (no prior fingerprint)"]
    elif stored == current:
        lines = [f"channels.json matches last run ({current[:12]})"]
    else:
        lines = [f"channels.json drifted vs last run ({stored[:12]} -> {current[:12]})"]
    env_now = env_fingerprint()
    env_stored = str((trace or {}).get("env_sha256") or "").strip()
    if not env_stored:
        lines.append(f".env shape {env_now[:12]} (no prior fingerprint)")
    elif env_stored == env_now:
        lines.append(f".env shape matches last run ({env_now[:12]})")
    else:
        lines.append(f".env shape drifted vs last run ({env_stored[:12]} -> {env_now[:12]})")
    return lines
