"""#333. Persist walked-back claims so a later run cannot re-assert them."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config.paths import DATA_DIR

STORE_PATH = Path(DATA_DIR) / "negative_facts.json"
_TOKEN = re.compile(r"[a-z0-9]+", re.I)
_STOP = frozenset("a an the for of to in on at as by with from is was are were".split())


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall((text or "").lower()) if t not in _STOP and len(t) > 1}


def franchise_for(topic: str, channel_id: str | None = None) -> str:
    low = f"{topic or ''} {channel_id or ''}".lower()
    for key in ("gta", "ufc", "nba", "nfl", "moneywise"):
        if key in low:
            return key
    return (channel_id or "tapin").strip().lower() or "tapin"


def _load() -> dict[str, list[dict[str, Any]]]:
    if not STORE_PATH.is_file():
        return {}
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_negative(franchise: str, claim: str, *, reason: str = "") -> None:
    key = (franchise or "tapin").strip().lower() or "tapin"
    text = (claim or "").strip()
    if not text:
        return
    data = _load()
    rows = list(data.get(key) or [])
    if any(str(r.get("claim") or "").lower() == text.lower() for r in rows):
        return
    rows.append({"claim": text, "reason": reason})
    data[key] = rows
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def matching_negatives(script: str, *, franchise: str) -> list[str]:
    rows = list(_load().get((franchise or "").strip().lower()) or [])
    hay = _tokens(script)
    hits: list[str] = []
    for row in rows:
        claim = str(row.get("claim") or "").strip()
        tokens = _tokens(claim)
        if len(tokens) < 3:
            continue
        overlap = tokens & hay
        if len(overlap) >= min(4, len(tokens)) or tokens <= hay:
            hits.append(claim)
    return hits


def apply_negative_facts(script: str, *, franchise: str) -> list[str]:
    return matching_negatives(script, franchise=franchise)


# The operator's recorded decision (planning_log, 2026-08): the store is "a memory
# of corrections already paid for, once per claim, able to VETO (operator wants a
# hard block, not a warning)". The first implementation shipped warn-only; this
# restores the veto behind the same env-gate shape `GROUNDING_GATE` uses
# (decisions §3/§9), defaulting to what was asked for rather than to the softer
# option. `warn` stays available for a run the operator decides to push through.
NEGATIVE_PREFIX = "negative-fact: "


def negative_fact_gate_mode() -> str:
    """block (default) | warn — mirrors GROUNDING_GATE's shape, not its default."""
    import os

    return os.getenv("NEGATIVE_FACT_GATE", "block").strip().lower() or "block"


def negative_gate_blocks(ungrounded: list[str] | None) -> bool:
    """True when the gate is `block` and a *retracted claim* was re-asserted.

    Keyed on the `negative-fact: ` prefix, not on the flagged list as a whole: an
    ordinary ungrounded entity is a warning, and only a claim the operator has
    already paid to correct earns the veto.
    """
    if negative_fact_gate_mode() != "block":
        return False
    return any(str(item).startswith(NEGATIVE_PREFIX) for item in ungrounded or [])
