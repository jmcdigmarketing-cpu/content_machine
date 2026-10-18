"""Channel Health Agent (Pillar 5) - one Green/Yellow/Red read per channel.

Composes the signals the other pillars already expose into a single operational
health verdict - the "is this channel OK right now?" glance. Rules only, no LLM;
read-only and fail-open per sub-score (the `creator_coach` pattern): a subsystem
that errors reads **yellow "n/a"**, never crashes the view.

Sub-scores (each `green|yellow|red` + a one-line rationale):
- **engagement** - recent engaged-rate vs the channel baseline (trend).
- **cadence** - headroom under `MAX_VIDEOS_PER_WEEK` when one is set (decision 65: none by default).
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
    why: list[str] = field(default_factory=list)  # #1271: what a falling metric has in common


@dataclass
class HealthReport:
    channel_id: str
    overall: str = YELLOW
    subs: list[HealthSub] = field(default_factory=list)


def _worst(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: _RANK.get(s, 1)) if statuses else YELLOW


# #1238: run 119 - 3 views, 0% engaged - turned engagement RED on its own.
HEALTH_MIN_VIEWS = 20


def _engagement_sub(channel_id: str) -> HealthSub:
    from core.engagement_predictor import run_engagement_map

    rates = run_engagement_map(channel_id, min_views=HEALTH_MIN_VIEWS)  # {run_id: engaged_rate}
    everything = run_engagement_map(channel_id)
    left = len(everything) - len(rates)
    if len(rates) < 3:
        return HealthSub("engagement", YELLOW, f"collecting ({len(rates)} measured)")
    ordered = [rates[rid] for rid in sorted(rates)]
    baseline = sum(ordered) / len(ordered)
    recent = ordered[-5:]
    recent_mean = sum(recent) / len(recent)
    delta = recent_mean - baseline
    span = sorted(rates)[-5:]
    # #1291: "recent" was runs 109-133 (Oct 1-10) while four newer videos had no rate yet.
    detail = (
        f"recent {recent_mean * 100:.1f}% (runs {span[0]}-{span[-1]}) vs baseline "
        f"{baseline * 100:.1f}% ({delta * 100:+.1f}pp)"
    )
    if left > 0:
        plural = "video" if left == 1 else "videos"
        detail += f"; {left} {plural} under {HEALTH_MIN_VIEWS} views left out"
    unmeasured = _unmeasured_recent(channel_id, measured=set(everything))
    if unmeasured:
        plural = "video" if len(unmeasured) == 1 else "videos"
        detail += (
            f"; {len(unmeasured)} newer {plural} not measured yet "
            f"(runs {', '.join(str(r) for r in unmeasured)})"
        )
    if delta < -0.01:
        why = engagement_why(rates, _engagement_info(list(rates)))
        status, word = (RED, "declining") if delta < -0.05 else (YELLOW, "softening")
        return HealthSub("engagement", status, f"{word} - " + detail, why=why)
    return HealthSub("engagement", GREEN, "steady/up - " + detail)


def _unmeasured_recent(channel_id: str, *, measured: set[int], days: float = 7.0) -> list[int]:
    """Public videos of the last ``days`` with no engaged rate yet - YouTube's numbers lag."""
    from datetime import datetime, timedelta, timezone

    try:
        from storage.repositories.publish_log import get_publish_log_repository

        rows = get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
    except Exception as exc:
        logger.debug("unmeasured videos unread: %s", exc)
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out: set[int] = set()
    for row in rows:
        run_id = getattr(row, "content_run_id", None)
        when = getattr(row, "published_at", None)
        if isinstance(when, str):
            try:
                when = datetime.fromisoformat(when.replace("Z", "+00:00"))
            except ValueError:
                when = None
        if not run_id or int(run_id) in measured or not isinstance(when, datetime):
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= since:
            out.add(int(run_id))
    return sorted(out)


