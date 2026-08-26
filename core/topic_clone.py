"""#36 Seed a new draft from a winner run — the write path behind display-only winners()."""

from __future__ import annotations

from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger("core.topic_clone")


@dataclass
class CloneResult:
    ok: bool
    topic: str = ""
    run_id: int | None = None
    error: str = ""


def clone_from_run(run_id: int, channel_id: str | None = None) -> CloneResult:
    """New draft, new angles, refreshed facts, cloned topic seed via generate_draft."""
    from storage.repositories.content_runs import get_content_run_repository

    record = get_content_run_repository().get(run_id)
    if record is None:
        return CloneResult(ok=False, error=f"no content run #{run_id}")
    seed = (record.input_topic or record.selected_topic or "").strip()
    if not seed:
        return CloneResult(ok=False, error="run has no topic seed")
    channel = channel_id or record.channel_id
    from core.batch_generation import generate_draft

    outcome = generate_draft(seed, channel)
    return CloneResult(
        ok=bool(outcome.ok),
        topic=outcome.topic or seed,
        run_id=outcome.run_id,
        error=outcome.error or "",
    )
