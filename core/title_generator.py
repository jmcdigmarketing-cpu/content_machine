"""Fact-grounded YouTube title generation — runs after the script, not at discovery.

Discovery picks an editorial *angle*; the publishable title is generated here
once operator key facts and the script hook exist.
"""

from __future__ import annotations

import os
import re

from core.llm_router import complete
from core.logging import get_logger
from core.operator_facts import facts_for_prompt

logger = get_logger("core.title_generator")

_SLOP_PATTERNS = (
    "just broke the league",
    "here's what's actually broken",
    "nobody's talking about",
    "disaster for small markets",
    "the real winner isn't",
    "left fans furious",
    "reshapes the entire season",
    "community demands",
    "what's actually broken",
    "my hot take",
    "you won't believe",
    "this changes everything",
    "actually broken now",
)

_SLOP_RE = re.compile("|".join(re.escape(p) for p in _SLOP_PATTERNS), re.I)

_PIN_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "might",
        "more",
        "most",
        "must",
        "new",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "out",
        "over",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "up",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "one",
        "all",
    ]
)
_PIN_GENERIC = frozenset({"gta", "nba", "nfl", "ufc", "mma", "game", "games", "video"})


def _angle_pin_phrases(angle: str) -> list[str]:
    """Distinctive phrases from the selected angle that the public title must keep."""
    text = (angle or "").strip()
    if not text:
        return []
    low = text.lower()
    out: list[str] = []
    if "will it be the best" in low:
        out.append("will it be the best")
    words = re.findall(r"[a-z0-9']+", low)
    for word in words:
        if len(word) >= 5 and word not in _PIN_STOP and word not in _PIN_GENERIC:
            if word not in out:
                out.append(word)
    return out[:8]


def _title_keeps_angle(title: str, angle: str) -> bool:
    pins = _angle_pin_phrases(angle)
    if not pins:
        return True
    low = (title or "").lower()
    return any(pin in low for pin in pins)


def _repair_title_to_angle(title: str, angle: str, *, fallback: str) -> str:
    if _title_keeps_angle(title, angle):
        return title
    from_angle = _clean_title(re.sub(r"\s+", " ", (angle or "").strip()), fallback=fallback)
    if _title_keeps_angle(from_angle, angle):
        return from_angle
    return title


def _hook_line(script: str) -> str:
    from core.voice.delivery import display_text

    text = display_text(script).strip()  # the hook card and titles show no "*emphasis*" marks
    if not text:
        return ""
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return first[:200]


_TITLE_MAX = 100
_TITLE_MIN_KEPT = 40
# Where a title can end cleanly: punctuation, or before a trailing qualifier clause.
_CLAUSE_BREAK = re.compile(
    r"(?:\s*[:;,—–]\s+|\s+-\s+|\s+(?=(?:under|as|after|amid|with|while|despite|following|ahead of)\s))",
    re.I,
)


def _fit_title(title: str, *, angle: str) -> str:
    """A title within YouTube's 100 characters without cutting a phrase in half (#924).

    Run 109's LLM title ran past 100 and the old word cut uploaded "... narrative magic
    under Neil…". End at the last clause boundary that keeps 40+ characters; else use the
    angle when it fits; only then cut at a word (with an ellipsis, as before).
    """
    if len(title) <= _TITLE_MAX:
        return title
    cuts = [m.start() for m in _CLAUSE_BREAK.finditer(title[: _TITLE_MAX + 1])]
    for cut in reversed(cuts):
        head = title[:cut].rstrip(" ,;:-—–")
        if _TITLE_MIN_KEPT <= len(head) <= _TITLE_MAX:
            return head
    angle = re.sub(r"\s+", " ", (angle or "").strip())
    if _TITLE_MIN_KEPT <= len(angle) <= _TITLE_MAX:
        return angle
    return title[: _TITLE_MAX - 3].rsplit(" ", 1)[0] + "…"


_FRAME_CUT_MIN = 20

# #1181: the second word of a place name that never stands alone in these titles, and the word
# it needs before it. Run 149's title read "... After Denver Loss Angeles Stays Optimistic" and
# passed every check. First names ("Antonio", "Diego", "Jose") are left out - they are fighters.
_SPLIT_PLACES = {"Angeles": "Los", "Vegas": "Las", "Orleans": "New"}


# #1482: a script says "in Vegas" and "the Orleans Arena" - only "Angeles" never stands alone.
SPOKEN_SPLIT_PLACES = {"Angeles": "Los"}


