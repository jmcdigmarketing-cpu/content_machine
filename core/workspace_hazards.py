"""OneDrive / nested-.git hazard check (candidate 100).

operating_plan §7: OneDrive + git + output/ fight each other. Specific, not a
generic doctor. Nested try; never mutates files.

It also reads what the checkout is linked to (2026-10-10, after the move out of OneDrive): the
vault path, sync-conflict copies left in data/, and footage folders with no clips.
"""

from __future__ import annotations

import os
import platform
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


def _vault_path() -> str:
    return (os.environ.get("OBSIDIAN_VAULT_PATH") or "").strip()


def _conflict_copies(data_dir: str, host: str) -> list[str]:
    """`name-<COMPUTERNAME>.json` beside `name.json`: what a sync client leaves when two
    copies of one file disagree. Nothing reads them."""
    if not host or not os.path.isdir(data_dir):
        return []
    suffix = f"-{host}".casefold()
    found = []
    for entry in sorted(os.listdir(data_dir)):
        stem, ext = os.path.splitext(entry)
        if stem.casefold().endswith(suffix) and os.path.isfile(
            os.path.join(data_dir, stem[: -len(suffix)] + ext)
        ):
            found.append(entry)
    return found


def empty_footage_folders(library: str, rows: list[dict[str, Any]]) -> list[str]:
    """Footage folders a playlist row names that hold no clip - that sport cuts stock."""
    have: dict[str, bool] = {}
    for dirpath, _dirs, files in os.walk(library):
        name = os.path.basename(dirpath).casefold()
        clips = any(f.lower().endswith((".mp4", ".mov")) for f in files)
        have[name] = have.get(name, False) or clips
    wanted = [str(name) for row in rows for name in row.get("footage") or []]
    return [name for name in dict.fromkeys(wanted) if not have.get(name.casefold(), False)]


def _empty_footage(base: str) -> list[str]:
    from core.playlists import playlist_map

    return empty_footage_folders(os.path.join(base, "video", "backgrounds"), playlist_map("tapin"))


def gather(
    root: str | None = None,
    *,
    vault: str | None = None,
    host: str | None = None,
    empty_footage: list[str] | None = None,
) -> dict[str, Any]:
    """Hazards fail the doctor row; notes ride on it. The keyword arguments are what the
    checkout is linked to (the vault, this PC's name, footage folders with no clips) - read
    from the environment when not given."""
    try:
        from config.paths import ROOT_DIR

        base = root or ROOT_DIR
    except Exception as exc:
        logger.debug("ROOT_DIR skipped: %s", exc)
        base = root or os.getcwd()
    hazards: list[str] = []
    notes: list[str] = []
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
    try:
        vault_path = _vault_path() if vault is None else vault
        if vault_path and not os.path.isdir(vault_path):
            hazards.append(f"vault missing: OBSIDIAN_VAULT_PATH={vault_path}")
        elif vault_path and "onedrive" in os.path.abspath(vault_path).lower():
            hazards.append(f"vault is under OneDrive: {vault_path}")
    except Exception as exc:
        logger.debug("vault probe skipped: %s", exc)
    try:
        name = platform.node() if host is None else host
        copies = _conflict_copies(os.path.join(base, "data"), name)
        if copies:
            hazards.append(
                "sync-conflict copies in data/ (nothing reads them): " + ", ".join(copies)
            )
    except Exception as exc:
        logger.debug("conflict copy probe skipped: %s", exc)
    try:
        empty = _empty_footage(base) if empty_footage is None else empty_footage
        if empty:
            notes.append("no clips in " + ", ".join(empty) + " (py -m scripts.ops ingest-clips)")
    except Exception as exc:
        logger.debug("footage folder probe skipped: %s", exc)
    return {
        "root": os.path.abspath(base),
        "onedrive": onedrive,
        "hazards": hazards,
        "notes": notes,
    }


def render(data: dict[str, Any] | None = None) -> str:
    data = data or gather()
    hazards = data.get("hazards") or []
    notes = "".join(f"; note: {n}" for n in data.get("notes") or [])
    if not hazards:
        return (
            "workspace: ok (not OneDrive; no nested .git under output/ or data/; "
            "vault and data/ local)" + notes
        )
    return "workspace: " + "; ".join(str(h) for h in hazards) + notes
