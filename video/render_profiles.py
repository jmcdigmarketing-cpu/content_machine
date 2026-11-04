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


# #1902 (wave 145): the subtitle files are written on a 1080x1920 canvas; libass scales a
# 1920x1080 frame's fonts by 1080/1920, so run 203's 16:9 captions came out a twentieth of the
# frame. The landscape copy is laid out for its own canvas: fonts at 72%, edges re-measured.
_LANDSCAPE_FONT = 0.72
_BOTTOM_MARGIN_MAX = 110  # px up from the bottom of a 1080-tall frame - the lower band
_SIDE_MARGIN_MAX = 300


def _scale(row: dict[str, str], key: str, factor: float, cap: int | None = None) -> None:
    try:
        value = round(float(row[key]) * factor)
    except (KeyError, ValueError):
        return
    row[key] = str(min(value, cap) if cap is not None else value)


def _landscape_style(fields: list[str], line: str) -> str:
    values = [v.strip() for v in line.split(":", 1)[1].split(",")]
    if len(values) != len(fields):
        return line
    row = dict(zip(fields, values, strict=True))
    for key in ("Fontsize", "Outline", "Shadow"):
        _scale(row, key, _LANDSCAPE_FONT)
    for key in ("MarginL", "MarginR"):
        _scale(row, key, 1920 / 1080, _SIDE_MARGIN_MAX)
    align = int(row.get("Alignment") or 2)
    if align in (1, 2, 3):  # bottom: the lower band of a 16:9 frame
        _scale(row, "MarginV", 1080 / 1920, _BOTTOM_MARGIN_MAX)
    elif align in (7, 8, 9):
        _scale(row, "MarginV", 1080 / 1920)
    return "Style: " + ",".join(row[f] for f in fields)


def landscape_ass(text: str) -> str:
    """An .ass script laid out for 1920x1080 from one laid out for 1080x1920."""
    import re

    def font(match: re.Match[str]) -> str:
        return f"\\fs{round(int(match.group(1)) * _LANDSCAPE_FONT)}"

    out: list[str] = []
    fields: list[str] = []
    for line in (text or "").splitlines():
        if line.startswith("PlayResX:"):
            out.append("PlayResX: 1920")
        elif line.startswith("PlayResY:"):
            out.append("PlayResY: 1080")
        elif line.startswith("Format:") and not fields and "Fontsize" in line:
            fields = [f.strip() for f in line.split(":", 1)[1].split(",")]
            out.append(line)
        elif line.startswith("Style:") and fields:
            out.append(_landscape_style(fields, line))
        else:
            out.append(re.sub(r"\\fs(\d+)", font, line))
    return "\n".join(out) + ("\n" if (text or "").endswith("\n") else "")


def landscape_ass_file(path: str | None, *, suffix: str = "_16x9") -> str | None:
    """A landscape copy of an .ass file beside it; the path unchanged for anything else."""
    if not path or not str(path).lower().endswith(".ass") or not os.path.isfile(path):
        return path
    stem, ext = os.path.splitext(path)
    dest = f"{stem}{suffix}{ext}"
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    with open(dest, "w", encoding="utf-8") as handle:
        handle.write(landscape_ass(text))
    return dest
