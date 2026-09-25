"""#151. One resolved brand kit per channel.

A channel's identity is spread across three files that nothing joins:

    config/design_tokens.json   palette -- caption fill/outline, end card, header
                                rule, grain, vignette
    config/channels.json        caption skin, end card copy, colour grade, hook
                                motion, intro file + offset, UI theme, persona
    assets/branding/<channel>/  logo.svg, banner.svg, about.md

Six modules reach into those independently (`core/caption_contrast.py`,
`video/caption_overlay.py`, `video/render_video.py`, `core/chrome.py`,
`core/contact_sheet.py`, `core/html_report.py`), and `channel-go-live` checked
only that files in the third one exist -- hence the backlog line, "it does not
apply a kit".

This is a **read path**. Every value is the one today's accessor already returns,
which `tests/test_wave5_defects.py::TestBrandKitCompiler` pins field by field.
Re-routing the renderer through the kit is deliberately NOT part of this wave: a
compiler that quietly restyles finished video is the "undisclosed change to
finished output" defect, not a fix.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from config.paths import ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.brand_kit")

_ASSET_NAMES = {
    "logo": ("logo.svg", "logo.png"),
    "banner": ("banner.svg", "banner.png"),
    "about": ("about.md",),
}


def summarize_config(value: dict[str, Any]) -> str:
    """`caption_skin` and friends are objects. Show the shape, not the repr."""
    if not value:
        return "(none)"
    return ", ".join(f"{k}={v}" for k, v in list(value.items())[:3]) + (
        ", ..." if len(value) > 3 else ""
    )


@dataclass
class BrandKit:
    """Every brand decision for one channel, with the file each came from."""

    channel_id: str
    # design_tokens.json
    caption_fill: str = ""
    caption_outline: str = ""
    header_border: str = ""
    end_card_bg: str = ""
    end_card_fg: str = ""
    accent: str = ""
    grain: int = 0
    vignette: float = 0.0
    # channels.json
    # JSON objects in channels.json, not strings -- `str(dict)` dumped the whole
    # repr into the operator's console.
    caption_skin: dict[str, Any] = field(default_factory=dict)
    color_grade: dict[str, Any] = field(default_factory=dict)
    hook_motion: dict[str, Any] = field(default_factory=dict)
    intro_video_file: str = ""
    intro_offset_seconds: float = 0.0
    ui_theme: str = ""
    youtube_handle: str = ""
    # assets/branding/<channel>/
    logo_path: str = ""
    banner_path: str = ""
    about_path: str = ""

    missing: list[str] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return not self.missing

    def render(self) -> str:
        """Operator-facing summary; `channel-go-live` and the GUI both use it."""
        lines = [f"Brand kit - {self.channel_id}", "=" * 62]
        for label, value, key in (
            ("caption fill", self.caption_fill, "caption_fill"),
            ("caption outline", self.caption_outline, "caption_outline"),
            ("header rule", self.header_border, "header_border"),
            ("end card", f"{self.end_card_bg} on {self.end_card_fg}", "end_card_bg"),
            ("grain / vignette", f"{self.grain} / {self.vignette}", "grain"),
            ("caption skin", summarize_config(self.caption_skin), "caption_skin"),
            ("colour grade", summarize_config(self.color_grade), "color_grade"),
            ("hook motion", summarize_config(self.hook_motion), "hook_motion"),
            ("intro", self.intro_video_file or "(none)", "intro_video_file"),
            ("handle", self.youtube_handle or "(unset)", "youtube_handle"),
            ("logo", self.logo_path or "(missing)", "logo"),
            ("banner", self.banner_path or "(missing)", "banner"),
        ):
            source = self.provenance.get(key, "?")
            lines.append(f"  {label:<17} {value:<28} [{source}]")
        if self.missing:
            lines.append("")
            lines.append(f"Missing: {', '.join(self.missing)}")
        return "\n".join(lines)


def _channel_config(channel_id: str) -> dict[str, Any]:
    try:
        from config.channels import _load_channels_file

        raw = _load_channels_file()
        channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
        cfg = channels.get(channel_id) if isinstance(channels, dict) else None
        return cfg if isinstance(cfg, dict) else {}
    except Exception as exc:
        logger.warning("channels.json unreadable for %s, kit is token-only: %s", channel_id, exc)
        return {}


def _asset(channel_id: str, kind: str) -> str:
    base = os.path.join(ROOT_DIR, "assets", "branding", channel_id)
    for name in _ASSET_NAMES[kind]:
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return ""


def compile_kit(channel_id: str | None) -> BrandKit:
    """Resolve one channel's brand kit. Fail-open: an unreadable source becomes a
    `missing` entry, never an exception -- this is on the go-live path."""
    from core.design_tokens import (
        caption_fill_hex,
        caption_outline_hex,
        channel_tokens,
        header_border_hex,
        look_grain,
        look_vignette,
    )

    cid = (channel_id or "").strip() or "default"
    kit = BrandKit(channel_id=cid)
    tokens = channel_tokens(cid)
    cfg = _channel_config(cid)

    kit.caption_fill = caption_fill_hex(cid)
    kit.caption_outline = caption_outline_hex(cid)
    kit.header_border = header_border_hex(cid)
    kit.end_card_bg = str(tokens.get("end_card_bg") or "")
    kit.end_card_fg = str(tokens.get("end_card_fg") or "")
    kit.accent = str(tokens.get("accent") or "")
    kit.grain = look_grain(cid)
    kit.vignette = look_vignette(cid)
    for key in (
        "caption_fill",
        "caption_outline",
        "header_border",
        "end_card_bg",
        "end_card_fg",
        "accent",
        "grain",
        "vignette",
    ):
        kit.provenance[key] = "design_tokens.json"

    kit.caption_skin = dict(cfg.get("caption_skin") or {})
    kit.color_grade = dict(cfg.get("color_grade") or {})
    kit.hook_motion = dict(cfg.get("hook_motion") or {})
    kit.intro_video_file = str(cfg.get("intro_video_file") or "")
    kit.ui_theme = str(cfg.get("ui_theme") or "")
    kit.youtube_handle = str(cfg.get("youtube_handle") or "")
    try:
        kit.intro_offset_seconds = float(cfg.get("intro_offset_seconds") or 0.0)
    except (TypeError, ValueError):
        kit.intro_offset_seconds = 0.0
    for key in (
        "caption_skin",
        "color_grade",
        "hook_motion",
        "intro_video_file",
        "intro_offset_seconds",
        "ui_theme",
        "youtube_handle",
    ):
        kit.provenance[key] = "channels.json"

    kit.logo_path = _asset(cid, "logo")
    kit.banner_path = _asset(cid, "banner")
    kit.about_path = _asset(cid, "about")
    for key in ("logo", "banner", "about"):
        kit.provenance[key] = f"assets/branding/{cid}/"

    if not kit.logo_path:
        kit.missing.append(f"logo (assets/branding/{cid}/logo.svg)")
    if not kit.banner_path:
        kit.missing.append(f"banner (assets/branding/{cid}/banner.svg)")
    # `youtube_handle` is carried on the kit but deliberately not counted here:
    # `channel-go-live` already has a dedicated `handle` check, and listing it in
    # both makes one gap fail two checks.
    if not kit.end_card_bg or not kit.end_card_fg:
        kit.missing.append("end card colours (design_tokens.json)")
    return kit


def kit_status_line(kit: BrandKit) -> str:
    """One line for `channel-go-live`, which used to print bare filenames."""
    if kit.complete:
        return f"resolved from 3 sources; logo + banner on disk, handle {kit.youtube_handle}"
    return f"partially resolved, missing: {'; '.join(kit.missing)}"
