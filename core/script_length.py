"""Script length presets, word counting, and duration estimates."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Spoken delivery rate, measured — not guessed.
#
# Was 2.4 ("energetic Shorts-style narration"), which understated real delivery by 38%:
# run 66 was shown "243 words (~101s spoken)" and rendered 70.2s of audio. Recomputed
# across **all 14 real renders** carrying an ElevenLabs word sidecar
# (`py -m scripts.bench_script_duration`): median 3.32 w/s, range 2.76-3.64.
#
# Re-derive with that script if the voice, model or stability settings change — this
# drifted silently for months because nothing ever checked it against real audio.
WORDS_PER_SECOND = 3.3


@dataclass(frozen=True)
class LengthPreset:
    choice: str
    label: str
    min_words: int
    max_words: int

    @property
    def target_words(self) -> int:
        return (self.min_words + self.max_words) // 2

    # Durations are DERIVED from the word range, never stored. They used to be
    # hardcoded alongside it and the two silently disagreed: "Extended (420-900s)"
    # actually produced ~300-600s. Deriving them means a change to WORDS_PER_SECOND
    # can never leave the menu advertising a duration the preset cannot hit.
    @property
    def min_seconds(self) -> int:
        return round(self.min_words / WORDS_PER_SECOND)

    @property
    def max_seconds(self) -> int:
        return round(self.max_words / WORDS_PER_SECOND)

    def duration_hint(self) -> str:
        return f"{self.min_seconds}-{self.max_seconds}s"


# Word ranges are the source of truth; seconds follow from them. Deliberately left
# unchanged when the rate was corrected, so a stored `length_preset` label still means
# the same thing to the learned-length analytics loop.
PRESETS = {
    "1": LengthPreset("1", "Short", 100, 150),
    "2": LengthPreset("2", "Medium", 150, 300),
    "3": LengthPreset("3", "Long", 300, 750),
    "4": LengthPreset("4", "Extended", 1000, 2000),
}


def get_length_preset(length_choice: str) -> LengthPreset:
    return PRESETS.get(str(length_choice).strip(), PRESETS["2"])


def nudge_length(length_choice: str, delta: int) -> str:
    """Shift a length choice by `delta` presets, clamped to the 1-4 range.

    Used by the post-generation "+ longer / - shorter" prompt. An unparseable
    choice falls back to Medium ("2") before the shift.
    """
    try:
        current = int(str(length_choice).strip())
    except (TypeError, ValueError):
        current = 2
    return str(max(1, min(4, current + delta)))


def word_range(length_choice: str) -> tuple[int, int]:
    p = get_length_preset(length_choice)
    return p.min_words, p.max_words


def count_spoken_words(script: str) -> int:
    text = re.sub(r"\s+", " ", (script or "").strip())
    if not text:
        return 0
    return len(text.split())


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PADDING_LEAD = re.compile(
    r"^(anyway|that said|in conclusion|to wrap(?: it)? up|so yeah|basically|"
    r"at the end of the day|all in all|in other words|as i (?:said|mentioned)|"
    r"let that sink in|you already know|moving on)\b",
    re.I,
)


def trim_enabled() -> bool:
    return os.getenv("SCRIPT_TRIM", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def split_spoken_sentences(script: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split((script or "").strip())
    return [p.strip() for p in parts if p.strip()]


def trim_overlength(
    script: str,
    *,
    max_words: int,
    min_words: int = 0,
) -> tuple[str, int]:
    """Drop trailing padding sentences when over length.

    Never clips mid-sentence (hard cap remains refuse in TTS). Never drops the
    hook (first sentence). Never goes below min_words. Returns (script, words_removed).
    """
    if not trim_enabled() or max_words <= 0:
        return script, 0
    current = count_spoken_words(script)
    if current <= max_words:
        return script, 0
    sentences = split_spoken_sentences(script)
    if len(sentences) <= 1:
        return script, 0

    def _join(parts: list[str]) -> str:
        return " ".join(parts)

    def _ok(parts: list[str]) -> bool:
        return count_spoken_words(_join(parts)) >= min_words and len(parts) >= 1

    changed = True
    while changed and count_spoken_words(_join(sentences)) > max_words and len(sentences) > 1:
        changed = False
        for i in range(len(sentences) - 1, 0, -1):
            if not _PADDING_LEAD.search(sentences[i]):
                continue
            trial = sentences[:i] + sentences[i + 1 :]
            if _ok(trial):
                sentences = trial
                changed = True
                break
    while count_spoken_words(_join(sentences)) > max_words and len(sentences) > 1:
        trial = sentences[:-1]
        if not _ok(trial):
            break
        sentences = trial
    out = _join(sentences)
    return out, max(0, current - count_spoken_words(out))


def estimate_duration_seconds(script: str, *, wps: float = WORDS_PER_SECOND) -> float:
    return count_spoken_words(script) / wps if wps > 0 else 0.0


def format_length_report(script: str, preset: LengthPreset) -> str:
    words = count_spoken_words(script)
    seconds = estimate_duration_seconds(script)
    status = "ok"
    if words < preset.min_words:
        status = "SHORT"
    elif words > preset.max_words:
        status = "LONG"
    return (
        f"{words} words (~{seconds:.0f}s spoken) — target {preset.min_words}-{preset.max_words} "
        f"words ({preset.duration_hint()}) [{status}]"
    )


def length_system_addendum(preset: LengthPreset) -> str:
    if preset.choice == "4":
        return (
            "FORMAT: Extended deep-dive (7-15 minutes) — a LONG video, not a long-winded one. "
            "Open by stating exactly what happened in plain words. Then move through it "
            "concretely — fact, then your read on that fact; next fact, next read — building to "
            "one clear thesis you commit to. Use the specific moments and numbers in VERIFIED "
            "FACTS as the spine. "
            "Earn every minute with NEW information or a sharper take. Do NOT pad to hit length "
            "with abstraction, restating your own points, or 'on the other hand' filler — if "
            "there aren't enough verified facts to fill the time honestly, write tighter and "
            "shorter rather than bloating. "
            "It is NOT an academic essay: no 'steelman the other side', no balanced both-sides "
            "survey, no 'in conclusion'. No section headers or bullets in the spoken script. "
            "Aim for 1000+ words only if every word earns its place."
        )
    if preset.choice == "3":
        return (
            "FORMAT: Long-form vertical video (2-5 minutes). "
            "The script MUST be substantial: multiple beats, examples, and a clear conclusion. "
            "Do NOT write a 30-second Short."
        )
    if preset.choice == "2":
        return (
            "FORMAT: Medium vertical video (~1-2 minutes). "
            "Develop the angle with more than one section; avoid single-paragraph summaries."
        )
    return "FORMAT: YouTube Short (~40-60 seconds). " "Tight, punchy, one core angle."
