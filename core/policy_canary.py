"""YouTube inauthentic-content help-page hash canary (candidate 80).

Ops may hash a local fixture or a fetched snapshot. reliability.gather()
reads the last snapshot only — no HTTP. Tests use tests/fixtures HTML.
Never writes quota_state.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.policy_canary")

SNAPSHOT_FILE = os.path.join(DATA_DIR, "policy_canary.json")
DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / ("policy_canary_sample.html")
)
# Canonical help-page URL — fetch is opt-in (POLICY_CANARY_FETCH=1) and ops-only.
CANARY_URL = "https://support.google.com/youtube/answer/32577614"


def page_hash(text: str) -> str:
    body = (text or "").encode("utf-8", errors="replace")
    return hashlib.sha256(body).hexdigest()


def hash_file(path: str | os.PathLike[str]) -> str:
    return page_hash(Path(path).read_text(encoding="utf-8", errors="replace"))


def _snapshot_path(path: str | None = None) -> str:
    return path or SNAPSHOT_FILE


def load_snapshot(path: str | None = None) -> dict[str, Any]:
    dest = _snapshot_path(path)
    try:
        with open(dest, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_snapshot(payload: dict[str, Any], path: str | None = None) -> None:
    dest = _snapshot_path(path)
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, dest)
    except Exception as exc:
        logger.debug("policy canary snapshot write skipped: %s", exc)


def inspect(
    *,
    source_text: str | None = None,
    source_path: str | os.PathLike[str] | None = None,
    snapshot_path: str | None = None,
    fetch: bool = False,
) -> dict[str, Any]:
    """Hash current text vs last snapshot. fetch=True may HTTP — ops only."""
    text = source_text
    origin = "inline"
    if text is None and source_path is not None:
        try:
            text = Path(source_path).read_text(encoding="utf-8", errors="replace")
            origin = str(source_path)
        except Exception as exc:
            return {"ok": False, "detail": f"unreadable: {exc}", "changed": False}
    if (
        text is None
        and fetch
        and os.getenv("POLICY_CANARY_FETCH", "").strip().lower()
        in (
            "1",
            "true",
            "yes",
        )
    ):
        try:
            import requests

            resp = requests.get(CANARY_URL, timeout=15)
            resp.raise_for_status()
            text = resp.text
            origin = CANARY_URL
        except Exception as exc:
            logger.debug("policy canary fetch skipped: %s", exc)
            return {"ok": False, "detail": f"fetch failed: {type(exc).__name__}", "changed": False}
    if text is None:
        try:
            text = DEFAULT_FIXTURE.read_text(encoding="utf-8", errors="replace")
            origin = str(DEFAULT_FIXTURE)
        except Exception as exc:
            return {"ok": False, "detail": f"no fixture: {exc}", "changed": False}

    digest = page_hash(text)
    prev = load_snapshot(snapshot_path)
    prev_hash = str(prev.get("sha256") or "")
    changed = bool(prev_hash) and prev_hash != digest
    payload = {
        "sha256": digest,
        "at": time.time(),
        "origin": origin,
        "prev_sha256": prev_hash,
        "changed": changed,
        "ok": True,
        "detail": "hash moved vs last snapshot" if changed else "unchanged or first snapshot",
    }
    save_snapshot(
        {
            "sha256": digest,
            "prev_sha256": prev_hash,
            "at": payload["at"],
            "origin": origin,
            "changed": changed,
        },
        snapshot_path,
    )
    return payload


def warning_lines(snap: dict[str, Any] | None = None) -> list[str]:
    """Snapshot-only (no HTTP) — for reliability.gather()."""
    data = snap if snap is not None else load_snapshot()
    if not data:
        return []
    if data.get("changed") or (
        data.get("prev_sha256") and data.get("prev_sha256") != data.get("sha256")
    ):
        return ["YouTube inauthentic-content help page hash moved — re-read the policy"]
    return []


def render(result: dict[str, Any]) -> str:
    flag = "CHANGED" if result.get("changed") else "ok"
    return (
        f"Policy canary [{flag}] sha256={str(result.get('sha256') or '')[:12]}... "
        f"{result.get('detail') or ''}"
    )
