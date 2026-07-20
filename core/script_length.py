"""Script length presets, word counting, and duration estimates."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Spoken delivery ~2.4 words/sec (energetic Shorts-style narration)
WORDS_PER_SECOND = 2.4


@dataclass(frozen=True)
class LengthPreset:
    choice: str
    label: str
    min_words: int
    max_words: int
    min_seconds: int
    max_seconds: int

    @property
    def target_words(self) -> int:
        return (self.min_words + self.max_words) // 2

    def duration_hint(self) -> str:
        return f"{self.min_seconds}-{self.max_seconds}s"


PRESETS = {
    "1": LengthPreset("1", "Short", 100, 150, 40, 60),
    "2": LengthPreset("2", "Medium", 150, 300, 60, 120),
    "3": LengthPreset("3", "Long", 300, 750, 120, 300),
    "4": LengthPreset("4", "Extended", 1000, 2000, 420, 900),
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
