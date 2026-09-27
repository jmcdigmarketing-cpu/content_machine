"""Recency guard: does any fact name what the topic names? (#895)

`docs/assessment.md` weakness 1: a topic about a just-happened event (UFC "Freedom
250") produced "Topuria, the featherweight champion" and invented opponents. The event
was past the script model's training and the signals returned nothing about it, so the
model filled the gap from memory. The thin-facts stop did not fire: it counts fact
lines, and three generic UFC headlines are three lines.

The name checked is the one every signal already searched for,
`apis.topic_tokens.search_query(topic, mode="entity")` - "UFC Freedom 250", "GTA 6",
"Silksong". It is covered when one verified fact line (or a key fact the operator
pasted) holds every number in it and most of its words. YouTube titles do not count:
a title that names the event says nothing about what happened at it.

When it is not covered, the script prompt is told so, and the run stops before TTS
unless the operator says render anyway (`EVENT_COVERAGE_GATE=false` turns the stop
off; the prompt note stays, because it only ever tells the model not to guess).
"""

from __future__ import annotations

import math
import re
from typing import Any

from apis.topic_tokens import content_tokens, search_query

_ROMAN = {
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
    "xi": "11",
    "xii": "12",
    "xiii": "13",
    "xiv": "14",
    "xv": "15",
    "xvi": "16",
    "xvii": "17",
    "xviii": "18",
    "xix": "19",
    "xx": "20",
}
_WORDS = re.compile(r"[a-z0-9]+")


def event_name(topic: str) -> str:
    """The name the topic is about - the same one each signal searched for."""
    return search_query(topic or "", mode="entity").strip() if (topic or "").strip() else ""


def _name_tokens(name: str) -> list[str]:
    return [_ROMAN.get(tok, tok) for tok in content_tokens(name)]


def _line_tokens(line: str) -> set[str]:
    """A line's words, roman numerals as digits, plus the initials of short word runs
    ("Grand Theft Auto" also reads as "gta")."""
    words = _WORDS.findall((line or "").lower().replace("'", ""))
    tokens = {_ROMAN.get(w, w) for w in content_tokens(line)}
    for size in (2, 3, 4):
        for i in range(len(words) - size + 1):
            run = words[i : i + size]
            if all(w[0].isalpha() for w in run):
                tokens.add("".join(w[0] for w in run))
    return tokens


def covered(name: str, lines: list[str]) -> bool:
    """True when one line holds every number in `name` and most of its words."""
    wanted = _name_tokens(name)
    if not wanted:
        return True
    numbers = {t for t in wanted if t.isdigit()}
    need = len(wanted) if len(wanted) <= 2 else math.ceil(len(wanted) * 2 / 3)
    for line in lines:
        have = _line_tokens(line)
        if numbers <= have and sum(1 for t in wanted if t in have) >= need:
            return True
    return False


def coverage(topic: str, verified_facts: str, key_facts: list[str] | None) -> dict[str, Any] | None:
    """`{"name", "covered", "lines"}` for the topic's name, or None when it has none."""
    name = event_name(topic)
    if not name:
        return None
    lines = [ln for ln in (verified_facts or "").splitlines() if ln.strip()]
    lines += [str(f) for f in key_facts or [] if str(f).strip()]
    return {"name": name, "covered": covered(name, lines), "lines": len(lines)}


def gate_enabled() -> bool:
    from core.providers import flag_enabled

    return flag_enabled("EVENT_COVERAGE_GATE", default=True)


def abort_reason(features: dict[str, Any] | None) -> str | None:
    """Why TTS should wait for facts, or None. Reads `features["event_coverage"]`."""
    found = (features or {}).get("event_coverage")
    if not isinstance(found, dict) or found.get("covered", True) or not gate_enabled():
        return None
    name = str(found.get("name") or "").strip()
    if not name:
        return None
    return (
        f"facts never mention '{name}' - the script model's knowledge ends before recent "
        "events, so it would be guessing (paste facts, or EVENT_COVERAGE_GATE=false)"
    )


def prompt_block(name: str) -> str:
    """The script-prompt note when the name is not covered; "" when it is."""
    if not name:
        return ""
    return (
        f"\n⚠ EVENT NOT IN FACTS: none of the facts above mention '{name}'. Your "
        "training data predates it, so anything you remember about it may be wrong. Do "
        "NOT state its result, date, card, lineup or who holds a title. Say plainly that "
        "the details are not confirmed in the sources yet, and build the script only on "
        "what the facts above do say."
    )
