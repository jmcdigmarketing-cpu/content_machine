"""An editorial score for a generated angle, from the angle text alone.

**Why this exists.** `core/pipeline._score_variant` scores each variant with
`apis/topic_scorer.composite_score`, but `build_registry(variant,
reuse_signals=base_signals)` pins every signal in `_VARIANT_REUSE_DEFAULT` — so
all five variants are scored against the *base topic's* signals, unchanged. The
only way the variant string reaches `composite_score_raw` is `infer_domain`
(identical for five framings of one subject) and `get_historical_boost` (an
exact-string lookup, so 0.0 for an angle generated seconds ago). Five angles in,
one number out: live-run 71 tied at 100.00, run 72 at 92.14.

**What this is not.** This is not a better predictor of views, and it must not be
folded into the composite and presented as one. The composite is a *trend* score;
this is an *editorial* one, and the two answer different questions. The measured
record is that the composite does not predict engagement either (hit rate 40%;
the lowest-scored topic on record beat two 100.0s), so quietly averaging them
would launder one unvalidated number into another.

It ranks on three things the operator can check by eye, none of which needs a
network call — re-fetching signals per variant costs 150-185s and 5x the web
spend per run, which is exactly what `reuse_signals` exists to prevent:

- **distinctness** — how unlike the other four this angle is. The angle prompt
  already asks for this in words ("if two angles could share the same thumbnail,
  rewrite one"); nothing measured it.
- **seed fidelity** — how much of what the operator actually typed survives.
  Run 48 turned an NBA seed into a Marvel Rivals script and no number noticed.
- **specificity** — numbers and named entities, the same measure
  `core/fact_selection` uses to rank facts.
"""

from __future__ import annotations

import json
import re

from core.logging import get_logger

logger = get_logger("core.angle_ranker")

# Distinctness weighs most: five variants of one take is the complaint that
# reaches the operator first. Fidelity is close behind because drift is the
# failure that wastes a whole run. Specificity breaks the remaining ties.
_WEIGHT_DISTINCTNESS = 0.40
_WEIGHT_FIDELITY = 0.35
_WEIGHT_SPECIFICITY = 0.25

_NEUTRAL_FIDELITY = 0.5  # nothing nameable in the seed — do not punish or reward
_LISTICLE_LEFTOVER_PENALTY = 0.25

_WORD_RE = re.compile(r"[a-z0-9']+")

# Listicle leftovers from ANGLE_LIST templates. Run 76's honourable-mention
# angle still carried "Predictions" from the seed; entity overlap alone ranked
# it with the hype/criterion take.
_LISTICLE_LEFTOVER = (
    "honorable mention",
    "honourable mention",
    "almost made the list",
    "that almost made",
    "closest call",
    "forgotten feature",
    "coming in at",
)

_THESIS_KEYWORDS = frozenset(
    {
        "hype",
        "failure",
        "fail",
        "failed",
        "predictions",
        "prediction",
        "analysis",
        "criterion",
        "criteria",
        "candidate",
        "goat",
    }
)

_THESIS_PHRASES = (
    "meeting the hype",
    "best game",
    "long form",
    "will it be the best",
)

# Function words carry no editorial signal; leaving them in makes every pair of
# English sentences look similar and flattens distinctness toward zero.
_STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has have
    how in into is it its may might more most must new no not of on or our out over
    should so than that the their then there these they this to up was were what when
    where which who why will with would you your""".split()
)


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOPWORDS}


def _distinctness(angle: str, peers: list[str]) -> float:
    """1 - the highest Jaccard overlap with any other angle in the set."""
    mine = _content_words(angle)
    if not mine:
        return 0.0
    worst = 0.0
    for peer in peers:
        theirs = _content_words(peer)
        if not theirs:
            continue
        union = mine | theirs
        if not union:
            continue
        worst = max(worst, len(mine & theirs) / len(union))
    return round(1.0 - worst, 4)


def _thesis_terms(seed_topic: str) -> list[str]:
    """Question stems, hype/failure/prediction cues — not just named entities.

    Jaccard on proper nouns could not tell run 76's criterion angle from an
    honourable-mention listicle leftover; both said GTA 6.
    """
    text = seed_topic or ""
    low = text.lower()
    out: list[str] = []
    for phrase in _THESIS_PHRASES:
        if phrase in low:
            out.append(phrase)
    for kw in sorted(_THESIS_KEYWORDS):
        if re.search(rf"\b{re.escape(kw)}\b", low):
            out.append(kw)
    for match in re.finditer(r"\b((?:will|what|why|is|does|can)\b[^?]{8,80})", text, flags=re.I):
        words = _WORD_RE.findall(match.group(1).lower())
        if len(words) >= 4:
            out.append(" ".join(words[:5]))
    return out


def _seed_terms(seed_topic: str) -> list[str]:
    """What the operator's seed is *about* — subjects, franchise anchors, thesis."""
    terms: list[str] = []
    try:
        from apis.topic_variants import _subject_terms

        terms.extend(_subject_terms(seed_topic or ""))
    except Exception as exc:  # best-effort enrichment — fidelity degrades to neutral
        logger.debug("Subject-term extraction skipped: %s", exc)
    try:
        from core.channel_context import extract_anchors

        terms.extend(extract_anchors(seed_topic or ""))
    except Exception as exc:
        logger.debug("Anchor extraction skipped: %s", exc)
    terms.extend(_thesis_terms(seed_topic))
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        key = term.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def _fidelity(angle: str, seed_terms: list[str]) -> float:
    """Share of the seed's nameable subjects *and* thesis terms the angle still carries."""
    if not seed_terms:
        return _NEUTRAL_FIDELITY
    low = (angle or "").lower()
    kept = sum(1 for term in seed_terms if term.lower() in low)
    return round(kept / len(seed_terms), 4)


