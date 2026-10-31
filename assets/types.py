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
    # #424: source clip paths the run actually cut from, for the licence ledger.
    clip_paths: list[str] = field(default_factory=list)
    # Wave 135 (decision 85, L1): a frame of these shots, before captions, with no words.
    cover_path: str = ""
