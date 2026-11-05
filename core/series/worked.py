"""#1608 (B01.12, wave 150): a "more of what worked" slot.

The subjects of the top `WORKED_TOP` Shorts by organic views in their first seven days
(`success.target.views_7d`), from the Shorts of the last `WORKED_DAYS`, each get one idea in the
week's menu: the freshest headline of the last `WORKED_HOURS` naming the subject. One a night, the
best-watched subject first; a subject drafted since the channel's Monday has had its idea (the GTA 6
countdown spends GTA 6's). A subject with no fresh headline waits - its old story is not redrafted.

Live 11-05: of the Shorts public 10-22 to 11-05 with seven days measured, the top were GTA 6 (run
191, 1,091 organic views; run 154, 308) and Real Madrid (run 195, 91).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.worked")

WORKED_TOP = 3
WORKED_DAYS = 14
WORKED_HOURS = 48


def _features(run: Any) -> dict[str, Any]:
    try:
        data = json.loads(getattr(run, "features_json", "") or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def worked_subjects(channel_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """{subject, views, run_id, domain} for the top Shorts of the last `WORKED_DAYS` by organic
    views in their first 7 days - each subject once, best first. Long videos are not Shorts."""
    from core.success.target import views_7d
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded
    from video.week_compile import subject_name

    moment = now or datetime.now(timezone.utc)
    runs = get_content_run_repository()
    scored: list[tuple[int, int, str, str]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        run_id, when = getattr(row, "content_run_id", None), getattr(row, "published_at", None)
        if not run_id or when is None or is_seeded(row):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if str(getattr(row, "privacy_status", "") or "").lower() != "public":
            continue
        if when < moment - timedelta(days=WORKED_DAYS) or when > moment:
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
        subject = subject_name(str(getattr(run, "title", "") or ""), names)
        stored = features.get("domains")
        domain = str(
            stored.get("effective")
            if isinstance(stored, dict) and stored.get("effective")
            else features.get("domain") or ""
        )  # the growth report's own reading (`growth._domain`)
        if subject:
            scored.append((int(views), int(run_id), subject, domain))
    out: list[dict[str, Any]] = []
    for views, run_id, subject, domain in sorted(scored, key=lambda s: (-s[0], s[1])):
        low = subject.lower()
        if any(low in o["subject"].lower() or o["subject"].lower() in low for o in out):
            continue
        out.append({"subject": subject, "views": views, "run_id": run_id, "domain": domain})
        if len(out) == WORKED_TOP:
            break
    return out


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
