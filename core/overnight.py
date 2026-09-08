"""Overnight operator (Pillar 5) — the whole loop, chained and unattended.

One command that composes the pillars into a hands-off overnight run:

    best-bet topics  →  batch drafts (graded + verified, Pillar 2/3)
                     →  vault dossiers (Pillar 4)
                     →  channel-health snapshot (Pillar 5)

Render-free by construction (it calls `batch_generation.run_batch`, which drafts
scripts only — no TTS/render/publish), so it is **cadence-safe**: drafts wake up
graded, verified, and dossier'd for the operator to approve. Emits an
`overnight_completed` webhook (`core/events.py`). Schedulable like `daily_sync`
(Task Scheduler / cron).

    py -m scripts.ops overnight --channel tapin --count 3
    py -m core.overnight --channel tapin --file ideas.txt
    py -m scripts.ops overnight --facts-file facts.txt --file ideas.txt

`--file` is topics (one per line). `--facts-file` is operator key facts, parsed
the same way as `auto_generate --facts-file` and passed through
`run_batch(..., key_facts=)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.overnight")


@dataclass
class OvernightResult:
    channel_id: str
    requested: int = 0
    drafted: int = 0
    dossiers: int = 0
    outcomes: list[Any] = field(default_factory=list)
    health_line: str = ""
    skillopt_line: str = ""
    quota_line: str = ""
    pause_line: str = ""
    canary_line: str = ""


def run_overnight(
    channel_id: str | None = None,
    *,
    count: int = 3,
    topics: list[str] | None = None,
    file: str | None = None,
    facts_file: str | None = None,
) -> OvernightResult:
    """Chain best-bet → drafts → dossiers → health. Fail-open at every step."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    result = OvernightResult(channel_id=channel)

    try:
        from core.overnight_pause import is_paused

        if is_paused():
            result.pause_line = "Overnight paused by operator flag."
            return result
    except Exception as exc:
        logger.debug("overnight pause check skipped: %s", exc)

    try:
        return _run_overnight_body(
            channel,
            result,
            count=count,
            topics=topics,
            file=file,
            facts_file=facts_file,
        )
    finally:
        _probe_signals(result)


def _probe_signals(result: OvernightResult) -> None:
    """#663. Nightly liveness, fail-open, never via all-checks (CI has no network)."""
    try:
        from core.signal_canary import check_signals, render, save_results

        rows = check_signals()
        save_results(rows)
        result.canary_line = render(rows)
    except Exception as exc:
        logger.debug("overnight signal canary skipped: %s", exc)


