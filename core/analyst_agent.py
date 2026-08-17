"""Weekly analyst agent (Pillar 5) — one LLM pass over everything the pillars know.

Composes the rules-based intelligence the other pillars already produce (weekly
report, grade calibration, channel health, recent run traces, coach ideas, unit
economics) into a bounded context and asks the **premium** LLM tier for a short
prose briefing with 3–5 concrete lever changes for next week.

The only Pillar-5 component that spends an LLM call — and it's fail-open: any LLM
or assembly error falls back to the **rules-only** next-actions from the weekly
report, so `ops analyst` always returns something useful. The briefing is written
to the vault (`{channel}/_reports/{date}_analyst.md`, Pillar 4) and emitted on the
`analyst_briefing` webhook (`core/events.py`).

    py -m scripts.ops analyst --channel tapin
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger("core.analyst_agent")

_SYSTEM = (
    "You are the channel's weekly performance analyst for a short-form YouTube "
    "operation. You are given rules-based readouts (engagement by dimension, "
    "pre-publish grade vs realized engagement, operational health, recent runs, "
    "cost). Write a tight briefing (<220 words) for the solo operator: one "
    "headline read, 2-3 things working, 1-2 things not, then a numbered list of "
    "3-5 CONCRETE lever changes for next week (angle / length / post-time / hook "
    "style / topic to lean into or retire). Reference the data. No preamble, no "
    "fluff, no invented numbers — use only what's given."
)

_MAX_CONTEXT = 6000  # keep the premium call bounded


def _rules_fallback(channel_id: str) -> str:
    """Deterministic briefing from the weekly report's next-actions (no LLM)."""
    try:
        from analytics.weekly_report import build_next_actions, build_report

        report = build_report(channel_id)
        actions = build_next_actions(report) if report.get("ready") else []
    except Exception:
        actions = []
    lines = [f"Analyst briefing — {channel_id} (rules fallback)"]
    if actions:
        lines.append("Recommended lever changes:")
        lines.extend(f"  {i}. {a}" for i, a in enumerate(actions, 1))
    else:
        lines.append(
            "Not enough measured history yet — publish + sync metrics, then re-run. "
            "Meanwhile: keep cadence under the cap and lean on proven title patterns "
            "(see `ops coach`)."
        )
    return "\n".join(lines)


def _weekly_block(channel_id: str) -> str:
    from analytics.weekly_report import build_report, format_report

    return format_report(build_report(channel_id))


def _calibration_block(channel_id: str) -> str:
    from core.grade_calibration import build_calibration, summary_line

    return summary_line(build_calibration(channel_id)) or ""


def _health_block(channel_id: str) -> str:
    from core.channel_health import build_health, render_health

    return render_health(build_health(channel_id))


def _economics_block(channel_id: str) -> str:
    from core.unit_economics import channel_economics, summary_lines

    return "\n".join(summary_lines(channel_economics(channel_id)))


def _recent_runs_block(channel_id: str) -> str:
    from core.run_trace import list_traces

    rows = []
    for t in list_traces(limit=8, channel_id=channel_id):
        q = t.get("quality") or {}
        rows.append(
            f"- #{t.get('run_id')} [{t.get('status')}] "
            f"{str(t.get('selected_topic') or '')[:48]} "
            f"(hook {q.get('hook_score', '-')}, auth {q.get('authenticity_score', '-')})"
        )
    return "\n".join(rows)


_CONTEXT_BLOCKS = (
    ("Weekly report", _weekly_block),
    ("Grade calibration", _calibration_block),
    ("Channel health", _health_block),
    ("Unit economics", _economics_block),
    ("Recent runs", _recent_runs_block),
)


def _gather_context(channel_id: str) -> str:
    """Bounded, rules-derived context blocks for the LLM (each fail-open)."""
    blocks: list[str] = []
    for label, fn in _CONTEXT_BLOCKS:
        try:
            text = fn(channel_id)
            if text and str(text).strip():
                blocks.append(f"## {label}\n{str(text).strip()}")
        except Exception as exc:
            logger.debug("analyst context '%s' skipped: %s", label, exc)
    return "\n\n".join(blocks)[:_MAX_CONTEXT]


def build_analyst_brief(channel_id: str) -> str:
    """Prose briefing from the premium tier; rules-only fallback on any failure."""
    context = _gather_context(channel_id)
    if not context.strip():
        return _rules_fallback(channel_id)
    try:
        from core.llm_router import complete

        out = complete(
            f"Channel: {channel_id}\n\n{context}",
            tier="premium",
            system=_SYSTEM,
            temperature=0.4,
            max_tokens=700,
        )
        if out and out.strip():
            return out.strip()
    except Exception as exc:
        logger.info("analyst LLM call failed (%s) — using rules fallback", exc)
    return _rules_fallback(channel_id)


def run_analyst(channel_id: str | None = None) -> str:
    """Build the briefing, persist it to the vault, emit the webhook, return it."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    brief = build_analyst_brief(channel)

    try:
        from core.vault_dossiers import write_report_note

        write_report_note(channel, "analyst", "Weekly analyst briefing", brief, fenced=False)
    except Exception as exc:
        logger.debug("Analyst briefing not mirrored to the vault: %s", exc)
    try:
        from core.events import emit_event

        emit_event("analyst_briefing", {"channel_id": channel, "briefing": brief})
    except Exception as exc:
        logger.debug("analyst_briefing event not emitted: %s", exc)
    return brief


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Weekly analyst briefing (premium LLM)")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args(argv)
    print(run_analyst(args.channel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
