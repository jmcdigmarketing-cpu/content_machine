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

import json
import os
import re
from dataclasses import asdict, dataclass, fields

from core import process_state

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
# #1084: "no hope" / "hopeless" is not asking for hope. #1094: "any hope" only after a
# negation - "Is there any hope for the Jets?" asks for it; "they don't have any hope" does not.
_NO_HOPE = re.compile(
    r"\b(?:no|lost|zero|without)\s+(?:any\s+)?hope\b|\bhopeless"
    r"|(?:n't|\bnot|\bnever)\s+(?:\w+\s+){0,2}any\s+hope\b",
    re.I,
)
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
            # #1090: the operator's own verdict, stated. "Jets are doomed" read neutral, and the
            # neutral mockery filter then dropped the angle that agreed with it. Phrases, not
            # bare words: "is done" is news ("the trade is done"), "elite" alone is a tier.
            "is washed",
            "are washed",
            "washed up",
            "is cooked",
            "are cooked",
            "is doomed",
            "are doomed",
            "is elite",
            "are elite",
            "is the goat",
            "is finished",
            "are finished",
            "is a bust",
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


def _asks(topic: str | None) -> list[tuple[str, str]]:
    """Every (intent, cue) the text asks for, in table order - the reaction cues, then the
    cue tables, one cue per intent (#1096)."""
    text = (topic or "").strip()
    if not text:
        return []
    low = text.lower()
    out: list[tuple[str, str]] = []
    reaction = next((cue for cue in _REACTION_CUES if cue in low), "")
    if reaction:
        out.append((ANGLE_REACTION, reaction))
    for intent, cues in _INTENT_CUES:
        if intent == ANGLE_HOPE and _NO_HOPE.search(text):
            continue
        cue = next((c for c in cues if c in low), "")
        if cue:
            out.append((intent, cue.strip()))
    if out:
        return out
    # A question is asking, not reacting — "is it really that incredible?". Checked
    # after the cue tables, because "how does X work?" is a question *and* an
    # explainer, and the explainer reading is the useful one.
    if _QUESTION.search(text):
        return []
    for word in _SUPERLATIVES:
        if word in low and _SHOUTING.search(text):
            return [(ANGLE_REACTION, word)]
    return []


def intents_in(text: str | None) -> list[str]:
    """Every intent ``text`` asks for, in table order (#1096). Run 125's sibling: "How the
    Chargers turn it around - reasons for hope" asks for hope AND a plan; first match wins
    kept only the hope."""
    return [intent for intent, _cue in _asks(text)]


def _detect(topic: str | None) -> tuple[str, str]:
    """(intent, the cue that set it) - "" for the cue when nothing did."""
    asks = _asks(topic)
    return asks[0] if asks else (ANGLE_DEFAULT, "")


def detect_angle_intent(topic: str | None) -> str:
    """The frame the operator asked for, read from the topic they typed."""
    return _detect(topic)[0]


@dataclass(frozen=True)
class IntentRead:
    """The run's intent, read once (#1091) - with where it came from, for the record.

    ``source``: "cue" (a cue word in the operator's text), "default" (none - neutral
    analysis), "operator" (changed on the angle screen, #1092). ``cue``: the words that set it.
    """

    intent: str = ANGLE_DEFAULT
    source: str = "default"
    cue: str = ""
    # #1096: the second thing the idea asks for ("turn it around" beside "reasons for hope").
    also: str = ""
    also_cue: str = ""
    # #1089: what was read before the operator changed it - the correction, for the record.
    detected: str = ""

    def features(self) -> dict[str, str]:
        out = {
            "angle_intent": self.intent,
            "intent_source": self.source,
            "intent_cue": self.cue,
            "intent_also": self.also,
        }
        if self.detected:
            out["intent_detected"] = self.detected
        return out

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def intent_read_from(data: object) -> IntentRead | None:
    """An `IntentRead` back from `as_dict()` (a discovery's `meta["intent_read"]`), or None."""
    if not isinstance(data, dict) or str(data.get("intent") or "") not in ALL_INTENTS:
        return None
    names = {f.name for f in fields(IntentRead)}
    return IntentRead(**{k: str(v or "") for k, v in data.items() if k in names})


def read_intent(*texts: str | None) -> IntentRead:
    """The intent of the first of ``texts`` (the topic, then the operator's thoughts) that
    names one (#1091). Until 2026-10-10 each stage re-read it from its own text: the angle
    screen and the angles read topic then thoughts, the run record the topic only, the
    research brief the seed only - so a hope idea typed as thoughts ran as hope and was
    recorded as neutral. #1096: the next different ask, in any of the texts, is ``also``."""
    asks = [ask for text in texts for ask in _asks(text)]
    if not asks:
        return IntentRead()
    intent, cue = asks[0]
    also, also_cue = next(((i, c) for i, c in asks[1:] if i != intent), ("", ""))
    return IntentRead(intent, "cue", cue, also, also_cue)


