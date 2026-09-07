"""#170. One JSON of palette, type, spacing, and per-channel accents."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.paths import ROOT_DIR

TOKENS_PATH = Path(ROOT_DIR) / "config" / "design_tokens.json"


@lru_cache(maxsize=1)
def load_tokens() -> dict[str, Any]:
    with TOKENS_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("design_tokens.json must be an object")
    return data


def channel_tokens(channel_id: str | None) -> dict[str, Any]:
    cid = (channel_id or "default").strip().lower()
    channels = load_tokens().get("channels") or {}
    if isinstance(channels.get(cid), dict):
        return dict(channels[cid])
    return dict(channels.get("tapin") or {})


def caption_fill_hex(channel_id: str | None) -> str:
    fill = str(channel_tokens(channel_id).get("caption_fill") or "").strip()
    return fill or "#FFFFFF"


def caption_outline_hex(channel_id: str | None) -> str:
    outline = str(channel_tokens(channel_id).get("caption_outline") or "").strip()
    return outline or "#111111"


def header_border_hex(channel_id: str | None) -> str:
    border = str(channel_tokens(channel_id).get("header_border") or "").strip()
    return border or "#c62828"


def role_ansi_pair(role: str, *, colorblind: bool = False) -> tuple[str, str] | None:
    tokens = load_tokens()
    table = tokens.get("colorblind_roles") if colorblind else tokens.get("roles")
    spec = (table or {}).get(role) or {}
    if not isinstance(spec, dict):
        return None
    try:
        ansi16 = int(spec["ansi16"])
        ansi256 = int(spec["ansi256"])
    except (KeyError, TypeError, ValueError):
        return None
    return (f"\033[{ansi16}m", f"\033[38;5;{ansi256}m")
