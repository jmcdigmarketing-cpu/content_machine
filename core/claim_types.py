"""Claim types with their own grounding bar (#345).

One rule for every unsupported claim meant a hedged rumor ("reportedly getting a second
trailer") stopped a render exactly like run 77's "GTA 5 didn't win Game of the Year in
2013". Operator call 2026-09-16:

- result / award / stat / date / schedule / other: an unsupported claim always blocks.
- rumor: blocks unless the script hedges it (reportedly, rumored, according to, ...),
  in which case it only warns.
- opinion: never blocks - unless it carries a number, which makes it a factual claim the
  verifier mislabelled.

A claim with no type (rows written before #345, or a model that ignored the field) is held
to the strict bar, so nothing that blocked before this change passes now by omission.
"""

from __future__ import annotations

import re
from typing import Any

CLAIM_TYPES = ("result", "award", "stat", "date", "schedule", "rumor", "opinion", "other")

_HEDGE_RE = re.compile(
    r"\b(reportedly|rumou?red|rumou?rs?|allegedly|according to|leak(?:s|ed)?|unconfirmed|"
    r"could|might|may|expected to|reports? (?:claim|say|said|suggest)s?|supposedly)\b",
    re.IGNORECASE,
)
_DIGIT_RE = re.compile(r"\d")


def normalize_type(raw: object) -> str:
    """A known claim type, or "" (treated as strict)."""
    text = str(raw or "").strip().lower()
    return text if text in CLAIM_TYPES else ""


def is_hedged(claim: str) -> bool:
    return bool(_HEDGE_RE.search(claim or ""))


def hedge_density(script: str) -> float:
    """Hedge phrases per 100 spoken words on the finished script.

    #800 / decisions.md §25: "12/12 backed" can be bought by restating every
    unsupported claim as attributed speculation. This is the number the grade
    reads. Zero on an empty script, never a warning.
    """
    from core.script_length import count_spoken_words

    text = script or ""
    words = count_spoken_words(text)
    if words <= 0:
        return 0.0
    return round(100.0 * len(_HEDGE_RE.findall(text)) / words, 2)


def claim_blocks(claim: str, claim_type: str) -> bool:
    kind = normalize_type(claim_type)
    if kind == "opinion":
        return bool(_DIGIT_RE.search(claim or ""))
    if kind == "rumor":
        return not is_hedged(claim)
    return True


def typed_unsupported(verification_dict: dict[str, Any] | None) -> list[tuple[str, str]]:
    """(claim, type) for each unsupported claim, type "" when unknown."""
    data = verification_dict or {}
    claims = [str(c).strip() for c in (data.get("unsupported") or []) if str(c).strip()]
    types = data.get("unsupported_types")
    if isinstance(types, list) and len(types) == len(claims):
        return [(c, normalize_type(t)) for c, t in zip(claims, types, strict=True)]
    by_claim: dict[str, str] = {}
    for row in data.get("claims") or []:
        if isinstance(row, dict) and not row.get("supported"):
            by_claim.setdefault(
                str(row.get("claim") or "").strip(), normalize_type(row.get("type"))
            )
    return [(c, by_claim.get(c, "")) for c in claims]


def blocking_typed(verification_dict: dict[str, Any] | None) -> list[tuple[str, str]]:
    return [(c, t) for c, t in typed_unsupported(verification_dict) if claim_blocks(c, t)]


def blocking_unsupported(verification_dict: dict[str, Any] | None) -> list[str]:
    """Unsupported claims that clear no bar - these stop a render."""
    return [c for c, _t in blocking_typed(verification_dict)]


def warn_only_unsupported(verification_dict: dict[str, Any] | None) -> list[str]:
    """Unsupported claims shown to the operator but allowed through (hedged rumor, opinion)."""
    return [c for c, t in typed_unsupported(verification_dict) if not claim_blocks(c, t)]
