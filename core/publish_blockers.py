"""One-sentence "what's blocking publish" from already-shipped gates.

Reads grade, authenticity, quota, thin-facts, cadence, RPM-cost, TTS cap,
disk preflight. Never writes quota stores. Fail-open: a broken gate is skipped.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger("core.publish_blockers")


def fact_count_from_record(record: Any) -> int | None:
    """`key_facts_count` persisted in a content run's features, or None."""
    try:
        features = json.loads(getattr(record, "features_json", "") or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(features, dict) or features.get("key_facts_count") is None:
        return None
    try:
        return int(features["key_facts_count"])
    except (TypeError, ValueError):
        return None


def last_run_context(channel_id: str | None = None) -> dict[str, Any]:
    """#734: what the blockers read, taken from the run the operator would publish.

    `ops blocking` and `/next` used to pass only a channel id, so the render gate graded
    an empty dict: measured "report card F" while the last rendered run graded A.
    Empty when there is no reviewable run.
    """
    try:
        from core.review_booth import last_reviewable_trace

        trace = last_reviewable_trace(channel_id)
    except Exception as exc:
        logger.debug("publish context trace skipped: %s", exc)
        return {}
    if not trace:
        return {}
    context: dict[str, Any] = {"quality": dict(trace.get("quality") or {})}
    record = None
    run_id = trace.get("run_id")
    if run_id:
        try:
            from storage.repositories.content_runs import get_content_run_repository

            record = get_content_run_repository().get(int(run_id))
        except Exception as exc:
            logger.debug("publish context record skipped for run %s: %s", run_id, exc)
    if record is not None:
        try:
            features = json.loads(getattr(record, "features_json", "") or "{}")
        except (TypeError, ValueError):
            features = {}
        if isinstance(features, dict) and features:
            context["features"] = features
        facts = fact_count_from_record(record)
        if facts is not None:
            context["fact_count"] = facts
        mp4 = str(getattr(record, "mp4_path", "") or "")
        if mp4:
            context["mp4_path"] = mp4
    return context


def publish_status_sentence(channel_id: str | None = None) -> str:
    """The operator sentence for `ops blocking` and `/next`, from the real last run."""
    context = last_run_context(channel_id)
    if not context:
        return "Nothing to publish yet: no rendered or drafted run found."
    return blocking_publish_sentence(channel_id=channel_id, **context)


def blocking_publish_sentence(
    *,
    channel_id: str | None = None,
    quality: dict[str, Any] | None = None,
    fact_count: int | None = None,
    features: dict[str, Any] | None = None,
    script: str | None = None,
    mp4_path: str | None = None,
) -> str:
    """First blocking reason, or a clear 'ready' sentence. Operator-facing ASCII."""
    reasons = blocking_publish_reasons(
        channel_id=channel_id,
        quality=quality,
        fact_count=fact_count,
        features=features,
        script=script,
        mp4_path=mp4_path,
    )
    if not reasons:
        return "Nothing is blocking publish: grade, authenticity, quota, and facts look clear."
    return reasons[0]


def blocking_publish_reasons(
    *,
    channel_id: str | None = None,
    quality: dict[str, Any] | None = None,
    fact_count: int | None = None,
    features: dict[str, Any] | None = None,
    script: str | None = None,
    mp4_path: str | None = None,
) -> list[str]:
    out: list[str] = []
    features = features or {}
    quality = quality or {}

    try:
        from core.thin_facts import thin_facts_abort_reason

        if fact_count is not None:
            why = thin_facts_abort_reason(fact_count=fact_count, features=features)
            if why:
                out.append(why)
    except Exception as exc:
        logger.debug("thin-facts blocker skipped: %s", exc)

    try:
        # #734: no run data is not an F. Grading an empty dict made `ops blocking`
        # report "report card F" for every channel.
        if quality:
            from core.render_gate import block_reason_from_quality

            why = block_reason_from_quality(quality)
            if why:
                out.append(why)
    except Exception as exc:
        logger.debug("render-gate blocker skipped: %s", exc)

    try:
        from core.authenticity import gate_mode

        # #735: the same rule that stops the render - a block verdict. A 'review'
        # verdict used to refuse publishing too once the gate was armed.
        verdict = str(quality.get("authenticity_verdict") or "").strip().lower()
        if gate_mode() == "block" and verdict == "block":
            out.append(f"authenticity gate: verdict {verdict} (AUTHENTICITY_GATE=block)")
    except Exception as exc:
        logger.debug("authenticity blocker skipped: %s", exc)

    try:
        from apis.youtube_quota import has_quota_for_upload, uploads_remaining

        if not has_quota_for_upload():
            out.append(f"YouTube quota: ~{uploads_remaining()} uploads left this reset (need 1)")
    except Exception as exc:
        logger.debug("youtube quota blocker skipped: %s", exc)

    try:
        from core.cadence import cadence_status

        cid = channel_id or "tapin"
        status = cadence_status(cid)
        if not status.ok:
            out.append(
                f"cadence: {status.total}/{status.cap} videos in {status.window_days}d window"
            )
    except Exception as exc:
        logger.debug("cadence blocker skipped: %s", exc)

    try:
        from core.rpm_cost_gate import rpm_cost_gate_reason

        if channel_id:
            why = rpm_cost_gate_reason(channel_id)
            if why:
                out.append(why)
    except Exception as exc:
        logger.debug("rpm-cost blocker skipped: %s", exc)

    try:
        if script:
            from core.tts_char_cap import tts_char_cap_reason

            why = tts_char_cap_reason(script)
            if why:
                out.append(why)
    except Exception as exc:
        logger.debug("tts-cap blocker skipped: %s", exc)

    try:
        if mp4_path:
            from core.disk_preflight import block_reason as disk_block

            why = disk_block(mp4_path)
            if why:
                out.append(why)
    except Exception as exc:
        logger.debug("disk preflight blocker skipped: %s", exc)

    try:
        from core.publish_windows import window_reason

        topic = ""
        if isinstance(features, dict):
            topic = str(features.get("selected_topic") or features.get("topic") or "")
        why = window_reason(channel_id=channel_id, topic=topic)
        if why:
            out.append(why)
    except Exception as exc:
        logger.debug("publish-window blocker skipped: %s", exc)

    try:
        from core.cross_channel_dup import cross_channel_dup_block_reason

        topic = ""
        if isinstance(features, dict):
            topic = str(features.get("selected_topic") or features.get("topic") or "")
        if channel_id and topic:
            why = cross_channel_dup_block_reason(topic, channel_id)
            if why:
                out.append(why)
    except Exception as exc:
        logger.debug("cross-channel dup blocker skipped: %s", exc)

    return out
