"""OneDrive / nested-.git hazard check (candidate 100).

operating_plan §7: OneDrive + git + output/ fight each other. Specific, not a
generic doctor. Nested try; never mutates files.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.workspace_hazards")


def _under_onedrive(root: str) -> bool:
    abs_root = os.path.abspath(root)
    low = abs_root.replace("/", "\\").lower()
    if "onedrive" in low:
        return True
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        od = (os.environ.get(key) or "").strip()
        if not od:
            continue
        try:
            if abs_root.lower().startswith(os.path.abspath(od).lower()):
                return True
        except Exception as exc:
            logger.debug("OneDrive env path skipped: %s", exc)
    return False


def gather(root: str | None = None) -> dict[str, Any]:
    try:
        from config.paths import ROOT_DIR

        base = root or ROOT_DIR
    except Exception as exc:
        logger.debug("ROOT_DIR skipped: %s", exc)
        base = root or os.getcwd()
    hazards: list[str] = []
    onedrive = False
    try:
        onedrive = _under_onedrive(base)
    except Exception as exc:
        logger.debug("onedrive probe skipped: %s", exc)
    if onedrive:
        hazards.append(
            "repo is under OneDrive (operating_plan §7) — git + output/ will fight the sync client"
        )
    for rel in ("output/.git", "data/.git"):
        try:
            path = os.path.join(base, rel.replace("/", os.sep))
            if os.path.isdir(path):
                hazards.append(f"{rel} exists — nested repo / sync hazard")
        except Exception as exc:
            logger.debug("nested git probe skipped: %s", exc)
    return {"root": os.path.abspath(base), "onedrive": onedrive, "hazards": hazards}


def render(data: dict[str, Any] | None = None) -> str:
    data = data or gather()
    hazards = data.get("hazards") or []
    if not hazards:
        return "workspace: ok (not OneDrive; no nested .git under output/ or data/)"
    return "workspace: " + "; ".join(str(h) for h in hazards)
