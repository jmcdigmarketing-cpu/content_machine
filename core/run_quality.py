"""Pre-publish quality persistence (Pillar 1 — Run Ledger).

The audit finding this fixes: hook and authenticity scores were computed,
printed, and discarded (batch ``meta.json`` aside) — nothing downstream could
read them back, so no grading or calibration was possible. This module builds
one ``quality`` dict per run and persists it to ``content_runs.quality_json``
from every generation path (interactive, headless, batch) via
``core/pipeline._finalize_run``.

Shape (all keys optional — consumers must tolerate absence):

    {
      "hook_score": 72, "hook_verdict": "strong",
      "authenticity_score": 85,          # #804: the continuous grade
      "authenticity_gate_score": 100,    # #804: the binary 40/35/25 gate sum
      "authenticity_verdict": "ok",      # ...from the gate sum, never the grade
      "ungrounded_count": 1, "ungrounded_entities": [...],
      "trade_warning_count": 0,
      "tier_warning_count": 0,          # Pillar 3: grounding-tier lint
      "fact_conflict_count": 0,         # Pillar 3: operator-vs-source conflicts
      "claim_support_rate": 0.9,        # Pillar 3: LLM claim verifier (when it ran)
      "unsupported_claim_count": 1,
      "claims_rewritten": True,         # 322: the rewrite pass hedged unsupported claims
      "pre_rewrite_unsupported_count": 7,   # ...what the script asserted before that
      "pre_rewrite_support_rate": 0.417,
      "thumbnail_overall": 61.0, "thumbnail_source": "llm",   # merged post-render
      "quality_version": "v2",
    }

Everything here is fail-open: quality persistence is an observability layer,
never load-bearing for a run.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger("core.run_quality")

QUALITY_VERSION = "v4"  # v2: Pillar 3 keys (tier/conflict counts, claim support)
# v3 (2026-09-05): word_count / min_words / max_words, for the report card's
# `length` component (#645). A v2 row has no length keys and grades on the
# renormalised remainder, so its score is unchanged - see core/video_grade.py.
# v4 (2026-09-20): #808 grade_score / grade_letter / grade_components - the
# grade *this* row's inputs actually produced, recorded beside them. No rubric
# moved, so GRADE_VERSION stays v4.


def authenticity_gate_value(quality: dict[str, Any] | None) -> float | None:
    """The binary 40/35/25 authenticity sum, across the v3/v4 boundary.

    #804 made ``authenticity_score`` a continuous 0-100 grade and moved the
    binary sum to ``authenticity_gate_score``. Pre-v4 rows have no gate key, but
    their ``authenticity_score`` *is* that sum — so readers calibrated on the
    binary series (channel-health thresholds, the engagement fit) keep one
    consistent series either side of the boundary instead of averaging two
    different rubrics together. Readers that want the grade — the report card —
    read ``authenticity_score`` directly.
    """
    row = quality or {}
    for key in ("authenticity_gate_score", "authenticity_score"):
        val = row.get(key)
        if isinstance(val, int | float) and not isinstance(val, bool):
            return float(val)
    return None


def snapshot_grade(quality: dict[str, Any], composite_score: float | None) -> dict[str, Any]:
    """The grade *these* inputs produced, for recording beside them (#808).

    `core/grade_calibration` re-grades every archived run with today's code, so
    without this a v2 letter and a v4 letter are indistinguishable and a
    component change can never be measured against the archive. Graded with
    ``channel_id=None`` — the same no-predictor convention calibration uses, so
    the recorded number stays a property of the content, not of the channel's
    engagement history at the moment it was taken.

    Returns the keys to merge, or ``{}`` when there is nothing gradeable.
    Never raises: this is an observability layer.
    """
    try:
        from core.video_grade import grade_from_parts

        grade = grade_from_parts(
            quality=quality,
            composite_score=composite_score,
            channel_id=None,
        )
        if not grade.components:
            return {}
        return {
            "grade_score": round(float(grade.score), 1),
            "grade_letter": grade.letter,
            "grade_components": {
                c.name: {"score": round(float(c.score), 1), "weight": round(float(c.weight), 4)}
                for c in grade.components
            },
        }
    except Exception as exc:
        logger.debug("grade snapshot skipped: %s", exc)
        return {}


def build_quality(
    *,
    script: str,
    channel_id: str,
    features: dict[str, Any] | None = None,
    exclude_run_id: int | None = None,
    composite_score: float | None = None,
) -> dict[str, Any]:
    """Score a finished script on the existing quality axes (pure reads, fail-open)."""
    features = features or {}
    from core.video_grade import GRADE_VERSION

    quality: dict[str, Any] = {"quality_version": QUALITY_VERSION, "grade_version": GRADE_VERSION}
    if not (script or "").strip():
        return quality

    # Length, for the report card's `length` component (#645). Sourced here rather
    # than read out of features_json by the grader, so it arrives the same way
    # every other component does. Absent on historical rows, which is what keeps
    # their grades numerically unchanged.
    try:
        from core.script_length import count_spoken_words, get_length_preset

        preset = get_length_preset(str(features.get("length_preset") or "2"))
        quality["word_count"] = int(features.get("word_count") or count_spoken_words(script))
        quality["min_words"] = preset.min_words
        quality["max_words"] = preset.max_words
    except Exception as exc:
        logger.debug("length scoring skipped: %s", exc)

    try:
        from core.hook_score import score_script_hook

        hook = score_script_hook(script)
        quality["hook_score"] = hook.score
        quality["hook_verdict"] = hook.verdict
    except Exception as exc:
        logger.debug("hook scoring skipped: %s", exc)

    try:
        from core.authenticity import evaluate_authenticity

        auth = evaluate_authenticity(
            script,
            channel_id,
            fact_count=int(features.get("key_facts_count") or 0),
            exclude_run_id=exclude_run_id,
        )
        quality["authenticity_score"] = auth.score
        quality["authenticity_gate_score"] = int(auth.gate_score)
        quality["authenticity_verdict"] = auth.verdict
        quality["authenticity_semantic"] = round(float(auth.semantic_overlap or 0.0), 3)
        # #803: report-only, but it has to be persisted or the card and the
        # archive cannot see the repeat that the peak similarity hides.
        recurrence = auth.recurrence or {}
        if recurrence.get("n"):
            quality["style_recurrence_opener"] = int(recurrence.get("opener") or 0)
            quality["style_recurrence_closer"] = int(recurrence.get("closer") or 0)
            quality["style_recurrence_n"] = int(recurrence["n"])
    except Exception as exc:
        logger.debug("authenticity scoring skipped: %s", exc)

    try:
        from core.claim_types import hedge_density

        quality["hedge_density"] = hedge_density(script)
    except Exception as exc:
        logger.debug("hedge density skipped: %s", exc)

    ungrounded = features.get("ungrounded_entities") or []
    quality["ungrounded_count"] = len(ungrounded)
    if ungrounded:
        quality["ungrounded_entities"] = list(ungrounded)[:20]
    try:
        from core.fact_grounding import numeric_claims_among

        numeric = numeric_claims_among(list(ungrounded) if ungrounded else [])
        if numeric:
            quality["ungrounded_numeric"] = numeric[:12]
    except Exception as exc:
        logger.debug("ungrounded numeric split skipped: %s", exc)
    try:
        from core.fact_grounding import find_plausibility_outliers

        facts = str(features.get("grounding_text") or features.get("facts") or "")
        outliers = find_plausibility_outliers(script, facts)
        if outliers:
            quality["numeric_outliers"] = outliers[:8]
    except Exception as exc:
        logger.debug("numeric plausibility skipped: %s", exc)
    try:
        from analytics.competitor_context import list_recent_competitor_titles
        from core.title_overlap import verbatim_competitor_advisory

        title = str(features.get("title") or "")
        note = verbatim_competitor_advisory(
            title, list_recent_competitor_titles(channel_id, topic=title)
        )
        if note:
            quality["competitor_title_duplicate"] = note
    except Exception as exc:
        logger.debug("competitor title overlap skipped: %s", exc)
    try:
        from analytics.competitor_context import topic_saturation

        topic = str(features.get("title") or features.get("topic") or "")
        if topic:
            covered = topic_saturation(channel_id, topic)
            if covered:
                quality["topic_saturation"] = int(covered)
    except Exception as exc:
        logger.debug("topic saturation skipped: %s", exc)
    try:
        from core.publish_windows import resolve_relative_clock

        lowered = script.lower()
        if "tonight" in lowered:
            resolved = resolve_relative_clock("tonight")
            if resolved is not None:
                quality["clock_tonight"] = resolved.isoformat()
        if "this weekend" in lowered:
            resolved = resolve_relative_clock("this weekend")
            if resolved is not None:
                quality["clock_weekend"] = resolved.isoformat()
    except Exception as exc:
        logger.debug("channel clock skipped: %s", exc)
    quality["trade_warning_count"] = len(features.get("trade_warnings") or [])

    # Pillar 3 (Fact Engine): tier lint + conflicts always count; the claim
    # verifier's keys appear only when it actually ran (absence ≠ perfect).
    quality["tier_warning_count"] = len(features.get("tier_warnings") or [])
    quality["fact_conflict_count"] = len(features.get("fact_conflicts") or [])
    if features.get("disputed"):
        quality["disputed"] = True
        quality["disputed_claims"] = list(features.get("disputed_claims") or [])[:8]
    verification = features.get("claim_verification") or {}
    if verification.get("total"):
        # Only persist a numeric support_rate — a malformed/None value would
        # leave a non-numeric quality_json key that the calibration/analyst
        # averages then have to special-case.
        support_rate = verification.get("support_rate")
        if isinstance(support_rate, int | float):
            quality["claim_support_rate"] = float(support_rate)
        quality["unsupported_claim_count"] = len(verification.get("unsupported") or [])
        # Candidate 322: a hedged run scores like a clean one, because the rate above
        # is measured after the rewrite pass restated the unsupported claims as
        # attributed speculation. Keep what the script asserted before that.
        if verification.get("rewritten"):
            quality["claims_rewritten"] = True
            quality["pre_rewrite_unsupported_count"] = int(
                verification.get("pre_rewrite_unsupported") or 0
            )
            pre_rate = verification.get("pre_rewrite_support_rate")
            if isinstance(pre_rate, int | float):
                quality["pre_rewrite_support_rate"] = float(pre_rate)
            pre_script = verification.get("script_pre_rewrite")
            post_script = verification.get("script_post_rewrite")
            if pre_script:
                quality["script_pre_rewrite"] = str(pre_script)
            if post_script:
                quality["script_post_rewrite"] = str(post_script)

    if "script_passes" in features:
        quality["script_passes"] = list(features.get("script_passes") or [])

    # Pillar 2: freeze the data-gated engaged-rate prediction at generation time
    # so the calibration loop can score it against the realized outcome later.
    try:
        from core.engagement_predictor import predict_engaged_rate

        prediction = predict_engaged_rate(channel_id, quality=quality)
        if prediction is not None:
            quality["predicted_engaged_rate"] = prediction.rate
    except Exception as exc:
        logger.debug("prediction skipped: %s", exc)

    # #808, last: the snapshot has to see every component above it. The
    # thumbnail is the one it cannot see - it merges post-render, which is why
    # `merge_quality` re-stamps.
    quality.update(snapshot_grade(quality, composite_score))
    return quality


def persist_quality(run_id: int | None, quality: dict[str, Any]) -> None:
    """Write the quality dict onto the run row (no-op without a run id)."""
    if not run_id or not quality:
        return
    try:
        from storage.repositories.content_runs import get_content_run_repository

        payload = dict(quality)
        try:
            from storage.alembic_runner import current_revision

            payload.setdefault("schema_revision", current_revision())
        except Exception as exc:
            logger.debug("schema revision stamp skipped: %s", exc)
        get_content_run_repository().update(run_id, {"quality_json": json.dumps(payload)})
    except Exception as exc:
        logger.debug("quality persistence skipped for run %s: %s", run_id, exc)


def merge_quality(run_id: int | None, updates: dict[str, Any]) -> None:
    """Merge keys into an existing quality_json (e.g. thumbnail score post-render)."""
    if not run_id or not updates:
        return
    try:
        from storage.repositories.content_runs import get_content_run_repository

        repo = get_content_run_repository()
        record = repo.get(run_id)
        current: dict[str, Any] = {}
        if record is not None:
            try:
                loaded = json.loads(record.quality_json or "{}")
                if isinstance(loaded, dict):
                    current = loaded
            except Exception:
                current = {}
        current.update(updates)
        # #808: the thumbnail score arrives here, after the generation-time
        # snapshot was taken. Re-stamp, or every published run carries a grade
        # missing its thumbnail component and disagrees with the card the
        # operator saw. Only when there was a snapshot to begin with - this must
        # not retro-grade a historical row under today's rubric.
        if "grade_score" in current:
            current.update(
                snapshot_grade(
                    current,
                    float(record.composite_score or 0.0) if record is not None else None,
                )
            )
        current.setdefault("quality_version", QUALITY_VERSION)
        try:
            from storage.alembic_runner import current_revision

            current.setdefault("schema_revision", current_revision())
        except Exception as exc:
            logger.debug("schema revision stamp skipped: %s", exc)
        repo.update(run_id, {"quality_json": json.dumps(current)})
    except Exception as exc:
        logger.debug("quality merge skipped for run %s: %s", run_id, exc)


def load_quality(run_id: int) -> dict[str, Any]:
    """Read a run's persisted quality dict ({} when absent/undecodable)."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
        if record is None:
            return {}
        loaded = json.loads(record.quality_json or "{}")
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}
