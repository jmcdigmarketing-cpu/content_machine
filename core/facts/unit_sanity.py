"""Number-unit sanity: "80 hours" must not ride an "80 minutes" fact (#552).

Grounding already checks that a script's numbers appear in the facts. That lets
"80 hours" pass when the source said "80 minutes" because the numeral matches.
`find_unit_mismatches` compares converted magnitudes for the same subject and
flags a unit swap while accepting equivalent conversions.
"""

from __future__ import annotations

import re
from typing import TypedDict

from apis.topic_tokens import content_tokens


class _Quantity(TypedDict):
    value: float
    unit: str
    display: str
    family: str
    factor: float
    subject: set[str]


_UNIT_TO_FAMILY = {
    "hour": ("time", 3600.0),
    "hours": ("time", 3600.0),
    "hr": ("time", 3600.0),
    "hrs": ("time", 3600.0),
    "minute": ("time", 60.0),
    "minutes": ("time", 60.0),
    "min": ("time", 60.0),
    "mins": ("time", 60.0),
    "second": ("time", 1.0),
    "seconds": ("time", 1.0),
    "sec": ("time", 1.0),
    "secs": ("time", 1.0),
    "kilogram": ("mass", 1000.0),
    "kilograms": ("mass", 1000.0),
    "kg": ("mass", 1000.0),
    "pound": ("mass", 453.592),
    "pounds": ("mass", 453.592),
    "lb": ("mass", 453.592),
    "lbs": ("mass", 453.592),
    "kilometer": ("length", 1000.0),
    "kilometers": ("length", 1000.0),
    "km": ("length", 1000.0),
    "mile": ("length", 1609.344),
    "miles": ("length", 1609.344),
    "mi": ("length", 1609.344),
}
_UNIT_ALT = "|".join(sorted((_UNIT_TO_FAMILY), key=len, reverse=True))
_QUANTITY = re.compile(rf"\b(\d+(?:\.\d+)?)\s+({_UNIT_ALT})\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_SKIP = {"hour", "hours", "hr", "hrs", "minute", "minutes", "min", "mins", "second",
         "seconds", "sec", "secs", "kilogram", "kilograms", "kg", "pound", "pounds",
         "lb", "lbs", "kilometer", "kilometers", "km", "mile", "miles", "mi"}  # fmt: skip


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(text or "") if part.strip()]


def _subject(sentence: str) -> set[str]:
    return {
        tok for tok in content_tokens(sentence, min_len=3) if tok not in _SKIP and not tok.isdigit()
    }


def _quantities(text: str) -> list[_Quantity]:
    rows: list[_Quantity] = []
    for sentence in _sentences(text):
        for match in _QUANTITY.finditer(sentence):
            unit = match.group(2).lower()
            family, factor = _UNIT_TO_FAMILY[unit]
            rows.append(
                {
                    "value": float(match.group(1)),
                    "unit": unit,
                    "display": match.group(0),
                    "family": family,
                    "factor": factor,
                    "subject": _subject(sentence),
                }
            )
    return rows


def _equivalent(left: _Quantity, right: _Quantity) -> bool:
    if left["family"] != right["family"]:
        return False
    base_left = float(left["value"]) * float(left["factor"])
    base_right = float(right["value"]) * float(right["factor"])
    scale = max(abs(base_left), abs(base_right), 1.0)
    slack = 30.0 if left["family"] == "time" else 0.05 * scale
    return abs(base_left - base_right) <= max(0.05 * scale, slack)


def find_unit_mismatches(script: str, facts: str) -> list[str]:
    """Phrases in ``script`` whose unit disagrees with a same-subject fact."""
    fact_rows = _quantities(facts)
    flagged: list[str] = []
    for row in _quantities(script):
        related = [
            fact
            for fact in fact_rows
            if fact["family"] == row["family"] and (row["subject"] & fact["subject"])
        ]
        if not related:
            continue
        if any(_equivalent(row, fact) for fact in related):
            continue
        same_number = [
            fact
            for fact in related
            if abs(float(fact["value"]) - float(row["value"])) < 1e-9
            and str(fact["unit"]) != str(row["unit"])
        ]
        if same_number:
            flagged.append(f"{row['display']} does not match the facts")
    return flagged
