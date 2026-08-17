"""Caption text from the script, timing from whisper.

`core/caption_align.py` transcribes audio *blind*, so its captions carry ASR text. On
real channel audio that means "Salkilld" comes back as "Salkal" and "Mateusz Gamrot" as
"Mattius Gamarat" — and fighter/game names are this channel's entire subject, so burned
captions would show mangled names despite ~45ms timing accuracy. That is what kept the
local-TTS path (and with it the **$0 TTS switch**, ~91% of a rendered run's cost)
unusable.

We always have the real script at caption time — `generate_subtitle_file(script, …)`
receives it. So: keep whisper's **timings**, take the **text** from the script.

**The hard part is re-tokenisation, not misspelling.** Whisper does not merely spell
things differently, it splits and merges words, writes numerals as words, and drops or
invents tokens. From the run-65 pair:

    script  "Quillan Salkilld just submitted Mateusz Gamrot ... a top-10 lightweight"
    whisper "Quill and Salkal   just submitted Mattius Gamarat ... a top ten lightweight"

A positional zip desyncs permanently at the first split. `difflib.SequenceMatcher` over
*normalised* tokens gives an opcode stream instead, and each opcode has an honest answer:

  - `equal`   — 1:1, take whisper's start/end.
  - `replace` — n script tokens share the m ASR tokens' span, split by character length.
  - `delete`  — script words whisper missed; timed by interpolation from their neighbours.
  - `insert`  — words whisper invented; dropped, their time absorbed by the neighbours.

**Declines rather than guesses.** If too few script tokens match, the transcript is not
describing this script — which means its *timings* describe different audio too, and
painting the script over them would produce confidently-wrong captions. That is
precisely the failure shape decisions §18 is about, so we return None and let the caller
fall back to the proportional estimate, which is at least spelled correctly.

The threshold is measured, not guessed. On the real run-65 script (191 words) both the
ElevenLabs and the Piper renders score **0.869**, while unrelated audio scores ~0.0 and
a deliberately worst-case 9-word line dense with proper nouns scores 0.44. The default
sits in that empty middle, far enough below live values to never fire spuriously and far
enough above zero to still catch a genuine mismatch.

    CAPTION_RETEXT=off               # keep raw ASR text (benching/debugging)
    CAPTION_RETEXT_MIN_MATCH=0.35    # below this, decline

**What it costs:** nothing in timing. Against ElevenLabs' own word timings the retexted
output scores **p50 36ms / p90 110ms** — identical to the raw matched-word error — while
covering all 191 script words rather than the 166 that happened to transcribe cleanly.
Text goes from mangled to 191/191 exact.

Pure and deterministic — no I/O, no model, unit-tested without audio.
"""

from __future__ import annotations

import os
from difflib import SequenceMatcher

from core.logging import get_logger
from core.utils import clean_script_for_tts

logger = get_logger("video.caption_retext")

_MIN_MATCH_DEFAULT = 0.35

# Whisper writes numerals as words ("10" -> "ten"), and this channel talks about
# rankings, rounds and seasons constantly — without this, every number is a desync.
_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
    "million": "1000000",
}


def retext_enabled() -> bool:
    """On by default: whenever we have the script, its text beats the ASR's."""
    raw = (os.getenv("CAPTION_RETEXT", "") or "").strip().lower()
    return raw not in ("0", "off", "false", "no")


def min_match_ratio() -> float:
    raw = (os.getenv("CAPTION_RETEXT_MIN_MATCH", "") or "").strip()
    try:
        value = float(raw)
    except ValueError:
        return _MIN_MATCH_DEFAULT
    return value if 0.0 <= value <= 1.0 else _MIN_MATCH_DEFAULT


def normalize_token(token: object) -> str:
    """Lowercase alphanumerics, with number-words folded onto their digits."""
    cleaned = "".join(ch for ch in str(token or "").lower() if ch.isalnum())
    return _NUMBER_WORDS.get(cleaned, cleaned)


def matched_pairs(a_tokens: list[str], b_tokens: list[str]) -> list[tuple[int, int]]:
    """Index pairs of tokens that align 1:1 between two token sequences.

    Shared with `scripts/bench_caption_align.py` so the measurement and the shipped
    retexter agree on what "the same word" means.
    """
    matcher = SequenceMatcher(
        None,
        [normalize_token(t) for t in a_tokens],
        [normalize_token(t) for t in b_tokens],
        autojunk=False,
    )
    pairs: list[tuple[int, int]] = []
    for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            pairs.extend((i1 + k, j1 + k) for k in range(i2 - i1))
    return pairs


