"""
Publisher registry — resolves enabled publishers per channel.

TikTok and Instagram are intentionally not registered until a later phase.
"""

from __future__ import annotations

from config.channels import get_channel_profile, resolve_channel_id
from publishing.base import PLATFORM_YOUTUBE, Publisher
from publishing.youtube_publisher import YouTubePublisher

_ALL: dict[str, Publisher] = {
    PLATFORM_YOUTUBE: YouTubePublisher(),
}


def _platform_names_for_channel(channel_id: str) -> tuple[str, ...]:
    profile = get_channel_profile(channel_id)
    enabled = getattr(profile, "publishers_enabled", None)
    if enabled is not None:
        return tuple(str(p).strip().lower() for p in enabled if p)
    return (PLATFORM_YOUTUBE,)


def listed_publish_platforms(channel_id: str | None = None) -> tuple[str, ...]:
    """All platform names from channel config (includes deferred, not yet implemented)."""
    return _platform_names_for_channel(resolve_channel_id(channel_id))


def enabled_publish_platforms(channel_id: str | None = None) -> tuple[str, ...]:
    """Platforms listed on the channel profile with a registered publisher."""
    channel_id = resolve_channel_id(channel_id)
    names = _platform_names_for_channel(channel_id)
    return tuple(n for n in names if n in _ALL)


def publishers_for_channel(channel_id: str | None = None) -> list[Publisher]:
    """
    Enabled publishers for a channel. Default: YouTube only when upload is enabled.
    """
    channel_id = resolve_channel_id(channel_id)
    names = _platform_names_for_channel(channel_id)

    out: list[Publisher] = []
    for name in names:
        pub = _ALL.get(name)
        if pub and pub.is_configured(channel_id):
            out.append(pub)
    return out


def get_publisher(platform: str) -> Publisher | None:
    return _ALL.get(platform.strip().lower())


def list_platforms() -> list[str]:
    return list(_ALL.keys())
