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
        from core.caption_align import align_backend, transcribe_and_align

        if align_backend() in ("", "none"):
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
    ms = round((seconds - int(seconds)) * 1000)
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
Style: Default,{font},{size},{primary},{secondary},&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,{alignment},80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

_ASS_HEADER_PAIRED = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{title_font},{size},{primary},{secondary},&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,{alignment},80,80,260,1
Style: Body,{body_font},{size},{primary},{secondary},&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,{alignment},80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# Usable caption width: PlayResX 1080 minus the styles' 80 px side margins.
_ASS_TEXT_WIDTH = 1080 - 2 * 80
# Bold Arial/Impact averages about half an em per character in mixed-case English.
_CHAR_EM = 0.52


def karaoke_max_chars(size: int) -> int:
    """Characters that fit on one karaoke line at `size` px (WrapStyle 2 never wraps)."""
    return max(8, int(_ASS_TEXT_WIDTH / (max(1, int(size)) * _CHAR_EM)))


def _fit_chars(lines: list[list[dict]], max_chars: int) -> list[list[dict]]:
    """Split any line wider than `max_chars` greedily; a single long word keeps its own line.

    Found in the wave 23 preview: at the restored 90 px (#783) a 4-word line such as
    "aunts Rockstar because they" ran off both edges of the frame.
    """
    out: list[list[dict]] = []
    for line in lines:
        cur: list[dict] = []
        width = 0
        for w in line:
            n = len(str(w.get("word") or ""))
            if cur and width + 1 + n > max_chars:
                out.append(cur)
                cur, width = [], 0
            width = n if not cur else width + 1 + n
            cur.append(w)
        if cur:
            out.append(cur)
    return out


_NARRATOR = "narrator"


def _role(word: dict) -> str:
    return str(word.get("role") or _NARRATOR)


def _lines_by_voice(words: list[dict], max_words: int) -> list[list[dict]]:
    """#506: a caption line never mixes voices - group each voice's run on its own."""
    runs: list[list[dict]] = []
    for w in words:
        if runs and _role(runs[-1][-1]) == _role(w):
            runs[-1].append(w)
        else:
            runs.append([w])
    lines: list[list[dict]] = []
    for run in runs:
        lines.extend(group_into_lines(run, max_words))
    return lines


# #503: how a caption line arrives. Each is an override block that leads the line's text,
# so per-word `\\k` timing after it is untouched.
ENTRANCES = ("none", "pop", "fade", "slide")
_POP = r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}"
_FADE = r"{\fad(150,0)}"


def entrance_tag(
    entrance: str | None,
    *,
    play_res: tuple[int, int] = (1080, 1920),
    alignment: int = 2,
    margin_v: int = 260,
) -> str:
    """The override block for `entrance` ("" for none or an unknown name).

    `slide` needs the line's own position: `\\move` rises 40 px (on a 1920-px canvas,
    scaled to the script's) onto where the style would have put it.
    """
    name = str(entrance or "none").strip().lower()
    if name == "pop":
        return _POP
    if name == "fade":
        return _FADE
    if name == "slide":
        width, height = play_res
        x = width // 2
        y = margin_v if alignment == 8 else height - margin_v
        rise = max(1, round(40 * height / 1920))
        return rf"{{\move({x},{y + rise},{x},{y},0,150)}}"
    return ""