def broken_place_name(title: str, *, places: dict[str, str] | None = None) -> str:
    """The place name a title has broken ("Los Angeles" for "Loss Angeles"), or "". #1224: or
    the team name that lost its first word ("New England Patriots" for "England Patriots").
    #1481: a word that starts a team's name is not a broken place - "Vegas Golden Knights".
    `places` replaces `_SPLIT_PLACES` (the script check passes `SPOKEN_SPLIT_PLACES`)."""
    from apis.team_gazetteer import team_spans

    split_places = _SPLIT_PLACES if places is None else places
    words = re.findall(r"[A-Za-z']+", title or "")
    starts = {start for start, _end in team_spans(words)}
    for i, word in enumerate(words):
        first = split_places.get(word)
        if first and i not in starts and (i == 0 or words[i - 1] != first):
            return f"{first} {word}"
    return broken_team_name(title)


def broken_team_name(title: str) -> str:
    """A team named without its city's first word ("England Patriots", "York Rangers", "Ham
    United"), as the full name, or "" (#1224, run 159). #1486: each mention is read - "New
    England Patriots fans meet England Patriots" has one whole and one broken. #1481: every
    league in `apis.team_gazetteer`; a two-word nickname ("Maple Leafs") has lost nothing."""
    from apis.team_gazetteer import broken_tails

    text = title or ""
    for tail, full, prefixes in broken_tails():
        whole = "".join(f"(?<!\\b{re.escape(prefix)})" for prefix in prefixes)
        if re.search(rf"{whole}\b{re.escape(tail)}\b", text):
            return full
    return ""


_CUT_OFF_RE = re.compile(r"(?:\u2026|\.{3})\s*$")


def title_cut_off(title: str) -> bool:
    """#1225: a title that ends in an ellipsis - run 158's model wrote "... positive outlook\u2026"."""
    return bool(_CUT_OFF_RE.search(title or ""))


def _clean_title(raw: str, *, fallback: str, angle: str = "") -> str:
    title = (raw or "").strip().strip('"').strip("'")
    title = re.sub(r"\s+", " ", title)
    title = _CUT_OFF_RE.sub("", title).rstrip(" ,;:-")  # #1225: the model's own "..."
    if not title or _SLOP_RE.search(title):
        return fallback
    title = _drop_frame(title, angle)
    return _fit_title(title, angle=angle)


def _drop_frame(title: str, angle: str) -> str:
    """#973: "X is a trap, not a peak" -> "X is a trap" when the cut still stands as a title
    (20+ characters) and keeps the angle."""
    from core.persona_lint import drop_contrast_tail, title_contrast_frame

    if not title_contrast_frame(title):
        return title
    cut = drop_contrast_tail(title)
    if cut == title or len(cut) < _FRAME_CUT_MIN or (angle and not _title_keeps_angle(cut, angle)):
        return title
    logger.info("Title contrast frame cut: %r -> %r", title, cut)
    return cut


# #1138: an angle's label pasted in front of the title ("Contrarian: Spain's World Cup win ...",
# run 116). Stripped where the title is written; `title_label` names it for the checks.
_LABEL_RE = re.compile(
    r"^(?:contrarian|hot take|take|explainer|prediction|recap|analysis|angle)\s*:\s*", re.I
)


def title_label(title: str) -> str:
    found = _LABEL_RE.match((title or "").strip())
    return found.group(0).strip() if found else ""


def strip_label(title: str) -> str:
    """The title without a leading angle label, its first letter capitalised."""
    text = (title or "").strip()
    rest = _LABEL_RE.sub("", text, count=1).strip()
    if not rest or rest == text:
        return text
    return rest[0].upper() + rest[1:]


