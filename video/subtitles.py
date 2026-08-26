"""
Burned-caption (SRT) generation for vertical video.

Captions are table stakes for short-form retention. This builds an SRT where:
  - lines are short, punchy chunks (default 5 words — tuned for Shorts),
  - chunks respect sentence boundaries (no caption spanning two sentences),
  - each chunk's on-screen time is PROPORTIONAL to its word count, so the
    captions track the spoken audio instead of being spaced uniformly.

Configurable via CAPTION_WORDS_PER_LINE (default 5).
"""

import json
import os
import re

_DEFAULT_WORDS_PER_LINE = 5


def caption_words_per_line() -> int:
    raw = os.getenv("CAPTION_WORDS_PER_LINE", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return _DEFAULT_WORDS_PER_LINE


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:  # rounding spillover
        millis = 0
        secs += 1
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def split_script_into_lines(script: str, max_words: int | None = None) -> list[str]:
    """Sentence-aware chunks of at most `max_words` words each."""
    max_words = max_words or caption_words_per_line()
    sentences = re.split(r"(?<=[.!?])\s+", (script or "").strip())
    lines: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i : i + max_words]).strip()
            if chunk:
                lines.append(chunk)
    return lines


def build_srt(script: str, duration: float, *, max_words: int | None = None) -> str:
    """Return SRT text with chunk durations proportional to word count."""
    lines = split_script_into_lines(script, max_words)
    if not lines:
        return ""

    weights = [max(1, len(line.split())) for line in lines]
    total = sum(weights)

    blocks: list[str] = []
    elapsed_words = 0
    for i, line in enumerate(lines):
        start = duration * (elapsed_words / total)
        elapsed_words += weights[i]
        end = duration if i == len(lines) - 1 else duration * (elapsed_words / total)
        blocks.append(f"{i + 1}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{line}\n")
    return "\n".join(blocks) + "\n"


def _caption_skin(channel_id: str | None = None) -> dict:
    try:
        from config.channels import get_channel_profile

        return dict(get_channel_profile(channel_id).caption_skin or {})
    except Exception:
        return {}


def caption_style(channel_id: str | None = None) -> str:
    """plain (proportional SRT) | word (accurate SRT, default) | karaoke (animated ASS).

    Default `word` is a safe strict upgrade: when real word timings exist it produces
    accurately-synced SRT (proven format), else falls back to the proportional
    estimate. `karaoke` adds the animated highlight (ASS) — verify it once with a
    real render before relying on it.
    """
    env_style = os.getenv("CAPTION_STYLE", "").strip().lower()
    if env_style:
        return env_style
    return str(_caption_skin(channel_id).get("mode") or "word").strip().lower()


def _ass_color(value: object, default: str) -> str:
    raw = str(value or default).strip().lstrip("#")
    if len(raw) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in raw):
        raw = default.lstrip("#")
    rr, gg, bb = raw[0:2], raw[2:4], raw[4:6]
    return f"&H00{bb}{gg}{rr}&"


def caption_force_style(channel_id: str | None = None) -> str:
    """FFmpeg/libass style derived from the shipped channel caption skin."""
    skin = _caption_skin(channel_id)
    font = str(skin.get("font") or "Arial").replace(",", " ").strip() or "Arial"
    fill = _ass_color(skin.get("fill_color"), "#FFFFFF")
    outline = _ass_color(skin.get("outline_color"), "#111111")
    boxed = bool(skin.get("boxed", False))
    border_style = 3 if boxed else 1
    back = "&H99000000&" if boxed else "&H00000000&"
    return (
        f"FontName={font},FontSize=18,PrimaryColour={fill},"
        f"OutlineColour={outline},BackColour={back},BorderStyle={border_style},"
        "Outline=2,Shadow=0,Alignment=2,MarginV=72"
    )


def _load_word_timings(audio_path: str | None) -> list[dict] | None:
    """Word timings written by the TTS step, if present + non-empty."""
    if not audio_path:
        return None
    sidecar = audio_path + ".words.json"
    if not os.path.exists(sidecar):
        return None
    try:
        with open(sidecar, encoding="utf-8") as f:
            words = json.load(f)
        return words if isinstance(words, list) and words else None
    except Exception:
        return None


def generate_subtitle_file(
    script: str,
    duration: float,
    *,
    audio_path: str | None = None,
    channel_id: str | None = None,
    output_path: str | None = None,
) -> str:
    output_dir = os.path.join("output", "video")
    os.makedirs(output_dir, exist_ok=True)

    style = caption_style(channel_id)
    words = _load_word_timings(audio_path) if style in ("word", "karaoke") else None
    if words is None and style in ("word", "karaoke"):
        # No ElevenLabs sidecar (local TTS, imported audio) — try the whisper
        # alignment seam (CAPTION_ALIGN_BACKEND; off by default, fail-open to
        # the proportional estimate below).
        from video.caption_timing import words_from_caption_align

        words = words_from_caption_align(audio_path)
        if words:
            # Whisper transcribes blind, so those words are ASR text — "Salkal" for
            # "Salkilld". Keep its timings, take the text from the script we already
            # have. None = the transcript didn't match, so its timings can't be
            # trusted either; fall through to the proportional estimate.
            from video.caption_retext import retext_words_from_script

            words = retext_words_from_script(words, script)

    # Real word timings → accurate SRT or animated karaoke ASS; else the
    # proportional SRT estimate (unchanged behaviour).
    if words:
        from video.caption_timing import build_ass_karaoke, build_srt_from_words

        max_words = caption_words_per_line()
        if style == "karaoke":
            text = build_ass_karaoke(words, max_words=max(2, min(4, max_words)))
            ext = ".ass"
            companion_srt = build_srt_from_words(words, max_words=max_words)
        else:
            text = build_srt_from_words(words, max_words=max_words)
            ext = ".srt"
            companion_srt = ""
    else:
        text = build_srt(script, duration)
        ext = ".srt"
        companion_srt = ""

    if not text.strip():
        raise ValueError("Subtitle generation failed: empty script.")

    requested = output_path or os.path.join(output_dir, f"temp_subtitles{ext}")
    subtitle_path = os.path.abspath(os.path.splitext(requested)[0] + ext)
    os.makedirs(os.path.dirname(subtitle_path), exist_ok=True)
    with open(subtitle_path, "w", encoding="utf-8") as f:
        f.write(text)
    if companion_srt:
        with open(os.path.splitext(subtitle_path)[0] + ".srt", "w", encoding="utf-8") as f:
            f.write(companion_srt)
    return subtitle_path
