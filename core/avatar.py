"""Talking-head / avatar seam (Pillar 6) — OFF by default, fail-open, baseline stub.

"Faceless with a face" mode: lip-sync a portrait/still to the VO as an alternative to
stock / AI b-roll. Reference open backends: LatentSync (ByteDance), MuseTalk, SadTalker,
Wav2Lip; paid: Hedra, HeyGen, D-ID.

**Disclosure:** a real-person likeness on the avatar track MUST trip the 2026
AI-disclosure layer (`core/authenticity.py`, `core/description_extras.py`).

    AVATAR_PROVIDER=latentsync     # default: none

Baseline only — no backend wired yet; always fails open so nothing in the render path
changes until a provider is implemented.
"""

from __future__ import annotations

from core.logging import get_logger
from core.providers import STATUS_NOT_CONFIGURED, ProviderResult, selected_provider

logger = get_logger("core.avatar")

SLOT = "avatar"


def lip_sync(portrait_path: str, vo_path: str, *, out_path: str | None = None) -> ProviderResult:
    """Return a `ProviderResult` whose `data` is a lip-synced clip path, or fail-open."""
    provider = selected_provider("AVATAR_PROVIDER", "none")
    if provider in ("", "none"):
        return ProviderResult.fail_open(SLOT, "AVATAR_PROVIDER unset", status=STATUS_NOT_CONFIGURED)
    return ProviderResult.fail_open(
        SLOT,
        f"avatar provider {provider!r} not implemented (baseline seam) — "
        "real-likeness output must trip AI disclosure",
        status=STATUS_NOT_CONFIGURED,
    )
