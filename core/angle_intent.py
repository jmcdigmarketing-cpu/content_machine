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
# #533. Until 2026-09-05 this file knew one alternative frame, so every calm idea
# fell to `default` — and `controversy` is in every non-reaction angle table.
# The operator's own seeds ("how does the offside rule actually work", "top 5
# heavyweights") were structurally indistinguishable from a request for a take.
ANGLE_EXPLAINER = "explainer"
ANGLE_LIST = "list"
ANGLE_TUTORIAL = "tutorial"
ANGLE_COMPARISON = "comparison"
ANGLE_RETROSPECTIVE = "retrospective"

ALL_INTENTS = (
    ANGLE_REACTION,
    ANGLE_EXPLAINER,
    ANGLE_LIST,
    ANGLE_TUTORIAL,
    ANGLE_COMPARISON,
    ANGLE_RETROSPECTIVE,
    ANGLE_DEFAULT,
)

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

# Cues for the frames beyond reaction. Deliberately narrow, for one measured
# reason: "GTA 6 meta breakdown" on an established franchise *should* keep the
# staleness pivot into critique, so "breakdown" is not an explainer cue and
# "review" is not a comparison cue. A loose lexicon here would silently disable a
# guard that is correct — `test_the_established_critique_pivot_still_survives`
# pins it. Ordered: the first match wins, so the more specific frames are checked
# before the more general ones.
_INTENT_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        ANGLE_TUTORIAL,
        ("how to ", "how do i ", "guide to", "tips for", "beginner's guide", "walkthrough"),
    ),
    (
        ANGLE_LIST,
        (
            "top 5",
            "top 10",
            "top five",
            "top ten",
            "tier list",
            "ranking every",
            "ranked:",
            "every ",
            "best ",
            "worst ",
        ),
    ),
    (
        ANGLE_COMPARISON,
        ("better or worse", " vs ", " vs. ", "compared to", "which is better", "head to head"),
    ),
    (
        ANGLE_RETROSPECTIVE,
        (
            "revisiting",
            "years later",
            "looking back",
            "retrospective",
            "back in the day",
            "anniversary",
        ),
    ),
    (
        ANGLE_EXPLAINER,
        (
            "how does",
            "how did",
            "what is ",
            "what are ",
            "why does",
            "why is ",
            "explained",
            "explainer",
            "the hidden cost",
            "actually work",
        ),
    ),
)


def detect_angle_intent(topic: str | None) -> str:
    """The frame the operator asked for, read from the topic they typed."""
    text = (topic or "").strip()
    if not text:
        return ANGLE_DEFAULT
    low = text.lower()

    if any(cue in low for cue in _REACTION_CUES):
        return ANGLE_REACTION

    for intent, cues in _INTENT_CUES:
        if any(cue in low for cue in cues):
            return intent

    # A question is asking, not reacting — "is it really that incredible?". Checked
    # after the cue tables, because "how does X work?" is a question *and* an
    # explainer, and the explainer reading is the useful one.
    if _QUESTION.search(text):
        return ANGLE_DEFAULT
    if any(word in low for word in _SUPERLATIVES) and _SHOUTING.search(text):
        return ANGLE_REACTION
    return ANGLE_DEFAULT


_INTENT_NOTES = {
    ANGLE_REACTION: "reaction (read from your topic) - analysis/critique framings suppressed",
    ANGLE_EXPLAINER: "explainer (read from your topic) - take/controversy framings suppressed",
    ANGLE_LIST: "list / ranking (read from your topic)",
    ANGLE_TUTORIAL: "tutorial (read from your topic) - take/controversy framings suppressed",
    ANGLE_COMPARISON: "comparison (read from your topic)",
    ANGLE_RETROSPECTIVE: "retrospective (read from your topic)",
}


def angle_intent_note(intent: str) -> str:
    """One operator-facing line for the angle screen. cp1252-safe (candidate 250)."""
    detail = _INTENT_NOTES.get(intent)
    return f"Angle mode: {detail}" if detail else "Angle mode: standard"
