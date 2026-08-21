"""YPP / membership readiness checklist (candidate 87).

Watch-hours proxy, AI disclosure, cadence headroom. Fail-open when metrics
are missing — this is a checklist, not a publish gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.ypp_readiness")

# YouTube YPP Shorts alternative: 10M Shorts views in 90 days is one path;
# classic is 1k subs + 4k public watch hours. We only have views/duration.
WATCH_HOURS_TARGET = 4000.0
SHORTS_VIEWS_TARGET = 10_000_000


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


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _watch_hours_from_metrics(metrics: dict[str, Any]) -> float:
    """Approximate watch hours from views * averageViewDuration seconds."""
    try:
        views = float(metrics.get("views") or 0)
    except (TypeError, ValueError):
        views = 0.0
    dur = metrics.get("averageViewDuration") or metrics.get("average_view_duration") or 0
    try:
        seconds = float(dur)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        # Shorts often lack AVD; treat 20s as a conservative stand-in only when views exist.
        seconds = 20.0 if views else 0.0
    return (views * seconds) / 3600.0


def inspect_ypp(
    channel_id: str,
    *,
    metrics_rows: list[dict[str, Any]] | None = None,
    disclosure: str | None = None,
    cadence: Any = None,
) -> YppReport:
    from config.channels import resolve_channel_id

    cid = resolve_channel_id(channel_id)
    report = YppReport(channel_id=cid)

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
        try:
            views += float(m.get("views") or 0)
        except (TypeError, ValueError):
            pass
        hours += _watch_hours_from_metrics(m)

    if not have_metrics:
        report.checks.append(
            YppCheck("ypp_threshold", True, "no metrics yet — fail-open (run sync-metrics)")
        )
    else:
        hours_ok = hours >= WATCH_HOURS_TARGET
        shorts_ok = views >= SHORTS_VIEWS_TARGET
        report.checks.append(
            YppCheck(
                "ypp_threshold",
                hours_ok or shorts_ok,
                f"~{hours:.0f}h (need {WATCH_HOURS_TARGET:.0f}) or "
                f"{views:,.0f} Shorts views (need {SHORTS_VIEWS_TARGET:,.0f}) — either path",
            )
        )

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
