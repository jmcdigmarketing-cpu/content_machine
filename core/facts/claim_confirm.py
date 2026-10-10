"""Confirm or reject a flagged claim on a rendered run - no re-render (#1013).

A run rendered past the grounding gate stays unlisted (`grounding_override`, #754) until its
flagged claim is fixed, and the only fix used to be a re-render that pays for the voice
again. Runs 119 and 120 sat locked for claims the operator could settle in a minute - run
120's "Claude Opus 5.5 dropped on September 22" is in its own auto-research text.

Here the operator confirms a claim with a source, or rejects it. A confirmation is recorded
on the run (`claims_confirmed`), counted in the stored verification and the quality row
(which re-stamps the grade), and clears the hold once no blocking claim is left - every
reader of `grounding_override` (go-public, the queue, the blockers list, the schedule hold)
then releases it, and a Short cut from the run with it. The verifier's own verdict is kept
(`pre_confirm_unsupported`). A rejection lists the sentence to cut and leaves the run held.
Nothing is written on a dry run. The desktop review room (#1068) calls the same functions.
"""

from __future__ import annotations

import copy
import datetime
import re
from dataclasses import dataclass, field
from typing import Any

from apis.topic_tokens import content_tokens
from core.claim_types import blocking_unsupported, claim_blocks, typed_unsupported
from core.logging import get_logger
from core.run_features import load_features, merge_features
from core.run_quality import merge_quality
from core.run_trace import full_script

logger = get_logger("core.facts.claim_confirm")

_FOUND_SHARE = 0.6  # of the claim's content words, for "your research already says this"
_SENTENCE_SHARE = 0.75  # as youtube_meta.drop_unbacked_sentences (#972)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class FlaggedClaim:
    number: int
    claim: str
    claim_type: str
    blocking: bool
    found_in: str = ""
    # #1086: confirmed earlier with a placeholder ("LINK") - listed again for a real source.
    needs_source: bool = False


# #1086: the to-do list showed `--source "LINK"`; the operator ran it as written and run
# 120's confirmation recorded the word LINK as its source.
_PLACEHOLDER_SOURCES = frozenset(
    {"link", "url", "source", "todo", "tbd", "xxx", "here", "n/a", "na", "none", "http", "https"}
)


def source_problem(source: str | None) -> str:
    """Why ``source`` cannot back a confirmation, or "" when it can (#1086).

    A link (anything with "." or "/") or a description of two words or more ("ESPN
    broadcast, Oct 5") is a source; a placeholder or a lone word is not.
    """
    text = " ".join((source or "").split())
    if not text:
        return "a confirmation needs --source: the link, or where you saw it"
    bare = text.strip("\"'<>[](){} ").lower()
    if bare in _PLACEHOLDER_SOURCES:
        return f"'{text}' is a placeholder - paste the real link"
    if " " not in text and "." not in text and "/" not in text:
        return f"'{text}' is not a link or a description - paste the link, or say where you saw it"
    return ""


@dataclass
class ClaimResult:
    status: str  # "confirmed" | "rejected" | "preview" | "invalid"
    detail: str = ""
    claim: str = ""
    released: bool = False
    remaining: list[str] = field(default_factory=list)
    sentences: list[str] = field(default_factory=list)


def _words(text: str) -> set[str]:
    return set(content_tokens(text or "", min_len=3))


def _coverage(claim: str, line: str) -> float:
    wanted = _words(claim)
    return len(wanted & _words(line)) / len(wanted) if wanted else 0.0


def _research_lines(features: dict[str, Any]) -> list[str]:
    research = features.get("auto_research")
    lines = research.get("kept_lines") if isinstance(research, dict) else None
    return [str(line) for line in lines or [] if str(line).strip()]


def flagged_claims(
    features: dict[str, Any] | None, *, research: list[str] | None = None
) -> list[FlaggedClaim]:
    """The run's unsupported claims, numbered, each with the line of its own research that
    already carries it (``found_in``) when there is one; ``research`` adds lines from outside
    the features (the signal snapshot). A claim confirmed with a placeholder source is listed
    after them, marked ``needs_source`` (#1086)."""
    feats = features or {}
    typed = typed_unsupported(feats.get("claim_verification"))
    if not typed:
        claims = [str(c) for c in feats.get("grounding_override_claims") or [] if str(c).strip()]
        types = list(feats.get("grounding_override_types") or [])
        typed = [(c, str(types[i]) if i < len(types) else "") for i, c in enumerate(claims)]
    lines = [*_research_lines(feats), *(research or [])]

    def _found(claim: str) -> str:
        best = max(lines, key=lambda line: _coverage(claim, line), default="")
        return best if best and _coverage(claim, best) >= _FOUND_SHARE else ""

    out: list[FlaggedClaim] = []
    for claim, claim_type in typed:
        out.append(
            FlaggedClaim(
                len(out) + 1, claim, claim_type, claim_blocks(claim, claim_type), _found(claim)
            )
        )
    listed = {row.claim for row in out}
    for row in feats.get("claims_confirmed") or []:
        claim = str((row or {}).get("claim") or "").strip() if isinstance(row, dict) else ""
        if claim and claim not in listed and source_problem(row.get("source")):
            listed.add(claim)
            out.append(FlaggedClaim(len(out) + 1, claim, "", False, _found(claim), True))
    return out


