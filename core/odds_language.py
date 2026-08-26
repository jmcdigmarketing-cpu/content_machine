"""Odds voice (#126) + advertiser-safe betting CTAs (#127).

Odds-derived scripts must say "market" / "favored", never "will win".
Gambling CTAs are stripped. Default-on; suite sets both flags false.
Distinct from the name pronunciation lexicon.
"""

from __future__ import annotations

import os
import re

from core.logging import get_logger

logger = get_logger("core.odds_language")

# Bare "favorite" / "the market" / "underdog" are ordinary gaming copy
# ("fan favorite", "skin market"). Require betting/odds vocabulary.
_ODDS_CONTEXT = re.compile(
    r"\b(odds|moneyline|money line|implied probability|betting line|"
    r"sportsbook|as the favorite|as the favourite|"
    r"the favorite to|the favourite to)\b",
    re.IGNORECASE,
)
_WILL_FIGHT = re.compile(
    r"\bwill (win|beat|finish|submit|knock out|take (?:it|this))\b",
    re.IGNORECASE,
)
# "lock it in" and bare "use code" are gaming slang / console copy — not CTAs.
_BETTING_CTA = re.compile(
    r"\b(?:bet now|place your bets?|put money on|"
    r"this parlay|odds boost|use promo(?:\s+code)?)\b[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def has_odds_context(text: str, topic: str = "") -> bool:
    blob = f"{topic or ''} {text or ''}"
    return bool(_ODDS_CONTEXT.search(blob))


def soften_odds_certainty(script: str, *, topic: str = "") -> tuple[str, list[str]]:
    """Rewrite 'will win/beat' to market language when odds context is present."""
    if not _flag("ODDS_MARKET_VOICE", True):
        return script or "", []
    text = script or ""
    if not text or not has_odds_context(text, topic):
        return text, []
    if not _WILL_FIGHT.search(text):
        return text, []

    def _sub(match: re.Match[str]) -> str:
        rest = match.group(0).split(None, 1)[1]
        return f"is favored to {rest}"

    out = _WILL_FIGHT.sub(_sub, text)
    return out, ["odds voice: 'will' softened to 'is favored to' (market, not prediction)"]


def strip_betting_ctas(text: str) -> tuple[str, int]:
    """Drop implied betting CTAs. Returns (cleaned, n_removed)."""
    if not _flag("GAMBLING_SAFE", True):
        return text or "", 0
    raw = text or ""
    if not raw:
        return raw, 0
    cleaned, n = _BETTING_CTA.subn("", raw)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, n


def apply_odds_language(script: str, *, topic: str = "") -> tuple[str, list[str]]:
    """CTA strip then market-voice rewrite. Never raises."""
    notes: list[str] = []
    try:
        out, n = strip_betting_ctas(script)
        if n:
            notes.append(f"gambling-safe: stripped {n} betting CTA(s)")
        out, more = soften_odds_certainty(out, topic=topic)
        notes.extend(more)
        return out, notes
    except Exception as exc:
        logger.debug("odds language skipped: %s", exc)
        return script or "", []
