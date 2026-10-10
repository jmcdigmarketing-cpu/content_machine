"""Date checks for text written before any facts - the angles (#1008).

Angles are generated in parallel with the signal fetch, so they are written from the model's
memory with no date in the prompt. Runs 119 and 120 offered "obsolete by 2025" in October 2026
and "faces real threat at UFC 305" two years after UFC 305. Neither check that existed caught
them: `date_math` only knows elapsed-time phrases, and `recency.stale_preview` needs a month
and a day. Two narrow detectors:

- a year that has passed, used as a prediction ("by 2025", "2025 predictions", "will ... in
  2025");
- a numbered event that has happened. A fact line naming the event with a date decides when
  one exists; otherwise numbered UFC events run about 13 a year from UFC 300 (13 April 2024),
  and only an event estimated a year or more back is flagged, so a borderline estimate never
  costs an angle. An event the topic itself names is the operator asking about it.

Pure and stdlib-only; ``today`` is injectable (the #725 clock-shift harness patches
``_today``).
"""

from __future__ import annotations

import datetime
import re

from core.facts.recency import _preview_dates

_YEAR = r"((?:19|20)\d{2})"
_FORWARD_YEAR = re.compile(
    rf"\b(?:by|before|until|come|through)\s+(?:the\s+end\s+of\s+)?{_YEAR}\b"
    rf"|\b{_YEAR}\s+(?:predictions?|forecasts?|outlook|projections?|preview)\b"
    rf"|\b(?:predictions?|forecasts?|outlook|projections?|preview)\s+(?:for|in)\s+{_YEAR}\b",
    re.I,
)
_IN_YEAR = re.compile(rf"\bin\s+{_YEAR}\b", re.I)
_FORWARD_CUE = re.compile(
    r"\b(?:will|won't|would|could|might|going to|gonna|set to|about to|predict\w*|"
    r"expect\w*|forecast\w*|next)\b",
    re.I,
)
_UFC_EVENT = re.compile(r"\bUFC\s*(\d{3})\b", re.I)
_UFC_ANCHOR = (300, datetime.date(2024, 4, 13))
_UFC_PER_YEAR = 13.0
_ESTIMATE_MARGIN_DAYS = 365
# #1082: WrestleMania 40 was 2024-04-07; Super Bowl LVIII (58) was 2024-02-11.
_WRESTLEMANIA = re.compile(r"\bWrestleMania\s+(\d{1,3})\b", re.I)
_SUPER_BOWL_ARABIC = re.compile(r"\bSuper Bowl\s+(\d{1,3})\b", re.I)
_SUPER_BOWL_ROMAN = re.compile(r"\bSuper Bowl\s+([IVXLCDM]+)\b")
_MADDEN = re.compile(r"\bMadden\s+(\d{2})\b", re.I)
_WM_ANCHOR = (40, datetime.date(2024, 4, 7))
_SB_ANCHOR = (58, datetime.date(2024, 2, 11))
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _today() -> datetime.date:
    return datetime.date.today()


def run_date() -> datetime.date:
    """Today, through the same patch point the checks use."""
    return _today()


def _as_day(today: datetime.date | str | None) -> datetime.date:
    """``today`` as a date - an ISO string is accepted so a corpus case can pin one."""
    if isinstance(today, str) and today.strip():
        return datetime.date.fromisoformat(today.strip()[:10])
    if isinstance(today, datetime.date):
        return today
    return _today()


def past_year_prediction(text: str, today: datetime.date | str | None = None) -> str:
    """A note when ``text`` predicts a year that has already passed, else ""."""
    day = _as_day(today)
    body = text or ""
    for match in _FORWARD_YEAR.finditer(body):
        year = int(next(g for g in match.groups() if g))
        if year < day.year:
            return f"'{match.group(0)}' is a year that has passed"
    if _FORWARD_CUE.search(body):
        for match in _IN_YEAR.finditer(body):
            if int(match.group(1)) < day.year:
                return f"'{match.group(0)}' is a year that has passed"
    return ""


def _ufc_estimate(number: int) -> datetime.date:
    anchor_number, anchor_day = _UFC_ANCHOR
    days = (number - anchor_number) * 365.25 / _UFC_PER_YEAR
    return anchor_day + datetime.timedelta(days=round(days))