def build_ass_karaoke(
    words: list[dict],
    *,
    max_words: int = 4,
    font: str = "Arial",
    size: int = 90,
    primary: str = "&H0000FFFF",  # spoken word — yellow (BGR)
    secondary: str = "&H00FFFFFF",  # not-yet-spoken — white
    title_font: str | None = None,
    body_font: str | None = None,
    anchor: str = "bottom",
    voice2_primary: str = "&H00F7C34F&",  # #506: the second voice's spoken word
    entrance: str = "none",  # #503: pop / fade / slide / none
) -> str:
    """Karaoke ASS: each word highlights as it's spoken (per-word \\k timing).

    Words carrying a non-narrator `role` (a two-voice render, #506) are grouped apart
    and use the `Voice2` style, whose highlight is `voice2_primary`. With no such word
    the output is byte-identical to the single-voice builder.
    """
    two_voices = any(_role(w) != _NARRATOR for w in words)
    grouped = (
        _lines_by_voice(words, max_words) if two_voices else group_into_lines(words, max_words)
    )
    lines = _fit_chars(grouped, karaoke_max_chars(size))
    paired = title_font is not None or body_font is not None
    title = (title_font or font).replace(",", " ").strip() or font
    body = (body_font or font).replace(",", " ").strip() or font
    alignment = 8 if str(anchor).strip().lower() == "top" else 2
    lead = entrance_tag(entrance, alignment=alignment)
    events: list[str] = []
    from video.caption_emoji import wrap_emoji

    for index, line in enumerate(lines):
        start, end = _line_span(line)
        style = "Title" if paired and index == 0 else ("Body" if paired else "Default")
        if two_voices and line and _role(line[0]) != _NARRATOR:
            style = "Voice2"
        # #504: an emoji run switches to the emoji font and back to this line's own font.
        line_font = title if style == "Title" else body if paired else font
        parts: list[str] = []
        for w in line:
            ws = float(w["start"] or start)
            we = float(w["end"] or ws)
            dur_cs = max(1, round((we - ws) * 100))
            text = (w["word"] or "").replace("{", "(").replace("}", ")")
            parts.append(f"{{\\k{dur_cs}}}{wrap_emoji(text, line_font)}")
        events.append(
            f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},{style},,0,0,0,,{lead}{' '.join(parts)}"
        )
    if paired:
        header = _ASS_HEADER_PAIRED.format(
            title_font=title,
            body_font=body,
            size=size,
            primary=primary,
            secondary=secondary,
            alignment=alignment,
        )
    else:
        header = _ASS_HEADER.format(
            font=font,
            size=size,
            primary=primary,
            secondary=secondary,
            alignment=alignment,
        )
    if two_voices:
        voice2 = (
            f"Style: Voice2,{body if paired else font},{size},{voice2_primary},{secondary},"
            "&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,"
            f"{alignment},80,80,260,1\n"
        )
        header = header.replace("\n\n[Events]", "\n" + voice2.rstrip("\n") + "\n\n[Events]", 1)
    return header + "\n".join(events) + "\n"


# libass's canvas and style defaults for a converted .srt (FFmpeg's
# ff_ass_subtitle_header_default, checked against `ffmpeg -i x.srt x.ass`, FFmpeg 7.0). Word mode's .ass keeps them, so the skin's
# force_style keys land on the same canvas they were sized for.
_SRT_CANVAS = (384, 288)
_SRT_STYLE_DEFAULTS = {
    "FontName": "Arial",
    "FontSize": "16",
    "PrimaryColour": "&Hffffff",
    "SecondaryColour": "&Hffffff",
    "OutlineColour": "&H0",
    "BackColour": "&H0",
    "Bold": "0",
    "Italic": "0",
    "Underline": "0",
    "StrikeOut": "0",
    "ScaleX": "100",
    "ScaleY": "100",
    "Spacing": "0",
    "Angle": "0",
    "BorderStyle": "1",
    "Outline": "1",
    "Shadow": "0",
    "Alignment": "2",
    "MarginL": "10",
    "MarginR": "10",
    "MarginV": "10",
    "Encoding": "1",
}


def build_ass_from_words(
    words: list[dict], *, max_words: int = 5, style: str = "", entrance: str = "none"
) -> str:
    """Word-mode captions as .ass so an entrance can render (#503).

    FFmpeg's SRT decoder strips every override tag but `\\an`, so a `\\fad` in an .srt
    never shows. Same cues as `build_srt_from_words`, on the SRT canvas, with `style`
    (a force_style string, `Key=Value,...`) as the Default style.
    """
    fields = dict(_SRT_STYLE_DEFAULTS)
    for part in (style or "").split(","):
        key, sep, value = part.partition("=")
        if sep and key.strip() in fields:
            fields[key.strip()] = value.strip()
    width, height = _SRT_CANVAS
    try:
        alignment, margin_v = int(fields["Alignment"]), int(fields["MarginV"])
    except ValueError:
        alignment, margin_v = 2, 10
    lead = entrance_tag(entrance, play_res=_SRT_CANVAS, alignment=alignment, margin_v=margin_v)
    from video.caption_emoji import wrap_emoji

    events = []
    for line in group_into_lines(words, max_words):
        start, end = _line_span(line)
        text = " ".join(str(w["word"] or "") for w in line).replace("{", "(").replace("}", ")")
        text = wrap_emoji(text, fields["FontName"])  # #504
        events.append(f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},Default,,0,0,0,,{lead}{text}")
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: None\n\n"
        "[V4+ Styles]\nFormat: " + ", ".join(["Name", *_SRT_STYLE_DEFAULTS]) + "\n"
        "Style: Default," + ",".join(fields.values()) + "\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    return header + "\n".join(events) + ("\n" if events else "")
