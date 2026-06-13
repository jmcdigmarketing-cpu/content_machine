"""
Burned-caption (SRT) generation for vertical video.

Captions are table stakes for short-form retention. This builds an SRT where:
  - lines are short, punchy chunks (default 5 words — tuned for Shorts),
  - chunks respect sentence boundaries (no caption spanning two sentences),
  - each chunk's on-screen time is PROPORTIONAL to its word count, so the
    captions track the spoken audio instead of being spaced uniformly.

Configurable via CAPTION_WORDS_PER_LINE (default 5).
"""

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


def generate_subtitle_file(script: str, duration: float) -> str:
    output_dir = os.path.join("output", "video")
    os.makedirs(output_dir, exist_ok=True)
    subtitle_path = os.path.abspath(os.path.join(output_dir, "temp_subtitles.srt"))

    srt = build_srt(script, duration)
    if not srt.strip():
        raise ValueError("Subtitle generation failed: empty script.")

    with open(subtitle_path, "w", encoding="utf-8") as f:
        f.write(srt)
    return subtitle_path
