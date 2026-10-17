"""#333. Persist walked-back claims so a later run cannot re-assert them."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from apis.topic_tokens import FUNCTION_WORDS, content_tokens
from config.paths import DATA_DIR

STORE_PATH = Path(DATA_DIR) / "negative_facts.json"
_TOKEN = re.compile(r"[a-z0-9]+", re.I)
_STOP = FUNCTION_WORDS | frozenset(
    [
        "a",
        "an",
        "the",
        "for",
        "of",
        "to",
        "in",
        "on",
        "at",
        "as",
        "by",
        "with",
        "from",
        "is",
        "was",
        "are",
        "were",
    ]
)


def _tokens(text: str) -> set[str]:
    return {t for t in content_tokens(text, min_len=2) if t not in _STOP}


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


def all_records() -> list[dict[str, Any]]:
    """Every recorded negative fact, with its franchise (#342 reads the dossier reasons)."""
    return [
        {**row, "franchise": franchise}
        for franchise, rows in _load().items()
        for row in rows or []
        if isinstance(row, dict)
    ]


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


# #545. One spoken sentence. The veto ignores it (decisions §29): naming the
# correction is not re-asserting it. A later sentence that states the claim is.
BEAT_PREFIX = "What I got wrong last time:"


def _script_without_correction_beat(script: str) -> str:
    pieces = re.split(r"(?<=[.!?])\s+", script or "")
    kept = [part for part in pieces if not part.lstrip().startswith(BEAT_PREFIX)]
    return " ".join(kept)


def correction_beat(topic: str, channel_id: str | None = None) -> str:
    """The newest recorded negative for this topic's franchise, or ""."""
    key = franchise_for(topic, channel_id)
    rows = [
        row
        for row in (_load().get(key) or [])
        if isinstance(row, dict) and str(row.get("claim") or "").strip() and not row.get("said_at")
    ]
    if not rows:
        return ""
    claim = str(rows[-1].get("claim") or "").strip()
    spoken = claim if claim[-1:] in ".!?" else f"{claim}."
    return f"{BEAT_PREFIX} {spoken}"


def with_correction_beat(script: str, topic: str, channel_id: str | None = None) -> str:
    """The beat before the script's closing line, once per correction. No correction, or the
    beat already present, returns `script`.

    Review of 2026-10-16: appended, it followed "Tap in for more." and came back on every later
    script of the franchise; #545 asks for the next script.
    """
    beat = correction_beat(topic, channel_id)
    if not beat or BEAT_PREFIX in (script or ""):
        return script
    text = (script or "").rstrip()
    if not text:
        out = beat
    else:
        if text[-1] not in ".!?":
            text += "."
        pieces = re.split(r"(?<=[.!?])\s+", text)
        out = " ".join([*pieces[:-1], beat, pieces[-1]]) if len(pieces) > 1 else f"{beat} {text}"
    _mark_said(franchise_for(topic, channel_id), beat[len(BEAT_PREFIX) :].strip().rstrip("."))
    return out


def _mark_said(franchise: str, claim: str) -> None:
    """The correction has had its sentence; the next script of the franchise goes without."""
    data = _load()
    rows = data.get(franchise) or []
    for row in rows:
        if isinstance(row, dict) and str(row.get("claim") or "").strip().rstrip(".") == claim:
            row["said_at"] = datetime.now().isoformat(timespec="seconds")
            break
    else:
        return
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def matching_negatives(script: str, *, franchise: str) -> list[str]:
    rows = list(_load().get((franchise or "").strip().lower()) or [])
    hay = _tokens(_script_without_correction_beat(script))
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
