"""`ops recheck-claims` (#1164): the fixed claim check, on drafts already waiting.

#1148 found why most drafts were blocked: the checker cited the research brief and a rule
then called those claims unsupported. The fix changed how new drafts are checked. The drafts
already waiting kept their old verdicts, so what the fix bought was never measured.

This re-checks only each draft's unbacked claims, against the facts the run saved
(`core.runs.replay.load_snapshot`). Those are the signals as discovery left them, without the
research a run adds later, so a re-check can clear a claim and never adds one. One checker
call per draft. A dry run prints old against new; `--apply` stores it on the draft and the run.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger("core.runs.recheck")

_MATCH_SHARE = 0.6


def _facts_for(run_id: int) -> str:
    """The run's saved signal facts as the check reads them, or "" when none were saved."""
    from core.grounding_tiers import build_tiered_corpus
    from core.runs.replay import load_snapshot
    from core.signal_facts import format_signal_facts

    signals = load_snapshot(run_id)
    if not signals:
        return ""
    return build_tiered_corpus(signal_facts=format_signal_facts(signals)).factual_text


def _match(claim: str, answers: list[Any]) -> Any | None:
    """The checker's answer for `claim` - the one sharing most of its words - or None."""
    from apis.topic_tokens import content_tokens

    wanted = set(content_tokens(claim, min_len=3))
    best, share = None, 0.0
    for item in answers:
        got = set(content_tokens(str(getattr(item, "claim", "")), min_len=3))
        if not wanted or not got:
            continue
        overlap = len(wanted & got) / min(len(wanted), len(got))
        if overlap > share:
            best, share = item, overlap
    return best if share >= _MATCH_SHARE else None


def recheck_draft(draft: Any, *, verify: Callable[..., Any] | None = None) -> dict[str, Any]:
    """{run_id, before, cleared, citations, note} for one waiting draft."""
    from core.claim_types import blocking_unsupported

    meta = draft.meta
    blocking = blocking_unsupported(meta.get("claim_verification"))
    out: dict[str, Any] = {
        "run_id": draft.run_id,
        "before": len(blocking),
        "cleared": [],
        "citations": {},
        "note": "",
    }
    if not blocking:
        return out
    facts = _facts_for(draft.run_id)
    if not str(facts or "").strip():
        out["note"] = "no saved facts"
        return out
    from core.claim_verifier import verify_claims

    check = verify or verify_claims
    text = " ".join(c if c.rstrip().endswith((".", "!", "?")) else f"{c}." for c in blocking)
    topic = str(meta.get("variant") or meta.get("topic") or "")
    answer = check(text, facts, topic=topic)
    claims = list(getattr(answer, "claims", None) or [])
    if not claims:
        out["note"] = "the check did not answer"
        return out
    for claim in blocking:
        hit = _match(claim, claims)
        if hit is not None and getattr(hit, "supported", False):
            out["cleared"].append(claim)
            out["citations"][claim] = str(getattr(hit, "citation_line", "") or "")
    return out


def _apply(draft: Any, result: dict[str, Any]) -> None:
    """Store the cleared claims on the draft record and the run, and the check again."""
    from core.claim_types import blocking_unsupported
    from core.run_features import merge_features
    from core.script_craft import script_check

    meta = draft.meta
    ver = dict(meta.get("claim_verification") or {})
    cleared = set(result["cleared"])
    claims = []
    for item in ver.get("claims") or []:
        row = dict(item) if isinstance(item, dict) else {}
        if row.get("claim") in cleared and not row.get("supported"):
            citation = str(result["citations"].get(row["claim"]) or "")[:200]
            row.update(supported=True, citation_line=citation, by="recheck")
        claims.append(row)
    old_unsupported = list(ver.get("unsupported") or [])
    types = ver.get("unsupported_types")
    if isinstance(types, list) and len(types) == len(old_unsupported):
        ver["unsupported_types"] = [
            t for c, t in zip(old_unsupported, types, strict=True) if c not in cleared
        ]
    total = int(ver.get("total") or len(claims))
    supported = int(ver.get("supported") or 0) + len(cleared)
    ver.update(
        claims=claims,
        unsupported=[c for c in old_unsupported if c not in cleared],
        supported=supported,
        support_rate=round(supported / total, 3) if total else None,
        rechecked_at=datetime.now().isoformat(timespec="seconds"),
    )
    previous = meta.get("script_clean") if isinstance(meta.get("script_clean"), dict) else {}
    check = script_check(
        script=draft.script,
        title=str(meta.get("title") or ""),
        idea=str(meta.get("topic") or ""),
        unsupported=blocking_unsupported(ver),
        cut=list(previous.get("cut") or []),
    )
    meta["claim_verification"] = ver
    meta["script_clean"] = check
    with open(os.path.join(draft.folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    if draft.run_id:
        merge_features(draft.run_id, {"claim_verification": ver, "script_clean": check})


def recheck_lines(
    channel_id: str,
    *,
    root: str | None = None,
    apply: bool = False,
    verify: Callable[..., Any] | None = None,
) -> list[str]:
    """`ops recheck-claims`: each waiting draft inside its window that has unbacked claims."""
    from core.batch_review import draft_age_days, freshness_window_days, pending_drafts

    mode = "stored" if apply else "dry run - --apply stores it"
    lines = [f"Recheck - {channel_id}: waiting drafts with unbacked claims ({mode})"]
    checked = before = cleared = 0
    for draft in pending_drafts(channel_id, root=root):
        age = draft_age_days(draft.meta)
        if age is not None and age > freshness_window_days(draft.meta):
            continue
        result = recheck_draft(draft, verify=verify)
        if not result["before"]:
            continue
        checked += 1
        before += result["before"]
        if result["note"]:
            lines.append(f"  run {draft.run_id}: {result['note']}")
            continue
        n = len(result["cleared"])
        cleared += n
        after = result["before"] - n
        lines.append(
            f"  run {draft.run_id}: {result['before']} unbacked -> {after}  {draft.title[:50]}"
        )
        for claim in result["cleared"][:3]:
            lines.append(f"      cleared: {claim[:90]}")
        if apply and n:
            _apply(draft, result)
    lines.append(
        f"  {checked} draft(s) checked: {cleared} of {before} unbacked claims are backed by the "
        "facts the run saved"
    )
    return lines
