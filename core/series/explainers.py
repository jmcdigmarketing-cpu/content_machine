"""#1680 (B04.9, wave 159): "In 60 seconds" explainers for coming events.

A numbered UFC card (ESPN's calendar, the one `recap.debate_ideas` reads) or an award
(`seasonal_calendar.AWARD_DATES`) two to five days away becomes "<event> in 60 seconds: what to
know" - who, when, what is at stake - drafted once, at about 60 seconds (`batch_generation.
EXPLAINER_WORDS`), in the explainer intent, from the card's main-event lines and three days of
headlines. A launch is left out: GTA 6's countdown and dated rows already explain it daily. One a
night; `EXPLAINERS=false` stops it (the suite does). Its topic names the event, so it keeps its own
shape and is never drafted as a preview (`batch_generation.keeps_own_shape`).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.explainers")

EXPLAIN_HOURS = (48.0, 120.0)  # two to five days before the event


def enabled() -> bool:
    return os.getenv("EXPLAINERS", "true").strip().lower() not in ("0", "false", "no", "off")


def explainer_topic(event: str) -> str:
    return f"{event} in 60 seconds: what to know"


def coming_events(
    *, now: datetime, board: dict[str, Any] | None = None
) -> list[tuple[str, datetime, str, list[str]]]:
    """(event, start, domain, names) for each numbered card and award `EXPLAIN_HOURS` away."""
    from core.seasonal_calendar import AWARD_DATES
    from core.series.recap import _calendar, _ufc_board, card_names, coming_card

    low, high = EXPLAIN_HOURS
    out: list[tuple[str, datetime, str, list[str]]] = []
    try:
        card = coming_card(_calendar(board if board is not None else _ufc_board()), now=now,
                           low_hours=low, high_hours=high)  # fmt: skip
    except Exception as exc:
        logger.debug("UFC calendar unread: %s", exc)
        card = None
    if card is not None:
        names = card_names(card[0])
        if names:
            out.append((names[0], card[1], "ufc", names))
    for day, title, domain in AWARD_DATES:
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        if now + timedelta(hours=low) <= start <= now + timedelta(hours=high):
            out.append((title, start, domain, [title]))
    return out


def explainer_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    board: dict[str, Any] | None = None,
    fetch: Callable[..., dict[str, Any]] | None = None,
    headlines: Callable[[str, dict[str, Any], datetime], list[dict[str, Any]]] | None = None,
    drafted: Callable[[str, str], bool] | None = None,
) -> list[Any]:
    """Tonight's explainer, or []. Never raises."""
    if not enabled():
        return []
    try:
        from core.batch_generation import series_drafted
        from core.best_bet import BestBetResult
        from core.series.countdown import feed_headlines, headline_facts
        from core.series.recap import _EASTERN, card_names, main_event_lines

        moment = now or datetime.now(timezone.utc)
        seen = drafted or series_drafted
        for event, start, domain, names in coming_events(now=moment, board=board):
            topic = explainer_topic(event)
            if seen(channel_id, topic):
                continue
            local = start.astimezone(_EASTERN)
            facts = [f"{event} is on {local:%A}, {local:%B} {local.day}, {local:%Y}."]
            if domain == "ufc" and len(names) == 3:
                label = f"{names[0]}: {names[1]} vs. {names[2]}"
                facts[0] = (f"{event} is on {local:%A}, {local:%B} {local.day}, {local:%Y}; "
                            f"{names[1]} vs. {names[2]} is its main event (ESPN's calendar).")  # fmt: skip
                facts += main_event_lines(label, start, fetch=fetch)
                subjects = card_names(label)[1:] or names
            else:
                subjects = names
            lines = (headlines or feed_headlines)(channel_id, {"domain": domain}, moment)
            facts += headline_facts(subjects, lines, now=moment, hours=72, limit=5)
            return [BestBetResult(
                topic=topic, domain=domain, avg_engaged_rate=0.0, source="explainer",
                supporting_runs=0, facts=facts, deadline=start.isoformat(),
                rationale=f"explainer · {event} in {int((start - moment).total_seconds() // 3600)} "
                          "hours - who, when and what is at stake, in 60 s",
            )]  # fmt: skip
        return []
    except Exception as exc:
        logger.debug("explainer ideas skipped: %s", exc)
        return []
