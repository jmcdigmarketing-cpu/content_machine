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

YouTube's stored per-video numbers do not split subscribers by paid and organic. The campaign's
own page in Studio does, so `ops spend result --entry N --subs N` (#992) records it, and then the
report uses paid subscribers per 1,000 paid views and the cost per paid subscriber; without it
the report compares rates between videos and says so.

After the window (#998, the operator's snowball idea): the channel's organic views a day, every
video, in up to the campaign's `days` after it, against the same span before - `held`.

`verdict` is "running" until the window ends (or "stop" early once a subscriber costs more than
`ADS_MAX_PER_SUB`, or the month is over `ADS_MONTHLY_CAP`, #996), then "keep" when paid viewers
subscribed at least as well as the other videos' viewers, the other videos' organic views rose
by `SPILLOVER_KEEP`, or organic views held that much higher for `AFTER_MIN_DAYS` after the ads,
else "stop". `candidates` (#997) names the videos worth a small test.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.promotions")

DEFAULT_DAYS = 14
SPILLOVER_KEEP = 0.2
AFTER_MIN_DAYS = 7
TEST_BUDGET = 10.0  # #997: the most one suggested test spends
TEST_DAYS = 5
_MIN_MEASURED = 5
_MAX_PICKS = 2


def max_per_subscriber() -> float | None:
    """#996: `ADS_MAX_PER_SUB` - the most one subscriber may cost; None when unset."""
    import os

    try:
        value = float(os.getenv("ADS_MAX_PER_SUB", "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


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
    from core.money.ledger import _day, charged
    from core.success.target import paid_between

    start = _day(entry.get("date"))
    if start is None:
        return None
    days = int(entry.get("days") or DEFAULT_DAYS)
    end = _day(entry.get("ended")) or start + timedelta(days=days - 1)
    amount = charged(entry)  # what it charged once the result says so (#992), else the budget
    result = entry.get("result") or {}
    paid_subs = result.get("subscribers")
    paid_subs = int(paid_subs) if isinstance(paid_subs, (int, float)) else None
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
    # #998: every video's organic views a day before, during and after the ads.
    everyone = [_organic_by_day(m) for m in promoted + others]
    all_before = _per_day(everyone, start - timedelta(days=days), start - timedelta(days=1))
    all_during = _per_day(everyone, start, end)
    after_last = min(end + timedelta(days=days), today - timedelta(days=1))
    all_after = (
        _per_day(everyone, end + timedelta(days=1), after_last) if after_last > end else None
    )
    after_days = len({d for s in everyone for d in s if end < d <= after_last})
    held = round(all_after / all_before - 1, 3) if all_after is not None and all_before else None
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
        "paid_subscribers": paid_subs,
        "cost_per_paid_subscriber": round(amount / paid_subs, 2) if paid_subs else None,
        "paid_subs_per_1k": _rate(paid_subs, paid_views) if paid_subs is not None else None,
        "subs_per_1k_promoted": _rate(subs, views_p),
        "subs_per_1k_others": _rate(subs_o, views_o),
        "others_before_per_day": round(before, 1) if before is not None else None,
        "others_during_per_day": round(during, 1) if during is not None else None,
        "spillover": spill,
        "before_per_day": round(all_before, 1) if all_before is not None else None,
        "during_per_day": round(all_during, 1) if all_during is not None else None,
        "after_per_day": round(all_after, 1) if all_after is not None else None,
        "after_days": after_days,
        "held": held,
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
    limit = max_per_subscriber()
    cps = camp.get("cost_per_paid_subscriber")
    over_limit = limit is not None and isinstance(cps, (int, float)) and cps > limit
    limit_text = (
        f"${cps:,.2f} a subscriber is above your ${limit:,.2f} limit (ADS_MAX_PER_SUB)"
        if over_limit
        else ""
    )
    if camp.get("state") == "running":
        if over_limit:  # #996: stop early, not on the last day
            return {
                "call": "stop",
                "why": f"{limit_text} - stop it now in YouTube Studio (Promote)",
            }
        from core.money.ledger import ads_over_cap

        if ads_over_cap():
            return {
                "call": "stop",
                "why": "this month's ads reached your ADS_MONTHLY_CAP cap - stop it in YouTube "
                "Studio (Promote)",
            }
        return {"call": "running", "why": f"decide on {camp.get('decide_on')}"}
    if not camp.get("paid_views"):
        return {
            "call": "no data",
            "why": "no paid views stored for its window - py -m scripts.ops backfill view-curve "
            "--apply fills them",
        }
    if over_limit:
        return {"call": "stop", "why": limit_text}
    others = camp.get("subs_per_1k_others")
    paid_rate = camp.get("paid_subs_per_1k")
    if paid_rate is not None:  # #992: the campaign page's own count
        rate = (
            f"{paid_rate} paid subscribers per 1,000 paid views vs {others} per 1,000 views on "
            "the other videos"
        )
        good = others is not None and paid_rate >= others
    else:
        promoted = camp.get("subs_per_1k_promoted")
        rate = (
            f"{promoted} subscribers per 1,000 views on the promoted videos vs {others} on the rest"
        )
        good = promoted is not None and others is not None and promoted >= others
    # A keep still names the price: the cap and the limit are the operator's call, not ours.
    price = f"; each paid subscriber cost ${cps:,.2f}" if isinstance(cps, (int, float)) else ""
    if good:
        return {"call": "keep", "why": f"{rate}: paid viewers subscribe at least as well{price}"}
    spill = camp.get("spillover")
    if isinstance(spill, (int, float)) and spill >= SPILLOVER_KEEP:
        return {
            "call": "keep",
            "why": f"organic views on the other videos rose {spill:+.0%}{price}",
        }
    held = camp.get("held")
    after_days = int(camp.get("after_days") or 0)
    held_ok = isinstance(held, (int, float)) and held >= SPILLOVER_KEEP
    if held_ok and after_days >= AFTER_MIN_DAYS:  # #998
        return {
            "call": "keep",
            "why": f"organic views stayed up {held:+.0%} after the ads stopped "
            f"({after_days} days after){price}",
        }
    lift = f"{spill:+.0%}" if isinstance(spill, (int, float)) else "unknown"
    why = f"{rate}; other videos' organic views {lift}"
    if after_days < AFTER_MIN_DAYS:
        why += f" ({after_days} days after the ads so far; judged at {AFTER_MIN_DAYS})"
    elif isinstance(held, (int, float)):
        why += f"; organic views after the ads {held:+.0%}"
    return {"call": "stop", "why": why}


def _money(value: Any, fmt: str = "{:,.2f}") -> str:
    return "$" + fmt.format(value) if isinstance(value, (int, float)) else "-"


def _num(value: Any) -> str:
    return "-" if value is None else str(value)


def render(channel_id: str, *, today: date | None = None) -> str:
    from core.money.ledger import ads_budget_line

    camps = report(channel_id, today=today)
    lines = [f"Promotions - {channel_id}"]
    try:
        cap = ads_budget_line()  # #996
    except Exception as exc:
        logger.debug("ads cap line skipped: %s", exc)
        cap = ""
    if cap:
        lines.append(f"  {cap}")
    if not camps:
        lines.append(
            "  No ad campaigns entered. Enter one with: py -m scripts.ops spend add --amount 10 "
            '--what "first campaign" --kind ads --date YYYY-MM-DD --video VIDEO_ID --days 5'
        )
    for camp in camps:
        call = verdict(camp)
        vids = ", ".join(camp["videos"]) or "the videos with paid views"
        lines += [
            f"  #{camp['id']} {camp['what']} - {_money(camp['amount'])} from {camp['start']} "
            f"({vids})",
            f"    paid views {camp['paid_views']:,} - {_money(camp['cost_per_paid_view'], '{:.4f}')}"
            f" each; subscribers {camp['subscribers']} - {_money(camp['cost_per_subscriber'])} each",
        ]
        if camp.get("paid_subscribers") is not None:
            lines.append(
                f"    paid subscribers {camp['paid_subscribers']} (from the campaign page) - "
                f"{_money(camp['cost_per_paid_subscriber'])} each; {camp['paid_subs_per_1k']} per "
                "1,000 paid views"
            )
        else:
            lines.append(
                f"    paid subscribers not entered - the campaign page in Studio shows them: "
                f"py -m scripts.ops spend result --entry {camp['id']} --subs N"
            )
        lines += [
            f"    subscribers per 1,000 views: promoted {camp['subs_per_1k_promoted']} vs other "
            f"videos {camp['subs_per_1k_others']}",
            f"    other videos' organic views a day: {camp['others_before_per_day']} before -> "
            f"{camp['others_during_per_day']} during",
            f"    organic views a day, every video: {_num(camp.get('before_per_day'))} before -> "
            f"{_num(camp.get('during_per_day'))} during -> {_num(camp.get('after_per_day'))} after "
            f"({camp.get('after_days', 0)} days after)",
            f"    -> {call['call']}: {call['why']}",
        ]
    if any(c.get("paid_subscribers") is None for c in camps):
        lines.append(
            "  YouTube's stored numbers are not split into paid and organic subscribers; without "
            "the campaign page's count the rates above compare videos, not viewers."
        )
    try:
        lines += candidate_lines(channel_id)  # #997
    except Exception as exc:
        logger.debug("promotion candidates skipped: %s", exc)
    return "\n".join(lines)


def candidates(channel_id: str, *, today: date | None = None) -> dict[str, Any]:
    """#997: videos worth a small paid test - a full first week, never promoted, organic 7-day
    views at or above the median, stayed share in the top third. {state, picks, budget, days}."""
    from analytics.growth import _median, _rows
    from core.money.ledger import ads_cap, ads_this_month, entries

    today = today or date.today()
    cap = ads_cap()
    left = None if cap is None else max(0.0, cap - ads_this_month(today))
    budget = TEST_BUDGET if left is None else round(min(TEST_BUDGET, left), 2)
    out: dict[str, Any] = {"state": "collecting", "picks": [], "budget": budget,
                           "days": TEST_DAYS}  # fmt: skip
    measured = [r for r in _rows(channel_id) if r.get("views7") is not None]
    if len(measured) < _MIN_MEASURED:
        out["measured"] = len(measured)
        return out
    out["state"] = "ready"
    promoted = {str(v) for e in entries() if e.get("kind") == "ads" for v in e.get("videos") or []}
    median = _median([float(r["views7"]) for r in measured])
    stayed = sorted((float(r["stayed"]) for r in measured if r.get("stayed") is not None),
                    reverse=True)  # fmt: skip
    third = len(stayed) // 3
    if third < 1:
        return out
    floor = stayed[third - 1]
    eligible = [
        r
        for r in measured
        if not r.get("paid")
        and str(r.get("video_id") or "") not in promoted
        and float(r["views7"]) >= median
        and r.get("stayed") is not None
        and float(r["stayed"]) >= floor
    ]
    eligible.sort(key=lambda r: (-float(r["stayed"]), -float(r["views7"])))
    out["picks"] = [
        {"title": r["title"], "video_id": r.get("video_id") or "", "stayed": r["stayed"],
         "views7": int(r["views7"])}
        for r in eligible[:_MAX_PICKS]
    ]  # fmt: skip
    return out


def candidate_lines(channel_id: str) -> list[str]:
    """`ops promotions`: the "Worth promoting" section."""
    got = candidates(channel_id)
    if got["state"] == "collecting":
        return [
            f"  Worth promoting: collecting - {got.get('measured', 0)} video(s) with a full first "
            f"week; needs {_MIN_MEASURED}"
        ]
    if not got["picks"]:
        return [
            "  Worth promoting: none - no unpromoted video is in the top third for staying past "
            "the swipe and at or above the median views. Ads amplify a video that holds viewers; "
            "they do not fix one that does not."
        ]
    lines = ["  Worth promoting (held organic viewers, never promoted):"]
    for pick in got["picks"]:
        lines.append(
            f"    {pick['title']} ({pick['video_id']}) - stayed {float(pick['stayed']):.0%}, "
            f"{pick['views7']:,} organic views in its first week"
        )
    lines.append(_test_text(got))
    return lines


def _test_text(got: dict[str, Any]) -> str:
    if got["budget"] <= 0:
        return "    a test: none this month - your cap is spent (ADS_MONTHLY_CAP)"
    stop = max_per_subscriber()
    rule = (
        f"stop early once a subscriber costs over ${stop:,.2f}"
        if stop
        else "set ADS_MAX_PER_SUB to stop it early"
    )
    return (
        f"    a test: one video, a ${got['budget']:,.2f} total budget over {got['days']} days, "
        f"an end date set in Studio; {rule}"
    )


def candidates_line(channel_id: str) -> str:
    """The app's Analytics page: one line."""
    got = candidates(channel_id)
    if got["state"] == "collecting" or not got["picks"]:
        return ""
    pick = got["picks"][0]
    if got["budget"] <= 0:
        return f"Worth promoting: {pick['title']} - next month; this month's ads cap is spent"
    return (
        f"Worth promoting: {pick['title']} (stayed {float(pick['stayed']):.0%}) - a "
        f"${got['budget']:,.0f} test over {got['days']} days"
    )


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
