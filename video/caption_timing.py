"""Word-level caption timing from ElevenLabs alignment → accurate SRT / karaoke ASS.

The old captions estimated timing by *word count* (proportional spacing). Since the
TTS step already gets per-character alignment back from ElevenLabs
(`convert_with_timestamps`), we can build captions on the *real* spoken timing:

  - `words_from_alignment` — character alignment → word timings (pure).
  - `build_srt_from_words` — accurately-timed, sentence/length-aware SRT chunks.
  - `build_ass_karaoke` — the same chunks as ASS with per-word karaoke highlight
    (the word "pops" as it's spoken), the Phase-Q animated-caption upgrade.

All pure + deterministic so they're unit-tested without the API or a render.
"""

from __future__ import annotations


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


def group_into_lines(words: list[dict], max_words: int) -> list[list[dict]]:
    """Sentence/length-aware grouping: break on sentence-end punctuation or length."""
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        cur.append(w)
        ends_sentence = (w.get("word") or "")[-1:] in ".!?"
        if len(cur) >= max_words or ends_sentence:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
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


def build_srt_from_words(words: list[dict], *, max_words: int = 5) -> str:
    """Accurately-timed SRT from word timings (chunk start/end = real spoken time)."""
    lines = group_into_lines(words, max_words)
    blocks: list[str] = []
    for i, line in enumerate(lines):
        start = line[0]["start"] or 0.0
        end = line[-1]["end"] or start
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
        start = line[0]["start"] or 0.0
        end = line[-1]["end"] or start
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