def _engagement_info(run_ids: list[int]) -> dict[int, dict[str, object]]:
    """Per run: domain, video length, hook score and footage - what `engagement_why` compares."""
    import json

    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    out: dict[int, dict[str, object]] = {}
    for run_id in run_ids:
        try:
            run = repo.get(int(run_id))
            features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
            quality = json.loads(getattr(run, "quality_json", "") or "{}") if run else {}
        except Exception as exc:
            logger.debug("engagement info for run %s unread: %s", run_id, exc)
            continue
        out[int(run_id)] = {
            "domain": features.get("domain") or "",
            "seconds": (features.get("technical_qc") or {}).get("video_duration"),
            "hook": quality.get("hook_score"),
            "footage": str(quality.get("footage") or "").split(" ")[0],
        }
    return out


def _length_band(info: dict[str, object]) -> str:
    try:
        seconds = float(info.get("seconds") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return "over 75 s" if seconds > 75 else ("under 45 s" if seconds < 45 else "45-75 s")


def _hook_band(info: dict[str, object]) -> str:
    try:
        hook = float(info.get("hook") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if hook <= 0:
        return ""
    return "a hook under 70" if hook < 70 else "a hook of 70+"


_WHY_FACTORS = (
    ("run", _length_band),
    ("are", lambda i: f"{i.get('domain')} videos" if i.get("domain") else ""),
    ("have", _hook_band),
    ("use", lambda i: f"{i.get('footage')} footage" if i.get("footage") else ""),
)


def engagement_why(rates: dict[int, float], info: dict[int, dict[str, object]]) -> list[str]:
    """#1271: the one thing most of the last five share that the channel's better videos do not
    - "4 of the last 5 run over 75 s: those average 20% against 35% for the rest". [] when no
    such thing stands out, or with too few videos to say."""
    from collections import Counter

    ordered = sorted(rates)
    recent = ordered[-5:]
    if len(ordered) < 8 or len(recent) < 3:
        return []
    best: tuple[float, str] | None = None
    for verb, band in _WHY_FACTORS:
        groups = {run: band(info.get(run, {})) for run in ordered}
        labels = Counter(groups[run] for run in recent if groups[run])
        if not labels:
            continue
        label, count = labels.most_common(1)[0]
        inside = [rates[run] for run in ordered if groups[run] == label]
        rest = [rates[run] for run in ordered if groups[run] and groups[run] != label]
        if count < 3 or len(inside) < 2 or not rest:
            continue
        mean_in, mean_rest = sum(inside) / len(inside), sum(rest) / len(rest)
        gap = mean_rest - mean_in
        if gap <= 0.02:
            continue
        line = (
            f"{count} of the last {len(recent)} {verb} {label}: those average {mean_in:.0%} "
            f"against {mean_rest:.0%} for the rest"
        )
        if best is None or gap * count > best[0]:
            best = (gap * count, line)
    if best:
        return [best[1]]
    # Live, 2026-10-17: no shared trait (the long videos did better) - one video drags it.
    weakest = min(recent, key=lambda run: rates[run])
    baseline = sum(rates[run] for run in ordered) / len(ordered)
    if baseline - rates[weakest] <= 0.05:
        return []
    traits = info.get(weakest, {})
    parts = [str(traits.get("domain") or "")]
    try:
        seconds = float(traits.get("seconds") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds > 0:
        parts.append(f"{seconds:.0f} s")
    hook = traits.get("hook")
    if isinstance(hook, (int, float)) and hook:
        parts.append(f"hook {hook:.0f}")
    described = ", ".join(part for part in parts if part)
    return [
        f"no one thing the last {len(recent)} share - the weakest is run {weakest}"
        + (f" ({described})" if described else "")
        + f" at {rates[weakest]:.0%}, against {baseline:.0%}"
    ]


def _cadence_sub(channel_id: str) -> HealthSub:
    from core.cadence import cadence_status

    c = cadence_status(channel_id)
    if not c.capped:  # decision 65: no cap
        return HealthSub("cadence", GREEN, f"{c.total} in the {c.window_days}-day window, no cap")
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
        lines.extend(f"      why: {line}" for line in s.why)
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
