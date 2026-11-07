"""#1608 (B01.12, wave 150): a "more of what worked" slot.

The subjects of the top `WORKED_TOP` Shorts by organic views in their first seven days
(`success.target.views_7d`), from the Shorts of the last `WORKED_DAYS`, each get one idea in the
week's menu: the freshest headline of the last `WORKED_HOURS` naming the subject. One a night, the
best-watched subject first; a subject drafted since the channel's Monday has had its idea (the GTA 6
countdown spends GTA 6's). A subject with no fresh headline waits - its old story is not redrafted.

Live 11-05: of the Shorts public 10-22 to 11-05 with seven days measured, the top were GTA 6 (run
191, 1,091 organic views; run 154, 308) and Real Madrid (run 195, 91).

#1597 (B01.1, wave 152): the same measurements teach the marquee list (`config/marquee.json`, the
operator's). Over the Shorts of the last `LEARN_DAYS` with seven days measured, a subject whose
Shorts beat the channel's median twice joins it, and a listed name whose last three Shorts missed
leaves - never a name a series row carries (the GTA 6 countdown is not the name's pull). Overnight
refreshes it once a night (`refresh_marquee`, `data/marquee_learned_<channel>.json`);
`best_bet.marquee_names` merges it. `MARQUEE_LEARN=false` stops the refresh.
"""

from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.worked")

WORKED_TOP = 3
WORKED_DAYS = 14
WORKED_HOURS = 48
LEARN_DAYS = 60
LEARN_MIN = 10  # a median needs ten measured Shorts
JOIN_BEATS = 2
LEAVE_MISSES = 3


