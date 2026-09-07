"""Word-level caption timing from ElevenLabs alignment → accurate SRT / karaoke ASS.

The old captions estimated timing by *word count* (proportional spacing). Since the
TTS step already gets per-character alignment back from ElevenLabs
(`convert_with_timestamps`), we can build captions on the *real* spoken timing:

  - `words_from_alignment` — character alignment → word timings (pure).
  - `build_srt_from_words` — accurately-timed, sentence/length-aware SRT chunks.
  - `build_ass_karaoke` — the same chunks as ASS with per-word karaoke highlight
    (the word "pops" as it's spoken), the Phase-Q animated-caption upgrade.

All pure + deterministic so they're unit-tested without the API or a render.

One exception: `words_from_caption_align` wires the Pillar-6 whisper alignment seam
(`core/caption_align.py`) for audio *without* an ElevenLabs sidecar — env-gated OFF
by default and fail-open (returns None), so it never breaks the proportional path.
"""

from __future__ import annotations


def _as_time(value: object) -> float | None:
    """Coerce a segment timestamp to float; None on anything non-numeric."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def words_from_caption_align(audio_path: str | None) -> list[dict] | None:
    """Whisper-aligned word timings for audio with no ElevenLabs `.words.json` sidecar.

    Calls `core.caption_align.transcribe_and_align` (lazy — whisperx/torch only load
    when `CAPTION_ALIGN_BACKEND` selects a backend) and converts its word segments
    to the same `[{word, start, end}, …]` shape `words_from_alignment` produces, so
    callers feed them into the existing SRT/ASS builders unchanged.

    Fail-open: returns None when the backend is unset, uninstalled, or errors —
    the caller keeps the proportional caption estimate. Never raises.
    """
    if not audio_path:
        return None
    try:
        from core.caption_align import transcribe_and_align
        from core.providers import selected_provider

        if selected_provider("CAPTION_ALIGN_BACKEND", "none") in ("", "none"):
            return None
        result = transcribe_and_align(audio_path)
    except Exception:
        return None
    if not result.ok or not isinstance(result.data, list):
        return None
    words: list[dict] = []
    for seg in result.data:
        if not isinstance(seg, dict):
            continue
        word = str(seg.get("word") or "").strip()
        if not word:
            continue
        # Unaligned words (whisperx skips timing for e.g. numerals) keep None
        # start/end — the builders below already tolerate that per-word.
        words.append(
            {"word": word, "start": _as_time(seg.get("start")), "end": _as_time(seg.get("end"))}
        )
    return words or None


def words_from_alignment(
    characters: list[str], starts: list[float], ends: list[float]
) -> list[dict]:
    """Group character alignment into word timings: [{word, start, end}, …]."""
    words: list[dict] = []
    cur = ""
    cur_start: float | None = None
    cur_end: float | None = None
    for ch, s, e in zip(characters, starts, ends, strict=False):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": cur_start, "end": cur_end})
                cur, cur_start, cur_end = "", None, None
        else:
            if not cur:
                cur_start = float(s)
            cur += ch
            cur_end = float(e)
    if cur:
        words.append({"word": cur, "start": cur_start, "end": cur_end})
    return words


def two_line_split_index(n: int, max_words: int) -> int | None:
    """#505. Midpoint for a two-line wrap; None when greedy fill still applies."""
    if n <= max_words or n > max_words * 2:
        return None
    mid = (n + 1) // 2
    return min(max(n - max_words, mid), max_words)


def group_into_lines(words: list[dict], max_words: int) -> list[list[dict]]:
    """Sentence/length-aware grouping: break on sentence-end punctuation or length."""
    sentences: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        cur.append(w)
        if (w.get("word") or "")[-1:] in ".!?":
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    lines: list[list[dict]] = []
    for sent in sentences:
        idx = two_line_split_index(len(sent), max_words)
        if idx is not None:
            lines.append(sent[:idx])
            lines.append(sent[idx:])
            continue
        for i in range(0, len(sent), max_words):
            chunk = sent[i : i + max_words]
            if chunk:
                lines.append(chunk)
    return _rebalance_orphan_line(lines)


def _ends_sentence(word: dict) -> bool:
    return (word.get("word") or "")[-1:] in ".!?"


def _rebalance_orphan_line(lines: list[list[dict]]) -> list[list[dict]]:
    """Candidate 419 on the word-timed path: never leave a lone word as the last
    cue. The word carries its own start/end, so moving it moves its timing and
    `_line_span` follows. A line that ends a sentence keeps its last word --
    `split_script_into_lines` holds the same boundary rule."""
    if len(lines) < 2:
        return lines
    if len(lines[-1]) != 1 or len(lines[-2]) < 2:
        return lines
    if _ends_sentence(lines[-2][-1]):
        return lines
    lines[-1].insert(0, lines[-2].pop())
    return lines


def _srt_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms, s = 0, s + 1
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _ass_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02}:{s:05.2f}"


def _line_span(line: list[dict]) -> tuple[float, float]:
    """Start/end for a caption line, tolerant of missing per-word times.

    whisper alignment (words_from_caption_align) can hand back words with None
    start/end; naively taking `line[-1]["end"] or start` then collapses the block to
    the line's START — a zero/negative-duration cue. Fall back to the last word that
    kept a valid time, and guarantee a minimum visible span."""
    starts = [w["start"] for w in line if w.get("start") is not None]
    ends = [w["end"] for w in line if w.get("end") is not None]
    start = float(starts[0]) if starts else 0.0
    end = float(ends[-1]) if ends else (float(starts[-1]) if starts else start)
    if end <= start:
        end = start + 0.4
    return start, end


def build_srt_from_words(words: list[dict], *, max_words: int = 5) -> str:
    """Accurately-timed SRT from word timings (chunk start/end = real spoken time)."""
    lines = group_into_lines(words, max_words)
    blocks: list[str] = []
    for i, line in enumerate(lines):
        start, end = _line_span(line)
        text = " ".join(w["word"] for w in line)
        blocks.append(f"{i + 1}\n{_srt_ts(start)} --> {_srt_ts(end)}\n{text}\n")
    return ("\n".join(blocks) + "\n") if blocks else ""


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},{secondary},&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass_karaoke(
    words: list[dict],
    *,
    max_words: int = 4,
    font: str = "Arial",
    size: int = 90,
    primary: str = "&H0000FFFF",  # spoken word — yellow (BGR)
    secondary: str = "&H00FFFFFF",  # not-yet-spoken — white
) -> str:
    """Karaoke ASS: each word highlights as it's spoken (per-word \\k timing)."""
    lines = group_into_lines(words, max_words)
    events: list[str] = []
    for line in lines:
        start, end = _line_span(line)
        parts: list[str] = []
        for w in line:
            ws = float(w["start"] or start)
            we = float(w["end"] or ws)
            dur_cs = max(1, int(round((we - ws) * 100)))
            text = (w["word"] or "").replace("{", "(").replace("}", ")")
            parts.append(f"{{\\k{dur_cs}}}{text}")
        events.append(
            f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},Default,,0,0,0,,{' '.join(parts)}"
        )
    header = _ASS_HEADER.format(font=font, size=size, primary=primary, secondary=secondary)
    return header + "\n".join(events) + "\n"