def operator_intent(intent: str, detected: IntentRead | None = None) -> IntentRead:
    """The mode the operator chose on the angle screen (#1092); the detected cue is kept.
    One mode: a second ask read from the idea does not survive the operator's choice."""
    if intent not in ALL_INTENTS:
        raise ValueError(f"unknown angle mode: {intent}")
    cue = detected.cue if detected and detected.intent == intent else ""
    return IntentRead(intent, "operator", cue, detected=detected.intent if detected else "")


# #1089: slang the cue tables have never seen ("bounce back", "is HIM") fell to neutral. The
# model is asked only when every text reads neutral, and its answer counts only when it quotes
# the idea's own words - so the angle screen can say what it read and from where, and M fixes it.
_MODEL_MODES = {"hope": ANGLE_HOPE, "take": ANGLE_TAKE, "plan": ANGLE_PLAN}
_MODEL_PROMPT = (
    "What is the creator asking for in this short-video idea? Answer with JSON only: "
    '{{"mode": "hope" | "take" | "plan" | "neutral", "phrase": "<the 1-5 words of the idea '
    'that say so, copied exactly>"}}. hope = they want the positives, reasons for optimism '
    "(slang counts: 'bounce back', 'we're so back'); take = they state or ask for an opinion to "
    "argue ('is HIM', 'is cooked'); plan = they ask what has to happen; neutral = none of "
    "these.\n\nIdea: {idea}"
)
_MODEL_READS: dict[str, tuple[str, str]] = {}
_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def model_read_from_reply(idea: str, reply: str | None) -> tuple[str, str]:
    """(intent, phrase) from the model's reply, or (default, "") - pure (#1089). The phrase must
    be the idea's own words: a read that cannot point at what it read is not shown."""
    match = _JSON_OBJECT.search(reply or "")
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        return ANGLE_DEFAULT, ""
    intent = _MODEL_MODES.get(str(data.get("mode") or "").strip().lower(), "")
    phrase = _plain(str(data.get("phrase") or "")).strip(" \"'.,!?")
    if not intent or not phrase or len(phrase.split()) > 6:
        return ANGLE_DEFAULT, ""
    if phrase.lower() not in _plain(idea).lower():
        return ANGLE_DEFAULT, ""
    return intent, phrase


def model_read_enabled() -> bool:
    return os.getenv("STANCE_MODEL_READ", "true").strip().lower() not in ("0", "false", "no", "off")


def model_read(idea: str | None) -> IntentRead | None:
    """One cheap model read of ``idea``, once per idea per process; None when it reads neutral,
    is off, or the model is down. Never raises."""
    text = _plain(idea)
    if not text or not model_read_enabled():
        return None
    if text not in _MODEL_READS:
        try:
            from core import llm_router

            reply = llm_router.complete(
                _MODEL_PROMPT.format(idea=text[:400]),
                tier="cheap",
                temperature=0.0,
                max_tokens=60,
                stage="intent",
            )
        except Exception:
            return None  # a missing read is neutral, never a failed run
        _MODEL_READS[text] = model_read_from_reply(text, reply)
    intent, phrase = _MODEL_READS[text]
    return IntentRead(intent, "model", phrase) if intent != ANGLE_DEFAULT else None


def reset_model_reads() -> None:
    _MODEL_READS.clear()


process_state.register_reset("core.angle_intent", reset_model_reads)


def resolve_intent(*texts: str | None) -> IntentRead:
    """`read_intent`, then - only when every text reads neutral - the model's read of the
    operator's words (#1089). The run's one read: discovery makes it, the rest reuse it."""
    read = read_intent(*texts)
    if read.intent != ANGLE_DEFAULT:
        return read
    words = " ".join(_plain(t) for t in texts if _plain(t))
    return model_read(words) or read


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


# #1092: the modes the operator can pick on the angle screen, by key. cp1252-safe.
MODE_KEYS: dict[str, tuple[str, str]] = {
    "n": (ANGLE_DEFAULT, "neutral analysis"),
    "h": (ANGLE_HOPE, "hope - reasons for optimism"),
    "t": (ANGLE_TAKE, "take - argue a side"),
    "p": (ANGLE_PLAN, "plan - what has to happen"),
    "e": (ANGLE_EXPLAINER, "explainer"),
    "u": (ANGLE_TUTORIAL, "tutorial / how-to"),
    "l": (ANGLE_LIST, "list / ranking"),
    "c": (ANGLE_COMPARISON, "comparison"),
    "b": (ANGLE_RETROSPECTIVE, "looking back"),
    "r": (ANGLE_REACTION, "reaction"),
}


def mode_menu_lines() -> list[str]:
    """The angle-screen mode menu, one line per mode (#1092)."""
    return [f"{key}) {label}" for key, (_intent, label) in MODE_KEYS.items()]


def mode_for_key(key: str | None) -> str:
    """The intent a mode key names, or "" (#1092). The intent's own name works too."""
    raw = (key or "").strip().lower()
    if raw in MODE_KEYS:
        return MODE_KEYS[raw][0]
    if raw == "neutral":
        return ANGLE_DEFAULT
    return raw if raw in ALL_INTENTS else ""