def past_numbered_event(
    text: str, today: datetime.date | str | None = None, *, facts: str = "", topic: str = ""
) -> str:
    """A note when ``text`` names a numbered event that has already happened, else ""."""
    day = _as_day(today)
    named_in_topic = {m.group(1) for m in _UFC_EVENT.finditer(topic or "")}
    fact_lines = [line for line in (facts or "").splitlines() if line.strip()]
    for match in _UFC_EVENT.finditer(text or ""):
        number = match.group(1)
        if number in named_in_topic:
            continue
        label = f"UFC {number}"
        pattern = re.compile(rf"\bUFC\s*{number}\b", re.I)
        dated = [
            when
            for line in fact_lines
            if pattern.search(line)
            for when in _preview_dates(line, None, day)
        ]
        if dated:
            latest = max(dated)
            if latest < day:
                return f"{label} took place on {latest.isoformat()} (the facts date it)"
            continue
        estimate = _ufc_estimate(int(number))
        if (day - estimate).days >= _ESTIMATE_MARGIN_DAYS:
            return f"{label} was around {estimate.year} (numbered UFC events run ~13 a year)"
    other = _other_numbered_event(text or "", fact_lines, day)
    if other:
        return other
    return ""


def _roman(text: str) -> int | None:
    vals: list[int] = []
    for ch in (text or "").upper():
        val = _ROMAN_VALUES.get(ch)
        if val is None:
            return None
        vals.append(val)
    if not vals:
        return None
    total = 0
    for index, val in enumerate(vals):
        if index + 1 < len(vals) and vals[index + 1] > val:
            total -= val
        else:
            total += val
    return total or None


def _fact_status(
    pattern: re.Pattern[str], fact_lines: list[str], day: datetime.date
) -> tuple[str, datetime.date | None]:
    """('past', date) when a fact dates the event before today, ('future', date) when
    the fact is still ahead, ('none', None) when no fact names a date."""
    dated = [
        when
        for line in fact_lines
        if pattern.search(line)
        for when in _preview_dates(line, None, day)
    ]
    if not dated:
        return "none", None
    latest = max(dated)
    if latest < day:
        return "past", latest
    return "future", latest


def _estimate_note(label: str, when: datetime.date, day: datetime.date, why: str) -> str:
    if (day - when).days >= _ESTIMATE_MARGIN_DAYS:
        return f"{label} was around {when.year} ({why})"
    return ""


def _other_numbered_event(text: str, fact_lines: list[str], day: datetime.date) -> str:
    """WrestleMania, Super Bowl, and a year-named game edition. A dated fact wins."""
    wm = _WRESTLEMANIA.search(text)
    if wm:
        number = int(wm.group(1))
        label = f"WrestleMania {number}"
        status, when = _fact_status(_WRESTLEMANIA, fact_lines, day)
        if status == "past" and when is not None:
            return f"{label} took place on {when.isoformat()} (the facts date it)"
        if status == "future":
            return ""
        anchor_n, anchor_day = _WM_ANCHOR
        estimate = anchor_day.replace(year=anchor_day.year + (number - anchor_n))
        return _estimate_note(label, estimate, day, "WrestleMania is once a year")
    bowl = _SUPER_BOWL_ROMAN.search(text) or _SUPER_BOWL_ARABIC.search(text)
    if bowl:
        raw = bowl.group(1)
        number = int(raw) if raw.isdigit() else _roman(raw)
        if number:
            label = f"Super Bowl {raw}"
            status, when = _fact_status(
                _SUPER_BOWL_ROMAN if not raw.isdigit() else _SUPER_BOWL_ARABIC,
                fact_lines,
                day,
            )
            if status == "past" and when is not None:
                return f"{label} took place on {when.isoformat()} (the facts date it)"
            if status != "future":
                anchor_n, anchor_day = _SB_ANCHOR
                estimate = anchor_day.replace(year=anchor_day.year + (number - anchor_n))
                return _estimate_note(label, estimate, day, "the Super Bowl is once a year")
    madden = _MADDEN.search(text)
    if madden:
        edition = int(madden.group(1))
        label = f"Madden {edition}"
        status, when = _fact_status(_MADDEN, fact_lines, day)
        if status == "past" and when is not None:
            return f"{label} took place on {when.isoformat()} (the facts date it)"
        if status == "future":
            return ""
        edition_year = 2000 + edition
        if edition_year < day.year:
            return f"{label} is the {edition_year} edition, and that year has passed"
    return ""


def stale_angle_reason(
    angle: str, *, today: datetime.date | str | None = None, facts: str = "", topic: str = ""
) -> str:
    """Why an angle is out of date, or "" when nothing is wrong with its dates."""
    day = _as_day(today)
    return past_year_prediction(angle, day) or past_numbered_event(
        angle, day, facts=facts, topic=topic
    )
