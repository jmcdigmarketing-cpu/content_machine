"""
Content Intelligence Report — human-readable output from the intelligence layer.

Aggregates discovery (signals + scored variants), research brief, and competitor
pulse into Markdown/JSON suitable for portfolio demos, freelance audits, and API
extraction later. Does not require the production tail (TTS/render/upload).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from apis.signal_contract import format_health_line
from apis.signal_corroboration import assess_corroboration
from apis.topic_scorer import infer_domain
from config.channels import get_channel_profile, resolve_channel_id
from core.analyst_accuracy import build_accuracy_report
from core.analyst_explain import build_explainability
from core.logging import get_logger, setup_logging
from core.opportunity import signal_breakdown
from core.opportunity_window import assess_opportunity_window
from core.pipeline import DiscoveryResult, run_discovery
from core.research_brief import BRIEF_VERSION, build_research_brief
from core.topic_trajectory import compute_trajectory, record_topic_snapshot
from core.ui import SIGNAL_ORDER

logger = get_logger("intelligence_report")

REPORT_VERSION = "intelligence_report_v2"


def intelligence_mode_enabled() -> bool:
    """True when production tail should be skipped (intelligence-only runs)."""
    mode = os.getenv("CONTENT_MODE", "").strip().lower()
    if mode in ("intelligence", "intel", "report"):
        return True
    flag = os.getenv("CONTENT_INTELLIGENCE_ONLY", "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def production_tail_enabled() -> bool:
    return not intelligence_mode_enabled()


def _slug(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (slug[:max_len] or "report").rstrip("_")


def _best_variant_index(discovery: DiscoveryResult) -> int:
    return max(range(len(discovery.evaluated)), key=lambda i: discovery.evaluated[i][1])


@dataclass
class IntelligenceReport:
    """Serializable intelligence-layer output for one topic + channel."""

    version: str = REPORT_VERSION
    generated_at: str = ""
    channel_id: str = "default"
    channel_name: str = ""
    input_topic: str = ""
    selected_variant: str = ""
    composite_score: float = 0.0
    domain: str = ""
    signal_health: dict[str, str] = field(default_factory=dict)
    signal_breakdown: dict[str, float] = field(default_factory=dict)
    variants: list[dict[str, Any]] = field(default_factory=list)
    research_brief: dict[str, Any] = field(default_factory=dict)
    competitor_titles: list[dict[str, str]] = field(default_factory=list)
    competitor_snapshot_age_hours: float | None = None
    timings: dict[str, float] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)
    trajectory: dict[str, Any] = field(default_factory=dict)
    corroboration: dict[str, Any] = field(default_factory=dict)
    opportunity_window: dict[str, Any] = field(default_factory=dict)
    explainability: dict[str, Any] = field(default_factory=dict)
    accuracy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _signal_health_map(signals: dict[str, Any]) -> dict[str, str]:
    health: dict[str, str] = {}
    order = list(SIGNAL_ORDER) + [k for k in signals if k not in SIGNAL_ORDER]
    for name in order:
        if name in signals:
            health[name] = format_health_line(name, signals[name])
    return health


def build_intelligence_report(
    discovery: DiscoveryResult,
    *,
    variant_index: int | None = None,
    include_brief: bool = True,
) -> IntelligenceReport:
    """Build a report from an existing DiscoveryResult."""
    if not discovery.evaluated:
        raise ValueError("discovery has no scored variants")

    idx = variant_index if variant_index is not None else _best_variant_index(discovery)
    if idx < 0 or idx >= len(discovery.evaluated):
        raise IndexError(f"variant_index {idx} out of range")

    variant, score, signals = discovery.evaluated[idx]
    channel_id = discovery.channel_id
    profile = get_channel_profile(channel_id)
    domain = infer_domain(variant, channel_id)
    breakdown = signal_breakdown(signals, variant, channel_id)

    brief_dict: dict[str, Any] = {}
    if include_brief:
        brief = build_research_brief(variant, signals, channel_id=channel_id)
        brief_dict = brief.to_dict()

    from analytics.competitor_context import list_recent_competitor_titles, snapshot_age_hours

    competitor_titles = list_recent_competitor_titles(channel_id, topic=variant, limit=12)
    age = snapshot_age_hours(channel_id)

    variants = [
        {"variant": v, "score": round(s, 4), "selected": i == idx}
        for i, (v, s, _) in enumerate(discovery.evaluated)
    ]

    corroboration = assess_corroboration(signals)
    record_topic_snapshot(
        channel_id,
        variant,
        composite_score=float(score),
        demand_index=float(score),
    )
    trajectory = compute_trajectory(channel_id, variant, current_score=float(score))
    opportunity_window = assess_opportunity_window(
        variant,
        composite_score=float(score),
        competitor_titles=competitor_titles,
        corroboration_confidence=float(corroboration.get("confidence", 0.5)),
    )
    explainability = build_explainability(
        topic=variant,
        composite_score=float(score),
        signals=signals,
        signal_breakdown=breakdown,
        corroboration=corroboration,
        trajectory=trajectory,
        opportunity_window=opportunity_window,
        research_brief=brief_dict,
    )
    accuracy = build_accuracy_report(channel_id)

    return IntelligenceReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        channel_id=channel_id,
        channel_name=profile.name or channel_id,
        input_topic=discovery.input_topic,
        selected_variant=variant,
        composite_score=round(float(score), 4),
        domain=domain,
        signal_health=_signal_health_map(discovery.base_signals),
        signal_breakdown=breakdown,
        variants=variants,
        research_brief=brief_dict,
        competitor_titles=competitor_titles,
        competitor_snapshot_age_hours=round(age, 1) if age is not None else None,
        timings=dict(discovery.timings),
        provenance={
            "report_version": REPORT_VERSION,
            "brief_version": brief_dict.get("version", BRIEF_VERSION),
            "channel_domain": profile.domain,
        },
        trajectory=trajectory,
        corroboration=corroboration,
        opportunity_window=opportunity_window,
        explainability=explainability,
        accuracy=accuracy,
    )


def run_intelligence(
    topic: str,
    *,
    channel_id: str | None = None,
    variant_limit: int = 5,
    variant_index: int | None = None,
    include_brief: bool = True,
) -> tuple[DiscoveryResult, IntelligenceReport]:
    """Full intelligence-layer run: discovery → report (no content generation)."""
    channel_id = resolve_channel_id(channel_id)
    discovery = run_discovery(topic, variant_limit=variant_limit, channel_id=channel_id)
    report = build_intelligence_report(
        discovery,
        variant_index=variant_index,
        include_brief=include_brief,
    )
    return discovery, report


def report_output_dir(channel_id: str) -> str:
    profile = get_channel_profile(channel_id)
    subdir = getattr(profile, "output_subdir", None) or channel_id
    path = os.path.join("output", subdir, "reports")
    os.makedirs(path, exist_ok=True)
    return path


def default_report_basename(report: IntelligenceReport) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"intelligence_{_slug(report.selected_variant)}_{ts}"


def save_report(
    report: IntelligenceReport,
    *,
    out_dir: str | None = None,
    basename: str | None = None,
    formats: tuple[str, ...] = ("md", "json"),
) -> dict[str, str]:
    """Write report files; returns paths written."""
    out_dir = out_dir or report_output_dir(report.channel_id)
    os.makedirs(out_dir, exist_ok=True)
    base = basename or default_report_basename(report)
    paths: dict[str, str] = {}

    if "json" in formats:
        json_path = os.path.join(out_dir, f"{base}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        paths["json"] = json_path

    if "md" in formats:
        md_path = os.path.join(out_dir, f"{base}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(to_markdown(report))
        paths["md"] = md_path

    return paths


def to_markdown(report: IntelligenceReport) -> str:
    """Render a portfolio-ready Markdown report."""
    lines: list[str] = [
        "# Content Intelligence Report",
        "",
        f"**Channel:** {report.channel_name} (`{report.channel_id}`)  ",
        f"**Generated:** {report.generated_at}  ",
        f"**Report version:** {report.version}",
        "",
        "---",
        "",
        "## Executive summary",
        "",
        f"- **Input topic:** {report.input_topic}",
        f"- **Recommended angle:** {report.selected_variant}",
        f"- **Opportunity score:** {report.composite_score:.2f} (domain: `{report.domain}`)",
    ]

    if report.corroboration:
        c = report.corroboration
        lines.append(
            f"- **Corroboration:** {c.get('confidence', 0):.0%} "
            f"({c.get('source_count', 0)} sources) — {c.get('label', '')}"
        )
    if report.trajectory.get("phase"):
        t = report.trajectory
        lines.append(
            f"- **Trajectory:** `{t.get('phase')}` "
            f"({t.get('velocity_per_hour', 0):+.1f} pts/hr) — {t.get('summary', '')}"
        )
    if report.opportunity_window.get("window_status"):
        w = report.opportunity_window
        lines.append(
            f"- **Opportunity window:** `{w.get('window_status')}` "
            f"(gap {w.get('gap_score', 0):.2f}) — {w.get('summary', '')}"
        )

    brief = report.research_brief
    if brief.get("narrative"):
        lines.extend(
            [
                f"- **Narrative:** {brief['narrative']}",
                f"- **Audience sentiment:** {brief.get('audience_sentiment', '—')}",
                f"- **Controversy (0–1):** {brief.get('controversy_score', 0):.2f}",
                f"- **Recommended format:** {brief.get('recommended_format', '—')}",
            ]
        )

    lines.extend(["", "---", "", "## Scored variants", ""])
    for row in report.variants:
        mark = " **← selected**" if row.get("selected") else ""
        lines.append(f"- **{row['score']:.2f}** — {row['variant']}{mark}")

    exp = report.explainability
    if exp:
        lines.extend(["", "---", "", "## Why now / why this", ""])
        if exp.get("why_now"):
            lines.append(f"**Why now:** {exp['why_now']}")
        if exp.get("why_this"):
            lines.append(f"**Why this angle:** {exp['why_this']}")
        if exp.get("contrarian_angle"):
            lines.append(f"**Contrarian hook:** {exp['contrarian_angle']}")

    lines.extend(["", "---", "", "## Signal rationale", ""])
    if report.signal_breakdown:
        sorted_parts = sorted(report.signal_breakdown.items(), key=lambda x: x[1], reverse=True)
        for name, weight in sorted_parts:
            lines.append(f"- **{name}:** {weight:.3f} weighted contribution")
    else:
        lines.append("- No active weighted signals for this variant.")

    if exp.get("signals_fired"):
        lines.extend(["", "### Signals fired (selected variant)", ""])
        for row in exp["signals_fired"][:8]:
            conf = row.get("confidence", 0)
            lines.append(
                f"- **{row['signal']}:** score {row['score']:.0f}, "
                f"weight share {row['weighted_contribution']:.3f}, "
                f"confidence {conf:.2f}"
            )

    lines.extend(["", "### Signal health (base topic)", ""])
    for health in report.signal_health.values():
        lines.append(f"- {health}")

    if brief.get("debate_angles"):
        lines.extend(["", "---", "", "## Debate angles", ""])
        for angle in brief["debate_angles"]:
            lines.append(f"- {angle}")

    if brief.get("supporting_evidence"):
        lines.extend(["", "## Supporting evidence", ""])
        for ev in brief["supporting_evidence"]:
            lines.append(f"- {ev}")

    if brief.get("stats_lines"):
        lines.extend(["", "## Reference stats", ""])
        for stat in brief["stats_lines"]:
            lines.append(f"- {stat}")

    if report.competitor_titles:
        lines.extend(["", "---", "", "## Competitor pulse", ""])
        if report.competitor_snapshot_age_hours is not None:
            lines.append(f"_Snapshot age: {report.competitor_snapshot_age_hours:.0f}h_")
            lines.append("")
        for row in report.competitor_titles:
            ch = row.get("channel", "?")
            title = row.get("title", "")
            lines.append(f"- **[{ch}]** {title}")

    if brief.get("rss_headlines"):
        lines.extend(["", "## RSS headlines", ""])
        for h in brief["rss_headlines"][:8]:
            lines.append(f"- {h.get('title', '')} ({h.get('source', '')})")

    if brief.get("community_summary"):
        lines.extend(["", "## Community pulse (RSS)", "", brief["community_summary"]])

    if report.accuracy.get("summary"):
        lines.extend(["", "---", "", "## Analyst self-measurement", ""])
        lines.append(f"_{report.accuracy['summary']}_")
        if report.accuracy.get("status") == "ok":
            lines.append(
                f"- Hit rate: **{report.accuracy.get('hit_rate', 0):.0%}** "
                f"(n={report.accuracy.get('runs_with_metrics', 0)})"
            )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Provenance & measurement",
            "",
            f"- Report: `{report.provenance.get('report_version', REPORT_VERSION)}`",
            f"- Brief: `{report.provenance.get('brief_version', BRIEF_VERSION)}`",
            f"- Channel profile domain: `{report.provenance.get('channel_domain', '')}`",
            "",
            "_Intelligence layer only — no script, TTS, or render in this output._",
        ]
    )

    if report.timings:
        total = sum(report.timings.values())
        timing_parts = ", ".join(f"{k}={v:.1f}s" for k, v in report.timings.items())
        lines.extend(["", f"_Pipeline timing: {timing_parts} (total ~{total:.1f}s)_"])

    return "\n".join(lines) + "\n"


def print_report_summary(report: IntelligenceReport, *, print_fn=print) -> None:
    print_fn()
    print_fn(f"  Opportunity score: {report.composite_score:.2f} ({report.domain})")
    print_fn(f"  Selected: {report.selected_variant}")
    if report.research_brief.get("narrative"):
        print_fn(f"  Narrative: {report.research_brief['narrative'][:120]}…")


def _cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Content Intelligence Report (no video production)"
    )
    parser.add_argument("--topic", required=True, help="Topic to analyze")
    parser.add_argument("--channel", default=None, help="Channel profile id")
    parser.add_argument(
        "--variant",
        type=int,
        default=0,
        help="Variant index 1-N (0 = highest score)",
    )
    parser.add_argument(
        "--no-brief",
        action="store_true",
        help="Skip LLM research brief (faster, scores only)",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory for report files (default: output/{channel}/reports/)",
    )
    parser.add_argument(
        "--format",
        default="md,json",
        help="Comma-separated: md, json (default: both)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print Markdown to stdout instead of saving files",
    )
    args = parser.parse_args(argv)

    setup_logging()
    channel_id = resolve_channel_id(args.channel)

    variant_index = None
    if args.variant and args.variant > 0:
        variant_index = args.variant - 1

    _, report = run_intelligence(
        args.topic,
        channel_id=channel_id,
        variant_index=variant_index,
        include_brief=not args.no_brief,
    )

    formats = tuple(f.strip() for f in args.format.split(",") if f.strip())

    if args.stdout:
        print(to_markdown(report))
        return 0

    paths = save_report(
        report,
        out_dir=args.out_dir,
        formats=formats,  # type: ignore[arg-type]
    )
    for kind, path in paths.items():
        print(f"Wrote {kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