def angle_intent_note(intent: str | IntentRead) -> str:
    """One operator-facing line for the angle screen. cp1252-safe (candidate 250).
    Given an `IntentRead`, it also says what set the mode (#1091)."""
    read = intent if isinstance(intent, IntentRead) else None
    key = read.intent if read else str(intent)
    detail = _INTENT_NOTES.get(key) or _INTENT_NOTES[ANGLE_DEFAULT]
    if read and read.source == "operator":
        detail = f"{detail} [you chose it]"
    elif read and read.source == "model":
        detail = f"{detail} [read by the model from '{read.cue}' - M if wrong]"  # #1089
    elif read and read.cue:
        detail = f"{detail} [from '{read.cue}']"
    if read and read.also:
        detail = f"{detail} + {read.also} [from '{read.also_cue}']"  # #1096
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


# #1090: a take that states its side ("Herbert is elite") is argued, not countered.
_CLAIM = re.compile(r"\b(?:is|are|was|were)\s+(.+)$", re.I)
_CLAUSE_SPLIT = re.compile(r"[:.!;\n]")
_NEGATORS = frozenset({"not", "isnt", "arent", "wasnt", "werent", "never", "no", "aint", "hardly"})
_COUNTER = ("myth", "mirage", "the case against", "not so fast", "overrated", "fraud")


def _plain(text: str | None) -> str:
    return " ".join((text or "").replace("\u2019", "'").split())


def stated_side(idea: str | None) -> list[str]:
    """The words of the verdict a take idea states, or [] (#1090).

    "Chargers hot take: Herbert is elite" -> ["elite"]; "Jets are doomed" -> ["doomed"]. A
    question ("Is Tua overrated?") or a request for takes in general ("NBA preseason hot
    takes") states no side - the angles may argue any.
    """
    text = _plain(idea)
    if not text or "?" in text or detect_angle_intent(text) != ANGLE_TAKE:
        return []
    from apis.topic_tokens import content_tokens

    for clause in _CLAUSE_SPLIT.split(text):
        match = _CLAIM.search(clause)
        if not match:
            continue
        subject = set(content_tokens(clause[: match.start()]))
        words = [
            t
            for t in content_tokens(match.group(1), min_len=3)
            if t not in _NEGATORS and t not in subject
        ]
        if words:
            return words[:3]
    return []


def _against_side(text: str, idea: str) -> str:
    """Why ``text`` argues against the side ``idea`` states, or "" (#1090)."""
    side = stated_side(idea)
    if not side:
        return ""
    from apis.topic_tokens import content_tokens

    tokens = content_tokens(text)
    for index, token in enumerate(tokens):
        window = tokens[max(0, index - 3) : index]
        if token in side and any(t in _NEGATORS for t in window):
            return f"'{' '.join([*window, token])}' argues against your take"
    low, idea_low = text.lower(), _plain(idea).lower()
    for word in _COUNTER:
        if re.search(rf"\b{re.escape(word)}", low) and word not in idea_low:
            return f"'{word}' argues against your take"
    return ""


def stance_flip(text: str, intent: str, *, idea: str = "") -> str:
    """Why ``text`` knocks the stance of an idea read as ``intent``, or "" (#1084).

    A hopeful idea is flipped by doubt or mockery; a neutral one by mockery only; a take by
    an angle that argues against the side it states (#1090). A word the idea itself uses is
    never a flip - "Chargers fans in denial" keeps "why Chargers fans are in denial".
    """
    low = _plain(text).lower()
    if intent == ANGLE_TAKE:
        return _against_side(low, idea)
    words = _DOUBT if intent == ANGLE_HOPE else _DERISION
    idea_low = _plain(idea).lower()
    for word in words:
        pattern = rf"\b{re.escape(word)}"
        if re.search(pattern, low) and not re.search(pattern, idea_low):
            stance = "a hopeful idea" if intent == ANGLE_HOPE else "a neutral one"
            return f"'{word}' knocks {stance}"
    return ""


def stance_rule(intent: str, idea: str = "") -> str:
    """The STANCE line every prompt that writes for this idea carries (#1084)."""
    if intent == ANGLE_HOPE:
        return (
            "STANCE: the operator is asking for reasons for HOPE. Slang like 'hopium' or "
            "'hopeium' is their word for optimism, not mockery. Every angle is a different, "
            "fact-checkable reason for optimism. Never question, debunk, psychoanalyse or mock "
            "the hope - no 'critics', 'denial', 'fragile', 'masks', 'reality check'."
        )
    if intent == ANGLE_TAKE:
        if not stated_side(idea):
            return ""
        return (
            f'STANCE: the operator\'s own take is "{_plain(idea)}". Every angle argues THAT '
            "side with facts - never the opposite, never a counter-take, never 'actually it "
            "isn't'."
        )
    return (
        "STANCE: neutral analysis - what happened, what it means, what to watch. No "
        "contrarian counter-take, no hot take and no mocking the fans or the subject; the "
        "operator asks by name when they want a take."
    )
