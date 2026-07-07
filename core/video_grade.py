"""Pre-publish video report card (Pillar 2 — Video Grading System).

Rolls the scorers that already exist (hook, authenticity, grounding, trade,
composite topic, thumbnail) into **one weighted 0–100 grade with a letter**,
reading the quality dict Pillar 1 now persists. Missing components renormalize
— a draft without a thumbnail is graded on what exists, not penalized for it.

Shown in the interactive flow before the render prompt, and on demand via
`py -m scripts.ops grade --run-id N`. When enough measured history exists the
grade also carries a **predicted engaged-rate band**
(core/engagement_predictor.py, data-gated).

Read-only and fail-open — grading never blocks a run (the authenticity gate
remains the only blocking check, per Phase O).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.video_grade")

GRADE_VERSION = "v1"

# Component weights (renormalized over the components actually present).
_WEIGHTS = {
    "hook": 0.28,
    "authenticity": 0.28,
    "grounding": 0.22,
    "topic": 0.12,
    "thumbnail": 0.10,
}

_UNGROUNDED_PENALTY = 25  # per unsupported specific
_TRADE_PENALTY = 20  # per trade-direction warning
# Pillar 3 (Fact Engine) penalties — advisory layers weigh less than hard
# token-grounding failures (they carry more false-positive risk).
_UNSUPPORTED_CLAIM_PENALTY = 15  # per LLM-verifier unsupported claim
_CONFLICT_PENALTY = 15  # per operator-vs-source fact conflict
_TIER_PENALTY = 10  # per grounding-tier warning


@dataclass
class GradeComponent:
    name: str
    score: float  # 0-100
    weight: float  # renormalized share of the final grade
    note: str = ""


@dataclass
class VideoGrade:
    score: float  # 0-100
    letter: str
    components: list[GradeComponent] = field(default_factory=list)
    predicted_engaged_rate: float | None = None
    prediction_note: str = ""


def _letter(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _grounding_score(quality: dict[str, Any]) -> tuple[float, str]:
    ungrounded = int(quality.get("ungrounded_count") or 0)
    trades = int(quality.get("trade_warning_count") or 0)
    unsupported = int(quality.get("unsupported_claim_count") or 0)
    conflicts = int(quality.get("fact_conflict_count") or 0)
    tiers = int(quality.get("tier_warning_count") or 0)
    score = max(
        0.0,
        100.0
        - _UNGROUNDED_PENALTY * ungrounded
        - _TRADE_PENALTY * trades
        - _UNSUPPORTED_CLAIM_PENALTY * unsupported
        - _CONFLICT_PENALTY * conflicts
        - _TIER_PENALTY * tiers,
    )
    notes = []
    if ungrounded:
        notes.append(f"{ungrounded} unsupported specific(s)")
    if trades:
        notes.append(f"{trades} trade warning(s)")
    if unsupported:
        notes.append(f"{unsupported} unsupported claim(s)")
    if conflicts:
        notes.append(f"{conflicts} fact conflict(s)")
    if tiers:
        notes.append(f"{tiers} tier warning(s)")
    return score, "; ".join(notes) or "fully grounded"


def grade_from_parts(
    *,
    quality: dict[str, Any],
    composite_score: float | None = None,
    channel_id: str | None = None,
) -> VideoGrade:
    """Pure rollup — quality dict (+ optional composite topic score) → grade."""
    raw: list[GradeComponent] = []

    hook = quality.get("hook_score")
    if hook is not None:
        raw.append(
            GradeComponent(
                "hook", float(hook), _WEIGHTS["hook"], str(quality.get("hook_verdict", ""))
            )
        )
    auth = quality.get("authenticity_score")
    if auth is not None:
        raw.append(
            GradeComponent(
                "authenticity",
                float(auth),
                _WEIGHTS["authenticity"],
                str(quality.get("authenticity_verdict", "")),
            )
        )
    if quality.get("ungrounded_count") is not None:
        g_score, g_note = _grounding_score(quality)
        raw.append(GradeComponent("grounding", g_score, _WEIGHTS["grounding"], g_note))
    if composite_score is not None and composite_score > 0:
        raw.append(
            GradeComponent(
                "topic", min(100.0, float(composite_score)), _WEIGHTS["topic"], "composite score"
            )
        )
    thumb = quality.get("thumbnail_overall")
    if thumb is not None:
        raw.append(
            GradeComponent(
                "thumbnail",
                float(thumb),
                _WEIGHTS["thumbnail"],
                str(quality.get("thumbnail_source", "")),
            )
        )

    if not raw:
        return VideoGrade(score=0.0, letter="F", components=[])

    total_weight = sum(c.weight for c in raw)
    components = [
        GradeComponent(c.name, c.score, round(c.weight / total_weight, 4), c.note) for c in raw
    ]
    score = round(sum(c.score * c.weight for c in components), 1)
    grade = VideoGrade(score=score, letter=_letter(score), components=components)

    if channel_id:
        try:
            from core.engagement_predictor import predict_engaged_rate

            prediction = predict_engaged_rate(channel_id, quality=quality)
            if prediction is not None:
                grade.predicted_engaged_rate = prediction.rate
                grade.prediction_note = prediction.note
        except Exception as exc:
            logger.debug("engagement prediction skipped: %s", exc)
    return grade


def grade_run(run_id: int) -> VideoGrade | None:
    """Grade a persisted run from its quality_json + composite score."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
    except Exception:
        record = None
    if record is None:
        return None
    from core.run_quality import load_quality

    quality = load_quality(run_id)
    if not quality:
        return None
    return grade_from_parts(
        quality=quality,
        composite_score=float(record.composite_score or 0),
        channel_id=record.channel_id,
    )


def render_grade(grade: VideoGrade) -> str:
    lines = [f"Report card: {grade.letter} ({grade.score:.0f}/100)"]
    for c in grade.components:
        note = f" — {c.note}" if c.note else ""
        lines.append(f"    {c.name:<12} {c.score:5.1f} × {c.weight:.0%}{note}")
    if grade.predicted_engaged_rate is not None:
        lines.append(
            f"    predicted engaged-rate ~{grade.predicted_engaged_rate * 100:.1f}%"
            + (f" ({grade.prediction_note})" if grade.prediction_note else "")
        )
    elif grade.prediction_note:
        lines.append(f"    prediction: {grade.prediction_note}")
    return "\n".join(lines)


def display_grade_for_run(run_id: int | None, *, print_fn=print) -> None:
    """Interactive-flow helper: grade the just-persisted run, fail-open."""
    if not run_id:
        return
    try:
        grade = grade_run(run_id)
        if grade is not None:
            print_fn("")
            for line in render_grade(grade).splitlines():
                print_fn(f"  {line}")
    except Exception as exc:
        logger.debug("grade display skipped: %s", exc)
