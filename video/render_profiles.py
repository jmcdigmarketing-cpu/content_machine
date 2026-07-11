"""Render aspect profiles (Pillar 6) — one script, multiple aspect ratios for reach.

The pipeline always produces the primary **vertical 9:16** cut (unchanged). When
`RENDER_FORMATS` names extra profiles, the render step emits additional cuts (16:9 / 1:1)
from the same background + VO + burned captions — cheap distribution reach with no new
dependency. Default (`RENDER_FORMATS` unset) → vertical only, byte-identical to before.

    RENDER_FORMATS=vertical,landscape,square
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Primary vertical dims mirror video/render_video.TARGET_W/TARGET_H (kept in sync).
VERTICAL_W, VERTICAL_H = 1080, 1920


@dataclass(frozen=True)
class RenderProfile:
    name: str
    width: int
    height: int
    suffix: str  # appended to the output stem for non-primary cuts ("" for vertical)


_PROFILES: dict[str, RenderProfile] = {
    "vertical": RenderProfile("vertical", VERTICAL_W, VERTICAL_H, ""),
    "landscape": RenderProfile("landscape", 1920, 1080, "_16x9"),
    "square": RenderProfile("square", 1080, 1080, "_1x1"),
}

VERTICAL = _PROFILES["vertical"]


def profiles_for(env_value: str | None = None) -> list[RenderProfile]:
    """Profiles to render. Vertical is always first (the primary cut); extras follow.

    `env_value` overrides the RENDER_FORMATS env var (for tests). Unknown names are
    ignored; the list is de-duplicated. Empty/unset → just the vertical profile.
    """
    raw = env_value if env_value is not None else os.getenv("RENDER_FORMATS", "")
    names = [n.strip().lower() for n in (raw or "").split(",") if n.strip()]
    out: list[RenderProfile] = []
    seen: set[str] = set()
    for name in ["vertical", *names]:  # vertical always present + first
        profile = _PROFILES.get(name)
        if profile and profile.name not in seen:
            seen.add(profile.name)
            out.append(profile)
    return out


def extra_profiles(env_value: str | None = None) -> list[RenderProfile]:
    """Non-primary profiles only (everything after the vertical primary)."""
    return [p for p in profiles_for(env_value) if p.name != "vertical"]
