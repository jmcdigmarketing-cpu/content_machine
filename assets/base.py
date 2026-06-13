from abc import ABC, abstractmethod
from typing import Optional

from assets.types import AssetResult


class AssetProvider(ABC):
    name: str = "base"

    @abstractmethod
    def find_video(
        self, topic: str, category: str, channel_id=None
    ) -> Optional[AssetResult]:
        """Return a local file path to a vertical-friendly background video."""
        pass

    def is_configured(self) -> bool:
        return True
