"""A wrong actor named in the script (#748's open gap).

Token grounding passes "Jon Jones defeated Tom Aspinall" whenever both names are in the
facts, and the LLM claim verifier is one extract-tier call that can miss the direction or
return nothing at all. The deterministic extractors already exist for exactly this - the
fact-conflict filter uses them to catch operator facts that disagree with scraped sources
(`core.fact_conflicts`: reversed results, trades to the wrong team). This points them at the
finished script (against the facts) and at the title (against the script).

A reversal is merged into `claim_verification` as an unsupported claim of type `result`, so
the grounding gate, the #754 override record, the publish list and the claim display all
handle it with no second gate.
"""

from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger

logger = get_logger("core.relational_check")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text or "") if s.strip()]


def reversed_relations(text: str, reference: str) -> list[str]:
    """Sentences of `text` whose winner/loser or player/team the `reference` reverses."""
    try:
        from core.fact_conflicts import _result_conflicts, _trade_conflicts

        claims = _sentences(text)
        facts = _sentences(reference)
        conflicts = [*_result_conflicts(claims, facts), *_trade_conflicts(claims, facts)]
    except Exception as exc:
        logger.debug("relational check skipped: %s", exc)
        return []
    out: list[str] = []
    for conflict in conflicts:
        line = f"{conflict.operator_line[:160]} (the facts say the reverse: {conflict.other_line[:120]})"
        if line not in out:
            out.append(line)
    return out


def merge_reversals(
    verification_dict: dict[str, Any] | None, script: str, facts_text: str
) -> dict[str, Any] | None:
    """`claim_verification` with every reversal added as an unsupported `result` claim."""
    found = reversed_relations(script, facts_text)
    if not found:
        return verification_dict
    merged: dict[str, Any] = dict(verification_dict or {})
    unsupported = list(merged.get("unsupported") or [])
    types = list(merged.get("unsupported_types") or [])
    if len(types) != len(unsupported):
        types = [""] * len(unsupported)
    claims = list(merged.get("claims") or [])
    for line in found:
        unsupported.append(line)
        types.append("result")
        claims.append({"claim": line, "supported": False, "citation_line": "", "type": "result"})
    total = int(merged.get("total") or 0) + len(found)
    supported = int(merged.get("supported") or 0)
    merged.update(
        {
            "total": total,
            "supported": supported,
            "support_rate": round(supported / total, 3) if total else None,
            "unsupported": unsupported,
            "unsupported_types": types,
            "claims": claims,
            "relational_reversals": found,
        }
    )
    return merged
