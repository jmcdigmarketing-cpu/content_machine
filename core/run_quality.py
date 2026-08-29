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
      "authenticity_score": 85, "authenticity_verdict": "ok",
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

QUALITY_VERSION = "v2"  # v2: Pillar 3 keys (tier/conflict counts, claim support)


def build_quality(
    *,
    script: str,
    channel_id: str,
    features: dict[str, Any] | None = None,
    exclude_run_id: int | None = None,
) -> dict[str, Any]:
    """Score a finished script on the existing quality axes (pure reads, fail-open)."""
    features = features or {}
    quality: dict[str, Any] = {"quality_version": QUALITY_VERSION}
    if not (script or "").strip():
        return quality

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
        quality["authenticity_verdict"] = auth.verdict
        quality["authenticity_semantic"] = round(float(auth.semantic_overlap or 0.0), 3)
    except Exception as exc:
        logger.debug("authenticity scoring skipped: %s", exc)

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

    # Pillar 2: freeze the data-gated engaged-rate prediction at generation time
    # so the calibration loop can score it against the realized outcome later.
    try:
        from core.engagement_predictor import predict_engaged_rate

        prediction = predict_engaged_rate(channel_id, quality=quality)
        if prediction is not None:
            quality["predicted_engaged_rate"] = prediction.rate
    except Exception as exc:
        logger.debug("prediction skipped: %s", exc)
    return quality


def persist_quality(run_id: int | None, quality: dict[str, Any]) -> None:
    """Write the quality dict onto the run row (no-op without a run id)."""
    if not run_id or not quality:
        return
    try:
        from storage.repositories.content_runs import get_content_run_repository

        get_content_run_repository().update(run_id, {"quality_json": json.dumps(quality)})
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
        current.setdefault("quality_version", QUALITY_VERSION)
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
