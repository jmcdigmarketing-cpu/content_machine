"""The fast lanes (wave 151): a story drafted, rendered and public in about an hour, unattended.

- #1647 (B03.1) breaking news: a story on `NEWS_OUTLETS`+ outlets whose first outlet published
  within `NEWS_HOURS`, naming a marquee name (`config/marquee.json`), not drafted yet.
- #1649 (B03.3) + #1875 (B12.4) results: a final on a national broadcast - NFL prime time
  (decision 81), a national NBA game - fresh off ESPN's board, written as what it means with a
  call (decision 76, `event_dates.result_brief`); its final is the draft's key fact.
- #1650 (B03.4) a numbered UFC card's finish: its result headline on `UFC_OUTLETS`+ outlets within
  the hour, once the card has started.
- Wave 152, first-hour stories on `QUICK_OUTLETS`+ outlets within `QUICK_MINUTES` (each counts as
  news): #1613 an injury to a marquee name (`best_bet.injury_story`); #1874 a weigh-in miss or
  fight-week drama naming a numbered card or its main event in its fight week (`recap.fight_week`);
  #1890 a marquee name's press-conference quote.

The worker runs only while the PC is awake - no wake timers (the operator, 2026-11-06): a final
that ends while it sleeps is not made.

The worker runs it once a pass, at most every `CHECK_MINUTES`: one story, the result first. The
draft is made the way overnight makes one (its own process), held by the same checks an unattended
render is (`batch_review.unattended_block_reason`, the second read), rendered in its own process,
and queued public now (#1655) - outside the noon and 10 PM slots. A draft held for a claim raises
one toast (#1667); any other hold only says so in the log. At most `PER_DAY` a day (news
`NEWS_PER_DAY`), never with under `MIN_UNITS` YouTube units, on battery, or while overnight runs.
`FAST_LANE=false` stops it (the suite does).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("jobs.fast_lane")

CHECK_MINUTES = 30
PER_DAY = 3
NEWS_PER_DAY = 2
NEWS_OUTLETS = 5
NEWS_HOURS = 2.0
UFC_OUTLETS = 3
UFC_MINUTES = 60
MIN_UNITS = 1600
RESULT_LEAGUES = ("nfl", "nba")
# A game's length from kickoff to its final, then the hour a result is still fresh.
GAME_HOURS = {"nfl": 3.3, "nba": 2.4}
FRESH_HOURS = 1.25
QUICK_OUTLETS = 3
QUICK_MINUTES = 60
NEWS_KINDS = ("news", "injury", "fight_week", "presser")  # NEWS_PER_DAY counts them together
_UFC_CARD = re.compile(r"\bUFC\s+\d{3}\b")
_DRAMA = re.compile(
    r"\b(miss(es|ed)? weight|weigh-?ins?|on the scale|pulled (out|from)|withdraws?|withdrew|"
    r"replaced|replacement|altercation|scuffle|shov(es|ed)|face-?offs?|brawl)\b",
    re.IGNORECASE,
)
_PRESSER = re.compile(
    r"\b(press conference|presser|media day|post-?fight|post-?game|calls? out|fires? back|"
    r"blasts?|slams?|trashes)\b",
    re.IGNORECASE,
)
_FINISH = re.compile(
    r"\b(results?|knocks? out|knockout|KO|TKO|submits?|submission|stops|stoppage|defeats?|"
    r"def\.|beats?|wins?|decision|finish(es|ed)?)\b",
    re.IGNORECASE,
)


def enabled() -> bool:
    return os.getenv("FAST_LANE", "true").strip().lower() not in ("0", "false", "no", "off")


def news_outlets() -> int:
    try:
        return max(2, int(os.getenv("FAST_LANE_OUTLETS", "") or NEWS_OUTLETS))
    except ValueError:
        return NEWS_OUTLETS


def store_path(channel_id: str) -> str:
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, f"fast_lane_{channel_id}.json")


def load_store(channel_id: str) -> dict[str, Any]:
    try:
        with open(store_path(channel_id), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_store(channel_id: str, data: dict[str, Any]) -> None:
    path = store_path(channel_id)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
        os.replace(tmp, path)
    except OSError as exc:
        logger.debug("fast lane store not written: %s", exc)


def _day(channel_id: str, moment: datetime) -> str:
    from core.series.dated import channel_day

    return channel_day(channel_id, moment).isoformat()


def on_battery() -> bool:
    """The PC is running on its battery (Windows' power status); False when it cannot be read."""
    try:
        import ctypes

        class _Power(ctypes.Structure):
            _fields_ = [("ac", ctypes.c_byte), ("flag", ctypes.c_byte),
                        ("percent", ctypes.c_byte), ("saver", ctypes.c_byte),
                        ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]  # fmt: skip

        status = _Power()
        windll = getattr(ctypes, "windll", None)
        if windll is None or not windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return False
        return status.ac == 0  # 0 offline (battery), 1 online, 255 unknown
    except Exception as exc:
        logger.debug("power status unread: %s", exc)
        return False


def overnight_running(now: datetime | None = None) -> bool:
    """Overnight is beating now (`nightly_task` beats every minute; 3 stale)."""
    try:
        from core.nightly_task import _BEAT_STALE_MINUTES, last_beat

        beat = last_beat() or {}
        last = datetime.fromisoformat(str(beat.get("beat") or ""))
    except Exception:
        return False
    local = (now or datetime.now(timezone.utc)).astimezone().replace(tzinfo=None)
    return (local - last).total_seconds() < _BEAT_STALE_MINUTES * 60


def units_left() -> int:
    try:
        from apis.youtube_quota import get_usage_summary

        return int(get_usage_summary().get("remaining") or 0)
    except Exception as exc:
        logger.debug("quota unread: %s", exc)
        return 0


def blocked(channel_id: str, *, now: datetime, store: dict[str, Any]) -> str:
    """Why the lane does not look this pass, or ""."""
    if not enabled():
        return "off (FAST_LANE)"
    checked = store.get("checked")
    if checked:
        try:
            last = datetime.fromisoformat(str(checked))
            if now - last < timedelta(minutes=CHECK_MINUTES):
                return f"looked {int((now - last).total_seconds() // 60)} minutes ago"
        except ValueError:
            pass
    today = (store.get("days") or {}).get(_day(channel_id, now)) or {}
    if sum(int(v or 0) for v in today.values()) >= PER_DAY:
        return f"{PER_DAY} made today"
    if units_left() < MIN_UNITS:
        return f"under {MIN_UNITS:,} YouTube units left"
    if on_battery():
        return "on battery"
    if overnight_running(now):
        return "overnight is running"
    return ""


# ---- the stories ------------------------------------------------------------------------------


def _pool(channel_id: str) -> list[dict[str, Any]]:
    """The idea pool's headlines, each story once with its outlets and first outlet's time."""
    from core import best_bet

    allowed = set(best_bet.on_brand_domains(channel_id))
    feeds = best_bet.idea_feeds(channel_id, allowed)
    pool: list[dict[str, Any]] = []
    seen: set[str] = set()
    for feed, rows in zip(feeds, best_bet._fetch_feeds(feeds), strict=True):
        for row in rows[:20]:
            cand = best_bet._consider_candidate(
                row.get("title", ""),
                feed.get("name", "RSS"),
                allowed=allowed,
                exclude=set(),
                seen_local=seen,
                published=best_bet._parse_pubdate(row.get("published")),
                feed_domains=list(feed.get("domains") or []),
            )
            if cand:
                pool.append(cand)
    return best_bet.rank_by_coverage(pool)


def _drafted(channel_id: str, topic: str) -> bool:
    from core.batch_generation import unreviewed_draft
    from core.best_bet import same_story
    from core.channel_context import recent_input_topics

    try:
        if unreviewed_draft(channel_id, topic) is not None:
            return True
        return same_story(topic, list(recent_input_topics(channel_id, limit=30)))
    except Exception as exc:
        logger.debug("drafted check skipped: %s", exc)
        return True  # unread: never risk a second draft of one story


def _fresh(cand: dict[str, Any], now: datetime, minutes: float) -> bool:
    first = cand.get("first") or cand.get("published")
    if not isinstance(first, datetime):
        return False
    first = first if first.tzinfo else first.replace(tzinfo=timezone.utc)
    return now - timedelta(minutes=minutes) <= first <= now


def news_story(
    channel_id: str, *, now: datetime, pool: list[dict[str, Any]], done: set[str]
) -> dict[str, Any] | None:
    """#1647: the story on the most outlets that broke within `NEWS_HOURS` and names a marquee
    name - never a death story (decision 97), never one drafted."""
    from apis.topic_tokens import names_any
    from core.authenticity import is_death_story
    from core.best_bet import marquee_names

    names = marquee_names(channel_id)
    for cand in pool:
        topic = str(cand.get("topic") or "")
        if len(cand.get("outlets") or []) < news_outlets() or f"news:{topic}" in done:
            continue
        if not _fresh(cand, now, NEWS_HOURS * 60) or not names_any(topic, names):
            continue
        if is_death_story(topic) or _drafted(channel_id, topic):
            continue
        return {"kind": "news", "key": f"news:{topic}", "topic": topic,
                "domain": str(cand.get("domain") or "gaming"),
                "why": f"on {len(cand['outlets'])} outlets within {NEWS_HOURS:g} h"}  # fmt: skip
    return None


def _card_started(topic: str, now: datetime) -> bool:
    try:
        from core.seasonal_calendar import _start_of, event_for

        _name, start = event_for(topic)
    except Exception:
        return True
    when = _start_of(start) if start else None
    return when is None or when <= now


def ufc_story(
    channel_id: str, *, now: datetime, pool: list[dict[str, Any]], done: set[str]
) -> dict[str, Any] | None:
    """#1650: a numbered card's finish - its headline on `UFC_OUTLETS`+ outlets within
    `UFC_MINUTES`, once the card has started (a prelim headline before it reads as a preview)."""
    from core.authenticity import is_death_story

    for cand in pool:
        topic = str(cand.get("topic") or "")
        if not _UFC_CARD.search(topic) or not _FINISH.search(topic) or f"ufc:{topic}" in done:
            continue
        if len(cand.get("outlets") or []) < UFC_OUTLETS or not _fresh(cand, now, UFC_MINUTES):
            continue
        if not _card_started(topic, now) or is_death_story(topic):
            continue
        if _drafted(channel_id, topic):
            continue
        return {"kind": "ufc", "key": f"ufc:{topic}", "topic": topic, "domain": "ufc",
                "why": f"a {_UFC_CARD.search(topic).group(0)} finish on "  # type: ignore[union-attr]
                       f"{len(cand['outlets'])} outlets"}  # fmt: skip
    return None


def _quick_story(
    channel_id: str,
    kind: str,
    *,
    now: datetime,
    pool: list[dict[str, Any]],
    done: set[str],
    match: Callable[[str], bool],
    why: str,
) -> dict[str, Any] | None:
    """Wave 152: the first story `match` takes on `QUICK_OUTLETS`+ outlets whose first outlet
    published within `QUICK_MINUTES` - never a death story, never one drafted."""
    from core.authenticity import is_death_story

    for cand in pool:
        topic = str(cand.get("topic") or "")
        key = f"{kind}:{topic}"
        if key in done or len(cand.get("outlets") or []) < QUICK_OUTLETS:
            continue
        if not _fresh(cand, now, QUICK_MINUTES) or not match(topic):
            continue
        if is_death_story(topic) or _drafted(channel_id, topic):
            continue
        return {"kind": kind, "key": key, "topic": topic,
                "domain": str(cand.get("domain") or "gaming"),
                "why": f"{why} on {len(cand['outlets'])} outlets within the hour"}  # fmt: skip
    return None


def quick_stories(
    channel_id: str,
    *,
    now: datetime,
    pool: list[dict[str, Any]],
    done: set[str],
    week: list[str] | None = None,
) -> dict[str, Any] | None:
    """#1613, then #1874, then #1890. `week` is the fight week's names; None reads them from
    ESPN's calendar - only when a headline has a fight-week word."""
    from apis.topic_tokens import names_any
    from core.best_bet import injury_story, marquee_names

    names = marquee_names(channel_id)
    found = _quick_story(channel_id, "injury", now=now, pool=pool, done=done,
                         match=lambda t: injury_story(t, names), why="a marquee injury")  # fmt: skip
    if found:
        return found
    if week is None and any(_DRAMA.search(str(c.get("topic") or "")) for c in pool):
        from core.series.recap import fight_week

        week = fight_week(now=now)
    if week:
        found = _quick_story(channel_id, "fight_week", now=now, pool=pool, done=done,
                             match=lambda t: bool(_DRAMA.search(t)) and names_any(t, week),
                             why=f"{week[0]} fight week")  # fmt: skip
        if found:
            return found
    return _quick_story(channel_id, "presser", now=now, pool=pool, done=done,
                        match=lambda t: bool(_PRESSER.search(t)) and names_any(t, names),
                        why="a marquee press-conference quote")  # fmt: skip


def _side(comp: dict[str, Any], key: str) -> dict[str, Any]:
    for side in comp.get("competitors") or []:
        if isinstance(side, dict) and side.get("homeAway") == key:
            return side
    return {}


def final_of(
    league: str, event: dict[str, Any], *, now: datetime, fresh_hours: float = FRESH_HOURS
) -> dict[str, Any] | None:
    """A national broadcast's final, fresh off the board: {topic, final, key, teams, ...} or
    None - a game not over, not national, or past `fresh_hours` after its expected end (#1999:
    overnight reads last night's with twelve)."""
    from core.best_bet import _NATIONAL_TV

    state = ((event.get("status") or {}).get("type") or {}) if isinstance(event, dict) else {}
    if state.get("completed") is not True:
        return None
    comps = event.get("competitions") or [{}]
    comp = comps[0] if isinstance(comps, list) and comps and isinstance(comps[0], dict) else {}
    tv = {str(n) for b in comp.get("broadcasts") or [] for n in (b.get("names") or []) if n}
    if not tv & set(_NATIONAL_TV.get(league, ())):
        return None
    try:
        start = datetime.fromisoformat(str(event.get("date") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=GAME_HOURS.get(league, 3.0))
    if not start < now <= end + timedelta(hours=fresh_hours):
        return None
    away, home = _side(comp, "away"), _side(comp, "home")

    def name(side: dict[str, Any]) -> str:
        team = side.get("team") or {}
        return str(team.get("shortDisplayName") or team.get("name") or "")

    try:
        scores = {"away": int(str(away.get("score"))), "home": int(str(home.get("score")))}
    except (TypeError, ValueError):
        return None
    if not name(away) or not name(home) or scores["away"] == scores["home"]:
        return None
    win, lose = ("away", "home") if scores["away"] > scores["home"] else ("home", "away")
    sides = {"away": away, "home": home}
    winner, loser = name(sides[win]), name(sides[lose])
    return {
        "kind": "result",
        "key": f"result:{event.get('id') or event.get('name')}",
        "topic": f"{winner} beat {loser} {scores[win]}-{scores[lose]}: what it means",
        "domain": league,
        "final": f"ESPN final: {name(away)} {scores['away']}, {name(home)} {scores['home']} - "
                 f"{winner} won ({', '.join(sorted(tv & set(_NATIONAL_TV[league])))})",
        "why": f"a {league.upper()} final on national TV",
        "league": league,
        "teams": [{"abbr": str((s.get("team") or {}).get("abbreviation") or ""), "name": name(s)}
                  for s in (away, home)],
    }  # fmt: skip


def result_story(
    channel_id: str,
    *,
    now: datetime,
    done: set[str],
    boards: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """#1649 / #1875: the first fresh national final on today's NFL and NBA boards."""
    if boards is None:
        from sports.espn import get_scoreboard

        boards = {}
        for league in RESULT_LEAGUES:
            try:
                boards[league] = get_scoreboard(league)
            except Exception as exc:
                logger.debug("%s board unread: %s", league, exc)
    for league in RESULT_LEAGUES:
        for event in (boards.get(league) or {}).get("events") or []:
            found = final_of(league, event, now=now) if isinstance(event, dict) else None
            if found and found["key"] not in done:
                return found
    return None


def next_story(
    channel_id: str,
    *,
    now: datetime,
    store: dict[str, Any],
    pool: Callable[[str], list[dict[str, Any]]] | None = None,
    boards: dict[str, Any] | None = None,
    week: list[str] | None = None,
) -> dict[str, Any] | None:
    """The one story this pass makes: a result, then a card's finish, then - while today's news
    kinds are under `NEWS_PER_DAY` - a quick story (#1613, #1874, #1890), then breaking news."""
    done = set(store.get("done") or [])
    found = result_story(channel_id, now=now, done=done, boards=boards)
    if found:
        return found
    rows = (pool or _pool)(channel_id)
    found = ufc_story(channel_id, now=now, pool=rows, done=done)
    if found:
        return found
    today = (store.get("days") or {}).get(_day(channel_id, now)) or {}
    if sum(int(today.get(kind) or 0) for kind in NEWS_KINDS) >= NEWS_PER_DAY:
        return None
    found = quick_stories(channel_id, now=now, pool=rows, done=done, week=week)
    if found:
        return found
    return news_story(channel_id, now=now, pool=rows, done=done)


# ---- draft, check, render, queue ----------------------------------------------------------------


def _draft(channel_id: str, story: dict[str, Any]) -> Any:
    """Overnight's own draft, in its own process, with the pick recorded as the fast lane's."""
    from core.best_bet import BestBetResult, pick_record
    from core.overnight import _draft_one

    bet = BestBetResult(topic=story["topic"], domain=story["domain"], avg_engaged_rate=0.0,
                        source=f"fast_{story['kind']}", supporting_runs=0, rationale=story["why"])  # fmt: skip
    facts = story_facts(channel_id, story) or None
    return _draft_one(channel_id, story["topic"], key_facts=facts,
                      pick=pick_record([bet], 1, by="fast lane"))  # fmt: skip


def story_facts(
    channel_id: str,
    story: dict[str, Any],
    *,
    schedule: Callable[[str, str], dict[str, Any]] | None = None,
) -> list[str]:
    """A story's key facts: a result's ESPN final, then each team's next game (#1687)."""
    if not story.get("final"):
        return []
    facts = [str(story["final"])]
    try:
        from core.series.last_night import next_game_lines

        facts += next_game_lines(str(story.get("league") or story.get("domain") or ""),
                                 list(story.get("teams") or []), now=datetime.now(timezone.utc),
                                 channel_id=channel_id, schedule=schedule)  # fmt: skip
    except Exception as exc:
        logger.debug("next games skipped: %s", exc)
    return facts


def _hold_toast(channel_id: str, run_id: int, reason: str) -> None:
    """#1667: one toast when a fast-lane draft is held for a claim - nothing for any other hold."""
    if "claim" not in reason.lower():
        return
    try:
        from core.win_notify import toast_daily

        toast_daily(f"fast-claim-{run_id}", "Content OS: a fast-lane draft needs a claim checked",
                    f"Run {run_id} is held: {reason} - py -m scripts.ops batch-review "
                    f"--channel {channel_id}")  # fmt: skip
    except Exception as exc:
        logger.debug("fast-lane toast skipped: %s", exc)


def _render_and_queue(channel_id: str, run_id: int) -> tuple[str, int]:
    """("", job id) once rendered and queued public now, else (why not, 0)."""
    from analytics.queue_manager import requeue_content_run
    from core import batch_review

    draft = next((d for d in batch_review.pending_drafts(channel_id) if d.run_id == run_id), None)
    if draft is None:
        return "its draft was not found", 0
    reason = batch_review.unattended_block_reason(draft) or batch_review._second_read_for(draft)
    if reason:
        batch_review._note_hold(draft, f"fast lane: {reason}")
        _hold_toast(channel_id, run_id, reason)
        return f"held - {reason}", 0
    stop = (
        batch_review._smoke_failure()
        or batch_review._memory_short()
        or (batch_review._disk_short())
    )
    if stop:
        return f"not rendered - {stop}", 0
    batch_review._render_in_process(draft, False)
    batch_review._write_review(draft, decision="rendered", override=False, by="fast lane")
    # #1655: public as it uploads, outside the noon and 10 PM slots
    return "", requeue_content_run(run_id, channel_id, privacy_status="public")


def run_fast_lane(
    channel_id: str,
    *,
    now: datetime | None = None,
    draft: Callable[[str, dict[str, Any]], Any] | None = None,
    render: Callable[[str, int], tuple[str, int]] | None = None,
    pool: Callable[[str], list[dict[str, Any]]] | None = None,
    boards: dict[str, Any] | None = None,
) -> list[str]:
    """One pass: a line for each thing done, [] when it did not look or found nothing."""
    if not enabled():  # off: not even the store is read
        return []
    moment = now or datetime.now(timezone.utc)
    store = load_store(channel_id)
    why = blocked(channel_id, now=moment, store=store)
    if why:
        logger.debug("fast lane: %s", why)
        return []
    store["checked"] = moment.isoformat(timespec="seconds")
    save_store(channel_id, store)
    story = next_story(channel_id, now=moment, store=store, pool=pool, boards=boards)
    if story is None:
        return []
    store.setdefault("done", []).append(story["key"])
    store["done"] = store["done"][-200:]
    save_store(channel_id, store)
    lines = [f"Fast lane ({story['why']}): {story['topic']}"]
    outcome = (draft or _draft)(channel_id, story)
    run_id = int(getattr(outcome, "run_id", 0) or 0)
    if not getattr(outcome, "ok", False) or not run_id:
        lines.append(f"  not drafted: {getattr(outcome, 'error', '') or 'no run'}")
        return lines
    try:
        held, job = (render or _render_and_queue)(channel_id, run_id)
    except Exception as exc:
        logger.warning("fast lane run %s not rendered: %s", run_id, exc)
        held, job = f"render failed - {str(exc)[:120]}", 0
    if held:
        lines.append(f"  run {run_id} {held}")
        return lines
    day = store.setdefault("days", {}).setdefault(_day(channel_id, moment), {})
    day[story["kind"]] = int(day.get(story["kind"]) or 0) + 1
    store["days"] = {k: v for k, v in store["days"].items() if k >= _day(channel_id, moment - timedelta(days=7))}  # fmt: skip
    save_store(channel_id, store)
    lines.append(f"  run {run_id} rendered and queued public now (job {job})")
    return lines
