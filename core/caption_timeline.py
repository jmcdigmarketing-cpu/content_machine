"""#153. Karaoke vs SRT cues from real word timings, plus a sidecar the next burn reads.

Timing and placement only. Font and fill stay in the channel caption skin (#21).
No word timings means an empty timeline, not a proportional guess.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from video.caption_timing import group_into_lines

DEFAULT_MARGIN_V = 260
LANE_GAP = 8
LANE_HEIGHT = 28
PX_PER_SEC = 80
KARAOKE_LANE = "karaoke"
SRT_LANE = "srt"


@dataclass
class CaptionCue:
    lane: str
    index: int
    text: str
    start: float
    end: float
    margin_v: int = DEFAULT_MARGIN_V
    word_indexes: tuple[int, ...] = ()


@dataclass
class CaptionTimeline:
    source: str
    reason: str = ""
    audio_path: str = ""
    duration: float = 0.0
    karaoke: list[CaptionCue] = field(default_factory=list)
    srt: list[CaptionCue] = field(default_factory=list)


def edits_path(audio_path: str) -> str:
    return audio_path + ".captions.json"


def load_words(audio_path: str | None) -> list[dict[str, Any]]:
    """ElevenLabs / Edge `.words.json` sidecar only. Missing is empty, not guessed."""
    if not audio_path:
        return []
    sidecar = audio_path + ".words.json"
    if not os.path.isfile(sidecar):
        return []
    try:
        with open(sidecar, encoding="utf-8") as fh:
            words = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    return words if isinstance(words, list) and words else []


def _span(line: list[dict[str, Any]]) -> tuple[float, float]:
    starts = [float(w["start"]) for w in line if w.get("start") is not None]
    ends = [float(w["end"]) for w in line if w.get("end") is not None]
    start = starts[0] if starts else 0.0
    end = ends[-1] if ends else (starts[-1] if starts else start)
    if end <= start:
        end = start + 0.4
    return start, end


def _cues_for(words: list[dict[str, Any]], lane: str, max_words: int) -> list[CaptionCue]:
    tagged = [{**dict(w), "_i": i} for i, w in enumerate(words)]
    lines = group_into_lines(tagged, max_words)
    cues: list[CaptionCue] = []
    for index, line in enumerate(lines):
        start, end = _span(line)
        cues.append(
            CaptionCue(
                lane=lane,
                index=index,
                text=" ".join(str(w.get("word") or "") for w in line),
                start=start,
                end=end,
                word_indexes=tuple(int(w["_i"]) for w in line),
            )
        )
    return cues


def _max_words() -> tuple[int, int]:
    from video.subtitles import caption_words_per_line

    srt_max = caption_words_per_line()
    return max(2, min(4, srt_max)), srt_max


def timeline_from_words(
    words: list[dict[str, Any]] | None,
    *,
    audio_path: str = "",
) -> CaptionTimeline:
    rows = list(words or [])
    if not rows:
        return CaptionTimeline(
            source="missing",
            reason="No word timings. Render with a .words.json sidecar, then reopen.",
            audio_path=audio_path,
        )
    karaoke_max, srt_max = _max_words()
    karaoke = _cues_for(rows, KARAOKE_LANE, karaoke_max)
    srt = _cues_for(rows, SRT_LANE, srt_max)
    last = 0.0
    for w in rows:
        try:
            last = max(last, float(w.get("end") or 0.0))
        except (TypeError, ValueError):
            continue
    return CaptionTimeline(
        source="word_timing",
        audio_path=audio_path,
        duration=last,
        karaoke=karaoke,
        srt=srt,
    )


def timeline_from_audio(audio_path: str) -> CaptionTimeline:
    return timeline_from_words(load_words(audio_path), audio_path=audio_path)


def cue_rect(cue: CaptionCue, *, px_per_sec: float = PX_PER_SEC) -> tuple[int, int, int, int]:
    lane_i = 0 if cue.lane == KARAOKE_LANE else 1
    x = int(round(float(cue.start) * px_per_sec))
    w = max(4, int(round((float(cue.end) - float(cue.start)) * px_per_sec)))
    y = LANE_GAP + lane_i * (LANE_HEIGHT + LANE_GAP)
    return x, y, w, LANE_HEIGHT


def clamp_cue_time(
    start: float,
    end: float,
    *,
    duration: float,
    min_span: float = 0.05,
) -> tuple[float, float]:
    duration = max(0.0, float(duration))
    span = max(min_span, float(end) - float(start))
    start = float(start)
    if start < 0.0:
        start = 0.0
    end = start + span
    if end > duration:
        end = duration
        start = max(0.0, end - span)
    if end <= start:
        end = min(duration, start + min_span)
    return start, end


def clamp_margin_v(margin_v: int, *, lo: int = 80, hi: int = 600) -> int:
    return min(hi, max(lo, int(margin_v)))


def load_edits(audio_path: str) -> list[dict[str, Any]]:
    path = edits_path(audio_path)
    if not audio_path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    edits = payload.get("edits") if isinstance(payload, dict) else payload
    return [e for e in edits if isinstance(e, dict)] if isinstance(edits, list) else []


def save_edits(audio_path: str, edits: list[dict[str, Any]]) -> str:
    path = edits_path(audio_path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"edits": edits}, fh, indent=2)
        fh.write("\n")
    return path


def apply_caption_edits(
    audio_path: str,
    words: list[dict[str, Any]],
    *,
    lane: str = KARAOKE_LANE,
) -> tuple[list[dict[str, Any]], list[int | None] | None]:
    """Shift the named lane's words and collect karaoke MarginV overrides.

    No sidecar, or no edits for that lane, returns the same list so a healthy
    burn stays byte-identical.
    """
    edits = [e for e in load_edits(audio_path) if str(e.get("lane") or "") == lane]
    if not edits or not words:
        return words, None
    tl = timeline_from_words(words, audio_path=audio_path)
    cues = tl.karaoke if lane == KARAOKE_LANE else tl.srt
    out = [dict(w) for w in words]
    margins: list[int | None] = [None] * len(cues)
    any_margin = False
    for edit in edits:
        raw_index = edit.get("index")
        if raw_index is None:
            continue
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(cues):
            continue
        dt = float(edit.get("dt") or 0.0)
        if dt:
            for word_i in cues[index].word_indexes:
                row = out[word_i]
                if row.get("start") is not None:
                    row["start"] = float(row["start"]) + dt
                if row.get("end") is not None:
                    row["end"] = float(row["end"]) + dt
        if edit.get("margin_v") is not None and lane == KARAOKE_LANE:
            margins[index] = clamp_margin_v(int(edit["margin_v"]))
            any_margin = True
    return out, (margins if any_margin else None)


def timeline_report(
    words_or_timeline: list[dict[str, Any]] | CaptionTimeline,
    *,
    audio_path: str = "",
) -> list[str]:
    if isinstance(words_or_timeline, CaptionTimeline):
        tl = words_or_timeline
    else:
        tl = timeline_from_words(words_or_timeline, audio_path=audio_path)
    audio = tl.audio_path or audio_path or "(none)"
    lines = [
        f"source: {tl.source}",
        f"audio: {audio}",
    ]
    if tl.source != "word_timing":
        lines.append(tl.reason)
        return lines
    if tl.karaoke:
        lines.append(
            f"karaoke: {len(tl.karaoke)} cues, {tl.karaoke[0].start:.2f}-{tl.duration:.2f}"
        )
    else:
        lines.append("karaoke: 0 cues")
    for cue in tl.karaoke:
        lines.append(f"  [{cue.index}] {cue.start:.2f}-{cue.end:.2f}  {cue.text}")
    lines.append(f"srt: {len(tl.srt)} cues")
    for cue in tl.srt:
        lines.append(f"  [{cue.index}] {cue.start:.2f}-{cue.end:.2f}  {cue.text}")
    stored = load_edits(tl.audio_path or audio_path)
    lines.append("edits: none" if not stored else f"edits: {len(stored)}")
    return lines
