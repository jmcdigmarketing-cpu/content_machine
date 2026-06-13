from dataclasses import dataclass
from typing import Optional


@dataclass
class AssetResult:
    path: str
    provider: str
    source_id: str = ""
    query: str = ""
    attribution: Optional[str] = None
