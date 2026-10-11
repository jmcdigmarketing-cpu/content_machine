"""Does unconfirmed mode hold up? (#977)

Wave 61 (#339) writes a fresh topic with thin facts in unconfirmed mode: what is not confirmed is
said with a label ("not confirmed yet", "early reports say", "reportedly") instead of dropped.
This checks afterwards whether those labelled claims turned out true. For each run written in
that mode it takes the labelled sentences and reads, when they share a subject name:

- the facts of *later* runs on the same subject;
- the vault's corrections (`core.negative_facts`, #342) - a conflict or a restatement
  contradicts the claim;
- the operator's own vault facts - the same confirm / contradict rules as later runs.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.unconfirmed_check")

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# The labels #339's prompt asks for, beyond the hedges `claim_types.is_hedged` already knows.
_LABEL = re.compile(
    r"^\s*(?:not (?:yet )?confirmed(?: yet)?[:,]?|unconfirmed[:,]?|early reports? (?:say|said|"
    r"suggest)s?(?: that)?[:,]?|reports? (?:say|claim|said|suggest)s?(?: that)?[:,]?|"
    r"reportedly[:,]?|rumou?r(?:s|ed)? (?:say|has it)(?: that)?[:,]?|allegedly[:,]?)\s*",
    re.IGNORECASE,
)
_ANY_LABEL = re.compile(r"\b(?:not (?:yet )?confirmed|early reports?|unconfirmed)\b", re.I)


def labelled_claims(script: str) -> list[str]:
    from core.claim_types import is_hedged

    out = []
    for sentence in _SENTENCE.split(script or ""):
        text = sentence.strip()
        if text and (is_hedged(text) or _ANY_LABEL.search(text)):
            out.append(text)
    return out


def strip_label(claim: str) -> str:
    text = _LABEL.sub("", claim or "", count=1).strip()
    return text[:1].upper() + text[1:] if text else text


def _load(raw: Any) -> dict[str, Any]:
    try:
        loaded = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _topic(run: Any) -> str:
    return str(getattr(run, "selected_topic", "") or getattr(run, "input_topic", "") or "")


def _subject(text: str) -> set[str]:
    from apis.topic_tokens import title_phrases

    return {word.lower() for phrase in title_phrases(text) for word in phrase.split()}


def _facts(run: Any) -> str:
    features = _load(getattr(run, "features_json", None))
    return str(features.get("grounding_text") or features.get("facts") or "")


def _specifics(claim: str) -> list[str]:
    from apis.topic_tokens import title_phrases

    numbers = re.findall(r"\d[\d.,]*", claim)
    return [n.rstrip(".,") for n in numbers] + list(title_phrases(claim))


def verdict_for(claim: str, later_facts: str) -> str:
    from core.facts.conflicts import find_fact_conflicts

    if later_facts.strip() and find_fact_conflicts([claim], later_facts):
        return "contradicted"
    specifics = _specifics(strip_label(claim))
    low = later_facts.lower()
    if specifics and all(s.lower() in low for s in specifics):
        return "confirmed"
    return "open"


def _shares(subject: set[str], text: str) -> bool:
    return bool(subject and subject & _subject(text))


def _operator_lines(topic: str, channel_id: str, subject: set[str]) -> str:
    """Operator facts that name the run's subject. Empty vault is not a warning."""
    try:
        from core.obsidian_facts import load_facts

        lines = [line for line in load_facts(topic, channel_id, limit=40) if _shares(subject, line)]
    except Exception as exc:
        logger.debug("operator facts unavailable for unconfirmed check: %s", exc)
        return ""
    return "\n".join(lines)


def _correction_text(subject: set[str]) -> str:
    """#342 corrections that name the run's subject."""
    try:
        from core.negative_facts import all_records

        lines = [
            str(row.get("claim") or "")
            for row in all_records()
            if _shares(subject, str(row.get("claim") or ""))
        ]
    except Exception as exc:
        logger.debug("corrections unavailable for unconfirmed check: %s", exc)
        return ""
    return "\n".join(line for line in lines if line.strip())


def _correction_hits(claim: str, corrections: str) -> bool:
    """A correction that conflicts with the claim, or restates it, walks it back."""
    if not corrections.strip():
        return False
    from core.facts.conflicts import find_fact_conflicts

    stripped = strip_label(claim)
    if find_fact_conflicts([stripped], corrections):
        return True
    specifics = _specifics(stripped)
    low = corrections.lower()
    return bool(specifics) and all(item.lower() in low for item in specifics)


def _runs(channel_id: str) -> list[Any]:
    from storage.repositories.content_runs import get_content_run_repository

    return list(get_content_run_repository().list_for_channel(channel_id) or [])


def check(channel_id: str) -> dict[str, Any]:
    runs = sorted(_runs(channel_id), key=lambda r: int(getattr(r, "id", 0) or 0))
    out: dict[str, Any] = {"runs": 0, "claims": 0, "confirmed": 0, "contradicted": 0, "open": 0,
                           "rows": []}  # fmt: skip
    for run in runs:
        if _load(getattr(run, "quality_json", None)).get("script_mode") != "unconfirmed":
            continue
        out["runs"] += 1
        subject = _subject(_topic(run))
        later = [
            _facts(r) for r in runs if int(r.id) > int(run.id) and subject & _subject(_topic(r))
        ]
        operator = _operator_lines(_topic(run), channel_id, subject)
        corrections = _correction_text(subject)
        evidence = "\n".join(part for part in ("\n".join(f for f in later if f), operator) if part)
        for claim in labelled_claims(str(getattr(run, "script", "") or "")):
            found = (
                "contradicted"
                if _correction_hits(claim, corrections)
                else verdict_for(claim, evidence)
            )
            out["claims"] += 1
            out[found] += 1
            out["rows"].append({"run_id": run.id, "claim": claim, "verdict": found})
    return out


def render_lines(channel_id: str) -> list[str]:
    """`ops auto-research`: how the labelled claims have held up (#977)."""
    try:
        got = check(channel_id)
    except Exception as exc:
        logger.debug("unconfirmed check skipped: %s", exc)
        return []
    if not got["runs"]:
        return ["  Unconfirmed mode (#977): no run written in it yet."]
    lines = [
        f"  Unconfirmed mode (#977): {got['runs']} run(s), {got['claims']} labelled claim(s) - "
        f"{got['confirmed']} confirmed, {got['contradicted']} contradicted, {got['open']} still "
        "open (judged by later runs, vault corrections and operator facts)"
    ]
    for row in [r for r in got["rows"] if r["verdict"] == "contradicted"][:3]:
        lines.append(f"    contradicted, run #{row['run_id']}: {row['claim'][:110]}")
    return lines


def status_line(channel_id: str) -> str:
    """`ops status`: once any labelled claim has resolved, else ""."""
    try:
        got = check(channel_id)
    except Exception as exc:
        logger.debug("unconfirmed status skipped: %s", exc)
        return ""
    if not got["confirmed"] and not got["contradicted"]:
        return ""
    return (
        f"Unconfirmed claims: {got['confirmed']} confirmed, {got['contradicted']} contradicted, "
        f"{got['open']} open (ops auto-research)"
    )
