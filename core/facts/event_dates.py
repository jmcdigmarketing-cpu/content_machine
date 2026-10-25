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


# ---- #1151: a draft about a scheduled game -------------------------------------------------
#
# 2026-10-13: overnight wrote "Oklahoma City's young core flexes growth in statement win over
# Indiana Pacers" hours before the game, and rendered a Texans preview two days after kick-off.

_FIXTURE_RE = re.compile(
    r"^(?P<away>(?:[A-Z0-9][\w.'&-]*\s+){1,4})(?:at|vs\.?|@)\s+"
    r"(?P<home>[A-Z0-9][\w.'&-]*(?:\s+[A-Z0-9][\w.'&-]*){0,3})$"
)
_RESULT_RE = re.compile(
    # #1363: "defeat" and "prevail over" too - "NFL Week 7 picks: Seahawks defeat Chiefs; Rams
    # prevail over Raiders" read as no result.
    r"\b(?:beat|beats|defeat|defeated|defeats|won|win over|victory over|statement win|routed|"
    r"crushed|prevails? over|prevailed over|"
    r"dissected|dominated|blew out|blowout|swept|edged|upset|outlasted|topped|downed|lost to|"
    r"loss to|fell to|falls to)\b",
    re.I,
)
_HISTORY_RE = re.compile(
    r"\b(?:19|20)\d{2}\b|\blast (?:season|year|week|month|time|night)\b|\byears? ago\b|"
    r"\bstraight\b|\bin a row\b|\bsince\b|\bGame \d\b|\bFinals?\b|\bprevious(?:ly)?\b|"
    r"\bhistory\b|\ball-time\b|\bcareer\b",
    re.I,
)
_NOT_YET_RE = re.compile(
    r"\?|\b(?:will|would|could|can|might|may|if|whether|should|must|expect(?:s|ed)?|"
    r"needs? to|looks? to|looking to|hop(?:e|es|ing)|chance|predict(?:s|ion)?|pick|"
    r"to beat|to win)\b",
    re.I,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


PREVIEW_PREFIX = "This game has not been played yet"


def preview_brief(event_at: str, *, call: str = "") -> str:
    """The brief a scheduled game's draft is written to (#1169).

    Overnight on 2026-10-14 drafted three NFL games two to four days ahead and all three came
    back as recaps: "Seattle Seahawks miss tackles as Denver Broncos convert short-yardage
    plays". Nothing told the angles or the script the game was ahead.
    """
    day = str(event_at or "")[:10]
    try:
        when = datetime.date.fromisoformat(day).strftime("%b %d").replace(" 0", " ")
    except ValueError:
        when = "soon"
    brief = (
        f"{PREVIEW_PREFIX} - it is on {when}. Write a preview: the matchup, who is in form or "
        "hurt, what to watch and what is at stake. Never describe plays, a score or a result "
        "as if the game happened."
    )
    if call:  # #1301: a preview is a prediction
        brief += f" Make this call and argue it from the facts: {call}."
        # #1322 (wave 113, the operator: previews with a call): 2 of 64 new subscribers came from
        # the videos. The call is graded after the game (calls.score_calls, "Picks, graded"), so
        # that is a true reason to follow - said once, in the last line.
        brief += (
            " End on why to follow, in your own words: this call is graded after the game - "
            'for example "I grade this call after the game - follow to see if I was right."'
        )
    return brief


RESULT_PREFIX = "This game is over"


def finished_game(signals: dict | None, topic: str, *, brief: str = "") -> dict | None:
    """#1362 (decision 76): ESPN's final for the game the topic is about, or None - only when ESPN
    calls it final and the topic names both sides' nicknames; never under a preview's brief."""
    if PREVIEW_PREFIX in (brief or ""):
        return None
    live = (signals or {}).get("live_scores") or {}
    data = live.get("data") if isinstance(live, dict) else None
    game = data.get("matched_game") if isinstance(data, dict) else None
    if not isinstance(game, dict) or game.get("completed") is not True:
        return None
    lower = str(topic or "").lower()
    for side in (game.get("away_team"), game.get("home_team")):
        words = str(side or "").split()
        if not words or not re.search(rf"\b{re.escape(words[-1].lower())}\b", lower):
            return None
    return game


def result_brief(game: dict) -> str:
    """#1362 (decision 76, the operator: "What it means + next call"): the directive for a game
    that is over - the final once, then what it changes, then a call; never a play-by-play."""
    final = (
        f"{game.get('away_team')} {game.get('away_score')}, "
        f"{game.get('home_team')} {game.get('home_score')}"
    )
    winner = f" - {game['winner']} won" if game.get("winner") else ""
    return (
        f"{RESULT_PREFIX} - ESPN's final: {final}{winner}. Write what the result means, not a "
        "play-by-play: say the final in one sentence, then what it changes for each side - "
        "record, standing, next game - from the facts. End on a call about the next game, argued "
        "from the facts. Never retell plays, drives or quarters in order."
    )


def _game_day(game: dict) -> datetime.date | None:
    """The day a game was played, in US Eastern time - ESPN dates a Sunday night game Monday UTC."""
    raw = str((game or {}).get("date") or "").strip()
    if not raw:
        return None
    try:
        when = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    from zoneinfo import ZoneInfo

    return when.astimezone(ZoneInfo("America/New_York")).date()


def is_pregame_result(line: str, game: dict) -> bool:
    """#1363: a line that states a result between the game's two sides and is dated only before
    the game's day - a pick, not the result. Run 185's facts held "NFL Week 7 picks: Seahawks
    defeat Chiefs ... (22 Oct 2026)". A line with no date is not judged."""
    day = _game_day(game)
    text = str(line or "")
    if day is None or not _RESULT_RE.search(text):
        return False
    away = _side_words(str(game.get("away_team") or ""))
    home = _side_words(str(game.get("home_team") or ""))
    words = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", text)}
    if not (words & away and words & home):
        return False
    dates = _preview_dates(text, None, day)
    return bool(dates) and all(d < day for d in dates)


def drop_pregame_results(text: str, game: dict) -> tuple[str, list[str]]:
    """#1363: `text` without its pre-game result lines (`is_pregame_result`), and those lines."""
    kept: list[str] = []
    dropped: list[str] = []
    for line in str(text or "").splitlines():
        if line.strip() and is_pregame_result(line, game):
            dropped.append(line.strip())
        else:
            kept.append(line)
    return "\n".join(kept), dropped


def fixture_sides(topic: str) -> tuple[str, str] | None:
    """("Indiana Pacers", "Oklahoma City Thunder") for a topic named the way a schedule names
    a game - "A at B", every word of both sides capitalised - else None."""
    found = _FIXTURE_RE.match(str(topic or "").strip())
    if not found:
        return None
    return found.group("away").strip(), found.group("home").strip()


# #1577: run 193, a Bengals-Ravens preview, was drafted at 11:29 AM CDT for a 1 PM EDT kickoff.
PREVIEW_MIN_LEAD_HOURS = 3.0


def starts_within(
    event_at: str, hours: float, *, now: datetime.datetime | str | None = None
) -> bool:
    """#1577: True when the game starts in under `hours` and has not started - too close to draft,
    render and decide. False for a start that cannot be read."""
    raw = str(event_at or "").strip()
    try:
        when = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    if isinstance(now, str):
        try:
            moment = datetime.datetime.fromisoformat(now.replace("Z", "+00:00"))
        except ValueError:
            return False
    else:
        moment = now or datetime.datetime.now(datetime.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return moment < when <= moment + datetime.timedelta(hours=hours)


def game_started(event_at: str, *, now: datetime.datetime | None = None) -> bool | None:
    """True once the game has started, False before, None when `event_at` cannot be read.
    A board day with no hour counts as started once that day is over."""
    raw = str(event_at or "").strip()
    if not raw:
        return None
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        if len(raw) <= 10:
            return moment.date() > datetime.date.fromisoformat(raw)
        when = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment >= when


def _side_words(side: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[A-Za-z0-9]+", side) if len(word) >= 4}


def unplayed_result(text: str, topic: str, *, sides: tuple[str, str] | None = None) -> str:
    """The sentence of `text` that states a result between the two sides `topic` names, or "".

    For a game that has not been played. A sentence counts when it names both sides and uses
    a result word ("win over", "dissected") with nothing marking it as history ("last
    season", a year, "three straight") or as still to come ("will", "if", a question).
    """
    sides = sides or fixture_sides(topic)
    if not sides:
        return ""
    away, home = _side_words(sides[0]), _side_words(sides[1])
    for sentence in _SENTENCE_RE.split(str(text or "")):
        line = sentence.strip()
        if not line or not _RESULT_RE.search(line):
            continue
        if _HISTORY_RE.search(line) or _NOT_YET_RE.search(line):
            continue
        words = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", line)}
        if words & away and words & home:
            return line
    return ""


def stale_angle_reason(
    angle: str, *, today: datetime.date | str | None = None, facts: str = "", topic: str = ""
) -> str:
    """Why an angle is out of date, or "" when nothing is wrong with its dates."""
    day = _as_day(today)
    return past_year_prediction(angle, day) or past_numbered_event(
        angle, day, facts=facts, topic=topic
    )
