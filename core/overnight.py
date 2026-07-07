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

Facts-file intake (like `auto_generate --facts-file`) is a planned follow-up —
it needs `batch_generation.generate_draft` to accept key facts first.
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


def run_overnight(
    channel_id: str | None = None,
    *,
    count: int = 3,
    topics: list[str] | None = None,
    file: str | None = None,
) -> OvernightResult:
    """Chain best-bet → drafts → dossiers → health. Fail-open at every step."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    result = OvernightResult(channel_id=channel)

    from core.batch_generation import collect_topics, run_batch

    picked = collect_topics(channel, topics, file, count)
    result.requested = len(picked)
    if not picked:
        logger.warning("overnight: no topics (best bets unavailable) for %s", channel)
        return result

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
    except Exception:
        pass
    return result


def render_overnight(result: OvernightResult) -> str:
    from core.batch_generation import render_summary

    lines = [f"Overnight operator — {result.channel_id}", "=" * 44]
    if not result.requested:
        lines.append("No topics to draft (best bets unavailable). Nothing done.")
        return "\n".join(lines)
    try:
        lines.append(render_summary(result.outcomes).strip())
    except Exception:
        lines.append(f"{result.drafted}/{result.requested} drafts saved")
    lines.append("")
    lines.append(f"Dossiers written to vault: {result.dossiers}")
    if result.health_line:
        lines.append(result.health_line)
    lines.append("Review drafts in output/<channel>/drafts/, then approve to render.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Overnight operator (drafts + grade + dossiers)")
    parser.add_argument("--channel", default=None)
    parser.add_argument("--count", type=int, default=3, help="Best-bet topics when none given")
    parser.add_argument("--file", default=None, help="File of topics (one per line)")
    parser.add_argument("topics", nargs="*", help="Explicit topics")
    args = parser.parse_args(argv)
    result = run_overnight(
        args.channel, count=args.count, topics=args.topics or None, file=args.file
    )
    print(render_overnight(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