def _snapshot_lines(run_id: int | None) -> list[str]:
    """Text lines from the run's saved signal snapshot - the research it was written from
    (#1086: run 120's claim was there, not in `auto_research.kept_lines`)."""
    if not run_id:
        return []
    try:
        from core.runs.replay import load_snapshot

        signals = load_snapshot(int(run_id)) or {}
    except Exception as exc:
        logger.debug("snapshot for run %s unavailable: %s", run_id, exc)
        return []
    out: list[str] = []

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            if len(value.split()) >= 4:
                out.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    for signal in signals.values():
        if isinstance(signal, dict):
            _walk(signal.get("data"))
    return out[:400]


def run_flagged_claims(run_id: int | None) -> list[FlaggedClaim]:
    """`flagged_claims` for a stored run, its signal snapshot counted as its research."""
    return flagged_claims(load_features(run_id), research=_snapshot_lines(run_id))


def apply_confirmation(
    verification: dict[str, Any] | None, claim: str, *, source: str
) -> dict[str, Any]:
    """The verification payload with ``claim`` counted as supported by the operator. Pure."""
    data = copy.deepcopy(verification or {})
    unsupported = [str(c) for c in data.get("unsupported") or []]
    types = data.get("unsupported_types")
    data.setdefault("pre_confirm_unsupported", list(unsupported))
    if claim in unsupported:
        index = unsupported.index(claim)
        unsupported.pop(index)
        if isinstance(types, list) and len(types) > index:
            types = [t for i, t in enumerate(types) if i != index]
            data["unsupported_types"] = types
        data["unsupported"] = unsupported
        if isinstance(data.get("supported"), int | float):
            data["supported"] = int(data["supported"]) + 1
    for row in data.get("claims") or []:
        if isinstance(row, dict) and str(row.get("claim") or "").strip() == claim:
            row["supported"] = True
            row["citation_line"] = f"operator confirmed: {source}"
    total = data.get("total")
    if isinstance(total, int | float) and total:
        data["support_rate"] = round(float(data.get("supported") or 0) / float(total), 3)
    return data


def _pick(run_id: int, number: int) -> tuple[dict[str, Any], FlaggedClaim | None]:
    features = load_features(run_id)
    rows = flagged_claims(features)
    if not 1 <= int(number or 0) <= len(rows):
        return features, None
    return features, rows[int(number) - 1]


def confirm_claim(
    run_id: int, number: int, *, source: str, note: str = "", dry_run: bool = True
) -> ClaimResult:
    """Record the operator's confirmation of flagged claim ``number`` (1-based)."""
    source = (source or "").strip()
    problem = source_problem(source)
    if problem:
        return ClaimResult("invalid", problem)
    features, pick = _pick(run_id, number)
    if pick is None:
        return ClaimResult("invalid", f"run {run_id} has no flagged claim {number}")
    verification = apply_confirmation(features.get("claim_verification"), pick.claim, source=source)
    remaining = blocking_unsupported(verification) if features.get("claim_verification") else [
        c for c in features.get("grounding_override_claims") or [] if c != pick.claim
    ]  # fmt: skip
    released = bool(features.get("grounding_override")) and not remaining
    result = ClaimResult(
        "preview" if dry_run else "confirmed",
        claim=pick.claim,
        released=released,
        remaining=list(remaining),
    )
    if dry_run:
        return result
    # #1086: re-confirming a claim recorded with a placeholder replaces that entry.
    confirmed = [
        row
        for row in features.get("claims_confirmed") or []
        if not (isinstance(row, dict) and str(row.get("claim") or "").strip() == pick.claim)
    ]
    confirmed.append(
        {
            "claim": pick.claim,
            "source": source,
            "note": note,
            "at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        }
    )
    updates: dict[str, Any] = {"claims_confirmed": confirmed}
    if features.get("claim_verification"):
        updates["claim_verification"] = verification
    if released:
        updates["grounding_override"] = False
        updates["grounding_override_cleared_by"] = "verify-claim"
    merge_features(run_id, updates)
    quality: dict[str, Any] = {"claims_confirmed_count": len(confirmed)}
    if features.get("claim_verification"):
        quality["unsupported_claim_count"] = len(verification.get("unsupported") or [])
        if "support_rate" in verification:
            quality["claim_support_rate"] = verification["support_rate"]
    merge_quality(run_id, quality)
    logger.info("run %s: claim confirmed by the operator (%s): %s", run_id, source, pick.claim)
    return result


def _script_for(run_id: int) -> str:
    text = full_script(run_id)
    if text:
        return text
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
        return str(getattr(record, "script_preview", "") or "")
    except Exception as exc:
        logger.debug("script for run %s unavailable: %s", run_id, exc)
        return ""


def reject_claim(run_id: int, number: int, *, dry_run: bool = True) -> ClaimResult:
    """The sentence(s) of the run's script that carry flagged claim ``number``. The run stays
    held - the fix is a cut and a re-render, or taking the video down."""
    features, pick = _pick(run_id, number)
    if pick is None:
        return ClaimResult("invalid", f"run {run_id} has no flagged claim {number}")
    sentences = [s.strip() for s in _SENTENCE_RE.split(_script_for(run_id)) if s.strip()]
    hits = [s for s in sentences if _coverage(pick.claim, s) >= _SENTENCE_SHARE]
    result = ClaimResult("preview" if dry_run else "rejected", claim=pick.claim, sentences=hits)
    if not dry_run:
        rejected = [*list(features.get("claims_rejected") or [])]
        rejected.append({"claim": pick.claim, "sentences": hits})
        merge_features(run_id, {"claims_rejected": rejected})
    return result
