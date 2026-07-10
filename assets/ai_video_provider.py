"""AI-video-generation asset provider (Pillar 6 slot 1) — OFF by default, fail-open.

Plugs generated, prompt-matched footage into the existing background chain in the exact
shape `assets/manager` already uses (`AssetProvider.find_video`). It routes through the
single `core/comfy_client` HTTP endpoint (local Wan / LTX-Video, or a hosted aggregator
later), so no per-model SDK lands here.

    AI_VIDEO_PROVIDER=comfyui     # default: none

**Not registered in the live chain yet** (keeps the render path untouched for the
baseline). To activate, add one line to `assets/manager._PROVIDERS`:

    "ai_video": AIVideoProvider,

and put `ai_video` in `ASSET_PROVIDER_ORDER`. It fails open to `None` (⇒ stock / local
B-roll) whenever ComfyUI is unreachable or no workflow is configured.
"""

from __future__ import annotations

from typing import Optional

from assets.base import AssetProvider
from assets.types import AssetResult
from core.providers import selected_provider


class AIVideoProvider(AssetProvider):
    name = "ai_video"

    def is_configured(self) -> bool:
        return selected_provider("AI_VIDEO_PROVIDER", "none") not in ("", "none")

    def find_video(self, topic: str, category: str, channel_id=None) -> Optional[AssetResult]:
        if not self.is_configured():
            return None
        from core.comfy_client import generate

        result = generate(topic)
        if result.ok and isinstance(result.data, str) and result.data:
            return AssetResult(
                path=result.data,
                provider="ai_video",
                query=topic,
                attribution="AI-generated (ComfyUI)",
            )
        return None
