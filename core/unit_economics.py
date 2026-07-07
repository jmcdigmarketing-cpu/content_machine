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
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoEconomics:
    run_id: int
    title: str
    cost_usd: float
    revenue_usd: float | None  # None = no revenue data (not monetized/synced)
    views: int = 0
    engaged_rate: float = 0.0

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


def _run_costs_and_titles(channel_id: str) -> tuple[dict[int, float], dict[int, str]]:
    """run_id -> fully-loaded cost (features_json.cost.total) and run title.

    Titles come from the run row — publish_log.detail holds status text, not
    the video title.
    """
    costs: dict[int, float] = {}
    titles: dict[int, str] = {}
    try:
        from storage.repositories.content_runs import get_content_run_repository

        for run in get_content_run_repository().list_for_channel(channel_id):
            cost = _load_json(run.features_json).get("cost") or {}
            try:
                costs[run.id] = float(cost.get("total") or 0.0)
            except (TypeError, ValueError):
                costs[run.id] = 0.0
            titles[run.id] = (run.title or run.selected_topic or "").strip()
    except Exception:
        pass
    return costs, titles


def channel_economics(channel_id: str | None = None, *, limit: int = 25) -> ChannelEconomics:
    """Join uploaded videos to their run costs (newest uploads first)."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    econ = ChannelEconomics(channel_id=channel)
    costs, titles = _run_costs_and_titles(channel)
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
        f"Unit economics ({n} uploaded): cost ${econ.total_cost:.2f}"
        f" (${econ.total_cost / n:.2f}/video)"
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
    return lines


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
