"""Claim-level LLM verifier (Pillar 3 — Fact Engine 2.0).

Token grounding (`core/fact_grounding.py`) checks that *names* in the script
appear in the facts; it cannot check that the *claim about them* is what the
facts say (decisions §3: a real Giannis→Heat trade fused with an invented
Butler→Celtics one passes token grounding as long as every name is present).
Semantic trade validation covers exactly one claim type. This generalizes it:
one extract-tier LLM call decomposes the finished script into declarative
factual claims and checks each against the numbered fact corpus →
``{claim, supported, citation_line}``.

Behavior contract:
  - Runs post-generation in ``generate_content_package`` (all paths —
    interactive, headless, batch). Default ON; ``CLAIM_VERIFIER_ENABLED=false``
    disables. Fail-open: any LLM/parse failure returns ``None``, never raises.
  - Verifies against the **factual** corpus only (context-tier YouTube
    titles/descriptions are excluded — they must not "support" a claim).
  - WARNS by default. ``GROUNDING_GATE=block`` mirrors the authenticity gate:
    unsupported claims become a hard stop the operator must override
    (interactive prompt / headless ``--force``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.claim_verifier")

_MAX_CLAIMS = 12
_MAX_UNSUPPORTED_KEPT = 10


def _max_fact_chars() -> int:
    """Same budget the script prompt packs — run 76's verifier dropped fact 75."""
    try:
        from core.operator_facts import operator_key_fact_char_budget

        return operator_key_fact_char_budget()
    except Exception:
        return 12000


@dataclass
class VerifiedClaim:
    claim: str
    supported: bool
    citation_line: str = ""  # the fact line that backs a supported claim
    claim_type: str = ""  # #345 - result|award|stat|date|schedule|rumor|opinion|other


@dataclass
class ClaimVerification:
    claims: list[VerifiedClaim] = field(default_factory=list)
    # Candidate 322 — set only when the claim-rewrite pass replaced the script it
    # verified. Without these, a rewritten run is indistinguishable from a run that
    # was right first time: the persisted numbers are all post-rewrite.
    rewritten: bool = False
    pre_rewrite_unsupported: int = 0
    pre_rewrite_total: int = 0
    script_pre_rewrite: str = ""
    script_post_rewrite: str = ""

    @property
    def total(self) -> int:
        return len(self.claims)

    @property
    def pre_rewrite_support_rate(self) -> float | None:
        """Support rate of the script as first written, before any hedging."""
        if not self.rewritten or not self.pre_rewrite_total:
            return None
        supported = self.pre_rewrite_total - self.pre_rewrite_unsupported
        return round(supported / self.pre_rewrite_total, 3)

    @property
    def supported_count(self) -> int:
        return sum(1 for c in self.claims if c.supported)

    @property
    def unsupported(self) -> list[VerifiedClaim]:
        return [c for c in self.claims if not c.supported]

    @property
    def support_rate(self) -> float | None:
        if not self.claims:
            return None
        return round(self.supported_count / self.total, 3)

    def to_dict(self) -> dict[str, Any]:
        """Compact shape persisted into features_json / quality."""
        out: dict[str, Any] = {
            "total": self.total,
            "supported": self.supported_count,
            "support_rate": self.support_rate,
            "unsupported": [c.claim[:200] for c in self.unsupported[:_MAX_UNSUPPORTED_KEPT]],
            # #112. The claim->source edge. Without `citation_line` persisted, a
            # post-publish reversal can say a source moved but never which claim
            # it backed, and `<stem>.facts.json` -- which reads exactly this key
            # -- shipped an empty list on every render.
            "claims": [
                {
                    "claim": c.claim[:200],
                    "supported": bool(c.supported),
                    "citation_line": (c.citation_line or "")[:200],
                    "type": c.claim_type,
                }
                for c in self.claims[:_MAX_CLAIMS]
            ],
        }
        # #345 - aligned with `unsupported`; each type has its own grounding bar. Only
        # present when the verifier typed its claims, so an untyped run keeps its shape.
        if any(c.claim_type for c in self.claims):
            out["unsupported_types"] = [
                c.claim_type for c in self.unsupported[:_MAX_UNSUPPORTED_KEPT]
            ]
        # Only present on a rewritten run, so existing readers see no change.
        if self.rewritten:
            out["rewritten"] = True
            out["pre_rewrite_unsupported"] = self.pre_rewrite_unsupported
            out["pre_rewrite_total"] = self.pre_rewrite_total
            out["pre_rewrite_support_rate"] = self.pre_rewrite_support_rate
            if self.script_pre_rewrite:
                out["script_pre_rewrite"] = self.script_pre_rewrite
            if self.script_post_rewrite:
                out["script_post_rewrite"] = self.script_post_rewrite
        return out