def generate_title(
    *,
    script: str,
    topic: str,
    seed_topic: str = "",
    key_facts: list[str] | None = None,
    channel_id: str = "default",
    brief: str = "",
    intent: str = "",
) -> str:
    """Generate a fact-grounded title from the finished script + operator facts.

    `brief` (#1016): the operator's own idea - the title promises what it asks. `intent`
    (#1091): the run's intent, read once; read from the seed and brief when not given. #1093:
    a title that knocks the idea's stance is asked for once more, then falls back."""
    hook = _hook_line(script)
    facts = facts_for_prompt(key_facts)
    facts_block = (
        "\n".join(f"- {f}" for f in facts) if facts else "(none — use only what the script states)"
    )

    pin = (_angle_pin_phrases(topic) or [topic])[0]
    plain_brief = " ".join((brief or "").split())[:300]
    idea_line = (
        f"THE OPERATOR'S IDEA (the title promises what this asks - no other take): {plain_brief}\n"
        if plain_brief
        else ""
    )
    from core.angle_intent import ANGLE_HOPE, ANGLE_TAKE, intent_of, stance_flip, stated_side

    # #1084: the title keeps the operator's stance - run 125 asked for hope.
    stance = intent or intent_of(seed_topic or topic, brief)
    idea = " ".join(t for t in (brief, seed_topic or topic) if t)
    side_idea = next((t for t in (brief, seed_topic, topic) if t and stated_side(t)), "")
    stance_line = (
        "STANCE: the operator asked for reasons for hope - the title promises them; never "
        "doubts, mocks or calls the hope denial.\n"
        if stance == ANGLE_HOPE
        else (
            f'STANCE: the operator\'s own take is "{" ".join(side_idea.split())}" - the title '
            "argues it, never the opposite.\n"
            if side_idea
            else ""
        )
        if stance == ANGLE_TAKE
        else "STANCE: neutral - no hot take and no mockery in the title.\n"
    )
    prompt = f"""Write ONE YouTube Shorts title for this video.

EDITORIAL ANGLE: {topic}
SEED TOPIC: {seed_topic or topic}
{idea_line}{stance_line}SCRIPT HOOK: {hook or topic}

OPERATOR FACTS (title must not contradict these):
{facts_block}

RULES:
- Prefer 50–70 characters; hard max 100.
- The title MUST include this angle phrase: {pin}
- Name a specific person, team, or move when facts/script mention one.
- Accurate > catchy. No clickbait templates.
- BANNED phrases: {", ".join(_SLOP_PATTERNS[:8])}, etc.
- No ellipsis. No "My Hot Take" framing. No questions as the whole title.
- No contrast frame ("X, not Y", "a trap, not a peak", "isn't X, it's Y") - say what it is.
- Return ONLY the title line — no quotes, no JSON, no explanation.

Title:"""

    fallback = hook[:70] if hook else (seed_topic or topic)[:70]

    # Fail-open: the title runs *after* the script, grounding and claim verifier have
    # already succeeded — an LLM outage here must never throw that work away. Any failure
    # degrades to the script hook, mirroring the variant path's "using heuristic angles".
    raw = _complete_or_none(prompt, temperature=0.45, max_tokens=48)
    if raw is None:
        return _repair_title_to_angle(fallback, topic, fallback=fallback)

    title = _clean_title(raw, fallback=fallback, angle=topic)
    if title == fallback and facts:
        # Second attempt with explicit fact anchor when slop was rejected.
        anchor = facts[0][:80]
        retry = _complete_or_none(
            f"Write a 60-char YouTube title for a short about: {anchor}. "
            f"Hook: {hook}. Facts only — no hype templates. Title only:",
            temperature=0.35,
            max_tokens=40,
        )
        if retry is not None:
            title = _clean_title(retry, fallback=fallback, angle=topic)
    title = _repair_title_to_angle(title, topic, fallback=fallback)
    flip = stance_flip(title, stance, idea=idea)
    if flip:
        # #1093: the stance line is in the prompt; this is the check after it.
        logger.info("Title knocks the idea's stance (%s): %r - asking once more", flip, title)
        retry = _complete_or_none(
            prompt + f"\n(Not this - it knocks the operator's stance, {flip}: {title})\nTitle:",
            temperature=0.35,
            max_tokens=48,
        )
        again = _clean_title(retry, fallback=fallback, angle=topic) if retry else fallback
        again = _repair_title_to_angle(again, topic, fallback=fallback)
        safe = [t for t in (again, fallback, (seed_topic or topic)[:70]) if t]
        title = next((t for t in safe if not stance_flip(t, stance, idea=idea)), safe[-1])
    logger.debug("Generated title: %s", title)
    return title


def _complete_or_none(prompt: str, *, temperature: float, max_tokens: int) -> str | None:
    """Cheap-tier completion, or None when the LLM is unavailable (never raises)."""
    try:
        return (
            complete(
                prompt, tier="cheap", temperature=temperature, max_tokens=max_tokens, stage="title"
            )
            or ""
        )
    except Exception as exc:
        logger.warning("Title LLM unavailable (%s) — using the script hook", exc)
        return None


def suggest_mode() -> str:
    """`TITLE_SUGGEST`: off | report (default) | reword."""
    raw = (os.getenv("TITLE_SUGGEST", "") or "").strip().lower()
    return raw if raw in ("off", "report", "reword") else "report"


