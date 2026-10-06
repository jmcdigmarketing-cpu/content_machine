"""`ops growth` - where the views go, from the channel's own numbers (#983).

Operator, 2026-10-06: "why are we still barely getting 500 views per post? better or more
advertising?" The sync already keeps, per video, the organic 7-day views (#940), the share of
Shorts starts not swiped away (`stayed`, #951), the Shorts-feed share of organic views (#954)
and the paid views (#954). This reads them together:

- organic 7-day views: median, best and worst;
- viewers who stay: median views of the third of videos with the highest stayed share against
  the lowest third - the size of the gap is what the first second is worth on this channel;
- the Shorts-feed share; posting cadence over the last 28 days; the paid share of all views.

`levers` ranks the three largest gaps, each with the number behind it and one change. A gap
that is not there is not reported. Below `_MIN_VIDEOS` measured videos it says "collecting".
"""

from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.growth")

_MIN_VIDEOS = 5
_WINDOW_DAYS = 28
_DAILY = 7.0


def _repo() -> Any:
    from storage.repositories.publish_log import get_publish_log_repository

    return get_publish_log_repository()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _metrics(row: Any) -> dict[str, Any]:
    try:
        loaded = json.loads(getattr(row, "metrics_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _published(row: Any) -> datetime | None:
    when = getattr(row, "published_at", None)
    if isinstance(when, str):
        try:
            when = datetime.fromisoformat(when)
        except ValueError:
            return None
    if not isinstance(when, datetime):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _rows(channel_id: str) -> list[dict[str, Any]]:
    from analytics.packaging import packaging_figures
    from core.success.target import views_7d
    from storage.repositories.publish_log import is_seeded

    out: list[dict[str, Any]] = []
    for row in _repo().list_uploaded_for_channel(channel_id) or []:
        if not getattr(row, "youtube_video_id", "") or is_seeded(row):
            continue
        metrics = _metrics(row)
        published = _published(row)
        figures = packaging_figures(metrics)
        try:
            views = int(float(metrics.get("views") or 0))
            paid = int(float(metrics.get("paid_views") or 0))
        except (TypeError, ValueError):
            views, paid = 0, 0
        out.append({
            "title": str(getattr(row, "detail", "") or row.youtube_video_id)[:60],
            "published": published,
            "views7": views_7d(metrics, published) if published else None,
            "stayed": figures.get("stayed"),
            "feed": figures.get("feed"),
            "views": views,
            "paid": paid,
            "run_id": getattr(row, "content_run_id", None),
        })  # fmt: skip
    return out


def videos(channel_id: str) -> list[dict[str, Any]]:
    """Videos with a full first week, oldest first (#984: the app's bar chart)."""
    measured = [r for r in _rows(channel_id) if r["views7"] is not None]
    far = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(measured, key=lambda r: r["published"] or far)


def _opening(run_id: Any) -> dict[str, Any] | None:
    """The run's recorded opening (#988), or None before wave 64 / without a run."""
    if not run_id:
        return None
    from storage.repositories.content_runs import get_content_run_repository

    run = get_content_run_repository().get(int(run_id))
    try:
        quality = json.loads(getattr(run, "quality_json", None) or "{}") if run else {}
    except (TypeError, ValueError):
        return None
    opening = quality.get("opening") if isinstance(quality, dict) else None
    return opening if isinstance(opening, dict) else None


_INTRO_MIN = 3


def intro_split(channel_id: str) -> dict[str, Any]:
    """#988: median stayed share of videos that opened on the intro vs those that did not."""
    with_intro: list[float] = []
    without: list[float] = []
    for row in _rows(channel_id):
        if row.get("stayed") is None:
            continue
        opening = _opening(row.get("run_id"))
        if opening is None:
            continue
        (with_intro if opening.get("intro") else without).append(float(row["stayed"]))
    out: dict[str, Any] = {"n_with": len(with_intro), "n_without": len(without)}
    if with_intro:
        out["with"] = round(_median(with_intro), 3)
    if without:
        out["without"] = round(_median(without), 3)
    return out


def intro_line(channel_id: str) -> str:
    split = intro_split(channel_id)
    if split["n_with"] >= _INTRO_MIN and split["n_without"] >= _INTRO_MIN:
        return (
            f"Intro: {split['with']:.0%} stayed past the swipe with the channel intro "
            f"(n={split['n_with']}) vs {split['without']:.0%} without it (n={split['n_without']})"
        )
    return (
        f"Intro: {split['n_without']} video(s) without the channel intro so far, "
        f"{split['n_with']} with it - INTRO_TEST=alternate in .env drops it on every other "
        f"render until both have {_INTRO_MIN}"
    )


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def report(channel_id: str) -> dict[str, Any]:
    """The numbers `render` and `levers` read."""
    rows = _rows(channel_id)
    measured = [r for r in rows if r["views7"] is not None]
    views = [float(r["views7"]) for r in measured]
    out: dict[str, Any] = {"n": len(measured), "videos": len(rows)}
    if measured:
        best = max(measured, key=lambda r: r["views7"])
        worst = min(measured, key=lambda r: r["views7"])
        out.update(
            median_views=round(_median(views)),
            best={"title": best["title"], "views": int(best["views7"])},
            worst={"title": worst["title"], "views": int(worst["views7"])},
        )
    stayed = sorted((r for r in measured if r["stayed"] is not None), key=lambda r: -r["stayed"])
    third = len(stayed) // 3
    if third >= 1:
        high, low = stayed[:third], stayed[-third:]
        out["stayed_split"] = {
            "high_stayed": round(_median([r["stayed"] for r in high]), 3),
            "low_stayed": round(_median([r["stayed"] for r in low]), 3),
            "high_views": round(_median([float(r["views7"]) for r in high])),
            "low_views": round(_median([float(r["views7"]) for r in low])),
        }
    feeds = [r["feed"] for r in rows if r["feed"] is not None]
    if feeds:
        out["feed_share"] = round(_median(feeds), 3)
    cutoff = datetime.combine(_today() - timedelta(days=_WINDOW_DAYS), datetime.min.time(),
                              tzinfo=timezone.utc)  # fmt: skip
    recent = [r for r in rows if r["published"] and r["published"] >= cutoff]
    out["per_week"] = round(len(recent) / (_WINDOW_DAYS / 7), 2)
    total = sum(r["views"] for r in rows)
    out["paid_share"] = round(sum(r["paid"] for r in rows) / total, 4) if total else 0.0
    try:
        out["intro_split"] = intro_split(channel_id)  # #988
    except Exception as exc:
        logger.debug("intro split skipped: %s", exc)
    return out


def levers(rep: dict[str, Any]) -> list[dict[str, Any]]:
    """The three largest gaps, largest first: {key, score, line}. Empty when none is real."""
    found: list[dict[str, Any]] = []
    split = rep.get("stayed_split") or {}
    if split and split.get("low_views"):
        ratio = split["high_views"] / max(1, split["low_views"])
        if ratio >= 1.5:
            found.append({"key": "stayed", "score": ratio, "line": (
                f"Viewers who stay drive the views: videos where {split['high_stayed']:.0%} "
                f"stayed got {split['high_views']:,} views in 7 days, those at "
                f"{split['low_stayed']:.0%} got {split['low_views']:,}. The first second decides "
                "it: open on the payoff (the clip, the number, the face), no intro, text on "
                "screen from frame one."
            )})  # fmt: skip
    per_week = float(rep.get("per_week") or 0)
    if per_week < _DAILY:
        found.append({"key": "cadence", "score": _DAILY / max(per_week, 0.5), "line": (
            f"You post {per_week:.1f} a week. The Shorts feed tests each video on a small "
            "audience first; more videos means more tests, and a channel posting daily for weeks "
            "is shown more. Aim for one a day (ops backlog schedules two weeks at once)."
        )})  # fmt: skip
    paid = float(rep.get("paid_share") or 0)
    if paid >= 0.25:
        found.append({"key": "paid", "score": 1 + paid * 4, "line": (
            f"{paid:.0%} of all views were paid. Ad views do not teach the feed who to show "
            "your videos to, and they hide how the organic ones do. Pause ads until the "
            "stayed share is up; put the money into footage and volume."
        )})  # fmt: skip
    feed = rep.get("feed_share")
    if isinstance(feed, (int, float)) and feed < 0.7:
        found.append({"key": "feed", "score": 0.7 / max(feed, 0.05), "line": (
            f"Only {feed:.0%} of organic views came from the Shorts feed - the feed is where "
            "Shorts grow. Vertical, under 60 s, #Shorts-ready, and a hook in the first second."
        )})  # fmt: skip
    intro = rep.get("intro_split") or {}
    if (
        intro.get("n_with", 0) >= _INTRO_MIN
        and intro.get("n_without", 0) >= _INTRO_MIN
        and intro["without"] - intro["with"] >= 0.05
    ):
        found.append({"key": "intro", "score": 1 + (intro["without"] - intro["with"]) * 10,
                      "line": (
            f"Videos without the channel intro held {intro['without']:.0%} of viewers past the "
            f"swipe, those with it {intro['with']:.0%}. The intro spends the first second on a "
            "logo: set CHANNEL_INTRO_ENABLED=false (or keep it only at the end)."
        )})  # fmt: skip
    return sorted(found, key=lambda lever: -lever["score"])[:3]


def render(channel_id: str) -> str:
    rep = report(channel_id)
    lines = [f"Growth - {channel_id} (organic views, ads taken out)"]
    if rep["n"] < _MIN_VIDEOS:
        lines.append(
            f"  collecting: {rep['n']} video(s) with a full first week; the report needs "
            f"{_MIN_VIDEOS} (py -m scripts.ops backfill view-curve --apply fills older ones)"
        )
        return "\n".join(lines)
    lines.append(
        f"  7-day views: median {rep['median_views']:,} over {rep['n']} videos - best "
        f"{rep['best']['views']:,} ({rep['best']['title']}), worst {rep['worst']['views']:,} "
        f"({rep['worst']['title']})"
    )
    split = rep.get("stayed_split")
    if split:
        lines.append(
            f"  stayed past the swipe: top third {split['high_stayed']:.0%} -> "
            f"{split['high_views']:,} views, bottom third {split['low_stayed']:.0%} -> "
            f"{split['low_views']:,}"
        )
    else:
        lines.append("  stayed past the swipe: not synced yet (ops sync-metrics)")
    if "feed_share" in rep:
        lines.append(f"  from the Shorts feed: {rep['feed_share']:.0%} of organic views")
    lines.append(f"  posting: {rep['per_week']:.1f} a week over the last {_WINDOW_DAYS} days")
    lines.append(f"  paid: {rep['paid_share']:.0%} of all views")
    try:
        from analytics.promotions import status_line

        ads = status_line(channel_id)  # #959
        if ads:
            lines.append(f"  {ads}")
    except Exception as exc:
        logger.debug("promotions line skipped: %s", exc)
    try:
        lines.append(f"  {intro_line(channel_id)}")  # #988
    except Exception as exc:
        logger.debug("intro line skipped: %s", exc)
    try:
        from analytics.hook_learning import render_line

        lines.append(f"  {render_line(channel_id)}")  # #985: which openers held viewers
    except Exception as exc:
        logger.debug("hook learning line skipped: %s", exc)
    found = levers(rep)
    lines.append("")
    if not found:
        lines.append(
            "  No large gap in these numbers - keep the cadence and watch the stayed share."
        )
    for i, lever in enumerate(found, 1):
        lines.append(f"  {i}. {lever['line']}")
    return "\n".join(lines)