def verifier_enabled() -> bool:
    """Default on — one extract-tier (free-first) call per generated script."""
    return os.getenv("CLAIM_VERIFIER_ENABLED", "true").lower() not in ("0", "false", "no")


def grounding_gate_mode() -> str:
    """block (default since #735, operator call 2026-09-13) | warn - mirrors
    AUTHENTICITY_GATE. `GROUNDING_GATE=warn` makes unsupported claims advisory."""
    return os.getenv("GROUNDING_GATE", "block").strip().lower() or "block"


def gate_blocks(verification_dict: dict[str, Any] | None) -> bool:
    """True when GROUNDING_GATE=block and an unsupported claim fails its type's bar (#345).

    A hedged rumor or a number-free opinion warns only; an untyped claim stays strict.
    """
    if grounding_gate_mode() != "block":
        return False
    from core.claim_types import blocking_unsupported

    return bool(blocking_unsupported(verification_dict))


def override_features(verification_dict: dict[str, Any] | None) -> dict[str, Any]:
    """Features recording that the operator rendered past flagged claims (#754).

    Run 77 answered `y` at the grounding gate and the video queued public; nothing after
    the render remembered. `blocking_publish_reasons` and the upload prompt read these.
    """
    from core.claim_types import blocking_typed, typed_unsupported

    typed = blocking_typed(verification_dict) or typed_unsupported(verification_dict)
    return {
        "grounding_override": True,
        "grounding_override_claims": [claim for claim, _type in typed[:5]],
        "grounding_override_types": [claim_type for _claim, claim_type in typed[:5]],
    }


