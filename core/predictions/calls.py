"""#1301: a preview is a prediction - the call and the why.

The operator, 2026-10-18: "predictions are still lazy". A preview on the idea menu was the
matchup, the kickoff and the records ("Cowboys 3-3 at Packers 4-1"); the script was left to find
a take of its own, and the take check held drafts that had none. Asked "a call + the why", one
cheap model call per preview reads the matchup, the board's line and this week's headlines that
name either side, and returns who wins and one reason.

The reason may only use what it was given: a number in it that no supplied line carries drops
the reason (the call stays). Fail-open - no model, no call, the preview reads as it did.
`PREVIEW_CALLS=false` turns it off; the suite pins it off.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.logging import get_logger

logger = get_logger("core.predictions.calls")

# Live 2026-10-18 the first wording gave "Experts backing Giants" (a reason that is not one)
# and "49ers are 5-0 at home" (a season record, said as a home one).
_SYSTEM = (
    "You make one prediction for a short sports video. Use only the lines you are given - no "
    "stat, injury or result that is not in them. A record is the season record; say home or "
    "road only if a line does. The why is a reason in the game itself - form, a matchup, an "
    "injury, a record - never that experts, analysts or bettors pick a side. Reply as JSON: "
    '{"call": "<who wins, at most 8 words>", "why": "<one reason, at most 18 words, from the '
    'lines>"}. With no such reason in the lines, give the call and an empty why.'
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_MAX_HEADLINES = 6


def enabled() -> bool:
    return os.getenv("PREVIEW_CALLS", "true").strip().lower() not in ("0", "false", "no", "off")


def _named(topic: str, headlines: list[str]) -> list[str]:
    """This week's headlines that name a side of `topic`."""
    from apis.topic_tokens import names_any, subject_markers, subject_terms

    markers = subject_markers(subject_terms(topic, limit=6))
    if not markers:
        return []
    return [h for h in headlines if h and names_any(h, markers)][:_MAX_HEADLINES]


def _prompt(bet: Any, detail: dict[str, Any], headlines: list[str]) -> str:
    lines = [f"Event: {bet.topic}", f"When and records: {bet.rationale}"]
    if detail.get("line"):
        total = f" (total {detail['total']})" if detail.get("total") else ""
        lines.append(f"Betting line: {detail['line']}{total}")
    if headlines:
        lines.append("Headlines this week:")
        lines.extend(f"- {h}" for h in headlines)
    return "\n".join(lines)


def _grounded(why: str, prompt: str) -> str:
    """The reason, or "" when it carries a number no supplied line does."""
    supplied = set(_NUMBER.findall(prompt))
    return "" if any(n not in supplied for n in _NUMBER.findall(why)) else why


def _one(bet: Any, headlines: list[str]) -> dict[str, str] | None:
    from core.llm_router import complete_json
    from core.seasonal_calendar import game_details

    try:
        detail = dict(game_details(bet.topic) or {})
    except Exception:
        detail = {}
    prompt = _prompt(bet, detail, _named(bet.topic, headlines))
    try:
        payload = complete_json(prompt, tier="cheap", system=_SYSTEM, temperature=0.4,
                                max_tokens=200, stage="preview_call")  # fmt: skip
    except Exception as exc:
        logger.debug("preview call for %r failed: %s", bet.topic, exc)
        return None
    call = str((payload or {}).get("call") or "").strip().rstrip(".")
    if not call:
        return None
    why = _grounded(str((payload or {}).get("why") or "").strip().rstrip("."), prompt)
    return {"call": call, "why": why, "line": str(detail.get("line") or "")}


def preview_calls(previews: list[Any], *, headlines: list[str]) -> dict[str, dict[str, str]]:
    """{topic: {call, why, line}} for each preview the model made a call on - side by side."""
    if not previews or not enabled():
        return {}
    with ThreadPoolExecutor(max_workers=min(5, len(previews))) as pool:
        made = list(pool.map(lambda bet: _one(bet, headlines), previews))
    return {bet.topic: call for bet, call in zip(previews, made, strict=True) if call}


def call_text(call: dict[str, str]) -> str:
    """ "Packers win - Dallas allows the most deep completions" (the brief's call)."""
    text = str(call.get("call") or "")
    return f"{text} - {call['why']}" if call.get("why") else text


def call_line(call: dict[str, str]) -> str:
    """The menu's line: "Call: Packers win - Dallas allows ... (GB -3.5)"."""
    line = f" ({call['line']})" if call.get("line") else ""
    return f"Call: {call_text(call)}{line}"


def headlines_for(previews: list[Any]) -> list[str]:
    """This week's headlines from the feeds of each preview's league - fetched side by side."""
    from config.data_sources import domain_rss_feeds

    domains = sorted({str(getattr(bet, "domain", "") or "") for bet in previews} - {""})
    feeds: list[dict] = []
    for domain in domains:
        feeds.extend(domain_rss_feeds(domain))
    if not feeds:
        return []
    from core.best_bet import _fetch_feeds

    return [str(row.get("title") or "") for rows in _fetch_feeds(feeds) for row in rows[:25]]
