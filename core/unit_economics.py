"""Unit-economics ledger (Pillar 1 — was Phase U).

Joins the per-video fully-loaded cost (already metered into
``content_runs.features_json.cost`` by core/cost_meter) to YouTube AdSense
``estimatedRevenue`` (synced fail-open into ``publish_log.metrics_json`` by
analytics/youtube_metrics). The output is contribution margin per video and
per channel — the number that decides what to scale.

Revenue requires a monetized channel + the yt-analytics-monetary scope; until
then every row shows cost-only, which is still the half that's impossible to
reconstruct later. Read-only + fail-open. Surfaced via ``ops economics`` and
the weekly report.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.unit_economics")

# Creator plan defaults — documented in cost_meter comments ($22 / 100k chars).
# Marginal rates stay in cost_meter; these are the *allocated* subscription numbers.
TTS_PLAN_USD_ENV = "COST_TTS_PLAN_USD"
TTS_PLAN_USD_DEFAULT = 22.0
TTS_PLAN_CHARS_ENV = "COST_TTS_PLAN_CHARS"
TTS_PLAN_CHARS_DEFAULT = 100_000
TTS_TYPICAL_CHARS_PER_VIDEO = 1100  # ~90 videos at Creator quota


def _plan_usd() -> float:
    try:
        val = float(os.getenv(TTS_PLAN_USD_ENV, str(TTS_PLAN_USD_DEFAULT)))
        return val if val > 0 else TTS_PLAN_USD_DEFAULT
    except (TypeError, ValueError):
        return TTS_PLAN_USD_DEFAULT


def _plan_chars() -> int:
    try:
        val = int(float(os.getenv(TTS_PLAN_CHARS_ENV, str(TTS_PLAN_CHARS_DEFAULT))))
        return val if val > 0 else TTS_PLAN_CHARS_DEFAULT
    except (TypeError, ValueError):
        return TTS_PLAN_CHARS_DEFAULT


def allocated_per_video(n_videos: int, *, plan_usd: float | None = None) -> float:
    """Subscription cost spread across videos actually made this window."""
    if n_videos <= 0:
        return 0.0
    return round((plan_usd if plan_usd is not None else _plan_usd()) / n_videos, 4)


def plan_capacity_videos(
    *, plan_chars: int | None = None, chars_per_video: int | None = None
) -> int:
    """How many typical scripts the monthly character quota covers."""
    chars = plan_chars if plan_chars is not None else _plan_chars()
    typical = chars_per_video if chars_per_video is not None else TTS_TYPICAL_CHARS_PER_VIDEO
    if typical <= 0:
        return 0
    return chars // typical


def allocated_vs_marginal_oneliner(
    *,
    n_videos: int | None = None,
    marginal: float | None = None,
) -> str:
    """Booth footer: allocated (plan / N) vs this-run metered TTS."""
    n = int(n_videos or 0)
    if n <= 0:
        n = plan_capacity_videos() or 90
    alloc = allocated_per_video(n)
    try:
        marg = float(marginal) if marginal is not None else 0.31
    except (TypeError, ValueError):
        marg = 0.31
    if marg <= 0:
        marg = 0.31
    return (
        f"allocated ${alloc:.2f}/video (plan ${_plan_usd():.0f}/mo / {n}) vs marginal ${marg:.2f}"
    )


@dataclass
class VideoEconomics:
    run_id: int
    title: str
    cost_usd: float
    revenue_usd: float | None  # None = no revenue data (not monetized/synced)
    views: int = 0
    engaged_rate: float = 0.0
    domain: str = ""

    @property
    def rpm_usd(self) -> float | None:
        if self.revenue_usd is None or self.views <= 0:
            return None
        return round(self.revenue_usd / self.views * 1000.0, 4)

    @property
    def margin_usd(self) -> float | None:
        return None if self.revenue_usd is None else self.revenue_usd - self.cost_usd


@dataclass
class ChannelEconomics:
    channel_id: str
    videos: list[VideoEconomics] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(v.cost_usd for v in self.videos)

    @property
    def total_revenue(self) -> float | None:
        with_rev = [v.revenue_usd for v in self.videos if v.revenue_usd is not None]
        return sum(with_rev) if with_rev else None

    @property
    def total_margin(self) -> float | None:
        rev = self.total_revenue
        if rev is None:
            return None
        covered_cost = sum(v.cost_usd for v in self.videos if v.revenue_usd is not None)
        return rev - covered_cost


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _run_costs_and_titles(
    channel_id: str,
) -> tuple[dict[int, float], dict[int, str], dict[int, str]]:
    """run_id -> fully-loaded cost, title, domain."""
    costs: dict[int, float] = {}
    titles: dict[int, str] = {}
    domains: dict[int, str] = {}
    try:
        from storage.repositories.content_runs import get_content_run_repository

        for run in get_content_run_repository().list_for_channel(channel_id):
            features = _load_json(run.features_json)
            cost = features.get("cost") or {}
            try:
                costs[run.id] = float(cost.get("total") or 0.0)
            except (TypeError, ValueError):
                costs[run.id] = 0.0
            titles[run.id] = (run.title or run.selected_topic or "").strip()
            domains[run.id] = str(features.get("domain") or "").strip()
            if not domains[run.id] and (run.selected_topic or run.input_topic):
                try:
                    from apis.topic_scorer import infer_domain

                    domains[run.id] = str(
                        infer_domain(run.selected_topic or run.input_topic, channel_id) or ""
                    )
                except Exception:
                    domains[run.id] = ""
    except Exception as exc:
        logger.debug("Run costs unavailable for unit economics: %s", exc)
    return costs, titles, domains


def channel_economics(channel_id: str | None = None, *, limit: int = 25) -> ChannelEconomics:
    """Join uploaded videos to their run costs (newest uploads first)."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    econ = ChannelEconomics(channel_id=channel)
    costs, titles, domains = _run_costs_and_titles(channel)
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        rows = [
            r
            for r in get_publish_log_repository().list_uploaded_for_channel(channel)
            if r.youtube_video_id
        ]
    except Exception:
        rows = []
    rows.sort(key=lambda r: r.id or 0, reverse=True)
    for row in rows[:limit]:
        metrics = _load_json(row.metrics_json)
        revenue = metrics.get("estimated_revenue_usd")
        econ.videos.append(
            VideoEconomics(
                run_id=row.content_run_id,
                title=titles.get(row.content_run_id, "")[:60],
                cost_usd=costs.get(row.content_run_id, 0.0),
                revenue_usd=float(revenue) if revenue is not None else None,
                views=int(float(metrics.get("views", 0) or 0)),
                engaged_rate=float(metrics.get("engaged_rate", 0) or 0),
                domain=domains.get(row.content_run_id, ""),
            )
        )
    return econ


