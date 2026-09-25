"""Channel Health Agent (Pillar 5) - one Green/Yellow/Red read per channel.

Composes the signals the other pillars already expose into a single operational
health verdict - the "is this channel OK right now?" glance. Rules only, no LLM;
read-only and fail-open per sub-score (the `creator_coach` pattern): a subsystem
that errors reads **yellow "n/a"**, never crashes the view.

Sub-scores (each `green|yellow|red` + a one-line rationale):
- **engagement** - recent engaged-rate vs the channel baseline (trend).
- **cadence** - headroom under `MAX_VIDEOS_PER_WEEK` (over-cadence is a policy risk).
- **authenticity** - mean authenticity score over recent runs' `quality_json`.
- **reliability** - Apify/LLM/signal breakers + budgets (`core/reliability.py`).
- **cost** - per-video cost, and margin when revenue exists (`core/unit_economics.py`).
- **data quality** - `core/data_quality.py` warnings (signal streaks, join gaps).

Overall folds worst-first (any red ⇒ red, any yellow ⇒ yellow). **Thin data reads
yellow "collecting," never green** - health is earned, not defaulted on.

Surfaced via `py -m scripts.ops health` and a line in `ops daily-brief`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger("core.channel_health")

GREEN, YELLOW, RED = "green", "yellow", "red"
_RANK = {GREEN: 0, YELLOW: 1, RED: 2}
_MARK = {GREEN: "+", YELLOW: "~", RED: "!"}  # cp1252-safe (ops doesn't force UTF-8)


@dataclass
class HealthSub:
    name: str
    status: str
    detail: str


@dataclass
class HealthReport:
    channel_id: str
    overall: str = YELLOW
    subs: list[HealthSub] = field(default_factory=list)


def _worst(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: _RANK.get(s, 1)) if statuses else YELLOW


def _engagement_sub(channel_id: str) -> HealthSub:
    from core.engagement_predictor import run_engagement_map

    rates = run_engagement_map(channel_id)  # {run_id: engaged_rate}
    if len(rates) < 3:
        return HealthSub("engagement", YELLOW, f"collecting ({len(rates)} measured)")
    ordered = [rates[rid] for rid in sorted(rates)]
    baseline = sum(ordered) / len(ordered)
    recent = ordered[-5:]
    recent_mean = sum(recent) / len(recent)
    delta = recent_mean - baseline
    detail = (
        f"recent {recent_mean * 100:.1f}% vs baseline {baseline * 100:.1f}% ({delta * 100:+.1f}pp)"
    )
    if delta < -0.05:
        return HealthSub("engagement", RED, "declining - " + detail)
    if delta < -0.01:
        return HealthSub("engagement", YELLOW, "softening - " + detail)
    return HealthSub("engagement", GREEN, "steady/up - " + detail)


def _cadence_sub(channel_id: str) -> HealthSub:
    from core.cadence import cadence_status

    c = cadence_status(channel_id)
    room = c.cap - c.total
    detail = f"{c.total}/{c.cap} in the {c.window_days}-day window"
    if c.total > c.cap:
        return HealthSub("cadence", RED, f"over cap - {detail} (authenticity/policy risk)")
    if room <= 1:
        return HealthSub("cadence", YELLOW, f"near cap - {detail}")
    return HealthSub("cadence", GREEN, f"room for {room} more - {detail}")


def _authenticity_sub(channel_id: str) -> HealthSub:
    import json

    from config.channels import resolve_channel_id
    from core.run_quality import authenticity_gate_value
    from storage.repositories.content_runs import get_content_run_repository

    channel = resolve_channel_id(channel_id)
    scores: list[float] = []
    for run in get_content_run_repository().list_for_channel(channel)[:15]:
        try:
            q = json.loads(run.quality_json or "{}")
        except Exception as exc:
            logger.debug("Unreadable quality_json on run %s: %s", run.id, exc)
            continue
        # #815: the binary gate sum, not #804's continuous grade — the 55/72
        # thresholds below were set when the gate sum was the only number.
        val = authenticity_gate_value(q)
        if val is not None:
            scores.append(val)
    if len(scores) < 3:
        return HealthSub("authenticity", YELLOW, f"collecting ({len(scores)} scored)")
    mean = sum(scores) / len(scores)
    detail = f"mean {mean:.0f}/100 over {len(scores)} recent"
    if mean < 55:
        return HealthSub("authenticity", RED, "thin/synthetic - " + detail)
    if mean < 72:
        return HealthSub("authenticity", YELLOW, "watch - " + detail)
    return HealthSub("authenticity", GREEN, "solid - " + detail)


def _reliability_sub() -> HealthSub:
    from core.reliability import gather

    data = gather()
    problems: list[str] = []
    apify = data.get("apify") or {}
    if apify.get("disabled") or apify.get("persisted_exhausted"):
        problems.append("Apify off")
    llm = data.get("llm") or {}
    disabled = llm.get("disabled_providers") or {}
    if disabled:
        problems.append(f"LLM {len(disabled)} provider(s) off")
    sig = data.get("signals") or {}
    persisted = sig.get("persisted") or {}
    if persisted:
        problems.append(f"{len(persisted)} signal(s) disabled")
    budget = llm.get("daily_budget")
    spend = llm.get("spend_today")
    over_budget = budget and spend and spend >= budget
    if over_budget:
        problems.append("LLM over daily budget")
    if not problems:
        return HealthSub("reliability", GREEN, "no breakers tripped")
    # LLM fully off would stop generation → red; degraded paid signals → yellow.
    status = RED if over_budget or "LLM" in " ".join(problems) else YELLOW
    return HealthSub("reliability", status, "; ".join(problems))


def _cost_sub(channel_id: str) -> HealthSub:
    from core.unit_economics import channel_economics

    econ = channel_economics(channel_id)
    if not econ.videos:
        return HealthSub("cost", YELLOW, "collecting (no uploaded videos)")
    n = len(econ.videos)
    avg = econ.total_cost / n
    margin = econ.total_margin
    if margin is not None:
        if margin < 0:
            return HealthSub("cost", RED, f"negative margin ${margin:+.2f} (rev < cost)")
        return HealthSub("cost", GREEN, f"positive margin ${margin:+.2f}, ${avg:.3f}/video")
    status = GREEN if avg <= 0.10 else YELLOW
    return HealthSub("cost", status, f"${avg:.3f}/video (revenue not synced)")


def _data_quality_sub(channel_id: str) -> HealthSub:
    from core.data_quality import warnings

    warns = warnings(channel_id=channel_id)
    if not warns:
        return HealthSub("data quality", GREEN, "no issues")
    status = RED if len(warns) >= 3 else YELLOW
    return HealthSub("data quality", status, f"{len(warns)} warning(s): {warns[0]}")


_CHECKS = (
    ("engagement", lambda ch: _engagement_sub(ch)),
    ("cadence", lambda ch: _cadence_sub(ch)),
    ("authenticity", lambda ch: _authenticity_sub(ch)),
    ("reliability", lambda _ch: _reliability_sub()),
    ("cost", lambda ch: _cost_sub(ch)),
    ("data quality", lambda ch: _data_quality_sub(ch)),
)


def build_health(channel_id: str | None = None) -> HealthReport:
    """Assemble the per-channel health verdict (read-only, fail-open per sub)."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    report = HealthReport(channel_id=channel)
    for name, check in _CHECKS:
        try:
            report.subs.append(check(channel))
        except Exception as exc:
            logger.debug("health sub '%s' skipped: %s", name, exc)
            report.subs.append(HealthSub(name, YELLOW, "n/a"))
    report.overall = _worst([s.status for s in report.subs])
    # Thin data must not read green: if every informative sub is "collecting/n/a",
    # hold at yellow.
    if report.overall == GREEN and all(
        ("collecting" in s.detail or s.detail == "n/a")
        for s in report.subs
        if s.name in ("engagement", "authenticity", "cost")
    ):
        report.overall = YELLOW
    return report


def render_health(report: HealthReport) -> str:
    lines = [
        f"Channel health - {report.channel_id}: {_MARK.get(report.overall, '~')} "
        f"{report.overall.upper()}",
        "=" * 52,
    ]
    for s in report.subs:
        lines.append(f"  {_MARK.get(s.status, '~')} {s.name:<13} {s.status.upper():<6} {s.detail}")
    return "\n".join(lines)


def health_line(report: HealthReport) -> str:
    """One-line summary for embedding (e.g. daily-brief)."""
    reds = [s.name for s in report.subs if s.status == RED]
    yellows = [s.name for s in report.subs if s.status == YELLOW]
    tail = ""
    if reds:
        tail = " - red: " + ", ".join(reds)
    elif yellows:
        tail = " - watch: " + ", ".join(yellows)
    return f"Health: {report.overall.upper()}{tail}"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Channel health (Green/Yellow/Red)")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args(argv)
    print(render_health(build_health(args.channel)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
