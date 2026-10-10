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
# #1016 (run 124): "How the 0-4 chargers can turn it around this year" asks what has to
# happen. It was `default`, so the prompt said "TAKE A SIDE" and the angles were takes.
ANGLE_PLAN = "plan"
# #1084 (run 125): "Chargers Hopeium going into week 5" asks for the positives - the points
# of hope. It was `default`, and every angle came back knocking the hope.
ANGLE_HOPE = "hope"
# #1084: the operator's decision (2026-10-10) - a take only when asked for. Until then the
# take machinery WAS `default`, so every topic without a cue word got one.
ANGLE_TAKE = "take"

ALL_INTENTS = (
    ANGLE_REACTION,
    ANGLE_PLAN,
    ANGLE_HOPE,
    ANGLE_TAKE,
    ANGLE_EXPLAINER,
    ANGLE_LIST,
    ANGLE_TUTORIAL,
    ANGLE_COMPARISON,
    ANGLE_RETROSPECTIVE,
    ANGLE_DEFAULT,
)

# Formats that must not be ordered to take a side. Used by the research brief
# and the script prompt (#659 / #660).
CALM_INTENTS = frozenset(
    {
        ANGLE_PLAN,
        ANGLE_HOPE,
        ANGLE_EXPLAINER,
        ANGLE_LIST,
        ANGLE_TUTORIAL,
        ANGLE_COMPARISON,
        ANGLE_RETROSPECTIVE,
    }
)

# Phrases, not bare adjectives. "looks" alone appears in "looks broken"; "amazing"
# alone appears in "is it really that amazing?". Both are critique framings.
_REACTION_CUES = (
    "reaction",
    "reacting",
    "react to",
    "first impressions",
    "first look",
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
# #1084: "no hope" / "hopeless" is not asking for hope.
_NO_HOPE = re.compile(r"\b(?:no|lost|zero|without|any)\s+hope\b|\bhopeless", re.I)
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
        # #1084: asked for by name - checked first, so "hot take: how can they fix it" stays one.
        ANGLE_TAKE,
        (
            "hot take",
            "overrated",
            "underrated",
            "frauds",
            "a fraud",
            "debate",
            "unpopular opinion",
            "my take",
            "controversial",
            "is it over",
        ),
    ),
    (
        # #1084: "hopium" is the operator's word for optimism, not mockery.
        ANGLE_HOPE,
        (
            "hopium",
            "hopeium",
            "hope",
            "positives",
            "bright spot",
            "reasons to believe",
            "reason to believe",
            "optimis",
            "silver lining",
            "good news",
            "what's going right",
            "whats going right",
            "upside",
        ),
    ),
    (
        ANGLE_PLAN,
        (
            "how can ",
            "how could ",
            "how will ",
            "how do the ",
            "what it takes",
            "what will it take",
            "what would it take",
            "turn it around",
            "turn things around",
            "path to ",
            "can still ",
            "how to fix",
            "what needs to change",
        ),
    ),
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
            "rankings",
            "ranked:",
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
            "what to ",
            "online economy",
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
        if intent == ANGLE_HOPE and _NO_HOPE.search(text):
            continue
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
    ANGLE_DEFAULT: (
        "neutral analysis - a take only when you ask ('hot take', 'overrated', 'debate')"
    ),
    ANGLE_HOPE: "hope (read from your idea) - every angle a reason for optimism; no hot take",
    ANGLE_TAKE: "take (you asked for one) - angles argue a side",
    ANGLE_PLAN: "plan (read from your idea) - answers what has to happen; no hot take",
    ANGLE_REACTION: "reaction (read from your topic) - analysis/critique framings suppressed",
    ANGLE_EXPLAINER: "explainer (read from your topic) - take/controversy framings suppressed",
    ANGLE_LIST: "list / ranking (read from your topic)",
    ANGLE_TUTORIAL: "tutorial (read from your topic) - take/controversy framings suppressed",
    ANGLE_COMPARISON: "comparison (read from your topic)",
    ANGLE_RETROSPECTIVE: "retrospective (read from your topic)",
}


def intent_of(*texts: str | None) -> str:
    """The first non-default intent among `texts` (the angle, the seed, the operator's
    brief), else default. #1016: a script whose angle said nothing kept the take push
    even when the operator's own words asked "how can ..."."""
    for text in texts:
        intent = detect_angle_intent(text)
        if intent != ANGLE_DEFAULT:
            return intent
    return ANGLE_DEFAULT


def format_for_intent(intent: str) -> str:
    """Research-brief `recommended_format` for a detected intent.

    #1084: `default` is neutral `analysis`; `short_debate` - the take machinery - is only
    for a take the operator asked for. (It was the default until 2026-10-10.)
    """
    if intent == ANGLE_TAKE:
        return "short_debate"
    if intent == ANGLE_DEFAULT or intent not in ALL_INTENTS:
        return "analysis"
    return intent


def angle_intent_note(intent: str) -> str:
    """One operator-facing line for the angle screen. cp1252-safe (candidate 250)."""
    detail = _INTENT_NOTES.get(intent) or _INTENT_NOTES[ANGLE_DEFAULT]
    return f"Angle mode: {detail}"


# #1084: words that doubt, mock or knock what a hopeful idea asked to celebrate. Run 125's
# angles: "masks deeper roster flaws", "critics question ... fan denial", "shatter ... fragile",
# "fanbase desperation". Phrases where a bare word is ambiguous ("the critical matchup",
# "why the doubters are wrong" are reasons for hope).
_DOUBT = (
    "mask",
    "flaw",
    "denial",
    "desperat",
    "fragile",
    "shatter",
    "critics question",
    "critics say",
    "critics argue",
    "delusion",
    "false hope",
    "wishful",
    "mirage",
    "overrated",
    "fraud",
    "doomed",
    "exposed",
    "copium",
    "reality check",
    "smoke and mirrors",
    "too good to be true",
)
# Mockery of what people believe - a hot take on a neutral topic nobody asked for. Kept narrow
# on purpose: "fraud" and "collapse" are facts in a finance story.
_DERISION = (
    "denial",
    "delusion",
    "desperat",
    "copium",
    "mirage",
    "overrated",
    "doomed",
    "smoke and mirrors",
)


def stance_flip(text: str, intent: str) -> str:
    """Why ``text`` knocks the stance of an idea read as ``intent``, or "" (#1084).

    A take the operator asked for is never a flip; a hopeful idea is flipped by doubt or
    mockery; any other idea by mockery only.
    """
    if intent == ANGLE_TAKE:
        return ""
    words = _DOUBT if intent == ANGLE_HOPE else _DERISION
    low = (text or "").lower()
    for word in words:
        if re.search(rf"\b{re.escape(word)}", low):
            stance = "a hopeful idea" if intent == ANGLE_HOPE else "a neutral one"
            return f"'{word}' knocks {stance}"
    return ""


def stance_rule(intent: str) -> str:
    """The STANCE line every prompt that writes for this idea carries (#1084)."""
    if intent == ANGLE_HOPE:
        return (
            "STANCE: the operator is asking for reasons for HOPE. Slang like 'hopium' or "
            "'hopeium' is their word for optimism, not mockery. Every angle is a different, "
            "fact-checkable reason for optimism. Never question, debunk, psychoanalyse or mock "
            "the hope - no 'critics', 'denial', 'fragile', 'masks', 'reality check'."
        )
    if intent == ANGLE_TAKE:
        return ""
    return (
        "STANCE: neutral analysis - what happened, what it means, what to watch. No "
        "contrarian counter-take, no hot take and no mocking the fans or the subject; the "
        "operator asks by name when they want a take."
    )
