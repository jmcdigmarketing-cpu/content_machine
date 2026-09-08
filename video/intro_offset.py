"""#669: intro-waveform offset comes from the shipped channel profile."""

from __future__ import annotations


def intro_offset_seconds(channel_id: str | None) -> float:
    from config.channels import get_channel_profile
    from video.channel_intro import DEFAULT_INTRO_DURATION

    profile = get_channel_profile(channel_id)
    raw = getattr(profile, "intro_offset_seconds", None)
    if raw is None:
        return float(DEFAULT_INTRO_DURATION)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return float(DEFAULT_INTRO_DURATION)
