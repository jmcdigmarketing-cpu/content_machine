"""The promotion ledger - what each ad campaign bought (#959).

Operator, 2026-10-06, keeping the ads until Oct 24 as a measured test: "maybe that's a week 3-4
october question to stop the ads once we have a big enough sample size". A campaign is an `ads`
entry in the spend ledger (#980): its date, amount, the Shorts it promoted (`--video`) and the
days it ran (`--days`, default `DEFAULT_DAYS`). From stored metrics only, per campaign:

- paid views in the window (#954's `daily_paid_views`) and the cost per paid view;
- subscribers gained by the promoted videos and the cost per subscriber; subscribers per 1,000
  views on the promoted videos against the channel's other videos;
- spillover: organic views a day on the other videos during the window, against the same number
  of days before it (over the days that have data).

YouTube's stored per-video numbers do not split subscribers by paid and organic, so the report
compares rates and says so. `verdict` is "running" until the window ends, then "keep" when the
promoted videos turned views into subscribers at least as well as the others or the other
videos' organic views rose by `SPILLOVER_KEEP`, else "stop".
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.promotions")

DEFAULT_DAYS = 14
SPILLOVER_KEEP = 0.2


def _repo() -> Any:
    from storage.repositories.publish_log import get_publish_log_repository

    return get_publish_log_repository()


def _metrics(row: Any) -> dict[str, Any]:
    try:
        loaded = json.loads(getattr(row, "metrics_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _series(raw: Any) -> dict[date, int]:
    out: dict[date, int] = {}
    for item in raw or []:
        try:
            out[date.fromisoformat(str(item[0])[:10])] = int(float(item[1]))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def _organic_by_day(metrics: dict[str, Any]) -> dict[date, int]:
    paid = _series(metrics.get("daily_paid_views"))
    return {d: max(0, v - paid.get(d, 0)) for d, v in _series(metrics.get("daily_views")).items()}


def _per_day(series: list[dict[date, int]], start: date, end: date) -> float | None:
    """Summed views a day across videos, over the days in `start..end` that have data."""
    days = {d for s in series for d in s if start <= d <= end}
    if not days:
        return None
    return sum(v for s in series for d, v in s.items() if start <= d <= end) / len(days)


def _rate(subs: int, views: int) -> float | None:
    return round(subs / views * 1000, 2) if views else None


def _campaign(entry: dict[str, Any], rows: list[Any], today: date) -> dict[str, Any] | None:
    from core.money.ledger import _day
    from core.success.target import paid_between

    start = _day(entry.get("date"))
    if start is None:
        return None
    days = int(entry.get("days") or DEFAULT_DAYS)
    end = _day(entry.get("ended")) or start + timedelta(days=days - 1)
    amount = float(entry.get("amount") or 0)
    named = set(entry.get("videos") or [])
    promoted: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for row in rows:
        metrics = _metrics(row)
        vid = str(getattr(row, "youtube_video_id", "") or "")
        paid = paid_between(metrics, start, end)
        is_promoted = vid in named if named else paid > 0
        (promoted if is_promoted else others).append(metrics)
    paid_views = sum(paid_between(m, start, end) for m in promoted)
    subs = sum(int(float(m.get("subscribers_gained") or 0)) for m in promoted)
    views_p = sum(int(float(m.get("views") or 0)) for m in promoted)
    subs_o = sum(int(float(m.get("subscribers_gained") or 0)) for m in others)
    views_o = sum(int(float(m.get("views") or 0)) for m in others)
    organic = [_organic_by_day(m) for m in others]
    during = _per_day(organic, start, end)
    before = _per_day(organic, start - timedelta(days=days), start - timedelta(days=1))
    spill = round(during / before - 1, 3) if during is not None and before else None
    return {
        "id": entry.get("id"),
        "what": str(entry.get("what") or ""),
        "amount": amount,
        "start": start.isoformat(),
        "decide_on": end.isoformat(),  # the last day: Oct 4 + 21 days -> decide on Oct 24
        "state": "running" if today < end else "done",
        "videos": sorted(named),
        "paid_views": paid_views,
        "cost_per_paid_view": round(amount / paid_views, 6) if paid_views else None,
        "subscribers": subs,
        "cost_per_subscriber": round(amount / subs, 2) if subs else None,
        "subs_per_1k_promoted": _rate(subs, views_p),
        "subs_per_1k_others": _rate(subs_o, views_o),
        "others_before_per_day": round(before, 1) if before is not None else None,
        "others_during_per_day": round(during, 1) if during is not None else None,
        "spillover": spill,
    }


def report(channel_id: str, *, today: date | None = None) -> list[dict[str, Any]]:
    """One dict per ads entry in the spend ledger, oldest first."""
    from core.money.ledger import entries
    from storage.repositories.publish_log import is_seeded

    today = today or date.today()
    ads = [e for e in entries() if e.get("kind") == "ads"]
    if not ads:
        return []
    rows = [
        r
        for r in _repo().list_uploaded_for_channel(channel_id) or []
        if getattr(r, "youtube_video_id", "") and not is_seeded(r)
    ]
    out = [_campaign(entry, rows, today) for entry in ads]
    return [c for c in out if c is not None]


def verdict(camp: dict[str, Any]) -> dict[str, str]:
    """{call: running | no data | keep | stop, why}."""
    if camp.get("state") == "running":
        return {"call": "running", "why": f"decide on {camp.get('decide_on')}"}
    if not camp.get("paid_views"):
        return {
            "call": "no data",
            "why": "no paid views stored for its window - py -m scripts.ops backfill view-curve "
            "--apply fills them",
        }
    promoted = camp.get("subs_per_1k_promoted")
    others = camp.get("subs_per_1k_others")
    spill = camp.get("spillover")
    rate = f"{promoted} subscribers per 1,000 views on the promoted videos vs {others} on the rest"
    if promoted is not None and others is not None and promoted >= others:
        return {"call": "keep", "why": f"{rate}: paid viewers subscribe at least as well"}
    if isinstance(spill, (int, float)) and spill >= SPILLOVER_KEEP:
        return {"call": "keep", "why": f"organic views on the other videos rose {spill:+.0%}"}
    lift = f"{spill:+.0%}" if isinstance(spill, (int, float)) else "unknown"
    return {"call": "stop", "why": f"{rate}; other videos' organic views {lift}"}


def _money(value: Any, fmt: str = "{:,.2f}") -> str:
    return "$" + fmt.format(value) if isinstance(value, (int, float)) else "-"


def render(channel_id: str) -> str:
    camps = report(channel_id)
    lines = [f"Promotions - {channel_id}"]
    if not camps:
        lines.append(
            "  No ad campaigns entered. Enter one with: py -m scripts.ops spend add --amount 10 "
            '--what "first campaign" --kind ads --date YYYY-MM-DD --video VIDEO_ID --days 21'
        )
        return "\n".join(lines)
    for camp in camps:
        call = verdict(camp)
        vids = ", ".join(camp["videos"]) or "the videos with paid views"
        lines += [
            f"  #{camp['id']} {camp['what']} - {_money(camp['amount'])} from {camp['start']} "
            f"({vids})",
            f"    paid views {camp['paid_views']:,} - {_money(camp['cost_per_paid_view'], '{:.4f}')}"
            f" each; subscribers {camp['subscribers']} - {_money(camp['cost_per_subscriber'])} each",
            f"    subscribers per 1,000 views: promoted {camp['subs_per_1k_promoted']} vs other "
            f"videos {camp['subs_per_1k_others']}",
            f"    other videos' organic views a day: {camp['others_before_per_day']} before -> "
            f"{camp['others_during_per_day']} during",
            f"    -> {call['call']}: {call['why']}",
        ]
    lines.append(
        "  YouTube's stored numbers are not split into paid and organic subscribers; the rates "
        "above compare videos, not viewers."
    )
    return "\n".join(lines)


def status_line(channel_id: str) -> str:
    """`ops status` / `ops growth`: the latest finished campaign's call, else ""."""
    try:
        done = [c for c in report(channel_id) if c["state"] == "done"]
    except Exception as exc:
        logger.debug("promotions line skipped: %s", exc)
        return ""
    if not done:
        return ""
    call = verdict(done[-1])
    return f"Ads #{done[-1]['id']}: {call['call']} - {call['why']} (ops promotions)"
