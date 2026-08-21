"""Unattended render-queue gate (candidate 58).

Overnight drafts are render-free; the cron path that *does* render is
``scripts/auto_generate`` plus any ``job_type=render`` worker job. Unattended
volume cannot tank the 2026 policy: report card ≥ B **and** authenticity ``ok``,
or the render does not start. Interactive ``main.py`` stays operator-controlled.

Missing grade/verdict fail-closed (the candidate is a require-both gate).
``--force`` / ``OVERNIGHT_RENDER_GATE=false`` bypass. Verifier import failures
fail-open so a broken grade module cannot freeze the worker.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.render_gate")

_PASS_LETTERS = frozenset({"A", "B"})
_AUTH_OK = "ok"


def gate_enabled() -> bool:
    return os.getenv("OVERNIGHT_RENDER_GATE", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def unattended_render_block_reason(
    *,
    letter: str | None,
    authenticity_verdict: str | None,
) -> str | None:
    """Why an unattended render must not start, or None when both bars pass."""
    if not gate_enabled():
        return None
    grade = (letter or "").strip().upper()
    if grade not in _PASS_LETTERS:
        shown = grade or "missing"
        return f"unattended render gate: report card {shown} (need >= B)"
    verdict = (authenticity_verdict or "").strip().lower()
    if verdict != _AUTH_OK:
        shown = verdict or "missing"
        return f"unattended render gate: authenticity {shown} (need ok)"
    return None


def block_reason_from_quality(quality: dict[str, Any] | None) -> str | None:
    """Roll a persisted quality dict into the same gate (worker / auto_generate)."""
    if not gate_enabled():
        return None
    quality = quality or {}
    letter = ""
    try:
        from core.video_grade import grade_from_parts

        grade = grade_from_parts(quality=quality)
        letter = grade.letter
    except Exception as exc:
        logger.debug("render-gate grade rollup skipped: %s", exc)
        return None  # fail-open: a broken grader must not freeze the worker
    return unattended_render_block_reason(
        letter=letter,
        authenticity_verdict=str(quality.get("authenticity_verdict") or ""),
    )


def block_reason_for_run(run_id: int | None) -> str | None:
    """Load quality_json for a run and apply the gate. Missing run fail-closes."""
    if not gate_enabled():
        return None
    if not run_id:
        return unattended_render_block_reason(letter=None, authenticity_verdict=None)
    try:
        from core.run_quality import load_quality

        quality = load_quality(run_id)
    except Exception as exc:
        logger.debug("render-gate quality load skipped for run %s: %s", run_id, exc)
        return None
    if not quality:
        return unattended_render_block_reason(letter=None, authenticity_verdict=None)
    return block_reason_from_quality(quality)
