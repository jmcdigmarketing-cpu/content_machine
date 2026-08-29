"""#340 / #426 render sidecars: facts JSON + input hashes beside the mp4."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.render_artifacts")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return _sha256_bytes(fh.read())
    except OSError as exc:
        logger.debug("mp4 hash skipped: %s", exc)
        return None


def write_render_sidecars(
    mp4_path: str,
    *,
    script: str = "",
    features: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write `<stem>.facts.json` next to the mp4. Fail-open; never raises."""
    features = dict(features or {})
    quality = dict(quality or {})
    out: dict[str, Any] = {
        "claims": [],
        "sources": list(features.get("source_urls") or []),
        "disputed": bool(features.get("disputed")),
        "disputed_claims": list(features.get("disputed_claims") or []),
        "ungrounded_count": quality.get("ungrounded_count"),
        "script_sha256": _sha256_bytes((script or "").encode("utf-8")),
        "mp4_sha256": None,
    }
    ver = features.get("claim_verification") or {}
    if isinstance(ver, dict):
        claims = ver.get("claims") or []
        if isinstance(claims, list):
            out["claims"] = claims
    if mp4_path and os.path.isfile(mp4_path):
        out["mp4_sha256"] = _sha256_file(mp4_path)
    dest = os.path.splitext(mp4_path or "")[0] + ".facts.json"
    try:
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        out["path"] = dest
    except Exception as exc:
        logger.warning("facts sidecar skipped: %s", exc)
    return out
