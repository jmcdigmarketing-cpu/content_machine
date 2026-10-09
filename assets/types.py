from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssetResult:
    path: str
    provider: str
    source_id: str = ""
    query: str = ""
    attribution: Optional[str] = None
    # #1019: credit lines a licence requires (CC BY), for the YouTube description.
    credits: list[str] = field(default_factory=list)