def _numbered_facts(
    facts_text: str,
    *,
    priority_facts: list[str] | None = None,
) -> list[str]:
    """Build the numbered fact list; operator key facts come first (never truncated away)."""
    seen: set[str] = set()
    numbered: list[str] = []
    used = 0

    def _add(ln: str) -> None:
        nonlocal used
        if used + len(ln) > _max_fact_chars():
            return
        numbered.append(ln)
        used += len(ln)

    for raw in priority_facts or []:
        ln = (raw or "").strip()
        if not ln:
            continue
        key = ln.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        _add(ln)

    for ln in (facts_text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        key = ln.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        _add(ln)
    return numbered


def verify_claims(
    script: str,
    facts_text: str,
    *,
    topic: str = "",
    priority_facts: list[str] | None = None,
) -> ClaimVerification | None:
    """Decompose the script into factual claims and verify each against the facts.

    Returns ``None`` when disabled, when there is nothing to verify, or on any
    LLM/parse failure — callers must treat ``None`` as "no verdict", not "ok".
    """
    if not verifier_enabled():
        return None
    if not (script or "").strip() or not (facts_text or "").strip():
        return None

    facts = _numbered_facts(facts_text, priority_facts=priority_facts)
    if not facts:
        return None
    facts_block = "\n".join(f"{i}. {ln}" for i, ln in enumerate(facts, 1))

    system_prompt = (
        "You are a fact-checker for a short-form video script. You are given "
        "numbered VERIFIED FACTS (the ONLY source of truth) and a SCRIPT. "
        f"Extract up to {_MAX_CLAIMS} declarative factual claims the script asserts "
        "as true — specific events, results, trades, signings, records, stats, "
        "dates, versions. Skip opinions, predictions, hypotheticals, and "
        "rhetorical questions. For each claim decide:\n"
        "- type: one of result, award, stat, date, schedule, rumor, opinion, other "
        "(rumor = a leak or report that is not confirmed).\n"
        "- supported: true only if one or more FACT lines directly back the claim "
        "(paraphrase is fine, but direction, names, and numbers must match).\n"
        "- citation: the number of the single FACT line that best supports it "
        "(null when unsupported).\n"
        'Return JSON only: {"claims": [{"claim": "...", "supported": true, '
        '"citation": 3, "type": "result"}]}'
    )
    user_prompt = f"TOPIC: {topic}\n\nVERIFIED FACTS:\n{facts_block}\n\nSCRIPT:\n{script}"

    from core.claim_types import normalize_type
    from core.llm_router import complete_json

    try:
        payload = complete_json(
            user_prompt,
            system=system_prompt,
            tier="extract",
            temperature=0.1,
            max_tokens=1200,
        )
    except Exception as exc:
        logger.debug("claim verification failed: %s", exc)
        return None
    raw_claims = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(raw_claims, list):
        return None

    verification = ClaimVerification()
    for item in raw_claims[:_MAX_CLAIMS]:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        supported = bool(item.get("supported"))
        citation = ""
        raw_citation = item.get("citation")
        if supported and isinstance(raw_citation, int) and 1 <= raw_citation <= len(facts):
            citation = facts[raw_citation - 1]
        verification.claims.append(
            VerifiedClaim(
                claim=claim,
                supported=supported,
                citation_line=citation,
                claim_type=normalize_type(item.get("type")),
            )
        )
    if not verification.claims:
        return None
    return verification


def display_claim_verification(verification_dict: dict[str, Any] | None, *, print_fn=print) -> bool:
    """Show the claim-verifier verdict. Returns True when review is needed."""
    if not verification_dict:
        return False
    total = int(verification_dict.get("total") or 0)
    supported = int(verification_dict.get("supported") or 0)
    unsupported = list(verification_dict.get("unsupported") or [])
    if not total:
        return False
    rewritten = bool(verification_dict.get("rewritten"))
    pre_unsupported = int(verification_dict.get("pre_rewrite_unsupported") or 0)
    density_raw = verification_dict.get("hedge_density")
    density_note = ""
    if isinstance(density_raw, int | float) and float(density_raw) > 0:
        density_note = f" (hedge density {float(density_raw):.1f}/100w)"
    if not unsupported:
        print_fn(
            f"  [ok] Claim check: {supported}/{total} factual claim(s) backed by the facts."
            f"{density_note}"
        )
        # Candidate 322 — run 71 printed exactly the line above after 7 of 12 claims had
        # been restated as "reports claim..." by the rewrite pass. Same check, rewritten
        # script: nothing was verified between the two numbers.
        if rewritten and pre_unsupported:
            print_fn(
                f"  ! {pre_unsupported} of those were restated as attributed speculation "
                '("reports claim...") by the rewrite pass, not evidenced.'
            )
            print_fn("    Read this as 'no bare assertions left', not 'all claims true'.")
            return True
        return False
    from core.claim_types import claim_blocks, typed_unsupported

    typed = typed_unsupported(verification_dict)
    print_fn(
        f"  ! Claim check: {len(unsupported)} of {total} claim(s) in the SCRIPT aren't in your facts:"
    )
    for claim, claim_type in typed[:6]:
        tag = f"[{claim_type}] " if claim_type else ""
        note = "  (warn only)" if not claim_blocks(claim, claim_type) else ""
        print_fn(f"    - {tag}{claim}{note}")
    if len(unsupported) > 6:
        print_fn(f"    - ...and {len(unsupported) - 6} more")
    if any(not claim_blocks(claim, claim_type) for claim, claim_type in typed):
        print_fn(
            "    Hedged rumors and opinions are warn only - they do not stop the render (#345)."
        )
    print_fn(
        "    These are unverified — the model likely added them. Cut them from the script, "
        "or add a source that backs them."
    )
    return True