def _listicle_leftover_penalty(angle: str) -> float:
    low = (angle or "").lower()
    if any(phrase in low for phrase in _LISTICLE_LEFTOVER):
        return _LISTICLE_LEFTOVER_PENALTY
    return 0.0


def _specificity_of(angle: str) -> float:
    from core.fact_selection import _specificity

    return _specificity(angle)


def _cheap_judge(angles: list[str], seed_topic: str) -> dict[str, float] | None:
    """Score each angle 0-1 against the typed thesis via the cheap LLM chain.

    Fail-open: any error or unparseable reply returns None. Does not add a
    provider — uses ``complete(tier="cheap")`` as already routed.
    """
    if not angles or not (seed_topic or "").strip():
        return None
    numbered = "\n".join(f"{i + 1}. {angle}" for i, angle in enumerate(angles))
    prompt = (
        "Score each angle 0-1 for how well it answers the operator's thesis "
        'questions. Return JSON only: {"scores": [n, n, ...]} in the same '
        "order as the angles. No commentary.\n\n"
        f"Thesis:\n{seed_topic.strip()}\n\nAngles:\n{numbered}\n"
    )
    try:
        from core.llm_router import complete

        raw = complete(
            prompt,
            tier="cheap",
            temperature=0.0,
            max_tokens=256,
            json_mode=True,
            stage="angle_judge",
        )
    except Exception as exc:
        logger.debug("cheap angle judge skipped: %s", exc)
        return None
    blob = (raw or "").strip()
    if not blob:
        return None
    try:
        start = blob.find("{")
        end = blob.rfind("}")
        payload = json.loads(blob[start : end + 1] if start >= 0 and end > start else blob)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.debug("cheap angle judge returned unparseable JSON")
        return None
    values = payload.get("scores") if isinstance(payload, dict) else None
    if not isinstance(values, list) or len(values) != len(angles):
        return None
    out: dict[str, float] = {}
    for angle, value in zip(angles, values, strict=True):
        try:
            out[angle] = min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return None
    return out


def rank_angles(
    angles: list[str],
    *,
    seed_topic: str = "",
    llm_judge: bool = False,
) -> dict[str, float]:
    """`{angle: 0..1}` — an editorial score per angle. Never raises.

    Deterministic by default (network-free). ``llm_judge=True`` asks the cheap
    chain to score each angle against the typed thesis and blends the result;
    any cheap-tier miss fails open to the deterministic ranking.
    Blank angles are dropped; duplicates collapse to one key (they are the same
    angle, and scoring one of them twice would imply a choice that does not exist).
    """
    cleaned: list[str] = []
    for angle in angles or []:
        text = (angle or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return {}

    terms = _seed_terms(seed_topic)
    scores: dict[str, float] = {}
    for angle in cleaned:
        peers = [other for other in cleaned if other != angle]
        composite = (
            _WEIGHT_DISTINCTNESS * _distinctness(angle, peers)
            + _WEIGHT_FIDELITY * _fidelity(angle, terms)
            + _WEIGHT_SPECIFICITY * _specificity_of(angle)
            - _listicle_leftover_penalty(angle)
        )
        scores[angle] = round(min(1.0, max(0.0, composite)), 4)

    if llm_judge:
        judged = _cheap_judge(cleaned, seed_topic)
        if judged:
            for angle in scores:
                scores[angle] = round(
                    min(1.0, max(0.0, 0.6 * scores[angle] + 0.4 * judged[angle])),
                    4,
                )
    return scores


def score_spread(scores: dict[str, float]) -> float:
    """max - min of an editorial ranking. 0.0 means a real tie (or no scores)."""
    if not scores:
        return 0.0
    values = list(scores.values())
    return round(max(values) - min(values), 4)
