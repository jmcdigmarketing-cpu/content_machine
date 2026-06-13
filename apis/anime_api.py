"""Anime signal — AniList primary, Jikan fallback."""

from __future__ import annotations

import os

from apis.anilist_api import get_anilist_signal
from apis.jikan_api import get_jikan_signal
from apis.signal_chain import ProviderFn, chain_signal


def _anime_providers() -> list[tuple[str, ProviderFn]]:
    order = os.getenv("ANIME_PROVIDER_ORDER", "anilist,jikan")
    registry = {
        "anilist": get_anilist_signal,
        "jikan": get_jikan_signal,
    }
    providers: list[tuple[str, ProviderFn]] = []
    for name in order.split(","):
        key = name.strip().lower()
        if key in registry:
            providers.append((key, registry[key]))
    if not providers:
        providers.append(("anilist", get_anilist_signal))
    return providers


def get_anime_signal(topic: str) -> dict:
    return chain_signal(topic, _anime_providers(), min_score=20)