def _features(run: Any) -> dict[str, Any]:
    try:
        data = json.loads(getattr(run, "features_json", "") or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def worked_subjects(channel_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """{subject, views, run_id, domain} for the top Shorts of the last `WORKED_DAYS` by organic
    views in their first 7 days - each subject once, best first. Long videos are not Shorts."""
    moment = now or datetime.now(timezone.utc)
    scored = [s for s in _measured_shorts(channel_id, now=moment, days=WORKED_DAYS) if s["subject"]]
    out: list[dict[str, Any]] = []
    for short in sorted(scored, key=lambda s: (-s["views"], s["run_id"])):
        low = short["subject"].lower()
        if any(low in o["subject"].lower() or o["subject"].lower() in low for o in out):
            continue
        out.append({key: short[key] for key in ("subject", "views", "run_id", "domain")})
        if len(out) == WORKED_TOP:
            break
    return out


def _measured_shorts(channel_id: str, *, now: datetime, days: int) -> list[dict[str, Any]]:
    """{views, run_id, subject, domain, title, when} for each public Short of the last `days`
    with its first 7 days measured (organic views). The subject may be ""."""
    from core.success.target import views_7d
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded
    from video.week_compile import subject_name

    moment = now
    runs = get_content_run_repository()
    measured: list[dict[str, Any]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        run_id, when = getattr(row, "content_run_id", None), getattr(row, "published_at", None)
        if not run_id or when is None or is_seeded(row):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if str(getattr(row, "privacy_status", "") or "").lower() != "public":
            continue
        if when < moment - timedelta(days=days) or when > moment:
            continue
        try:
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}")
        except (TypeError, ValueError):
            continue
        views = views_7d(metrics, when) if isinstance(metrics, dict) else None
        run = runs.get(int(run_id))
        features = _features(run)
        if not views or features.get("compilation") or features.get("long_form"):
            continue
        names = list((features.get("entity_research") or {}).get("names") or [])
        title = str(getattr(run, "title", "") or "")
        stored = features.get("domains")
        domain = str(
            stored.get("effective")
            if isinstance(stored, dict) and stored.get("effective")
            else features.get("domain") or ""
        )  # the growth report's own reading (`growth._domain`)
        measured.append({"views": int(views), "run_id": int(run_id), "domain": domain,
                         "subject": subject_name(title, names) or "", "title": title,
                         "when": when})  # fmt: skip
    return measured


# ---- #1597: the marquee list learns -----------------------------------------------------------


def learned_path(channel_id: str) -> str:
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, f"marquee_learned_{channel_id}.json")


def load_learned(channel_id: str) -> dict[str, Any]:
    """{joined: {name: [run ids]}, left: {name: [run ids]}, ...} - {} when there is none."""
    try:
        with open(learned_path(channel_id), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _series_names(channel_id: str) -> list[str]:
    """Every name a series row carries - a countdown's or a launch week's name never leaves."""
    from core.series.countdown import series_rows

    out: list[str] = []
    for row in series_rows(channel_id):
        out.extend(str(n) for n in [*(row.get("names") or []), row.get("subject")] if n)
    return out


def learn_marquee(
    channel_id: str,
    *,
    now: datetime | None = None,
    shorts: list[dict[str, Any]] | None = None,
    listed: list[str] | None = None,
    keep: list[str] | None = None,
) -> dict[str, Any]:
    """#1597: who joins the marquee list and who leaves it, from the Shorts' first-week organic
    views against the channel's median. `median` is None while under `LEARN_MIN` are measured."""
    from apis.topic_tokens import names_any

    moment = now or datetime.now(timezone.utc)
    rows = (
        shorts if shorts is not None else _measured_shorts(channel_id, now=moment, days=LEARN_DAYS)
    )
    if listed is None:
        from core import best_bet

        listed = best_bet._configured_marquee(channel_id)
    keep = keep if keep is not None else _series_names(channel_id)
    learned: dict[str, Any] = {"joined": {}, "left": {}, "median": None, "shorts": len(rows),
                               "at": moment.isoformat(timespec="seconds")}  # fmt: skip
    if len(rows) < LEARN_MIN:
        return learned
    median = float(statistics.median(int(r["views"]) for r in rows))
    learned["median"] = median
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        subject = str(row.get("subject") or "").strip()
        if subject and not names_any(subject, listed):
            by_subject.setdefault(subject, []).append(row)
    for subject, group in sorted(by_subject.items()):
        beat = sorted(int(r["run_id"]) for r in group if int(r["views"]) > median)
        if len(beat) >= JOIN_BEATS:
            learned["joined"][subject] = beat
    for name in listed:
        if any(names_any(k, [name]) or names_any(name, [k]) for k in keep):
            continue
        naming = sorted(
            (
                r
                for r in rows
                if names_any(f"{r.get('title') or ''} {r.get('subject') or ''}", [name])
            ),
            key=lambda r: r["when"],
        )[-LEAVE_MISSES:]
        if len(naming) == LEAVE_MISSES and all(int(r["views"]) <= median for r in naming):
            learned["left"][name] = [int(r["run_id"]) for r in naming]
    return learned


def refresh_marquee(channel_id: str, *, now: datetime | None = None) -> str:
    """Overnight, once a night: re-learn the list and keep it; the line names who joined or left
    ("" when nobody did, or too few Shorts are measured). Never raises."""
    if os.getenv("MARQUEE_LEARN", "true").strip().lower() in ("0", "false", "no", "off"):
        return ""
    try:
        learned = learn_marquee(channel_id, now=now)
        if learned.get("median") is None:
            return ""
        with open(learned_path(channel_id), "w", encoding="utf-8") as handle:
            json.dump(learned, handle, indent=1)
        parts = []
        if learned["joined"]:
            parts.append("joined: " + ", ".join(sorted(learned["joined"])))
        if learned["left"]:
            parts.append("left: " + ", ".join(sorted(learned["left"])))
        if not parts:
            return ""
        return (f"Marquee list (#1597, the median Short {learned['median']:,.0f} organic views in "
                f"its first week) - " + "; ".join(parts))  # fmt: skip
    except Exception as exc:
        logger.warning("marquee list not refreshed: %s", exc)
        return ""


def drafted_since(channel_id: str, subject: str, since: datetime) -> bool:
    """A run since `since` whose topic or title names `subject`."""
    from apis.topic_tokens import names_any
    from storage.repositories.content_runs import get_content_run_repository

    try:
        runs = get_content_run_repository().list_for_channel(channel_id)[:60]
    except Exception as exc:
        logger.debug("worked: runs unread: %s", exc)
        return True  # unread: never risk a second idea
    for run in runs:
        made = getattr(run, "created_at", None)
        if made is None:
            continue
        made = made if made.tzinfo else made.replace(tzinfo=timezone.utc)
        if made < since:
            continue
        text = f"{getattr(run, 'input_topic', '') or ''} {getattr(run, 'title', '') or ''}"
        if names_any(text, [subject]):
            return True
    return False


def worked_idea(
    channel_id: str,
    *,
    now: datetime | None = None,
    headlines: Any = None,
    notes: list[str] | None = None,
) -> Any:
    """Tonight's "more of what worked" idea (a `BestBetResult`, source "worked"), or None.
    `WORKED_SLOT=false` stops it (the suite does)."""
    import os

    if os.getenv("WORKED_SLOT", "true").strip().lower() in ("0", "false", "no", "off"):
        return None
    from core.best_bet import BestBetResult
    from core.series.countdown import feed_headlines, subject_headlines
    from core.series.dated import channel_day, channel_zone

    moment = now or datetime.now(timezone.utc)
    day = channel_day(channel_id, moment)
    monday = datetime.combine(day - timedelta(days=day.weekday()), datetime.min.time(),
                              tzinfo=channel_zone(channel_id))  # fmt: skip
    fetched: dict[str, list[dict[str, Any]]] = {}
    for found in worked_subjects(channel_id, now=moment):
        subject = str(found["subject"])
        if drafted_since(channel_id, subject, monday):
            continue
        domain = str(found.get("domain") or "gaming")
        if domain not in fetched:
            fetched[domain] = (headlines or feed_headlines)(channel_id, {"domain": domain}, moment)
        fresh = subject_headlines([subject], fetched[domain], now=moment, hours=WORKED_HOURS)
        if not fresh:
            if notes is not None:
                notes.append(f'"More of what worked": no {subject} headline in {WORKED_HOURS} h')
            continue
        story = fresh[0]
        return BestBetResult(
            topic=str(story["title"]),
            domain=domain,
            avg_engaged_rate=0.0,
            source="worked",
            supporting_runs=1,
            rationale=f"more of what worked · {subject}: {int(found['views']):,} organic views in "
            f"its first week (run {found['run_id']})",
            facts=[f"{story.get('source') or 'A source'} reported: {story['title']}"],
        )
    return None


def what_worked_lines(
    channel_id: str, *, now: datetime | None = None, shorts: list[dict[str, Any]] | None = None
) -> list[str]:
    """#1618 (B01.22): the weekly note - the three subjects whose Shorts earned the most in their
    first week over the last `WORKED_DAYS`, and the three dead ones. The menu leans to the first
    through its "more of what worked" idea (#1608). [] with under two subjects measured."""
    moment = now or datetime.now(timezone.utc)
    rows = (
        shorts if shorts is not None else _measured_shorts(channel_id, now=moment, days=WORKED_DAYS)
    )
    best: dict[str, int] = {}
    for row in rows:
        subject = str(row.get("subject") or "").strip()
        if subject:
            best[subject] = max(best.get(subject, 0), int(row.get("views") or 0))
    if len(best) < 2:
        return []
    ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:WORKED_TOP]
    dead = sorted(ranked[WORKED_TOP:], key=lambda kv: (kv[1], kv[0]))[:WORKED_TOP]
    line = (f"What worked (#1618, the last {WORKED_DAYS} days' Shorts, first-week organic views): "
            + " · ".join(f"{s} {v:,}" for s, v in top))  # fmt: skip
    if dead:
        line += "; dead: " + " · ".join(f"{s} {v:,}" for s, v in dead)
    return [line + ' - next week\'s menu leans to the first (its "more of what worked" idea).']
