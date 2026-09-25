"""#636: scan the written run traces for secrets, without ever printing one.

`core/run_trace.py` now scrubs env secret values and secret-named URL parameters on
write. This checks what is already on disk: a trace written before that scrub, or by
a path that bypasses it, is found here. Only counts and file names are printed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from config.paths import TRACES_DIR
from core.logging import get_logger

logger = get_logger("core.trace_secrets")


@dataclass
class TraceHit:
    name: str
    env_values: int
    url_params: int


def scan_traces(
    directory: str | None = None, environ: dict[str, str] | None = None
) -> tuple[int, list[TraceHit]]:
    """(files checked, files with any hit)."""
    from core.run_trace import SECRET_PARAM_RE, env_secret_values

    folder = Path(directory or TRACES_DIR)
    secrets = env_secret_values(os.environ if environ is None else environ)
    checked = 0
    hits: list[TraceHit] = []
    for path in sorted(folder.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("trace unreadable for secret scan %s: %s", path.name, exc)
            continue
        checked += 1
        env_count = sum(text.count(secret) for secret in secrets)
        param_count = len(SECRET_PARAM_RE.findall(text))
        if env_count or param_count:
            hits.append(TraceHit(path.name, env_count, param_count))
    return checked, hits


def render_scan(checked: int, hits: list[TraceHit]) -> str:
    lines = [f"Trace secrets scan: {checked} trace file(s) checked, {len(hits)} with a hit"]
    for hit in hits:
        lines.append(
            f"  {hit.name}: {hit.env_values} env secret value(s), {hit.url_params} secret URL param(s)"
        )
    lines.append(
        "Values are never printed. Env secrets = env vars named *KEY*/*TOKEN*/*SECRET*/*PASSWORD*/*AUTH*."
    )
    return "\n".join(lines)
