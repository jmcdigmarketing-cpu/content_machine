"""Pre-script contradiction detection (Pillar 3 — Fact Engine 2.0).

Flags disagreements between the operator's key facts and the signal/web corpus
BEFORE the script LLM sees both — previously a stale web line ("Giannis to the
Warriors") sat next to the operator's fresh paste ("Giannis to the Heat") in
one prompt and the model picked whichever it liked.

Deliberately high-precision: a conflict requires an **operator-side line**
(operator facts are ground truth, decisions §4 — anything contradicting them
is either a stale source or an operator typo; both deserve a flag). Intra-
signal disagreements without an operator anchor are not adjudicated here.

Three rule-based checks (no LLM — this runs in the hot path pre-generation):

  - ``trade_direction`` — operator says player→A, another source says
    player→B (reuses `core.trade_validation.extract_trade_claims`).
  - ``reversed_result`` — operator says "X beat Y", another source says
    "Y beat X".
  - ``champion`` — operator and a source name different people as the same
    division's champion.

When ``FACT_CONFLICT_FILTER`` is on (default), the conflicting NON-operator
lines are dropped from the corpus before prompting — same pattern as the
future-date filter (`core/fact_recency.py`): grounding stops invention, this
stops propagation. Conflicts are always surfaced to the operator either way.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from core.trade_validation import extract_trade_claims

# "X defeated/beat/KO'd Y" — result with an explicit winner and loser.
_RESULT_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+"
    r"(?:defeated|beat|knocked\s+out|ko'?d|tko'?d|submitted|outpointed)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
)

# "X is/remains/became the ... champion" — title holder claims.
_CHAMPION_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+"
    r"(?:is|remains|became|was\s+crowned)\s+(?:now\s+)?the\s+"
    r"(?:current\s+|new\s+|undisputed\s+|reigning\s+)*"
    r"([a-z][a-z\s]{0,30}?)\s*champion\b",
)

_DIVISION_WORDS = frozenset(
    {
        "flyweight",
        "bantamweight",
        "featherweight",
        "lightweight",
        "welterweight",
        "middleweight",
        "heavyweight",
        "strawweight",
        "world",
        "nba",
        "nfl",
        "mlb",
        "nhl",
        "ufc",
        "wnba",
    }
)

_MAX_CONFLICTS = 6


@dataclass(frozen=True)
class FactConflict:
    kind: str  # trade_direction | reversed_result | champion
    operator_line: str
    other_line: str
    detail: str

    def render(self) -> str:
        return (
            f'{self.detail} - operator: "{_short(self.operator_line)}" '
            f'vs source: "{_short(self.other_line)}"'
        )


def conflict_filter_enabled() -> bool:
    """Drop lines that contradict operator facts from the prompt (default on)."""
    return os.getenv("FACT_CONFLICT_FILTER", "true").lower() not in ("0", "false", "no")


def _short(line: str, limit: int = 90) -> str:
    line = " ".join((line or "").split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _name_tokens(name: str) -> frozenset[str]:
    return frozenset(t for t in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(t) >= 3)


def _same_name(a: str, b: str) -> bool:
    """Token-subset identity: 'Giannis' matches 'Giannis Antetokounmpo', and
    'Heat' matches 'Miami Heat' — but 'Justin Bieber' ≠ 'Justin Gaethje'."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


def _division_key(qualifier: str) -> str:
    words = set(re.findall(r"[a-z]+", (qualifier or "").lower()))
    hit = words & _DIVISION_WORDS
    return sorted(hit)[0] if hit else ""


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _trade_conflicts(operator_lines: list[str], source_lines: list[str]) -> list[FactConflict]:
    out: list[FactConflict] = []
    for op_line in operator_lines:
        for op_claim in extract_trade_claims(op_line):
            for src_line in source_lines:
                for src_claim in extract_trade_claims(src_line):
                    if not _same_name(op_claim.player, src_claim.player):
                        continue
                    if _same_name(op_claim.team, src_claim.team):
                        continue
                    out.append(
                        FactConflict(
                            kind="trade_direction",
                            operator_line=op_line,
                            other_line=src_line,
                            detail=(
                                f"Trade direction disagrees for {op_claim.player}: "
                                f"{op_claim.team} (operator) vs {src_claim.team} (source)"
                            ),
                        )
                    )
    return out


