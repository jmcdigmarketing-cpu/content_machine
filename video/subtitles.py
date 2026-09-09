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

from core.logging import get_logger
from video.caption_timing import two_line_split_index

logger = get_logger("video.subtitles")

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
        if not words:
            continue
        idx = two_line_split_index(len(words), max_words)
        if idx is not None:
            chunks = [" ".join(words[:idx]), " ".join(words[idx:])]
        else:
            chunks = []
            for i in range(0, len(words), max_words):
                chunk = " ".join(words[i : i + max_words]).strip()
                if chunk:
                    chunks.append(chunk)
        # Rebalance THIS sentence's own chunks. Rebalancing the running list
        # instead would let a one-word sentence steal the previous sentence's
        # last word into its cue, merging two sentences into one caption line --
        # which test_sentence_boundaries_not_crossed has forbidden since before
        # candidate 419 existed.
        lines.extend(_rebalance_orphan(chunks))
    return lines


def _rebalance_orphan(chunks: list[str]) -> list[str]:
    """Never leave a 1-word last cue; steal one word from the previous line."""
    if len(chunks) < 2:
        return chunks
    last = chunks[-1].split()
    if len(last) != 1:
        return chunks
    prev = chunks[-2].split()
    if len(prev) < 2:
        return chunks
    stolen = prev.pop()
    chunks[-2] = " ".join(prev)
    chunks[-1] = stolen + " " + chunks[-1]
    return chunks


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


def caption_fonts(channel_id: str | None = None) -> tuple[str, str]:
    """Title vs body caption fonts. Both fall back to the single `font` token."""
    skin = _caption_skin(channel_id)
    base = str(skin.get("font") or "Arial").replace(",", " ").strip() or "Arial"
    title = str(skin.get("title_font") or base).replace(",", " ").strip() or base
    body = str(skin.get("body_font") or base).replace(",", " ").strip() or base
    return title, body


def caption_force_style(channel_id: str | None = None) -> str:
    """FFmpeg/libass style derived from the shipped channel caption skin."""
    skin = _caption_skin(channel_id)
    _title, body = caption_fonts(channel_id)
    font = body
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


def load_word_timings(audio_path: str | None) -> list[dict] | None:
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


def resolve_word_timings(
    audio_path: str | None,
    script: str,
    *,
    channel_id: str | None = None,
) -> list[dict] | None:
    """Real per-word timings for this audio, or None when there are none to trust.

    The single source of truth: the ElevenLabs sidecar first, then the whisper aligner
    with the script's own spelling painted back on (decisions.md §23). Public because
    captions are not the only consumer — hook motion (#26) and lower thirds (#24) need
    the same timings, and reading only the sidecar left both dead on every local-TTS
    run while the captions on that same render had whisper timings.

    Fail-open: any aligner failure returns None, which callers must treat as "no
    timings", never as "zero-length timings".
    """
    style = caption_style(channel_id)
    if style not in ("word", "karaoke"):
        return None
    words = load_word_timings(audio_path)
    if words is not None:
        return words
    # No sidecar (local TTS, imported audio) — try the alignment seam
    # (CAPTION_ALIGN_BACKEND; off by default, fail-open).
    try:
        from video.caption_timing import words_from_caption_align

        words = words_from_caption_align(audio_path)
    except Exception as exc:
        logger.debug("caption alignment skipped: %s", exc)
        return None
    if not words:
        return None
    # Whisper transcribes blind, so those words are ASR text — "Salkal" for
    # "Salkilld". Keep its timings, take the text from the script we already have.
    # None = the transcript didn't match, so its timings can't be trusted either.
    try:
        from video.caption_retext import retext_words_from_script

        return retext_words_from_script(words, script)
    except Exception as exc:
        logger.debug("caption retext skipped: %s", exc)
        return None


def generate_subtitle_file(
    script: str,
    duration: float,
    *,
    audio_path: str | None = None,
    channel_id: str | None = None,
    output_path: str | None = None,
    words: list[dict] | None = None,
) -> str:
    output_dir = os.path.join("output", "video")
    os.makedirs(output_dir, exist_ok=True)

    style = caption_style(channel_id)
    # Resolved by the caller when the render already needed them (hook motion, lower
    # thirds), so alignment runs once per render rather than once per consumer.
    if words is None:
        words = resolve_word_timings(audio_path, script, channel_id=channel_id)

    # Real word timings → accurate SRT or animated karaoke ASS; else the
    # proportional SRT estimate (unchanged behaviour).
    if words:
        from video.caption_timing import build_ass_karaoke, build_srt_from_words

        max_words = caption_words_per_line()
        if style == "karaoke":
            title_font, body_font = caption_fonts(channel_id)
            text = build_ass_karaoke(
                words,
                max_words=max(2, min(4, max_words)),
                title_font=title_font,
                body_font=body_font,
            )
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
