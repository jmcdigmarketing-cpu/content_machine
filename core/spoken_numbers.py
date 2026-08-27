"""Spoken-number / SSML-ish expansions for TTS only.

Captions and ``clean_script_for_tts`` keep on-screen digits. Unmatched text is
returned unchanged (fail-open).
"""

from __future__ import annotations

import re

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = (
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
)

_MONEY_K_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*k\b", re.I)
_UFC_RE = re.compile(r"\bUFC\s+(\d{2,4})\b", re.I)
# Fighter records only, behind the same verb cue `core/fact_grounding._RECORD` uses.
# Without it this matched every range and percentage in the language: "5-10 years"
# became "five ten years", "10-15%" became "ten fifteen%", "9-5" became "nine five" —
# on every channel, and worst on MoneyWise. A hyphenated pair is a record only when
# something says so.
_RECORD_RE = re.compile(
    r"\b((?:is|now|went|sits|stands|moves(?:\s+to)?|record(?:ed)?(?:\s+of)?)\s+)"
    r"(\d{1,2})-(\d{1,2})(?:-(\d{1,2}))?\b",
    re.IGNORECASE,
)
# Highest event number the speller can voice: _event_number indexes _ONES with n // 100.
_MAX_EVENT_NUMBER = len(_ONES) * 100 - 1


def _under_hundred(n: int) -> str:
    n = max(0, int(n))
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return _TENS[tens]
    return f"{_TENS[tens]}-{_ONES[ones]}"


def _event_number(n: int) -> str:
    n = max(0, int(n))
    if n < 100:
        return _under_hundred(n)
    hundreds, rest = divmod(n, 100)
    if rest == 0:
        return f"{_ONES[hundreds]} hundred"
    return f"{_ONES[hundreds]} {_under_hundred(rest)}"


def _money_k(match: re.Match[str]) -> str:
    try:
        amount = float(match.group(1))
    except ValueError:
        return match.group(0)
    whole = int(amount)
    if whole != amount or whole < 0 or whole > 99:
        return match.group(0)
    return f"{_under_hundred(whole)} thousand dollars"


def _ufc(match: re.Match[str]) -> str:
    try:
        num = int(match.group(1))
    except ValueError:
        return match.group(0)
    if num > _MAX_EVENT_NUMBER:
        # Out of the speller's range. Leave the digits alone rather than raising:
        # the call site swallows the whole pass, so one bad match used to silence
        # every other expansion in the script (and only at logger.debug).
        return match.group(0)
    return f"UFC {_event_number(num)}"


def _record(match: re.Match[str]) -> str:
    cue = match.group(1)
    try:
        parts = [int(g) for g in match.groups()[1:] if g is not None]
    except ValueError:
        return match.group(0)
    return cue + " ".join(_under_hundred(n) for n in parts)


def expand_spoken_numbers(text: str) -> str:
    """Rewrite fight records, UFC event numbers, and $Nk purses for TTS."""
    if not text:
        return text
    out = _MONEY_K_RE.sub(_money_k, text)
    out = _UFC_RE.sub(_ufc, out)
    out = _RECORD_RE.sub(_record, out)
    return out
