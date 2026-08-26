"""One-sentence "what's blocking publish" from already-shipped gates.

Reads grade, authenticity, quota, thin-facts, cadence, RPM-cost, TTS cap,
disk preflight. Never writes quota stores. Fail-open: a broken gate is skipped.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger("core.publish_blockers")


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
        from core.render_gate import block_reason_from_quality

        why = block_reason_from_quality(quality)
        if why:
            out.append(why)
    except Exception as exc:
        logger.debug("render-gate blocker skipped: %s", exc)

    try:
        from core.authenticity import gate_mode

        verdict = str(quality.get("authenticity_verdict") or "").strip().lower()
        if gate_mode() == "block" and verdict and verdict != "ok":
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

    return out
