"""Run Ledger viewers (Pillar 1) — `ops traces` and `ops dossier`.

Read-only joins over what the ledger now persists:

- ``render_traces``  — recent runs from ``data/traces/`` (core/run_trace.py):
  status, total time + slowest phase, LLM cost, hook/authenticity, experiment arm.
- ``render_dossier`` — one run end-to-end: content_runs row + features_json +
  quality_json + trace + publish metrics + experiment arm.

Everything is fail-open: a missing table/file shows as "n/a", never raises.
"""

from __future__ import annotations

import json
from typing import Any

_PHASE_KEYS = (
    "signals_and_variants",
    "variant_scoring",
    "research_brief",
    "content_package",
)


def _fmt_secs(value: Any) -> str:
    try:
        return f"{float(value):.1f}s"
    except (TypeError, ValueError):
        return "?"


def _phase_times(timings: dict[str, Any]) -> list[tuple[str, float]]:
    out = []
    for key in _PHASE_KEYS:
        try:
            out.append((key, float(timings.get(key))))
        except (TypeError, ValueError):
            continue
    return out


def render_traces(limit: int = 10, *, channel_id: str | None = None) -> str:
    """Recent-runs table + hotspot summary from the trace files."""
    from core.run_trace import list_traces

    traces = list_traces(limit=limit, channel_id=channel_id)
    if not traces:
        return "No run traces yet - traces appear in data/traces/ after the next run."

    lines = [f"Run traces (most recent {len(traces)})", "=" * 72]
    slowest_phase_counts: dict[str, int] = {}
    for t in traces:
        timings = t.get("timings") or {}
        phases = _phase_times(timings)
        total = sum(s for _, s in phases)
        slowest = max(phases, key=lambda p: p[1]) if phases else ("", 0.0)
        if slowest[0]:
            slowest_phase_counts[slowest[0]] = slowest_phase_counts.get(slowest[0], 0) + 1
        quality = t.get("quality") or {}
        hook = quality.get("hook_score")
        auth = quality.get("authenticity_score")
        exp = t.get("experiment") or {}
        topic = str(t.get("selected_topic") or t.get("input_topic") or "")[:38]
        lines.append(
            f"  #{t.get('run_id'):<5} {t.get('status', '')!s:<9} {topic:<38} "
            f"{_fmt_secs(total):>7}  llm ${float(t.get('llm_cost_usd') or 0):.3f}"
            f"  hook {hook if hook is not None else '--':>3}"
            f"  auth {auth if auth is not None else '--':>3}"
            + (f"  [{exp.get('lever')}:{exp.get('arm')}]" if exp.get("arm") else "")
        )
        if slowest[0]:
            lines.append(f"          slowest: {slowest[0]} ({_fmt_secs(slowest[1])})")
        failed = [
            name
            for name, sig in (t.get("signals") or {}).items()
            if isinstance(sig, dict) and sig.get("status") not in (None, "", "ok")
        ]
        if failed:
            lines.append(f"          signals not-ok: {', '.join(sorted(failed)[:6])}")
    if slowest_phase_counts:
        top = max(slowest_phase_counts.items(), key=lambda kv: kv[1])
        lines.append("-" * 72)
        lines.append(f"Hotspot: '{top[0]}' was the slowest phase in {top[1]}/{len(traces)} runs")
    return "\n".join(lines)


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _publish_for_run(run_id: int, channel_id: str) -> dict[str, Any]:
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        repo = get_publish_log_repository()
        for row in repo.list_uploaded_for_channel(channel_id):
            if row.content_run_id == run_id:
                return {
                    "youtube_video_id": row.youtube_video_id,
                    "status": getattr(row, "status", ""),
                    "metrics": _load_json(row.metrics_json),
                }
    except Exception:
        pass
    return {}


