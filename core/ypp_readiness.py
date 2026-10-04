"""YPP / membership readiness checklist (candidate 87).

Watch hours, AI disclosure, cadence headroom. Fail-open when metrics are missing - this is a
checklist, not a publish gate.

#954: the threshold reads YouTube's own channel numbers, which the metrics sync stores in
`data/ypp_<channel>.json` (`youtube_metrics.fetch_ypp_numbers`): Shorts views over the last
90 days and long-form watch hours over the last 12 months, ads excluded as YouTube excludes
them, plus subscribers - both paths need 1,000. Until that has run it falls back to an
estimate from the synced videos, labelled as one: their window views less the paid ones, and
watch time from `estimated_minutes_watched` (the 20 s stand-in only when that is missing).
The old check counted ad views, summed a 28-day window as if it were 90 days or a year, read
an `averageViewDuration` the sync never stored, and counted Shorts minutes toward the hours.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.ypp_readiness")

# YPP: 1,000 subscribers and either 4,000 public long-form watch hours in 12 months or
# 10M public Shorts views in 90 days. Promotion views, watch time and subscribers do not count.
WATCH_HOURS_TARGET = 4000.0
SHORTS_VIEWS_TARGET = 10_000_000
SUBSCRIBERS_TARGET = 1000
YPP_TEMPLATE = os.path.join(DATA_DIR, "ypp_{channel}.json")


@dataclass
class YppCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class YppReport:
    channel_id: str
    checks: list[YppCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def save_ypp_numbers(channel_id: str, numbers: dict[str, Any]) -> None:
    """Keep the sync's YPP numbers (#954) for `ops ypp`."""
    path = YPP_TEMPLATE.format(channel=channel_id)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dict(numbers), f, indent=2)
    os.replace(tmp, path)


