"""Subject-tracked vertical auto-reframe seam (Pillar 6) — OFF by default, fail-open.

Reframes any-aspect source footage to a 9:16 crop that follows the subject — the shared
primitive for clip-from-source (Phase R) and repurposing.

**License:** the reference backend, Ultralytics YOLO, is **AGPL-3.0**. Fine for internal
use; shipping / selling Content Machine with it linked requires Ultralytics' commercial
license (same obligation class as MoneyPrinterV2). Kept behind `REFRAME_ENABLED` and
never imported unless explicitly enabled — a `pip install ultralytics` is easy to do
without noticing the license implication, so this seam makes the choice explicit.

    REFRAME_ENABLED=true     # default: false

Baseline only — no backend wired yet; always fails open.
"""

from __future__ import annotations

from core.logging import get_logger
from core.providers import STATUS_NOT_CONFIGURED, ProviderResult, flag_enabled

logger = get_logger("core.reframe")

SLOT = "reframe"


def reframe_vertical(video_path: str, *, out_path: str | None = None) -> ProviderResult:
    """Return a `ProviderResult` whose `data` is a reframed 9:16 clip path, or fail-open."""
    if not flag_enabled("REFRAME_ENABLED"):
        return ProviderResult.fail_open(SLOT, "REFRAME_ENABLED off", status=STATUS_NOT_CONFIGURED)
    return ProviderResult.fail_open(
        SLOT,
        "auto-reframe not implemented (baseline seam); backend is AGPL — check license before shipping",
        status=STATUS_NOT_CONFIGURED,
    )