def render_dossier(run_id: int) -> str:
    """One joined, human-readable view of a single run."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
    except Exception:
        record = None
    if record is None:
        return f"No content run #{run_id} found."

    features = _load_json(record.features_json)
    quality = _load_json(record.quality_json)
    timings = _load_json(record.timings_json)

    lines = [f"Run dossier - #{run_id}", "=" * 72]
    lines.append(f"Channel : {record.channel_id}   Status: {record.status}")
    lines.append(f"Topic   : {record.selected_topic or record.input_topic}")
    if record.title:
        lines.append(f"Title   : {record.title}")
    lines.append(f"Score   : composite {record.composite_score:.1f}")
    if record.abort_reason:
        lines.append(f"Aborted : {record.abort_reason}")

    if quality:
        lines.append("Quality :")
        if quality.get("hook_score") is not None:
            lines.append(f"  hook {quality['hook_score']}/100 ({quality.get('hook_verdict', '?')})")
        if quality.get("authenticity_score") is not None:
            lines.append(
                f"  authenticity {quality['authenticity_score']}/100 "
                f"({quality.get('authenticity_verdict', '?')})"
            )
        if quality.get("ungrounded_count") is not None:
            lines.append(f"  ungrounded specifics: {quality['ungrounded_count']}")
        if quality.get("trade_warning_count"):
            lines.append(f"  trade warnings: {quality['trade_warning_count']}")
        if quality.get("claim_support_rate") is not None:
            rate = float(quality["claim_support_rate"] or 0)
            unsupported = int(quality.get("unsupported_claim_count") or 0)
            lines.append(
                f"  claim support: {rate * 100:.0f}%"
                + (f" ({unsupported} unsupported)" if unsupported else "")
            )
        if quality.get("fact_conflict_count"):
            lines.append(f"  fact conflicts: {quality['fact_conflict_count']}")
        if quality.get("tier_warning_count"):
            lines.append(f"  tier warnings: {quality['tier_warning_count']}")
        if quality.get("thumbnail_overall") is not None:
            lines.append(
                f"  thumbnail {quality['thumbnail_overall']}/100 "
                f"({quality.get('thumbnail_source', '?')})"
            )

    cost = features.get("cost") or {}
    if cost:
        total = cost.get("total")
        parts = ", ".join(
            f"{k} ${v:.3f}"
            for k, v in cost.items()
            if k != "total" and isinstance(v, int | float) and v
        )
        lines.append(f"Cost    : ${total:.3f}" + (f"  ({parts})" if parts else ""))

    if features:
        keep = ("domain", "format", "angle", "title_structure", "fact_source", "key_facts_count")
        feats = ", ".join(f"{k}={features[k]}" for k in keep if features.get(k) not in (None, ""))
        if feats:
            lines.append(f"Features: {feats}")

    phases = _phase_times(timings)
    if phases:
        lines.append("Timings : " + ", ".join(f"{name} {_fmt_secs(secs)}" for name, secs in phases))

    try:
        from core.experiments import assignment_for_run

        exp = assignment_for_run(run_id)
        if exp and exp.get("arm"):
            lines.append(f"Experiment: {exp['lever']} -> arm '{exp['arm']}'")
    except Exception:
        pass

    publish = _publish_for_run(run_id, record.channel_id)
    if publish:
        metrics = publish.get("metrics") or {}
        lines.append(f"Publish : {publish.get('youtube_video_id', '?')}")
        if metrics:
            lines.append(
                f"  views {metrics.get('views', '?')}, "
                f"engaged {float(metrics.get('engaged_rate', 0) or 0) * 100:.1f}%, "
                f"likes {metrics.get('likes', '?')}"
            )
            if metrics.get("estimated_revenue_usd") is not None:
                revenue = float(metrics["estimated_revenue_usd"] or 0)
                total_cost = float((cost or {}).get("total") or 0)
                lines.append(
                    f"  revenue ${revenue:.2f} - margin ${revenue - total_cost:+.2f}"
                    " (est., 28d window)"
                )
    else:
        lines.append("Publish : (not uploaded)")

    from core.run_trace import read_trace

    trace = read_trace(run_id)
    if trace:
        calls = trace.get("llm_calls") or []
        lines.append(
            f"LLM     : {len(calls)} call(s), ${float(trace.get('llm_cost_usd') or 0):.4f}"
        )
        by_tier: dict[str, int] = {}
        for c in calls:
            tier = str(c.get("tier", "?"))
            by_tier[tier] = by_tier.get(tier, 0) + 1
        if by_tier:
            lines.append("  " + ", ".join(f"{tier}x{n}" for tier, n in sorted(by_tier.items())))
    else:
        lines.append("LLM     : (no trace - run predates the ledger)")
    return "\n".join(lines)