def _run_overnight_body(
    channel: str,
    result: OvernightResult,
    *,
    count: int,
    topics: list[str] | None,
    file: str | None,
    facts_file: str | None,
) -> OvernightResult:
    from core.batch_generation import collect_topics, run_batch
    from core.operator_facts import load_key_facts

    want = count
    try:
        from core.overnight_quota import adjust_count

        want, quota_reason = adjust_count(count)
        if quota_reason:
            result.quota_line = quota_reason
        if want <= 0:
            logger.warning("overnight skipped by quota gate: %s", quota_reason)
            result.requested = 0
            return result
    except Exception as exc:
        logger.debug("overnight quota gate skipped: %s", exc)

    picked = collect_topics(channel, topics, file, want)
    result.requested = len(picked)
    if not picked:
        logger.warning("overnight: no topics (best bets unavailable) for %s", channel)
        return result

    key_facts = load_key_facts(facts_file) if facts_file else None
    if key_facts:
        result.outcomes = run_batch(channel, picked, key_facts=key_facts)
    else:
        result.outcomes = run_batch(channel, picked)
    result.drafted = sum(1 for o in result.outcomes if getattr(o, "ok", False))

    # Mirror each drafted run into the vault (Pillar 4). run_batch persists a
    # content_run per draft, so dossiers can join grade/quality/cost by run_id.
    try:
        from core.vault_dossiers import write_run_dossier

        for o in result.outcomes:
            rid = getattr(o, "run_id", None)
            if getattr(o, "ok", False) and rid and write_run_dossier(rid):
                result.dossiers += 1
    except Exception as exc:
        logger.debug("overnight dossier step skipped: %s", exc)

    try:
        from core.channel_health import build_health, health_line

        result.health_line = health_line(build_health(channel))
    except Exception:
        result.health_line = ""

    # Pillar 7: nightly SkillOpt-Sleep — gated skill-directive optimization. Opt-in (LLM
    # calls) and fail-open; only proposes gate-beating directives, never edits live prompts.
    import os

    if os.getenv("SKILLOPT_ENABLED", "false").lower() in ("1", "true", "yes"):
        try:
            from core.skillopt import run_skillopt

            r = run_skillopt(channel)
            if r.improved:
                result.skillopt_line = (
                    f"SkillOpt: proposed a directive (+{r.margin:.1f} vs baseline) "
                    f"-> {r.proposal_path or 'vault unset'}"
                )
            elif r.n_topics:
                result.skillopt_line = "SkillOpt: no candidate beat the gate (prompts unchanged)"
        except Exception as exc:
            logger.debug("overnight skillopt step skipped: %s", exc)

    try:
        from core.events import emit_event

        emit_event(
            "overnight_completed",
            {
                "channel_id": channel,
                "requested": result.requested,
                "drafted": result.drafted,
                "dossiers": result.dossiers,
                "health": result.health_line,
            },
        )
    except Exception as exc:
        logger.debug("overnight event not emitted: %s", exc)
    try:
        from core.win_notify import notify_overnight_done

        notify_overnight_done(result.drafted, result.requested)
    except Exception as exc:
        logger.debug("overnight toast skipped: %s", exc)
    try:
        from core.retraction_watch import notify_retractions_if_due

        notify_retractions_if_due(channel)
    except Exception as exc:
        logger.debug("overnight retraction toast skipped: %s", exc)
    if topics:
        try:
            from core.best_bet import get_best_bet
            from core.counterfactual import record_override

            bet = get_best_bet(channel)
            picked = {str(t) for t in topics}
            if bet and bet.topic not in picked:
                record_override(bet.topic, ";".join(topics))
        except Exception as exc:
            logger.debug("overnight counterfactual skipped: %s", exc)
    return result


def render_overnight(result: OvernightResult) -> str:
    from core.batch_generation import render_summary

    lines = [f"Overnight operator — {result.channel_id}", "=" * 44]
    if result.pause_line:
        lines.append(result.pause_line)
        lines.append("Nothing drafted. Resume from the tray before the next scheduled run.")
        return "\n".join(lines)
    if result.quota_line:
        lines.append(f"Quota: {result.quota_line}")
    if not result.requested:
        if result.quota_line:
            lines.append("Overnight skipped (quota gate). Nothing drafted.")
        else:
            lines.append("No topics to draft (best bets unavailable). Nothing done.")
        if result.canary_line:
            lines.append("")
            lines.append(result.canary_line)
        return "\n".join(lines)
    try:
        lines.append(render_summary(result.outcomes).strip())
    except Exception:
        lines.append(f"{result.drafted}/{result.requested} drafts saved")
    lines.append("")
    lines.append(f"Dossiers written to vault: {result.dossiers}")
    if result.health_line:
        lines.append(result.health_line)
    if result.skillopt_line:
        lines.append(result.skillopt_line)
    if result.canary_line:
        lines.append("")
        lines.append(result.canary_line)
    lines.append("Review drafts in output/<channel>/drafts/, then approve to render.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Overnight operator (drafts + grade + dossiers)")
    parser.add_argument("--channel", default=None)
    parser.add_argument("--count", type=int, default=3, help="Best-bet topics when none given")
    parser.add_argument("--file", default=None, help="File of topics (one per line)")
    parser.add_argument(
        "--facts-file",
        default=None,
        help="Operator key facts (paste-block file; same as auto_generate --facts-file)",
    )
    parser.add_argument("topics", nargs="*", help="Explicit topics")
    args = parser.parse_args(argv)
    result = run_overnight(
        args.channel,
        count=args.count,
        topics=args.topics or None,
        file=args.file,
        facts_file=args.facts_file,
    )
    print(render_overnight(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
