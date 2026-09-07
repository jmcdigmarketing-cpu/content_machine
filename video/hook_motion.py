"""First-caption-beat motion derived only from real word timings."""

from __future__ import annotations

import math


def _first_cue_end(words: list[dict] | None, *, max_words: int = 5) -> float | None:
    if not words:
        return None
    cue: list[dict] = []
    for word in words:
        text = str(word.get("word") or "").strip()
        if not text or word.get("start") is None or word.get("end") is None:
            continue
        try:
            start = float(word["start"])
            end = float(word["end"])
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
            continue
        cue.append({"word": text, "start": start, "end": end})
        if len(cue) >= max_words or str(word.get("word") or "")[-1:] in ".!?":
            break
    if not cue:
        return None
    cue_end = float(cue[-1]["end"])
    return cue_end if cue_end > 0 else None


def first_caption_motion_filter(
    words: list[dict] | None, config: dict | None, *, max_words: int = 5
) -> str:
    if not words or not config or not bool(config.get("enabled", False)):
        return ""
    try:
        zoom = float(config.get("zoom", 1.0))
    except (TypeError, ValueError):
        return ""
    if not (1.0 < zoom <= 1.15):
        return ""
    cue_end = _first_cue_end(words, max_words=max_words)
    if cue_end is None:
        return ""
    # d=1 keeps one output frame per input frame. The expression returns exactly
    # 1.0 after the first cue, so later beats retain the existing composition.
    return (
        "zoompan="
        f"z='if(lte(in_time,{cue_end:.3f}),"
        f"1+({zoom:.4f}-1)*(in_time/{cue_end:.3f}),1)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
        "s={width}x{height}:fps=30"
    )


def named_motion_filter(
    words: list[dict] | None, config: dict | None, *, max_words: int = 5
) -> str:
    """Named punch-in / snap-zoom library. No timings or disabled -> empty filter."""
    if not words or not config or not bool(config.get("enabled", False)):
        return ""
    preset = str(config.get("preset") or "").strip().lower().replace("_", "-")
    cue_end = _first_cue_end(words, max_words=max_words)
    if cue_end is None:
        return ""
    if preset == "punch-in":
        return (
            "zoompan="
            f"z='if(lte(in_time,{cue_end:.3f}),"
            f"1+0.12*sqrt(in_time/{cue_end:.3f}),1.12)':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
            "s={width}x{height}:fps=30"
        )
    if preset == "snap-zoom":
        return (
            "zoompan="
            "z='if(lte(in_time,0.150),1.14,1.14)':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
            "s={width}x{height}:fps=30"
        )
    return first_caption_motion_filter(words, config, max_words=max_words)