def _suggest_fetch(phrase: str) -> list[str] | None:
    from apis.autocomplete_api import youtube_suggestions

    return youtube_suggestions(phrase)


def _one_edit_apart(a: str, b: str) -> bool:
    """True when `a` and `b` differ by one inserted, dropped or changed letter."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1 :] if len(a) < len(b) else a[i + 1 :] == b[i + 1 :]


def _subject_spelling(subject: str, suggestions: list[str]) -> dict[str, str] | None:
    """#1116: a word of the subject that most suggestions spell one letter differently.

    Run 132's title said "Illia Topuria"; people type "ilia topuria".
    """
    from apis.topic_tokens import content_tokens

    rows = [set(content_tokens(text)) for text in suggestions]
    for word in content_tokens(subject, min_len=4):
        if any(word in row for row in rows):
            continue
        counts: dict[str, int] = {}
        for row in rows:
            for other in row:
                if _one_edit_apart(word, other):
                    counts[other] = counts.get(other, 0) + 1
        best = max(counts, key=lambda k: counts[k], default="")
        if best and counts[best] * 2 > len(rows):
            return {"typed": word, "searched": best}
    return None


def suggest_check(title: str, topic: str, *, fetch=None) -> dict:
    """#1050: is the title worded the way people search its subject?

    {status, subject, match | suggestions}. `searched`: a suggestion shares a word with the
    title beyond the subject's own. `unsearched`: none does - `suggestions` is what people
    type instead. `none` / `unavailable` / `no_subject` are not verdicts.
    """
    from apis.topic_tokens import content_tokens, subject_terms

    subjects = subject_terms(title) or subject_terms(topic)
    if not subjects:
        return {"status": "no_subject"}
    subject = subjects[0]
    found = (fetch or _suggest_fetch)(subject)
    if found is None:
        return {"status": "unavailable", "subject": subject}
    if not found:
        return {"status": "none", "subject": subject}
    own = set(content_tokens(subject))
    said = set(content_tokens(title, min_len=3)) - own
    spelling = _subject_spelling(subject, found)
    extra = {"spelling": spelling} if spelling else {}
    for suggestion in found:
        if said & (set(content_tokens(suggestion, min_len=3)) - own):
            return {"status": "searched", "subject": subject, "match": suggestion, **extra}
    return {
        "status": "unsearched",
        "subject": subject,
        "suggestions": list(found[:5]),
        **extra,
    }


def suggest_line(report: dict) -> str:
    """One line for the review screen, or "" when there is no verdict to show."""
    status = report.get("status")
    spelling = report.get("spelling") or {}
    spelt = (
        f' - people spell "{spelling["typed"]}" as "{spelling["searched"]}"'
        if spelling.get("typed") and spelling.get("searched")
        else ""
    )
    if status == "searched":
        return f'Title: people search "{report["match"]}" - the title uses those words{spelt}'
    if status == "unsearched":
        typed = "; ".join(report.get("suggestions") or [])
        return (
            f'Title: nobody types its wording after "{report["subject"]}" - '
            f"people type: {typed}{spelt}"
        )
    return ""


def apply_suggest(title: str, topic: str, *, accept=None) -> tuple[str, dict]:
    """(title, report) after the suggest check. `report` mode leaves the title alone.

    `reword` asks once for the title in the words people type and keeps it only if it is
    then `searched` and `accept(candidate)` - the caller's own checks - says yes.
    """
    mode = suggest_mode()
    if mode == "off" or not (title or "").strip():
        return title, {}
    try:
        report = suggest_check(title, topic)
    except Exception as exc:
        logger.debug("title suggest check skipped: %s", exc)
        return title, {}
    if mode != "reword" or report.get("status") != "unsearched":
        return title, report
    typed = "; ".join(report["suggestions"])
    retry = _complete_or_none(
        "Reword this YouTube title so it uses the words people search. Keep every fact and "
        f"the same claim; change only the wording. Under 70 characters.\nTitle: {title}\n"
        f"People search: {typed}\nTitle only:",
        temperature=0.3,
        max_tokens=48,
    )
    candidate = _clean_title(retry, fallback=title, angle=topic) if retry else title
    if not candidate or candidate == title:
        return title, report
    try:
        again = suggest_check(candidate, topic)
        if again.get("status") == "searched" and (accept is None or accept(candidate)):
            logger.info("Title reworded to a searched phrase: %r -> %r", title, candidate)
            return candidate, {**again, "reworded_from": title}
    except Exception as exc:
        logger.debug("title reword check skipped: %s", exc)
    return title, report
