"""What the operator actually asked for, read from the topic they typed.

Run 73: three consecutive topics — "GTA 6 Extended look reactions, looks great!",
"GTA 6 looks amazing!!!" — produced critique angles, because `generate_variants`
chose angle types from the channel domain and a repeat counter and never looked at
the topic string at all. A reaction video was not something the operator could ask
for.

This is deliberately a small, readable lexicon rather than an LLM call: it runs
before discovery on every variant pass, the operator is shown the result on the
angle screen, and they can override it. An inference that cannot be seen or
overridden is the wrong kind of magic.
"""

from __future__ import annotations

import re

ANGLE_REACTION = "reaction"
ANGLE_DEFAULT = "default"

# Phrases, not bare adjectives. "looks" alone appears in "looks broken"; "amazing"
# alone appears in "is it really that amazing?". Both are critique framings.
_REACTION_CUES = (
    "reaction",
    "reacting",
    "react to",
    "first impressions",
    "my thoughts",
    "looks great",
    "looks amazing",
    "looks incredible",
    "looks insane",
    "looks unreal",
    "looks sick",
    "looks good",
    "looks stunning",
    "looks gorgeous",
    "so good",
    "so hyped",
    "hyped for",
    "can't wait",
    "cant wait",
    "blown away",
    "goosebumps",
)

# A bare superlative counts only when the operator is plainly excited, which in
# practice means shouting. "GTA 6 looks amazing!!!" yes; "is GTA 6 amazing?" no.
_SUPERLATIVES = ("amazing", "incredible", "insane", "unreal", "stunning", "gorgeous")
_SHOUTING = re.compile(r"!!|[A-Z]{4,}")
_QUESTION = re.compile(r"\?")


def detect_angle_intent(topic: str | None) -> str:
    """`ANGLE_REACTION` when the operator is reacting, else `ANGLE_DEFAULT`."""
    text = (topic or "").strip()
    if not text:
        return ANGLE_DEFAULT
    low = text.lower()

    if any(cue in low for cue in _REACTION_CUES):
        return ANGLE_REACTION

    # A question is asking, not reacting — "is it really that incredible?"
    if _QUESTION.search(text):
        return ANGLE_DEFAULT
    if any(word in low for word in _SUPERLATIVES) and _SHOUTING.search(text):
        return ANGLE_REACTION
    return ANGLE_DEFAULT


def angle_intent_note(intent: str) -> str:
    """One operator-facing line for the angle screen. cp1252-safe (candidate 250)."""
    if intent == ANGLE_REACTION:
        return "Angle mode: reaction (read from your topic) - analysis/critique framings suppressed"
    return "Angle mode: standard"
