"""Fact-expiry watchdog (candidate 55).

Vault notes with ``expires`` in the past that still sit on disk (load_facts
already drops them from prompts). reliability.gather() scans the vault only —
no HTTP. Empty OBSIDIAN_VAULT_PATH => nothing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("core.fact_expiry")


def expired_notes(
    channel_id: str | None = None,
    *,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Notes whose frontmatter expires date is in the past."""
    try:
        from core.fact_store import note_metadata
        from core.obsidian_facts import (
            _is_machine_record,
            _note_matches_channel,
            _vault_path,
        )
        from core.vault_index import iter_notes
    except Exception as exc:
        logger.debug("fact expiry imports skipped: %s", exc)
        return []
    vault = _vault_path()
    if not vault:
        return []
    today = today or date.today()
    out: list[dict[str, Any]] = []
    try:
        notes = list(iter_notes(vault))
    except Exception as exc:
        logger.debug("fact expiry iter skipped: %s", exc)
        return []
    for note in notes:
        try:
            rel = Path(note.rel_path)
            meta = note.meta or {}
            if channel_id and not _note_matches_channel(meta, rel, channel_id):
                continue
            if _is_machine_record(rel):
                continue
            _tier, _verified, expires, _url = note_metadata(meta, rel)
            if expires is None or expires >= today:
                continue
            out.append(
                {
                    "path": str(rel).replace("\\", "/"),
                    "expires": expires.isoformat(),
                    "days_past": (today - expires).days,
                }
            )
        except Exception as exc:
            logger.debug("fact expiry note skipped: %s", exc)
    out.sort(key=lambda r: r.get("expires") or "")
    return out


def warning_lines(channel_id: str | None = None, *, today: date | None = None) -> list[str]:
    notes = expired_notes(channel_id, today=today)
    if not notes:
        return []
    sample = notes[0]
    extra = f" (+{len(notes) - 1} more)" if len(notes) > 1 else ""
    return [
        f"{len(notes)} vault note(s) expired (still on disk, already dropped from prompts): "
        f"{sample.get('path')} expired {sample.get('expires')}{extra}"
    ]
