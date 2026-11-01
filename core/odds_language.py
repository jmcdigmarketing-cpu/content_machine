"""Odds voice (#126) + advertiser-safe betting CTAs (#127) + brand lexicon (#409).

Odds-derived scripts must say "market" / "favored", never "will win".
Gambling CTAs are stripped. Default-on; suite sets both flags false.
The brand file is a per-channel phrase list, not that odds pass.
Distinct from the name pronunciation lexicon.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

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


# #1764 (decision 95): sportsbooks, pick'em apps and crypto casinos - never an affiliate row,
# never a link in a description, whatever GAMBLING_SAFE says. Matched on the link's host (a
# sportsbook subdomain of a shop - sportsbook.fanatics.com - is one; fanatics.com's jerseys are not).
GAMBLING_HOSTS = (
    "draftkings.com", "fanduel.com", "betmgm.com", "caesars.com/sportsbook", "sportsbook.caesars.com",
    "bet365.com", "pointsbet.com", "betrivers.com", "hardrock.bet", "espnbet.com", "thescore.bet",
    "sportsbook.fanatics.com", "prizepicks.com", "underdogfantasy.com", "stake.com", "stake.us",
    "rollbit.com", "bovada.lv", "betonline.ag", "mybookie.ag", "betway.com", "williamhill.com",
    "paddypower.com", "unibet.com", "888sport.com", "betfair.com", "sportsbet.com.au",
    "parlayplay.io", "dabble.com", "betr.app", "chalkboard.io",
)  # fmt: skip
_GAMBLING_WORDS = re.compile(r"\b(?:sportsbook|casino|parlay|betting|bet now|odds boost)\b", re.I)
_LINK = re.compile(r"https?://\S+", re.I)


def is_gambling_link(url: str, label: str = "") -> bool:
    """A sportsbook, pick'em or casino link, or a label that sells betting."""
    if _GAMBLING_WORDS.search(str(label or "")):
        return True
    host, _sep, path = re.sub(r"^https?://", "", str(url or "").strip().lower()).partition("/")
    host = host.split(":")[0].removeprefix("www.")
    for entry in GAMBLING_HOSTS:
        domain, _slash, prefix = entry.partition("/")
        if (host == domain or host.endswith(f".{domain}")) and path.startswith(prefix):
            return True
    return False


def strip_gambling_links(text: str) -> tuple[str, int]:
    """Drop every line carrying a gambling link (#1764) - always, not behind GAMBLING_SAFE."""
    kept: list[str] = []
    removed = 0
    for line in (text or "").splitlines():
        if any(is_gambling_link(url) for url in _LINK.findall(line)):
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


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


def lexicon_path(channel_id: str) -> Path:
    from config.paths import ROOT_DIR

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (channel_id or ""))
    return Path(ROOT_DIR) / "config" / "brand_safety" / f"{safe}.txt"


def lexicon_phrases(channel_id: str) -> list[str]:
    """Phrases from the channel's file. A one-word line is not a phrase."""
    path = lexicon_path(channel_id)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    phrases: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if not line or " " not in line:
            continue
        phrases.append(line)
    return phrases


def apply_brand_lexicon(script: str, *, channel_id: str) -> tuple[str, list[str]]:
    """Drop a sentence that contains a channel phrase. Never raises."""
    text = script or ""
    phrases = lexicon_phrases(channel_id)
    if not text or not phrases:
        return text, []
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part]
    kept: list[str] = []
    dropped = 0
    for sentence in sentences:
        lowered = sentence.lower()
        if any(phrase in lowered for phrase in phrases):
            dropped += 1
            continue
        kept.append(sentence)
    if not dropped:
        return text, []
    return " ".join(kept).strip(), [f"brand-safety: dropped {dropped} sentence(s)"]


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
