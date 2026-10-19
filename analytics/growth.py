"""`ops growth` - where the views go, from the channel's own numbers (#983).

Operator, 2026-10-06: "why are we still barely getting 500 views per post? better or more
advertising?" The sync already keeps, per video, the organic 7-day views (#940), the share of
Shorts starts not swiped away (`stayed`, #951), the Shorts-feed share of organic views (#954)
and the paid views (#954). This reads them together:

- organic 7-day views: median, best and worst;
- viewers who stay: median views of the third of videos with the highest stayed share against
  the lowest third - the size of the gap is what the first second is worth on this channel;
- the Shorts-feed share; posting cadence over the last 28 days; the paid share of all views;
- Shorts cut from a chapter against Shorts made as Shorts (#1054).

`levers` ranks the three largest gaps, each with the number behind it and one change. A gap
that is not there is not reported. Below `_MIN_VIDEOS` measured videos it says "collecting".
"""

from __future__ import annotations

import json
import os
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


def _daily_paid(metrics: dict[str, Any]) -> int:
    """The paid views in a video's daily rows (#1156). `paid_views` is the 28-day window's
    count and was on 5 of 43 videos; the daily rows were on 41."""
    total = 0
    for item in metrics.get("daily_paid_views") or []:
        try:
            total += int(float(item[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            continue
    return total


def _rows(channel_id: str) -> list[dict[str, Any]]:
    from analytics.packaging import packaging_figures
    from core.success.target import views_7d
    from storage.repositories.publish_log import is_seeded, video_title

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
        paid = max(paid, _daily_paid(metrics))  # #1156
        try:
            lifetime = int(float(metrics.get("lifetime_views") or 0))
        except (TypeError, ValueError):
            lifetime = 0
        try:
            subs = int(float(metrics.get("subscribers_gained") or 0))
        except (TypeError, ValueError):
            subs = 0
        out.append({
            "title": video_title(row, fallback=str(row.youtube_video_id))[:60],
            "video_id": str(row.youtube_video_id),  # #997: which one to promote
            "published": published,
            "views7": views_7d(metrics, published) if published else None,
            "stayed": figures.get("stayed"),
            "feed": figures.get("feed"),
            "views": views,
            "paid": paid,
            "all_views": max(views, lifetime, paid),
            "subs": subs,
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


_GATE_VIDEOS = 10


def third_channel_line(channel_id: str) -> str:
    """#1079: a third channel is decided with data, once this channel's stayed share holds the
    bar (`THIRD_CHANNEL_BAR`, 35%) as the median of its last ten measured videos - or ""."""
    try:
        bar = float(os.getenv("THIRD_CHANNEL_BAR", "0.35") or 0.35)
    except ValueError:
        bar = 0.35
    measured = [r for r in _rows(channel_id) if r.get("stayed") is not None and r.get("published")]
    recent = sorted(measured, key=lambda r: r["published"], reverse=True)[:_GATE_VIDEOS]
    if len(recent) < _GATE_VIDEOS:
        return f"Third channel: not yet - {len(recent)} of {_GATE_VIDEOS} videos measured"
    median = _median([float(r["stayed"]) for r in recent])
    if median >= bar:
        return (f"Third channel: the bar is cleared - {median:.0%} stayed over the last "
                f"{_GATE_VIDEOS} videos against {bar:.0%}; the decision is yours (#1079)")  # fmt: skip
    return (f"Third channel: not yet - {median:.0%} stayed over the last {_GATE_VIDEOS} videos "
            f"against a bar of {bar:.0%} (#1079)")  # fmt: skip


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


_SHORTS_MIN = 3
_SHORT_PRESETS = frozenset({"1", "2"})


def _features(run_id: Any) -> dict[str, Any]:
    """The run's stored features, or {} without a run."""
    if not run_id:
        return {}
    from storage.repositories.content_runs import get_content_run_repository

    run = get_content_run_repository().get(int(run_id))
    try:
        features = json.loads(getattr(run, "features_json", None) or "{}") if run else {}
    except (TypeError, ValueError):
        return {}
    return features if isinstance(features, dict) else {}


def _cut_shorts_made(channel_id: str) -> int:
    """Shorts cut from a long video's chapter, published or not."""
    from storage.repositories.content_runs import get_content_run_repository

    runs = get_content_run_repository().list_for_channel(channel_id) or []
    return sum(1 for run in runs if '"short_source"' in (getattr(run, "features_json", "") or ""))


def shorts_split(channel_id: str) -> dict[str, Any]:
    """#1054: 7-day views and stayed share of Shorts cut from a chapter against Shorts made
    as Shorts (a Short or Medium script that is not an all-angles video)."""
    cut: list[dict[str, Any]] = []
    native: list[dict[str, Any]] = []
    for row in _rows(channel_id):
        if row.get("views7") is None:
            continue
        features = _features(row.get("run_id"))
        if features.get("short_source") == "chapter_cut":
            cut.append(row)
        elif (
            str(features.get("length_preset") or "") in _SHORT_PRESETS
            and not features.get("all_angles")
            and not features.get("parent_run_id")
        ):
            native.append(row)
    out: dict[str, Any] = {
        "n_cut": len(cut),
        "n_native": len(native),
        "made_cut": _cut_shorts_made(channel_id),
    }
    for name, rows in (("cut", cut), ("native", native)):
        if rows:
            out[f"{name}_views"] = round(_median([float(r["views7"]) for r in rows]))
        stayed = [float(r["stayed"]) for r in rows if r.get("stayed") is not None]
        if stayed:
            out[f"{name}_stayed"] = round(_median(stayed), 3)
    return out


def shorts_line(channel_id: str, split: dict[str, Any] | None = None) -> str:
    split = split if split is not None else shorts_split(channel_id)
    n_cut, n_native = split["n_cut"], split["n_native"]
    if n_cut >= _SHORTS_MIN and n_native >= _SHORTS_MIN:

        def side(name: str, n: int) -> str:
            stayed = split.get(f"{name}_stayed")
            held = f", {stayed:.0%} stayed" if stayed is not None else ""
            return f"{split[f'{name}_views']:,} views in 7 days{held} (n={n})"

        return (
            f"Shorts: cut from a chapter {side('cut', n_cut)} vs made as a Short "
            f"{side('native', n_native)}"
        )
    made = int(split.get("made_cut") or 0)
    if made and not n_cut:
        return (
            f"Shorts: {made} cut from chapters, none published with a full week yet - "
            f"the comparison needs {_SHORTS_MIN} (made as a Short: {n_native} measured)"
        )
    return (
        f"Shorts: cut from a chapter {n_cut} measured, made as a Short {n_native} measured - "
        f"the comparison needs {_SHORTS_MIN} of each"
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
    total = sum(r["all_views"] for r in rows)
    paid_views = sum(r["paid"] for r in rows)
    out["paid_share"] = round(paid_views / total, 4) if total else 0.0
    out["paid"] = {  # #1156
        "views": paid_views,
        "videos": sum(1 for r in rows if r["paid"] > 0),
        "of": len(rows),
        "channel_90d": _channel_paid(channel_id),
    }
    brought = sorted((r for r in rows if r["subs"] > 0), key=lambda r: -r["subs"])
    out["subscribers"] = {  # #1146
        "total": sum(r["subs"] for r in rows),
        "videos_with": len(brought),
        "videos": len(rows),
        "top": [{"title": r["title"], "subs": r["subs"], "views": r["views"]} for r in brought[:3]],
        "by": conversion(rows),  # #1323
    }
    try:
        out["intro_split"] = intro_split(channel_id)  # #988
    except Exception as exc:
        logger.debug("intro split skipped: %s", exc)
    try:
        out["shorts_split"] = shorts_split(channel_id)  # #1054
    except Exception as exc:
        logger.debug("shorts split skipped: %s", exc)
    return out


_LONG_SECONDS = 180.0


def _kind(run_id: Any) -> tuple[str, str]:
    """(domain, "Shorts" or "long") of a run, from its stored features; ("", "") without one."""
    features = _features(run_id)
    if not features:
        return "", ""
    stored = features.get("domains")
    domain = str(stored.get("effective") if isinstance(stored, dict) and stored.get("effective")
                 else features.get("domain") or "")  # fmt: skip
    try:
        seconds = float((features.get("technical_qc") or {}).get("video_duration") or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    return domain, "long" if seconds > _LONG_SECONDS else "Shorts"


def conversion(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """#1323 (wave 114): subscribers per 1,000 organic views by domain and format - which
    content converts. 2 of 64 new subscribers came from the videos; the total said nothing
    about which kind. Biggest view count first; a group under 100 views is left out."""
    groups: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        domain, kind = _kind(row.get("run_id"))
        if not domain:
            continue
        group = groups.setdefault((domain, kind), {"subs": 0, "views": 0, "videos": 0})
        group["subs"] += int(row.get("subs") or 0)
        group["views"] += max(0, int(row.get("views") or 0) - int(row.get("paid") or 0))
        group["videos"] += 1
    out = [
        {"domain": d, "format": k, "subs": int(g["subs"]), "views": int(g["views"]),
         "videos": int(g["videos"]), "per_1k": round(1000.0 * g["subs"] / g["views"], 2)}
        for (d, k), g in groups.items() if g["views"] >= 100
    ]  # fmt: skip
    return sorted(out, key=lambda g: -g["views"])


def conversion_line(rep: dict[str, Any]) -> str:
    groups = (rep.get("subscribers") or {}).get("by") or []
    if not groups:
        return ""
    parts = [f"{g['domain']} {g['format']} {g['per_1k']:.1f} ({g['subs']} from {g['views']:,})"
             for g in groups[:5]]  # fmt: skip
    return "subscribers per 1,000 organic views: " + "; ".join(parts)


def _channel_paid(channel_id: str) -> int | None:
    """YouTube's own count of paid Shorts views in 90 days, from the sync (`ops ypp`)."""
    try:
        from core.ypp_readiness import load_ypp_numbers

        numbers = load_ypp_numbers(channel_id) or {}
    except Exception:
        return None
    value = numbers.get("shorts_paid_90d")
    return int(value) if isinstance(value, (int, float)) else None


def paid_line(rep: dict[str, Any]) -> str:
    """#1156: what was paid for, in one number that agrees with `ops ypp`.

    Seen 2026-10-13: this report said "paid: 0% of all views" while `ops ypp` counted 4,544
    paid Shorts views. Both are said: what the synced videos hold, and what YouTube counts
    for the channel beyond them. Where the rest ran is not known from here - the daily paid
    rows start on the day a video was first synced for them.
    """
    paid = rep.get("paid") or {}
    views, videos, of = (int(paid.get(k) or 0) for k in ("views", "videos", "of"))
    raw = paid.get("channel_90d")
    channel = int(raw) if isinstance(raw, int) else 0
    beyond = channel - views if channel > views else 0
    if not views and not beyond:
        return "paid: none"
    line = (
        f"paid: {views:,} paid views on {videos} of {of} videos "
        f"({float(rep.get('paid_share') or 0):.0%} of their views)"
        if views
        else f"paid: none on these {of} videos"
    )
    if beyond:
        line += (
            f". YouTube counts {channel:,} paid Shorts views in 90 days - {beyond:,} "
            "of them are not in these videos' synced days"
        )
    return line


def subscriber_line(rep: dict[str, Any]) -> str:
    """#1146: which videos brought a subscriber. It is the number that leads the 1,000, and
    the report counted views only. The count is each video's own synced 28-day window."""
    subs = rep.get("subscribers") or {}
    videos = int(subs.get("videos") or 0)
    if not videos:
        return ""
    total = int(subs.get("total") or 0)
    if total <= 0:
        return f"subscribers: none of {videos} videos brought one in its synced window"
    top = "; ".join(
        f"{row['subs']} from {row['title']} ({int(row['views']):,} views)"
        for row in subs.get("top") or []
    )
    return (
        f"subscribers: {total} from {videos} videos - {int(subs.get('videos_with') or 0)} "
        f"brought any: {top}"
    )


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
    shorts = rep.get("shorts_split") or {}
    if (
        shorts.get("n_cut", 0) >= _SHORTS_MIN
        and shorts.get("n_native", 0) >= _SHORTS_MIN
        and shorts.get("cut_views")
        and shorts.get("native_views")
    ):
        low, high = sorted((shorts["cut_views"], shorts["native_views"]))
        if high / max(1, low) >= 1.5:
            better = "made as Shorts" if shorts["native_views"] > shorts["cut_views"] else "cut"
            found.append({"key": "shorts", "score": high / max(1, low), "line": (
                f"Shorts cut from a chapter got {shorts['cut_views']:,} views in 7 days "
                f"(n={shorts['n_cut']}), Shorts made as Shorts {shorts['native_views']:,} "
                f"(n={shorts['n_native']}). Put the next ones into the kind that wins: {better}."
            )})  # fmt: skip
    return sorted(found, key=lambda lever: -lever["score"])[:3]


def _feed_rows(channel_id: str) -> list[str]:
    """#1198: which feed liked what. Empty store says there are no results yet."""
    try:
        from publishing.platform_recommend import feed_lines

        return [f"  {line}" for line in feed_lines(channel_id)]
    except Exception as exc:
        logger.debug("platform results skipped: %s", exc)
        return []


def render(channel_id: str) -> str:
    rep = report(channel_id)
    lines = [f"Growth - {channel_id} (organic views, ads taken out)"]
    if rep["n"] < _MIN_VIDEOS:
        lines.append(
            f"  collecting: {rep['n']} video(s) with a full first week; the report needs "
            f"{_MIN_VIDEOS} (py -m scripts.ops backfill view-curve --apply fills older ones)"
        )
        lines.extend(_feed_rows(channel_id))
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
    lines.append(f"  {paid_line(rep)}")
    told = subscriber_line(rep)
    if told:
        lines.append(f"  {told}")
    converts = conversion_line(rep)
    if converts:
        lines.append(f"  {converts}")
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
        lines.append(f"  {third_channel_line(channel_id)}")  # #1079
    except Exception as exc:
        logger.debug("third-channel line skipped: %s", exc)
    try:  # wave 112: where the channel loses half its viewers
        from core.retention import cliff_line

        cliff = cliff_line(channel_id)
        if cliff:
            lines.append(f"  {cliff}")
    except Exception as exc:
        logger.debug("cliff line skipped: %s", exc)
    try:
        lines.append(f"  {shorts_line(channel_id, rep.get('shorts_split'))}")  # #1054
    except Exception as exc:
        logger.debug("shorts line skipped: %s", exc)
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
    lines.extend(_feed_rows(channel_id))
    return "\n".join(lines)
