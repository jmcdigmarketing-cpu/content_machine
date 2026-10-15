"""Claim-level LLM verifier (Pillar 3 — Fact Engine 2.0).

Token grounding (`core/facts/grounding.py`) checks that *names* in the script
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
import re
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.claim_verifier")

_MAX_CLAIMS = 12
_MAX_UNSUPPORTED_KEPT = 10


def _max_fact_chars() -> int:
    """The checker's own fact budget, `CLAIM_FACT_CHAR_BUDGET` (default 24,000 characters).

    #1171: it used the script prompt's 12,000 (run 76's verifier had dropped fact 75 under a
    smaller one). On 2026-10-13 and 10-14, 5 checks left 17-21 fact lines out. The writer's
    prompt is not capped the same way, so the checker read less than the writer was given.
    About 3,000 more input tokens a check.
    """
    raw = os.getenv("CLAIM_FACT_CHAR_BUDGET", "24000").strip()
    try:
        return max(4000, min(60000, int(raw)))
    except ValueError:
        return 24000


@dataclass
class VerifiedClaim:
    claim: str
    supported: bool
    citation_line: str = ""  # the fact line that backs a supported claim
    claim_type: str = ""  # #345 - result|award|stat|date|schedule|rumor|opinion|other
    tier: str = ""  # #1026 - operator | signal | web | brief | context, or ""
    by: str = ""  # #1148 - "match": the model said no and a fact line carries it


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
    # #1148: how many fact lines the check was sent, and how many did not fit its budget.
    facts_given: int = 0
    facts_left_out: int = 0

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
                    "tier": c.tier,
                    **({"by": c.by} if c.by else {}),
                }
                for c in self.claims[:_MAX_CLAIMS]
            ],
        }
        matched = sum(1 for c in self.claims if c.by == "match")
        if matched:
            out["matched"] = matched  # #1148
        if self.facts_given or self.facts_left_out:
            out["facts"] = {"given": self.facts_given, "left_out": self.facts_left_out}
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


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)*")
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'-]*")
_POSSESSIVE_RE = re.compile(r"['\u2019]s\b")
_CLAUSE_RE = re.compile(r"[.;|!?]\s+|,\s+|\s+(?:and|but|while)\s+", re.I)
_NEGATION_RE = re.compile(r"\b(?:not|never|no|without|nor)\b|n['\u2019]t\b", re.I)
_WIN_RE = re.compile(
    r"\b(?:beat|beats|defeated|defeats|topped|edged|downed|routed|crushed|swept|outlasted|"
    r"upset|won over|win over|victory over)\b",
    re.I,
)
_LOSE_RE = re.compile(r"\b(?:lost to|loses to|loss to|fell to|falls to|dropped to)\b", re.I)


def _plain(text: str) -> str:
    return _POSSESSIVE_RE.sub("", str(text or ""))


def _words(text: str) -> set[str]:
    """Lowercase words, a hyphenated one also as its parts ("re-signed": re, signed)."""
    out: set[str] = set()
    for word in _WORD_RE.findall(_plain(text).lower()):
        out.add(word)
        out.update(part for part in re.split(r"[-']", word) if part)
    return out


def _numbers(text: str) -> list[str]:
    return [m.group(0) for m in _NUMBER_RE.finditer(_plain(text).replace(",", ""))]


def _has_number(text: str, number: str) -> bool:
    return bool(
        re.search(rf"(?<![\d.-]){re.escape(number)}(?![\d-]|\.\d)", str(text).replace(",", ""))
    )


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _same_name(wanted: str, found: str) -> bool:
    """`wanted` from the claim against a word of the fact: the same, or a short plural
    nickname of it ("cavs" for "cavaliers")."""
    if wanted == found:
        return True
    return (
        wanted.endswith("s")
        and 3 < len(wanted) <= 5
        and len(found) > len(wanted)
        and found.startswith(wanted[:-1])
    )


def _claim_parts(claim: str) -> tuple[list[str], list[str], list[str], list[str]]:
    """(numbers, the ones that pin a fact, names, other content words) of a claim.

    A name is a content word the claim writes with a capital. A number pins a fact when it is
    a score or record ("119-105"), a decimal, or a count that does not sit in a name: the 4 of
    "Modern Warfare 4" and the 122 of "UFC Vegas 122" are part of a title and pin nothing.
    """
    from apis.topic_tokens import content_tokens

    text = _plain(claim).replace(",", "")
    numbers: list[str] = []
    pins: list[str] = []
    for found in _NUMBER_RE.finditer(text):
        number = found.group(0)
        numbers.append(number)
        before = text[: found.start()].split()
        in_a_name = bool(before) and before[-1][:1].isupper() and len(before) > 1
        if "-" in number or "." in number or not in_a_name:
            pins.append(number)
    capitals = {w.lower() for w in re.findall(r"\b[A-Z][\w-]*", text)}
    names: list[str] = []
    others: list[str] = []
    for token in content_tokens(text):
        if token[:1].isdigit():
            continue
        (names if token in capitals else others).append(token)
    return numbers, pins, names, others


def _winner_side(text: str) -> set[str] | None:
    """The words on the winning side of a result verb in `text`, None when it states none."""
    plain = _plain(text)
    win, lose = _WIN_RE.search(plain), _LOSE_RE.search(plain)
    found = win or lose
    if not found:
        return None
    return _words(plain[: found.start()]) if win else _words(plain[found.end() :])


_TOKEN_RE = re.compile(r"[A-Za-z0-9][\w.'-]*")


def _paired(part: str, number: str, names: list[str]) -> bool:
    """False when `part` holds several numbers of `number`'s shape and the nearest capital
    word to this one is not one of the claim's names - "Knicks (0-3) at Raptors (1-1)" gives
    the Raptors 1-1, not 0-3."""
    tokens = _TOKEN_RE.findall(_plain(part).replace(",", ""))
    shaped = [
        t for t in tokens if _NUMBER_RE.fullmatch(t.strip(".")) and ("-" in t) == ("-" in number)
    ]
    if len(set(shaped)) < 2:
        return True
    at = next((i for i, t in enumerate(tokens) if t.strip(".") == number), None)
    if at is None:
        return True
    capitals = [(abs(i - at), t.lower()) for i, t in enumerate(tokens) if t[:1].isupper()]
    if not capitals:
        return True
    nearest = min(distance for distance, _word in capitals)
    return any(
        _same_name(name, word.strip(".'"))
        for distance, word in capitals
        if distance == nearest
        for name in names
    )


def _carries(
    claim: str, part: str, numbers: list[str], pins: list[str], names: list[str], others: list[str]
) -> bool:
    words = _words(part)
    if not all(_has_number(part, number) for number in numbers):
        return False
    if not all(any(_same_name(name, word) for word in words) for name in names):
        return False
    if not all(_paired(part, number, names) for number in pins):
        return False
    claimed, stated = _winner_side(claim), _winner_side(part)
    if others:
        stems = {_stem(word) for word in words}
        shared = any(_stem(word) in stems for word in others)
        # "beat" and "defeated" share no stem; the result check below reads those.
        if not shared and (claimed is None or stated is None):
            return False
    if bool(_NEGATION_RE.search(claim)) != bool(_NEGATION_RE.search(part)):
        return False
    if claimed is not None:
        winners = [name for name in names if name in claimed]
        if stated is None or not winners:
            return False
        if not all(any(_same_name(name, word) for word in stated) for name in winners):
            return False
    return True


def carried_by_facts(claim: str, fact_lines: list[str], *, weak: set[str] | None = None) -> str:
    """The fact line that carries a numbered `claim` word for word, or "" (#1148).

    A second look that cannot vary, for a claim the model called unsupported: every number and
    every name of the claim inside one clause of one fact line, a word of the claim's own
    there too, the same side winning, the same yes or no. Measured on 13 recorded drafts it
    carries 3 of 50 blocking claims: two scores and a stat line.

    It is narrow on purpose. A claim with no number that pins a fact stays with the model:
    two names sharing a line is not a claim ("re-signed" and "added" sat in one sentence about
    three players). `weak` lines (#966, the model-written brief) carry nothing.
    """
    numbers, pins, names, others = _claim_parts(claim)
    if not pins or not names:
        return ""
    for line in fact_lines:
        text = str(line or "").strip()
        if not text or (weak and _weak_key(text) in weak):
            continue
        if any(
            _carries(claim, part, numbers, pins, names, others) for part in _CLAUSE_RE.split(text)
        ):
            return text
    return ""


def _quoted_first(lines: list[str], script: str) -> list[str]:
    """`lines` with those sharing a number with the script moved to the front, order kept."""
    wanted = [n for n in dict.fromkeys(_numbers(script)) if len(n) > 1]
    if not wanted:
        return lines
    first = [ln for ln in lines if any(_has_number(ln, number) for number in wanted)]
    if not first:
        return lines
    chosen = set(first)
    return first + [ln for ln in lines if ln not in chosen]


def _numbered_facts(
    facts_text: str,
    *,
    priority_facts: list[str] | None = None,
    script: str = "",
) -> list[str]:
    """Build the numbered fact list; operator key facts come first (never truncated away).

    `script` (#1148): when the facts do not all fit the budget, the lines that share a number
    with the script are packed before the rest. The writer's prompt has no such budget, so a
    fact past it could be written into a script and never shown to the check.
    """
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

    rest = [ln.strip() for ln in (facts_text or "").splitlines() if ln.strip()]
    if script and used + sum(len(ln) for ln in rest) > _max_fact_chars():
        rest = _quoted_first(rest, script)
    for ln in rest:
        key = ln.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        _add(ln)
    return numbered


def _fact_line_total(facts_text: str, priority_facts: list[str] | None) -> int:
    """How many distinct fact lines there were to send, by `_numbered_facts`' own key."""
    keys = {str(raw or "").strip().lower()[:120] for raw in priority_facts or []}
    keys |= {ln.strip().lower()[:120] for ln in (facts_text or "").splitlines()}
    keys.discard("")
    return len(keys)


def _weak_key(line: str) -> str:
    return " ".join(str(line or "").strip().lstrip("•-→ ").lower().split())


def verify_claims(
    script: str,
    facts_text: str,
    *,
    topic: str = "",
    priority_facts: list[str] | None = None,
    weak_lines: set[str] | None = None,
    line_tiers: dict[str, str] | None = None,
) -> ClaimVerification | None:
    """Decompose the script into factual claims and verify each against the facts.

    `weak_lines` (#966) are corpus lines an LLM wrote - the research brief - that cannot by
    themselves back a claim that blocks (`claim_types.claim_blocks`): a brief written from
    model memory must not "support" a stale team or result.

    Returns ``None`` when disabled, when there is nothing to verify, or on any
    LLM/parse failure — callers must treat ``None`` as "no verdict", not "ok".
    """
    if not verifier_enabled():
        return None
    if not (script or "").strip() or not (facts_text or "").strip():
        return None

    weak = {_weak_key(line) for line in weak_lines or () if _weak_key(line)}
    # #1148: the brief is model-written, so it is not shown as a fact to cite. Run 137's brief
    # restated the score and the signings; the model cited the brief for each and the #966
    # rule below then called all of them unsupported, with the sources two lines away.
    sourced = "\n".join(
        ln for ln in facts_text.splitlines() if not (weak and _weak_key(ln) in weak)
    )
    if sourced.strip():
        facts_text = sourced
    facts = _numbered_facts(facts_text, priority_facts=priority_facts, script=script)
    if not facts:
        return None
    left_out = max(0, _fact_line_total(facts_text, priority_facts) - len(facts))
    if left_out:
        logger.info(
            "Claim verifier: %d fact line(s) did not fit the %d-character budget",
            left_out,
            _max_fact_chars(),
        )
    facts_block = "\n".join(f"{i}. {ln}" for i, ln in enumerate(facts, 1))

    system_prompt = (
        "You are a fact-checker for a short-form video script. You are given "
        "numbered VERIFIED FACTS (the ONLY source of truth) and a SCRIPT. "
        f"Extract up to {_MAX_CLAIMS} declarative factual claims the script asserts "
        "as true — specific events, results, trades, signings, who plays for, coaches, "
        "leads or owns what (a person's team, title or job), records, stats, "
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

    from core.claim_types import claim_blocks, normalize_type
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

    verification = ClaimVerification(facts_given=len(facts), facts_left_out=left_out)
    # #1148: every fact line, not only those that fit - a line left out can still carry.
    every_line = [str(raw or "").strip() for raw in priority_facts or []]
    every_line += [ln.strip() for ln in facts_text.splitlines() if ln.strip()]
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
        tier = ""
        if citation and line_tiers:
            tier = str(line_tiers.get(citation.strip()) or "")
        claim_type = normalize_type(item.get("type"))
        if (
            supported
            and citation
            and _weak_key(citation) in weak
            and claim_blocks(claim, claim_type)
        ):
            supported, citation, tier = False, "", ""  # #966: the brief alone backs nothing strict
        if (
            supported
            and isinstance(raw_citation, int)
            and not 1 <= raw_citation <= len(facts)
            and claim_blocks(claim, claim_type)
        ):
            # #1148: it cites a line it was not shown. With the brief off the list, that is
            # how "the brief said so" arrives - and a made-up citation backs nothing either way.
            supported = False
        by = ""
        if not supported:
            carried = carried_by_facts(claim, every_line, weak=weak)
            if carried:
                supported, citation, by = True, carried, "match"
                tier = str((line_tiers or {}).get(carried) or "")
        verification.claims.append(
            VerifiedClaim(
                claim=claim,
                supported=supported,
                citation_line=citation,
                claim_type=claim_type,
                tier=tier,
                by=by,
            )
        )
    if not verification.claims:
        return None
    return verification


def _provenance_lines(verification_dict: dict[str, Any]) -> list[str]:
    """#1026: each claim, the fact that backs it, and that fact's tier. Missing is 'none'."""
    lines: list[str] = []
    for item in verification_dict.get("claims") or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        fact = str(item.get("citation_line") or "").strip() or "none"
        tier = str(item.get("tier") or "").strip() or "none"
        lines.append(f"    - {claim}  |  {fact}  |  {tier}")
    return lines


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
    for line in _provenance_lines(verification_dict):
        print_fn(line)
    matched = int(verification_dict.get("matched") or 0)
    if matched:  # #1148
        print_fn(
            f"  {matched} found word for word in the facts after the checker said no "
            "(marked 'match')."
        )
    facts = verification_dict.get("facts")
    if isinstance(facts, dict) and int(facts.get("left_out") or 0):
        given, left = int(facts.get("given") or 0), int(facts.get("left_out") or 0)
        print_fn(
            f"  ! {left} of {given + left} fact lines did not fit the checker's budget - a "
            "claim resting on one of them reads as unsupported."
        )
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