def _as_time(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _untimed(tokens: list[str]) -> list[dict]:
    return [{"word": token, "start": None, "end": None} for token in tokens]


def _spread(tokens: list[str], segments: list[dict]) -> list[dict]:
    """Share one ASR span across several script tokens, weighted by length.

    The `replace` case: "Quillan Salkilld" (2 script tokens) against
    "Quill and Salkal" (3 ASR tokens). Nothing pairs up, but the *span* is right, and
    longer words genuinely take longer to say — the same assumption `build_srt` makes.
    """
    starts = [t for t in (_as_time(s.get("start")) for s in segments) if t is not None]
    ends = [t for t in (_as_time(s.get("end")) for s in segments) if t is not None]
    if not starts or not ends:
        return _untimed(tokens)

    span_start, span_end = min(starts), max(ends)
    duration = max(0.0, span_end - span_start)
    weights = [max(1, len(token)) for token in tokens]
    total = sum(weights)

    spread: list[dict] = []
    elapsed = 0
    for token, weight in zip(tokens, weights, strict=False):
        start = span_start + duration * (elapsed / total)
        elapsed += weight
        spread.append(
            {"word": token, "start": start, "end": span_start + duration * (elapsed / total)}
        )
    return spread


def _fill_untimed(words: list[dict]) -> list[dict]:
    """Give every word whisper skipped a time, interpolated from its neighbours."""
    count = len(words)
    index = 0
    while index < count:
        if words[index]["start"] is not None:
            index += 1
            continue

        end = index
        while end < count and words[end]["start"] is None:
            end += 1
        run = end - index

        before = words[index - 1]["end"] if index > 0 else None
        after = words[end]["start"] if end < count else None
        if before is None and after is None:
            index = end  # nothing known anywhere — leave untimed, _line_span copes
            continue
        # A missing bound gets a nominal 0.3s per word rather than collapsing the run.
        if before is None:
            before = max(0.0, float(after) - 0.3 * run)
        if after is None:
            after = float(before) + 0.3 * run

        step = (float(after) - float(before)) / run
        for offset in range(run):
            words[index + offset]["start"] = float(before) + step * offset
            words[index + offset]["end"] = float(before) + step * (offset + 1)
        index = end
    return words


def _clamp_monotonic(words: list[dict]) -> list[dict]:
    """Captions must never travel backwards, whatever the spans said."""
    last_start = 0.0
    for word in words:
        start = word.get("start")
        if start is None:
            continue
        start = max(float(start), last_start)
        end = word.get("end")
        end = float(end) if end is not None else start
        word["start"], word["end"] = start, max(start, end)
        last_start = start
    return words


def retext_words_from_script(words: list[dict], script: str) -> list[dict] | None:
    """Whisper's timings carrying the script's words.

    Returns the same `[{word, start, end}, …]` shape `words_from_alignment` produces, so
    the SRT/ASS builders are unchanged. Returns **None** when the transcript doesn't
    match the script well enough to trust its timings — the caller should then fall back
    to the proportional estimate rather than burn confidently-wrong captions.

    An empty script (nothing to take text from) returns the input unchanged, as does
    `CAPTION_RETEXT=off`.
    """
    if not words:
        return None
    if not retext_enabled():
        return list(words)

    script_tokens = clean_script_for_tts(script or "").split()
    if not script_tokens:
        return list(words)

    asr = [w for w in words if isinstance(w, dict) and str(w.get("word") or "").strip()]
    if not asr:
        return None

    script_norm = [normalize_token(t) for t in script_tokens]
    asr_norm = [normalize_token(w.get("word")) for w in asr]
    opcodes = SequenceMatcher(None, script_norm, asr_norm, autojunk=False).get_opcodes()

    matched = sum(i2 - i1 for tag, i1, i2, _j1, _j2 in opcodes if tag == "equal")
    ratio = matched / len(script_tokens)
    if ratio < min_match_ratio():
        logger.warning(
            "caption retext declined: only %.0f%% of %d script words matched the "
            "transcript, so its timings describe different audio; falling back",
            ratio * 100,
            len(script_tokens),
        )
        return None

    retexted: list[dict] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for offset in range(i2 - i1):
                segment = asr[j1 + offset]
                retexted.append(
                    {
                        "word": script_tokens[i1 + offset],
                        "start": _as_time(segment.get("start")),
                        "end": _as_time(segment.get("end")),
                    }
                )
        elif tag == "replace":
            retexted.extend(_spread(script_tokens[i1:i2], asr[j1:j2]))
        elif tag == "delete":
            retexted.extend(_untimed(script_tokens[i1:i2]))
        # "insert" — whisper heard a word that isn't in the script; drop it and let the
        # neighbouring spans absorb its time.

    return _clamp_monotonic(_fill_untimed(retexted))
