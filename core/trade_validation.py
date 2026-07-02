"""Semantic trade validation — is the trade DIRECTION backed by the facts?

Token-level grounding (`core/fact_grounding.py`) passes a claim like
"LeBron traded to the Celtics" as long as *LeBron* and *Celtics* both appear
somewhere in the fact corpus — even if the facts actually say LeBron went to
the Heat. That is exactly how a real incident fused a genuine Giannis→Heat
trade with an invented Butler→Celtics one.

This layer extracts `player → team` trade claims from the script and checks
each pair co-occurs on a **single fact line** with a trade verb. Both names
present in the corpus but never together on one trade line ⇒ the pairing is
suspect (fused/mis-directed trade).

Opt-in via ``SEMANTIC_TRADE_VALIDATION`` (default **off**) — deliberately,
because sentence-level co-occurrence has a higher false-positive rate than
token grounding (a fact split across two pasted lines will flag). Like the
grounding check it WARNS, never blocks or rewrites.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_TRADE_VERBS = r"(?:traded|dealt|sent|shipped|moved|moving|headed|acquired|landed?|signed)"

# "<Player> [is/was/gets/being] traded/dealt/sent/... to [the] <Team>"
_PLAYER_TO_TEAM = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+"
    r"(?:is\s+|was\s+|gets\s+|being\s+|reportedly\s+)*"
    rf"{_TRADE_VERBS}\s+to\s+(?:the\s+)?"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
)

# "<Team> acquired/landed/added/got <Player>"
_TEAM_GETS_PLAYER = re.compile(
    r"\b(?:[Tt]he\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+"
    r"(?:have\s+|has\s+|just\s+|reportedly\s+)*"
    r"(?:acquired?|landed?|added|got)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
)

# Words that regex capture groups can grab but are never a player/team name.
_NOISE = {
    "the",
    "this",
    "that",
    "they",
    "their",
    "what",
    "when",
    "here",
    "there",
    "breaking",
    "sources",
    "reportedly",
    "officially",
    "league",
    "team",
    "player",
    "deal",
    "trade",
}


@dataclass(frozen=True)
class TradeClaim:
    player: str
    team: str

    def __str__(self) -> str:
        return f"{self.player} → {self.team}"


def trade_validation_enabled() -> bool:
    """Opt-in: higher false-positive risk than token grounding (see module doc)."""
    return os.getenv("SEMANTIC_TRADE_VALIDATION", "").lower() in ("1", "true", "yes")


def _clean(name: str) -> str:
    words = [w for w in (name or "").split() if w.lower() not in _NOISE]
    return " ".join(words).strip()


def extract_trade_claims(text: str) -> list[TradeClaim]:
    """`player → team` trade claims asserted in `text` (order-preserving, deduped)."""
    claims: list[TradeClaim] = []
    seen: set[tuple[str, str]] = set()

    def _add(player: str, team: str) -> None:
        player, team = _clean(player), _clean(team)
        if not player or not team or player.lower() == team.lower():
            return
        key = (player.lower(), team.lower())
        if key not in seen:
            seen.add(key)
            claims.append(TradeClaim(player=player, team=team))

    for m in _PLAYER_TO_TEAM.finditer(text or ""):
        _add(m.group(1), m.group(2))
    for m in _TEAM_GETS_PLAYER.finditer(text or ""):
        _add(m.group(2), m.group(1))
    return claims


def _tokens(name: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", name.lower()) if len(t) >= 3]


def _line_has(line: str, name: str) -> bool:
    """Any distinctive token of the name appears whole-word in the line.

    Any-token (not all-token) so "LeBron" matches a fact line that says
    "LeBron James", and "Celtics" matches "Boston Celtics".
    """
    toks = _tokens(name)
    return bool(toks) and any(
        re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", line) for t in toks
    )


def validate_trade_claims(script: str, facts_text: str) -> list[str]:
    """Warnings for trade claims whose player+team never share a fact line.

    Returns [] when validation is not applicable (no claims, or an empty
    corpus — nothing to validate against, token grounding covers that case).
    """
    claims = extract_trade_claims(script)
    if not claims or not (facts_text or "").strip():
        return []

    lines = [ln.strip().lower() for ln in facts_text.split("\n") if ln.strip()]
    warnings: list[str] = []
    for claim in claims:
        player_somewhere = any(_line_has(ln, claim.player) for ln in lines)
        if not player_somewhere:
            continue  # wholly unknown name — token grounding already flags it
        together = any(_line_has(ln, claim.player) and _line_has(ln, claim.team) for ln in lines)
        if not together:
            warnings.append(
                f"{claim} — '{claim.player}' is in the facts, but never on the same "
                f"line as '{claim.team}'. Possible fused/mis-directed trade."
            )
    return warnings


def display_trade_validation(warnings: list[str], *, print_fn=print) -> bool:
    """Show semantic-trade warnings. Returns True when review is needed."""
    if not warnings:
        return False
    print_fn(f"\n  ⚠ Trade direction check ({len(warnings)}):")
    for w in warnings[:8]:
        print_fn(f"    · {w}")
    if len(warnings) > 8:
        print_fn(f"    · …and {len(warnings) - 8} more")
    print_fn("    Verify each pairing against your pasted trade block before rendering.")
    return True
