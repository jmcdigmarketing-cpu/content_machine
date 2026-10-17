"""Read-only ledger of indexed clip licences, expiry, and the runs that used them (#424)."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.license_ledger")


def _clip_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _license_payload(clip_path: str) -> dict[str, Any]:
    from assets.local_provider import _nearest_license_file

    sidecar = _nearest_license_file(clip_path)
    if not sidecar:
        return {}
    try:
        with open(sidecar, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.debug("license sidecar unreadable (%s): %s", sidecar, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _expiry_status(expiry: str, today: date) -> str:
    try:
        expires = date.fromisoformat(str(expiry).strip())
    except (TypeError, ValueError):
        return "—"
    if expires < today:
        return "EXPIRED"
    if (expires - today).days <= 30:
        return "WARN"
    return "OK"


def _used_by_run(quality_json: str | None, clip_path: str) -> bool:
    try:
        quality = json.loads(quality_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    wanted = _clip_key(clip_path)
    return any(_clip_key(str(raw)) == wanted for raw in quality.get("footage_clips") or [])


def license_ledger_rows(
    *,
    index_path: str,
    runs: list[Any],
    today: date | None = None,
) -> list[dict[str, Any]]:
    """One row per indexed clip: licence, commercial use, expiry, and run ids."""
    from core.owned_beats import load_clip_index

    today = today or date.today()
    index = load_clip_index(index_path) or {}
    clips = index.get("clips") if isinstance(index, dict) else {}
    if not isinstance(clips, dict):
        return []
    rows: list[dict[str, Any]] = []
    for path in clips:
        license_data = _license_payload(str(path))
        expiry = str(
            license_data.get("expires_on") or license_data.get("valid_until") or ""
        ).strip()
        run_ids = [
            int(getattr(run, "id", 0) or 0)
            for run in runs or []
            if _used_by_run(getattr(run, "quality_json", None), str(path))
            and int(getattr(run, "id", 0) or 0)
        ]
        rows.append(
            {
                "path": str(path),
                "license": str(license_data.get("license") or "unknown"),
                "commercial_use": bool(license_data.get("commercial_use")),
                "expiry": expiry or "—",
                "expiry_status": _expiry_status(expiry, today) if expiry else "—",
                "run_ids": run_ids,
            }
        )
    return rows


def render_ledger(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Footage ledger: no indexed clips."
    lines = ["Footage license ledger", "=" * 40]
    for row in rows:
        used = ",".join(str(i) for i in row.get("run_ids") or []) or "—"
        commercial = "yes" if row.get("commercial_use") else "no"
        lines.append(f"{row.get('path')}")
        lines.append(
            f"  license={row.get('license')} commercial={commercial} "
            f"expiry={row.get('expiry')} ({row.get('expiry_status')}) runs={used}"
        )
    return "\n".join(lines)
