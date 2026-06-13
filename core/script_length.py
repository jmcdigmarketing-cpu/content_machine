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
            "FORMAT: Extended long-form video (7-15 minutes). "
            "Structure as a proper essay or documentary: "
            "  1. Cold open / hook (1-2 sentences of undeniable fact or contradiction). "
            "  2. Context section — what the situation is and why it matters. "
            "  3. Deep dive — 3-5 distinct sub-points or angles with examples. "
            "  4. Counter-argument or complication — steelman the other side. "
            "  5. Analysis / opinion — your take with reasoning. "
            "  6. Implication / call to action — what happens next, what viewers should think about. "
            "Each section should flow naturally; no section headers or bullet points in the spoken script. "
            "The script MUST reach at least 1000 words of spoken delivery."
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