def load_ypp_numbers(channel_id: str) -> dict[str, Any] | None:
    try:
        with open(YPP_TEMPLATE.format(channel=channel_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _watch_hours_from_metrics(metrics: dict[str, Any]) -> float:
    """Watch hours for one synced video: its `estimated_minutes_watched`, else an estimate
    from views x average view duration (a 20 s stand-in when that is missing too)."""
    try:
        minutes = float(metrics.get("estimated_minutes_watched") or 0)
    except (TypeError, ValueError):
        minutes = 0.0
    if minutes > 0:
        return minutes / 60.0
    views = _organic_views(metrics)
    dur = metrics.get("averageViewDuration") or metrics.get("average_view_duration") or 0
    try:
        seconds = float(dur)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        # Shorts often lack AVD; treat 20s as a conservative stand-in only when views exist.
        seconds = 20.0 if views else 0.0
    return (views * seconds) / 3600.0


def _organic_views(metrics: dict[str, Any]) -> float:
    """The window's views less the paid ones the sync saw (#954)."""
    try:
        views = float(metrics.get("views") or 0)
    except (TypeError, ValueError):
        views = 0.0
    try:
        paid = float(metrics.get("paid_views") or 0)
    except (TypeError, ValueError):
        paid = 0.0
    return max(0.0, views - paid)


def threshold_from_numbers(numbers: dict[str, Any]) -> YppCheck:
    """The YPP check on YouTube's own numbers, ads excluded (#954)."""
    shorts = int(numbers.get("shorts_views_90d") or 0)
    hours = float(numbers.get("long_hours_365d") or 0.0)
    subs = numbers.get("subscribers")
    views_ok = hours >= WATCH_HOURS_TARGET or shorts >= SHORTS_VIEWS_TARGET
    if isinstance(subs, int):
        ok = views_ok and subs >= SUBSCRIBERS_TARGET
        subs_text = f"{subs:,}/{SUBSCRIBERS_TARGET:,} subscribers"
    else:
        ok = views_ok
        subs_text = "subscribers unknown"
    as_of = f" (as of {numbers['as_of']})" if numbers.get("as_of") else ""
    paid = int(numbers.get("shorts_paid_90d") or 0)
    paid_text = f"; {paid:,} paid Shorts views not counted" if paid else ""
    return YppCheck(
        "ypp_threshold",
        ok,
        f"{subs_text} · {hours:,.0f}/{WATCH_HOURS_TARGET:,.0f} long-form watch hours "
        f"(12 months) or {shorts:,}/{SHORTS_VIEWS_TARGET:,} Shorts views (90 days), "
        f"ads excluded{paid_text}{as_of}",
    )


def _estimated_threshold(cid: str, metrics_rows: list[dict[str, Any]] | None) -> YppCheck:
    """From the synced videos when YouTube's numbers are not stored yet; labelled an estimate."""
    rows = metrics_rows
    if rows is None:
        rows = []
        try:
            from storage.repositories.publish_log import get_publish_log_repository

            for log in get_publish_log_repository().list_uploaded_for_channel(cid):
                rows.append(_load_json(log.metrics_json))
        except Exception as exc:
            logger.debug("ypp metrics skipped: %s", exc)

    views = 0.0
    hours = 0.0
    have_metrics = False
    for m in rows:
        if not isinstance(m, dict):
            continue
        if m.get("views") is not None or m.get("estimated_revenue_usd") is not None:
            have_metrics = True
        views += _organic_views(m)
        hours += _watch_hours_from_metrics(m)

    if not have_metrics:
        return YppCheck("ypp_threshold", True, "no metrics yet — fail-open (run sync-metrics)")
    return YppCheck(
        "ypp_threshold",
        hours >= WATCH_HOURS_TARGET or views >= SHORTS_VIEWS_TARGET,
        f"~{hours:.0f}h (need {WATCH_HOURS_TARGET:.0f}) or {views:,.0f} Shorts views "
        f"(need {SHORTS_VIEWS_TARGET:,}) — either path; an estimate from synced videos' "
        "windows, ads left out (py -m scripts.ops sync-metrics stores YouTube's own numbers)",
    )


def inspect_ypp(
    channel_id: str,
    *,
    metrics_rows: list[dict[str, Any]] | None = None,
    disclosure: str | None = None,
    cadence: Any = None,
    numbers: dict[str, Any] | None = None,
) -> YppReport:
    from config.channels import resolve_channel_id

    cid = resolve_channel_id(channel_id)
    report = YppReport(channel_id=cid)

    if numbers is None and metrics_rows is None:
        numbers = load_ypp_numbers(cid)
    if numbers:
        report.checks.append(threshold_from_numbers(numbers))
    else:
        report.checks.append(_estimated_threshold(cid, metrics_rows))

    disc = disclosure
    if disc is None:
        try:
            from core.description_extras import ai_disclosure_line

            disc = ai_disclosure_line(cid)
        except Exception as exc:
            logger.debug("ypp disclosure skipped: %s", exc)
            disc = ""
    report.checks.append(
        YppCheck(
            "disclosure",
            bool((disc or "").strip()),
            "AI disclosure line present" if (disc or "").strip() else "missing AI disclosure",
        )
    )

    cap_ok = True
    cap_detail = "cadence n/a (fail-open)"
    if cadence is None:
        try:
            from core.cadence import cadence_status

            cadence = cadence_status(cid)
        except Exception as exc:
            logger.debug("ypp cadence skipped: %s", exc)
            cadence = None
    if cadence is not None:
        total = int(getattr(cadence, "total", 0) or 0)
        cap = int(getattr(cadence, "cap", 0) or 0)
        head = max(0, cap - total) if cap else 0
        cap_ok = cap == 0 or total < cap
        cap_detail = f"{total}/{cap} posts this window, {head} headroom"
    report.checks.append(YppCheck("cadence_headroom", cap_ok, cap_detail))
    return report


def render_report(report: YppReport) -> str:
    flag = "READY" if report.ok else "NOT YET"
    lines = [f"YPP / membership checklist — {report.channel_id} [{flag}]", "=" * 48]
    for c in report.checks:
        mark = "PASS" if c.ok else "FAIL"
        lines.append(f"  [{mark}] {c.name}: {c.detail}")
    return "\n".join(lines)
