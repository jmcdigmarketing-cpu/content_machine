"""Wave 139 (decision 91): the hands-off plan's 22 shortfalls, each "done when" check run.

`ops shortfalls` printed each shortfall's check and its open items, and nothing read whether a check
passed - so the Story's "Where it falls short" kept every line it had on 2026-10-18, with "Shipped"
notes added, while half of them were done. Each shortfall here reads its own number:

- MET - measured, and the number passes;
- BUILT - the fix is code its tests hold; there is nothing to measure;
- WAITING - the window or the sample is still filling;
- YOURS - an operator step (a Google console click);
- NOT YET - measured, and the number does not pass;
- NO MEASURE - the number is not recorded anywhere yet (an item says what would record it).

A reader that fails reads NO MEASURE with the reason; it never raises.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.shortfalls")

MET, BUILT, WAITING, YOURS, NOT_YET, NO_MEASURE = (
    "MET", "BUILT", "WAITING", "YOURS", "NOT YET", "NO MEASURE"
)  # fmt: skip
CLOSED = (MET, BUILT)
ORDER = (NOT_YET, YOURS, WAITING, NO_MEASURE, MET, BUILT)

# The pass marks decision 91 wrote down where the plan named none.
CLAIM_HOLD_MAX = 0.2  # S08 (the plan's own mark)
CLAIM_MIN = 5  # S08: a week with fewer checked drafts says nothing
HOURS_FLOOR = 0.2  # S01: "rising from 0.2" long-form hours a week
VIDEO_SUBS = 10  # S02: subscribers from videos in 28 days
WEEKLY_UPLOADS = 7  # S13, for 4 weeks
HOOK_RULE_N = 10  # S16: videos after the first-line rule
BACKLOG_CEILING = 300  # S22, decision 68
SYNC_DAYS = 14  # S09: "0 records corrected for 2 weeks"
MIX_GAP = 15  # S15, decision 93: no domain's menu share over 15 points from its view share


@dataclass(frozen=True)
class Reading:
    status: str
    today: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(when: Any) -> datetime | None:
    if not isinstance(when, datetime):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _public_rows(channel_id: str) -> list[Any]:
    """Publish-log rows public on record (not the seeded history), each with its publish time."""
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    rows = get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
    return [
        r
        for r in rows
        if not is_seeded(r)
        and str(getattr(r, "privacy_status", "") or "").lower() == "public"
        and _aware(getattr(r, "published_at", None)) is not None
    ]


def _within(rows: list[Any], now: datetime, days: int) -> list[Any]:
    start = now - timedelta(days=days)
    return [r for r in rows if start <= _aware(r.published_at) <= now]  # type: ignore[operator]


def _run(run_id: Any) -> Any:
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository().get(int(run_id)) if run_id else None


def _json(text: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(text or "") or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


# ---- the 22 checks --------------------------------------------------------------------------------


def _s01(channel_id: str, now: datetime) -> Reading:
    from core.success.scorecard import hours_week, long_minutes, long_sources_line

    minutes = long_minutes(channel_id)
    if not minutes:
        return Reading(NO_MEASURE, "no long video has a synced window yet")
    week = hours_week(minutes)
    status = MET if week > HOURS_FLOOR else NOT_YET
    text = (f"long-form hours this week {week:.1f} from {len(minutes)} long video(s) (goal: "
            f"above {HOURS_FLOOR})")  # fmt: skip
    try:  # #1944: where those views came from
        sources = long_sources_line(channel_id)
    except Exception as exc:
        logger.debug("long sources unread: %s", exc)
        sources = ""
    return Reading(status, text + (f"; {sources[0].lower()}{sources[1:]}" if sources else ""))


def _s02(channel_id: str, now: datetime) -> Reading:
    from analytics.growth import report

    subs = report(channel_id).get("subscribers") or {}
    total, videos = int(subs.get("total") or 0), int(subs.get("videos") or 0)
    status = MET if total >= VIDEO_SUBS else NOT_YET
    return Reading(status, f"{total} subscribers from {videos} videos in their synced windows "
                           f"(goal: {VIDEO_SUBS})")  # fmt: skip


RETIRE_WHY_SINCE = datetime(2026, 11, 1, tzinfo=timezone.utc)  # #1933: why is kept from here


def _s03(channel_id: str, now: datetime) -> Reading:
    """Renders retired as wrong in 28 days (`ops retire-renders --why wrong`, #1933)."""
    from collections import Counter

    from storage.repositories.content_runs import get_content_run_repository

    why: Counter[str] = Counter()
    for run in get_content_run_repository().list_for_channel(channel_id) or []:
        features = _json(getattr(run, "features_json", ""))
        stamp, reason = features.get("retired_at"), features.get("retired_why")
        if not stamp or not reason:
            continue
        try:
            when = _aware(datetime.fromisoformat(str(stamp)))
        except ValueError:
            continue
        if when is not None and now - when <= timedelta(days=28):
            why[str(reason)] += 1
    wrong = why["wrong"]
    others = ", ".join(f"{n} {reason}" for reason, n in why.most_common() if reason != "wrong")
    text = (f"{wrong} render{'s' if wrong != 1 else ''} retired as wrong in 28 days (goal: 0)"
            + (f"; retired otherwise: {others}" if others else ""))  # fmt: skip
    if wrong:
        return Reading(NOT_YET, text)
    if now - RETIRE_WHY_SINCE < timedelta(days=28):
        return Reading(WAITING, text + f"; the record starts {RETIRE_WHY_SINCE:%Y-%m-%d}")
    return Reading(MET, text)


def _s04(channel_id: str, now: datetime) -> Reading:
    return Reading(BUILT, "the angle screen shows each angle's seed fidelity for a typed idea "
                          "(core/angle_ranker, core/ui); 0 open items")  # fmt: skip


def _s05(channel_id: str, now: datetime) -> Reading:
    """Decision 94: the grade against the audience. "Clean" was the grade, and it ranked videos no
    better than chance against their views - so it gates nothing (built); with a GRADE_GATE floor
    back, it must earn it: half the measured videos in their views' third, of 30+."""
    from core.success import verdicts
    from core.video_grade import gate_letter

    agree, total = verdicts.grade_agreement(channel_id)
    share = agree / total if total else 0.0
    text = (f"the grade puts {agree} of {total} measured videos in their views' third ({share:.0%};"
            " chance is 33%)")  # fmt: skip
    floor = gate_letter()
    if not floor:
        return Reading(BUILT, f"{text} - it gates nothing (decision 94)")
    text += (f" - GRADE_GATE holds drafts below {floor} (goal: {verdicts.GRADE_AGREE:.0%} of "
             f"{verdicts.GRADE_MIN}+)")  # fmt: skip
    if total < verdicts.GRADE_MIN:
        return Reading(WAITING, text)
    return Reading(MET if share >= verdicts.GRADE_AGREE else NOT_YET, text)


def _saved_script(run_id: Any) -> str | None:
    from core.run_trace import full_script

    return full_script(int(run_id)) if run_id else None


def _s06(channel_id: str, now: datetime) -> Reading:
    """#1936: each public video's saved script read with today's detector - the stored verdict
    is from the day it was written: 5 of the first reading's 9 have a take by today's."""
    from core.authenticity import has_insight

    recaps = 0
    rows = _within(_public_rows(channel_id), now, 28)
    for row in rows:
        run_id = getattr(row, "content_run_id", None)
        script = _saved_script(run_id)
        if script:
            recaps += 0 if has_insight(script) else 1
            continue
        quality = _json(getattr(_run(run_id), "quality_json", ""))
        if str(quality.get("authenticity_verdict") or "").lower() in ("review", "block"):
            recaps += 1
    status = MET if recaps == 0 else NOT_YET
    return Reading(status, f"{recaps} of {len(rows)} videos public in 28 days read as a neutral "
                           "recap (goal: 0)")  # fmt: skip


def _s07(channel_id: str, now: datetime) -> Reading:
    from core.nightly_task import recorded_nights

    nights = recorded_nights()
    days = {(now - timedelta(days=i)).date() for i in range(7)}
    ran = sorted(day for day in nights if day in days)
    text = f"overnight ran {len(ran)} of the last 7 nights (goal: every night, decision 69)"
    if len(ran) == 7:
        return Reading(MET, text)
    if not nights or min(nights) > min(days):
        return Reading(WAITING, text + f"; the record starts {min(nights) if nights else 'today'}")
    return Reading(NOT_YET, text)


def claim_hold_share(runs: list[Any], *, now: datetime | None = None, days: int = 7) -> dict:
    """#1381: {checked, held: [(run id, first claim)]} - the week's drafts whose claims were
    checked, and those an unsupported claim held. Read by the weekly report and S08."""
    from core.claim_types import blocking_unsupported

    cutoff = (now or _now()) - timedelta(days=days)
    checked = 0
    held: list[tuple[int, str]] = []
    for run in runs:
        made = _aware(getattr(run, "created_at", None))
        if made is None or made < cutoff:
            continue
        verification = _json(getattr(run, "features_json", "")).get("claim_verification")
        if not isinstance(verification, dict):
            continue
        checked += 1
        claims = blocking_unsupported(verification)
        if claims:
            past = (
                " (rendered past it)" if _json(run.features_json).get("grounding_override") else ""
            )
            held.append((int(run.id), f"{claims[0]}{past}"))
    return {"checked": checked, "held": held}


def _s08(channel_id: str, now: datetime) -> Reading:
    from storage.repositories.content_runs import get_content_run_repository

    runs = get_content_run_repository().list_for_channel(channel_id) or []
    found = claim_hold_share(runs, now=now)
    checked, held = found["checked"], len(found["held"])
    text = f"{held} of {checked} drafts this week held for a claim (goal: under 20%)"
    if checked < CLAIM_MIN:
        return Reading(WAITING, text)
    return Reading(MET if held / checked < CLAIM_HOLD_MAX else NOT_YET, text)


def _s09(channel_id: str, now: datetime) -> Reading:
    """Records the privacy sync corrected in `SYNC_DAYS` days (#1934 keeps the count a day)."""
    from analytics.privacy_sync import corrections

    got = corrections(days=SYNC_DAYS, today=now.date())
    fixed = int(got.get("corrected") or 0)
    text = (f"{fixed} record{'s' if fixed != 1 else ''} corrected by the privacy sync in "
            f"{SYNC_DAYS} days (goal: 0)")  # fmt: skip
    if fixed:
        return Reading(NOT_YET, text)
    since = str(got.get("since") or "")
    try:
        first: date | None = date.fromisoformat(since)
    except ValueError:
        first = None
    if first is None:
        return Reading(WAITING, text + "; the count starts at the next sync")
    if (now.date() - first).days < SYNC_DAYS - 1:
        return Reading(WAITING, text + f"; the record starts {since}")
    return Reading(MET, text)


def _s10(channel_id: str, now: datetime) -> Reading:
    """The week's posts the round did not make itself: a real hand post, or - found by this
    check on its first run - a post the round never made because another run's own post was
    taken for it (`crosspost.false_hand_posts`)."""
    from publishing import crosspost

    def recent(state: dict[str, Any]) -> bool:
        when = crosspost._stamp(str(state.get("at") or ""))
        return bool(when and now - when <= timedelta(days=7))

    false = [x for x in crosspost.false_hand_posts(channel_id) if recent(x)]
    left = [x for x in false if x.get("left")]  # #1942: left on the operator's word
    missed = [x for x in false if not x.get("left")]
    taken = {(x["run_id"], x["service"]) for x in false}
    posts = crosspost._load(channel_id).get("posts") or {}
    by_hand = [
        f"run {run_id} {service}"
        for run_id, entry in (posts.items() if isinstance(posts, dict) else [])
        for service, state in (entry.items() if isinstance(entry, dict) else [])
        if isinstance(state, dict) and state.get("state") == "manual" and recent(state)
        and (int(run_id), service) not in taken
    ]  # fmt: skip
    if missed:
        names = ", ".join(f"run {x['run_id']} {x['service']}" for x in missed[:4])
        return Reading(NOT_YET, f"{len(missed)} crossposts in 7 days never went - each was taken "
                                f"for another video's own Buffer post ({names}); "
                                f"{len(by_hand)} made by hand (goal: 0)")  # fmt: skip
    status = MET if not by_hand else NOT_YET
    names = f" ({', '.join(by_hand[:3])})" if by_hand else ""
    kept = f"; {len(left)} left on your word" if left else ""
    return Reading(status, f"{len(by_hand)} crossposts made by hand in 7 days{names} (goal: 0)"
                           + kept)  # fmt: skip


def _s11(channel_id: str, now: datetime) -> Reading:
    measured = 0
    for row in _public_rows(channel_id):
        impressions = _json(getattr(row, "metrics_json", "")).get("thumbnail_impressions")
        if isinstance(impressions, int | float) and impressions > 0:
            measured += 1
    if measured:
        return Reading(MET, f"click-through stored for {measured} videos")
    from analytics.reach_report import status

    running, line = status(channel_id)  # #1946: the API on and the job made - YouTube's turn
    if running:
        return Reading(WAITING, f"no click-through stored yet - {line.split(': ', 1)[-1]}")
    return Reading(YOURS, "no click-through stored - turn on the YouTube Reporting API "
                          "(py -m scripts.ops doctor prints the link)")  # fmt: skip


def _s12(channel_id: str, now: datetime) -> Reading:
    from publishing.platform_metrics import load
    from video.channel_intro import _intro_enabled

    rows = load(channel_id).get("rows") or {}
    watch = [
        float(p["tiktok"]["avg_watch_s"])
        for p in (rows.values() if isinstance(rows, dict) else [])
        if isinstance(p, dict) and isinstance(p.get("tiktok"), dict)
        and p["tiktok"].get("avg_watch_s") is not None
    ]  # fmt: skip
    if not watch:
        return Reading(NO_MEASURE, "no TikTok watch time read yet")
    mean = sum(watch) / len(watch)
    intro = "the intro on" if _intro_enabled() else "the intro dropped (decision 79)"
    status = MET if mean > 3 and not _intro_enabled() else NOT_YET
    return Reading(status, f"TikTok's average watch {mean:.2f} s over {len(watch)} posts; {intro} "
                           "(goal: above 3 s, the intro settled)")  # fmt: skip


def _s13(channel_id: str, now: datetime) -> Reading:
    rows = _public_rows(channel_id)
    weeks = [len(_within(rows, now - timedelta(days=7 * i), 7)) for i in range(4)]
    text = f"public videos a week, newest first: {', '.join(map(str, weeks))} (goal: {WEEKLY_UPLOADS} for 4)"
    if all(w >= WEEKLY_UPLOADS for w in weeks):
        return Reading(MET, text)
    streak = next((i for i, w in enumerate(weeks) if w < WEEKLY_UPLOADS), 4)
    if streak:
        return Reading(WAITING, text + f"; {streak} of 4 weeks so far")
    return Reading(NOT_YET, text)


def _s14(channel_id: str, now: datetime) -> Reading:
    from youtube.oauth import sign_in_expiry, sign_in_mode

    mode = sign_in_mode(channel_id, now=now)
    if mode == "production":
        return Reading(MET, "the sign-in outlived 7 days - the Google app is published")
    when = sign_in_expiry(channel_id)
    lapse = f"lapses {when:%a %b %d}" if when else "has no date on record"
    return Reading(YOURS, f"a Testing-mode sign-in {lapse} - publish the Google app "
                          "(py -m scripts.ops check-youtube prints the page)")  # fmt: skip


def _domain_views(channel_id: str, now: datetime) -> dict[str, int]:
    """Organic views by domain of the videos published in the last 28 days - growth's rows and
    its domain reader, the figures the gaming floor reads."""
    from analytics.growth import _kind, _rows

    out: dict[str, int] = {}
    for row in _rows(channel_id):
        published = _aware(row.get("published"))
        if published is None or now - published > timedelta(days=28):
            continue
        domain, _format = _kind(row.get("run_id"))
        if domain:
            views = max(0, int(row.get("views") or 0) - int(row.get("paid") or 0))
            out[domain] = out.get(domain, 0) + views
    return out


def _s15(channel_id: str, now: datetime) -> Reading:
    """#1935 (decision 93): the last 30 menus against what each domain earned - met when no
    domain's share of the menu is more than `MIX_GAP` points from its share of the organic views
    of the videos published in 28 days. Named: the domain furthest off."""
    from core.predictions.ledger import menu_mix

    offered, _taken, _menus = menu_mix(channel_id)
    views = _domain_views(channel_id, now)
    shown, earned = sum(offered.values()), sum(views.values())
    if not shown or not earned:
        return Reading(NO_MEASURE, "no menu, or no organic views in 28 days, to compare")
    share = {d: (100 * offered.get(d, 0) / shown, 100 * views.get(d, 0) / earned)
             for d in set(offered) | set(views)}  # fmt: skip
    worst = max(share, key=lambda d: (abs(share[d][0] - share[d][1]), d))
    menu, earn = share[worst]
    gap = abs(menu - earn)
    return Reading(MET if gap <= MIX_GAP else NOT_YET,
                   f"the menu offers {worst} {menu:.0f}% against {earn:.0f}% of organic views in "
                   f"28 days - {gap:.0f} points off (goal: within {MIX_GAP})")  # fmt: skip


def _s16(channel_id: str, now: datetime) -> Reading:
    from analytics.hook_learning import _rows, rule_effect, rule_effect_text

    effect = rule_effect(_rows(channel_id, detail=True))
    after = int((effect.get("after") or {}).get("n") or 0)
    text = rule_effect_text(effect)
    return Reading(MET if after >= HOOK_RULE_N else WAITING,
                   text + f" (read at {HOOK_RULE_N} after)")  # fmt: skip


def _s17(channel_id: str, now: datetime) -> Reading:
    from core.nightly_task import crash_count

    crashes = crash_count(days=28, now=now.astimezone().replace(tzinfo=None))  # its logs: local
    return Reading(MET if crashes == 0 else NOT_YET,
                   f"{crashes} overnight crashes in 28 days (goal: 0)")  # fmt: skip


def _s18(channel_id: str, now: datetime) -> Reading:
    return Reading(BUILT, "a missing input reads unknown, never red (wave 121); each health line "
                          "is tested against what the code stores (wave 122)")  # fmt: skip


def _s19(channel_id: str, now: datetime) -> Reading:
    from core.title_generator import broken_team_name

    rows = _within(_public_rows(channel_id), now, 30)
    broken = []
    for row in rows:
        title = str(getattr(_run(getattr(row, "content_run_id", None)), "title", "") or "")
        if title and broken_team_name(title):
            broken.append(title)
    status = MET if not broken else NOT_YET
    return Reading(status, f"{len(broken)} of {len(rows)} titles in 30 days break a team's name "
                           "(goal: 0; captions and thumbnails are checked at render)")  # fmt: skip


def _s20(channel_id: str, now: datetime) -> Reading:
    from core.channel_health import _made
    from core.engagement_predictor import run_engagement_map

    measured = run_engagement_map(channel_id)
    if not measured:
        return Reading(NO_MEASURE, "no video has an engaged rate yet")
    newest = max(measured)
    made = _aware(_made([newest]).get(newest))
    age = (now - made).days if made else None
    status = MET if age is not None and age <= 7 else NOT_YET
    when = f"{age} days old" if age is not None else "of unknown age"
    return Reading(status, f"the newest measured video (run {newest}) is {when} (goal: within 7)")


def _s21(channel_id: str, now: datetime) -> Reading:
    from core.video_grade import _WEIGHTS

    weight = float(_WEIGHTS.get("hook") or 0.0)
    status = MET if weight == 0 else NOT_YET
    return Reading(status, f"the hook score's weight in the grade is {weight:g} (out since wave "
                           "124; goal: 0, or r at or above 0)")  # fmt: skip


def _s22(channel_id: str, now: datetime) -> Reading:
    from core.roadmap_index import counts

    raw = counts().get("open_total")
    total = int(raw) if isinstance(raw, int | float | str) else 0
    status = MET if total <= BACKLOG_CEILING else NOT_YET
    return Reading(status, f"{total} open backlog items (goal: at or under {BACKLOG_CEILING})")


CHECKS: dict[str, Callable[[str, datetime], Reading]] = {
    f"S{i:02d}": fn
    for i, fn in enumerate(
        (_s01, _s02, _s03, _s04, _s05, _s06, _s07, _s08, _s09, _s10, _s11,
         _s12, _s13, _s14, _s15, _s16, _s17, _s18, _s19, _s20, _s21, _s22),
        start=1,
    )
}  # fmt: skip


def reading(key: str, channel_id: str, *, now: datetime | None = None) -> Reading:
    """One shortfall's check, run. A reader that fails reads NO MEASURE with the reason."""
    check = CHECKS.get(key)
    if check is None:
        return Reading(NO_MEASURE, "no check written for it")
    try:
        return check(channel_id, now or _now())
    except Exception as exc:
        logger.debug("shortfall %s unread: %s", key, exc)
        return Reading(NO_MEASURE, f"could not be read ({type(exc).__name__})")


def readings(channel_id: str, *, now: datetime | None = None) -> dict[str, Reading]:
    moment = now or _now()
    return {key: reading(key, channel_id, now=moment) for key in CHECKS}