def _result_conflicts(operator_lines: list[str], source_lines: list[str]) -> list[FactConflict]:
    out: list[FactConflict] = []
    for op_line in operator_lines:
        for op_w, op_l in _RESULT_RE.findall(op_line):
            for src_line in source_lines:
                for src_w, src_l in _RESULT_RE.findall(src_line):
                    if _same_name(op_w, src_l) and _same_name(op_l, src_w):
                        out.append(
                            FactConflict(
                                kind="reversed_result",
                                operator_line=op_line,
                                other_line=src_line,
                                detail=(
                                    f"Result direction disagrees: operator has "
                                    f"{op_w} over {op_l}, source has the reverse"
                                ),
                            )
                        )
    return out


def _champion_conflicts(operator_lines: list[str], source_lines: list[str]) -> list[FactConflict]:
    out: list[FactConflict] = []
    for op_line in operator_lines:
        for op_name, op_qual in _CHAMPION_RE.findall(op_line):
            op_div = _division_key(op_qual)
            for src_line in source_lines:
                for src_name, src_qual in _CHAMPION_RE.findall(src_line):
                    if _same_name(op_name, src_name):
                        continue
                    src_div = _division_key(src_qual)
                    # Same division named on both sides, or both unqualified.
                    if op_div != src_div:
                        continue
                    division = op_div or "the"
                    out.append(
                        FactConflict(
                            kind="champion",
                            operator_line=op_line,
                            other_line=src_line,
                            detail=(
                                f"Different {division} champion claims: "
                                f"{op_name} (operator) vs {src_name} (source)"
                            ),
                        )
                    )
    return out


def find_fact_conflicts(
    operator_facts: list[str] | None,
    source_text: str,
) -> list[FactConflict]:
    """Conflicts between operator key facts and the signal/web fact corpus.

    Returns [] without operator facts — there is no ground truth to compare
    against (intra-signal disagreements are deliberately not adjudicated).
    """
    operator_lines = [f for f in (operator_facts or []) if (f or "").strip()]
    if not operator_lines:
        return []
    source_lines = _lines(source_text)
    if not source_lines:
        return []

    conflicts = (
        _trade_conflicts(operator_lines, source_lines)
        + _result_conflicts(operator_lines, source_lines)
        + _champion_conflicts(operator_lines, source_lines)
    )

    seen: set[tuple[str, str, str]] = set()
    deduped: list[FactConflict] = []
    for c in conflicts:
        key = (c.kind, c.operator_line.lower(), c.other_line.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped[:_MAX_CONFLICTS]


def drop_conflicting_lines(source_text: str, conflicts: list[FactConflict]) -> tuple[str, int]:
    """Remove the non-operator side of each conflict from the source corpus.

    Returns (filtered_text, dropped_count). Operator facts stay untouched —
    they are the ground truth the source lines lost to.
    """
    if not conflicts:
        return source_text, 0
    bad = {c.other_line.strip().lower() for c in conflicts}
    kept: list[str] = []
    dropped = 0
    for line in (source_text or "").splitlines():
        if line.strip().lower() in bad:
            dropped += 1
            continue
        kept.append(line)
    return "\n".join(kept), dropped


def display_fact_conflicts(
    conflicts_rendered: list[str],
    *,
    dropped: int = 0,
    print_fn=print,
) -> bool:
    """Show pre-script conflict flags. Returns True when review is needed."""
    if not conflicts_rendered:
        return False
    print_fn(f"\n  ! Fact conflicts ({len(conflicts_rendered)}) - operator facts win:")
    for c in conflicts_rendered[:6]:
        print_fn(f"    - {c}")
    if dropped:
        print_fn(
            f"    {dropped} conflicting source line(s) were kept out of the prompt "
            f"(FACT_CONFLICT_FILTER)."
        )
    else:
        print_fn("    Conflicting lines stayed in the prompt (FACT_CONFLICT_FILTER=false).")
    return True