def summary_lines(econ: ChannelEconomics) -> list[str]:
    """Compact operator lines for status / weekly-report embedding."""
    if not econ.videos:
        return []
    lines = []
    n = len(econ.videos)
    lines.append(
        f"Unit economics ({n} uploaded): marginal ${econ.total_cost:.2f}"
        f" (${econ.total_cost / n:.2f}/video)"
        f" · allocated ${allocated_per_video(n):.2f}/video"
        f" (plan ${_plan_usd():.0f}/mo ÷ {n})"
    )
    cap = plan_capacity_videos()
    lines.append(
        f"  Creator quota ~{cap} videos/mo at {TTS_TYPICAL_CHARS_PER_VIDEO} chars; "
        f"{n} used this window"
    )
    if econ.total_revenue is not None:
        margin = econ.total_margin or 0.0
        lines.append(
            f"  revenue ${econ.total_revenue:.2f} - margin ${margin:+.2f} (est., 28d windows)"
        )
    else:
        lines.append(
            "  revenue: no data yet (needs monetized channel + yt-analytics-monetary scope)"
        )
    lines.extend(domain_margin_lines(econ))
    return lines


def domain_margin_lines(econ: ChannelEconomics) -> list[str]:
    """RPM x cost by domain (candidate 84). Views-by-domain already exist on runs."""
    buckets: dict[str, dict[str, float]] = {}
    for v in econ.videos:
        name = (v.domain or "unknown").strip() or "unknown"
        b = buckets.setdefault(name, {"cost": 0.0, "rev": 0.0, "views": 0.0, "n": 0, "n_rev": 0})
        b["cost"] += v.cost_usd
        b["views"] += v.views
        b["n"] += 1
        if v.revenue_usd is not None:
            b["rev"] += v.revenue_usd
            b["n_rev"] += 1
    if not buckets:
        return []
    lines = ["  RPM x cost by domain:"]
    for name in sorted(buckets, key=lambda k: -buckets[k]["rev"]):
        b = buckets[name]
        rpm = (b["rev"] / b["views"] * 1000.0) if b["views"] and b["n_rev"] else None
        margin = (b["rev"] - b["cost"]) if b["n_rev"] else None
        rpm_s = f"RPM ${rpm:.2f}" if rpm is not None else "RPM n/a"
        mar_s = f"margin ${margin:+.2f}" if margin is not None else "margin n/a"
        lines.append(f"    {name:<12} n={int(b['n'])} cost ${b['cost']:.2f} {rpm_s} {mar_s}")
    return lines


def to_csv(econ: ChannelEconomics) -> str:
    """CSV export of per-video unit economics (candidate 135). ASCII only."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["run_id", "title", "domain", "cost_usd", "revenue_usd", "views", "margin_usd"])
    for v in econ.videos:
        writer.writerow(
            [
                v.run_id,
                v.title,
                v.domain,
                f"{v.cost_usd:.4f}",
                "" if v.revenue_usd is None else f"{v.revenue_usd:.4f}",
                v.views,
                "" if v.margin_usd is None else f"{v.margin_usd:.4f}",
            ]
        )
    return buf.getvalue()


def render(channel_id: str | None = None, *, limit: int = 25) -> str:
    econ = channel_economics(channel_id, limit=limit)
    lines = [f"Unit economics - {econ.channel_id}", "=" * 64]
    if not econ.videos:
        lines.append("No uploaded videos with run links yet.")
        return "\n".join(lines)
    for v in econ.videos:
        rev = f"${v.revenue_usd:.2f}" if v.revenue_usd is not None else "  n/a"
        margin = f"{v.margin_usd:+.2f}" if v.margin_usd is not None else "   --"
        lines.append(
            f"  #{v.run_id:<5} {v.title:<40} cost ${v.cost_usd:5.2f}"
            f"  rev {rev}  margin {margin}"
        )
    lines.append("-" * 64)
    lines.extend(f"  {line}" for line in summary_lines(econ))
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Per-video cost vs revenue")
    parser.add_argument("--channel", default=None)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    print(render(args.channel, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
