"""Who speaks which part of a video, and in which voice (#883-#886).

A run picks its voices once (`pick_run_voices`): the narrator rotates through the
channel's `tts.voice_pool` without repeating the previous run's, and every extra role
gets a voice of its own. `plan_segments` cuts the script into the parts each role
speaks, for four modes:

- ``single``   - one narrator (the default, and what every run was before).
- ``quotes``   - a direct quote of four or more words is read in a second voice.
- ``chapters`` - an all-angles video changes voice at each chapter.
- ``debate``   - the script is written as HOST: / CO-HOST: lines; two voices argue.

The debate tags never reach anything a viewer or a checker reads: the content engine
strips them straight after the script is written and keeps the turns
(`parse_speaker_turns`), and the TTS plan re-attaches them to the final script's
sentences, which the rewrite passes may have changed.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Any

from apis.topic_tokens import content_tokens
from config.channels import get_channel_profile
from core.logging import get_logger
from core.run_features import load_features
from core.tts import ROLE_NARRATOR, load_voice_registry

logger = get_logger("core.voice.plan")

ROLE_QUOTE = "quote"
ROLE_COHOST = "cohost"
VOICE_MODES = ("single", "quotes", "chapters", "debate")
_MENU = {"1": "single", "2": "quotes", "3": "chapters", "4": "debate"}
QUOTE_MIN_WORDS = 4
_TURN_MATCH = 0.5

_QUOTE_RE = re.compile(r'“[^”]+”|"[^"\n]+"')
# A speaker tag starts a line or follows a sentence end; "the host city:" does not.
_TAG_RE = re.compile(
    r"(?:^|(?<=\n)|(?<=[.!?][ \t]))[ \t]*\**[ \t]*(CO-HOST|COHOST|CO HOST|HOST)[ \t]*\**[ \t]*:"
    r"[ \t]*\**[ \t]*",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Segment:
    text: str
    role: str


def normalize_mode(mode: str | None) -> str:
    mode = str(mode or "").strip().lower()
    return mode if mode in VOICE_MODES else "single"


def voice_menu_lines(*, all_angles: bool = False) -> list[str]:
    """The voices prompt (main.py). A voice per chapter is offered only with chapters."""
    lines = [
        "  1) One voice (rotates between the channel's voices)",
        "  2) Quotes in a second voice",
    ]
    if all_angles:
        lines.append("  3) A different voice for each chapter")
    lines.append("  4) Two-host debate (the script is written as two hosts arguing)")
    return lines


def voice_mode_from_choice(choice: str, *, all_angles: bool = False) -> str:
    """The voices menu answer as a mode; a voice per chapter needs chapters."""
    mode = _MENU.get(str(choice or "").strip(), "single")
    if mode == "chapters" and not all_angles:
        return "single"
    return mode


def voice_mode_directive(mode: str | None) -> str:
    """The script-prompt instruction a mode needs; only the debate changes the writing."""
    if normalize_mode(mode) != "debate":
        return ""
    return (
        "FORMAT: a two-host debate. Write every line as `HOST:` or `CO-HOST:` followed by "
        "what that host says. The hosts disagree and answer each other's points, "
        "alternating at least every two or three sentences. HOST opens with the hook and "
        "closes the video. Every claim either host makes must still come from the facts "
        "given; a host may be wrong only in opinion, never in fact."
    )


# ---- debate tags -----------------------------------------------------------------


def _tag_role(tag: str) -> str:
    return ROLE_COHOST if "co" in tag.lower() else ROLE_NARRATOR


def parse_speaker_turns(script: str) -> list[dict[str, str]]:
    """[{role, text}] from a HOST:/CO-HOST: script; [] when it carries no tags.

    Untagged text continues the previous speaker; adjacent turns of one speaker merge.
    """
    text = script or ""
    matches = list(_TAG_RE.finditer(text))
    if not matches:
        return []
    turns: list[dict[str, str]] = []
    lead = text[: matches[0].start()].strip()
    if lead:
        turns.append({"role": ROLE_NARRATOR, "text": lead})
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = " ".join(text[match.end() : end].split())
        if not body:
            continue
        role = _tag_role(match.group(1))
        if turns and turns[-1]["role"] == role:
            turns[-1]["text"] = f"{turns[-1]['text']} {body}"
        else:
            turns.append({"role": role, "text": body})
    return turns


def strip_speaker_tags(text: str) -> str:
    """`text` without HOST:/CO-HOST: tags; anything else is left exactly as it was."""
    if not text or not _TAG_RE.search(text):
        return text
    return _TAG_RE.sub("", text)


def _sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SENTENCE_RE.split(text or "")) if s]


def _overlap(a: str, b: str) -> float:
    ta, tb = set(content_tokens(a, min_len=2)), set(content_tokens(b, min_len=2))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _merge(segments: list[Segment], sep: str = " ") -> list[Segment]:
    out: list[Segment] = []
    for seg in segments:
        if not seg.text.strip():
            continue
        if out and out[-1].role == seg.role:
            out[-1] = Segment(f"{out[-1].text}{sep}{seg.text}", seg.role)
        else:
            out.append(seg)
    return out


def _debate_segments(script: str, turns: list[dict[str, Any]] | None) -> list[Segment]:
    direct = parse_speaker_turns(script)
    if direct:
        return _merge([Segment(t["text"], t["role"]) for t in direct])
    labelled = [
        (str(t.get("role") or ROLE_NARRATOR), sentence)
        for t in (turns or [])
        if isinstance(t, dict)
        for sentence in _sentences(str(t.get("text") or ""))
    ]
    if not labelled:
        return [Segment(script, ROLE_NARRATOR)]
    segments: list[Segment] = []
    role = ROLE_NARRATOR
    for sentence in _sentences(script):
        best_role, best = role, 0.0
        for turn_role, turn_sentence in labelled:
            score = _overlap(sentence, turn_sentence)
            if score > best:
                best_role, best = turn_role, score
        if best >= _TURN_MATCH:
            role = best_role
        segments.append(Segment(sentence, role))
    return _merge(segments)


# ---- quotes and chapters ---------------------------------------------------------


def _quote_segments(script: str) -> list[Segment]:
    segments: list[Segment] = []
    cursor = 0
    for match in _QUOTE_RE.finditer(script):
        inner = match.group(0)[1:-1]
        if len(inner.split()) < QUOTE_MIN_WORDS:
            continue
        segments.append(Segment(script[cursor : match.start()], ROLE_NARRATOR))
        end = match.end()
        # Punctuation closing the quote belongs to the quote, not a new narrator part.
        while end < len(script) and script[end] in ".,;:!?":
            end += 1
        segments.append(Segment(script[match.start() : end], ROLE_QUOTE))
        cursor = end
    segments.append(Segment(script[cursor:], ROLE_NARRATOR))
    return _merge([Segment(s.text.strip(), s.role) for s in segments])


def _chapter_segments(script: str, chapters: list | None) -> list[Segment]:
    """Chapter 1 (and any intro before it) is the narrator; chapter n is `chapter_n`."""
    starts = sorted(
        {
            max(0, int(getattr(c, "char_start", 0) or 0))
            for c in (chapters or [])
            if int(getattr(c, "char_start", 0) or 0) < len(script)
        }
    )
    if len(starts) < 2:
        return [Segment(script, ROLE_NARRATOR)]
    bounds = sorted({0, *starts, len(script)})
    segments = []
    for k in range(len(bounds) - 1):
        n = sum(1 for start in starts if start <= bounds[k])
        role = ROLE_NARRATOR if n <= 1 else f"chapter_{n}"
        segments.append(Segment(script[bounds[k] : bounds[k + 1]], role))
    return _merge(segments, sep="")


def plan_segments(
    script: str,
    mode: str | None,
    *,
    chapters: list | None = None,
    turns: list[dict[str, Any]] | None = None,
) -> list[Segment]:
    """The script as [Segment(text, role)] for `mode`; one narrator part when it has none."""
    script = script or ""
    mode = normalize_mode(mode)
    if mode == "quotes":
        return _quote_segments(script) or [Segment(script, ROLE_NARRATOR)]
    if mode == "chapters":
        return _chapter_segments(script, chapters)
    if mode == "debate":
        return _debate_segments(script, turns)
    return [Segment(script, ROLE_NARRATOR)]


# ---- voices ----------------------------------------------------------------------


def _weighted(pool: dict[str, int], rng) -> str:
    choices = [v for v, w in pool.items() for _ in range(max(1, int(w)))]
    return rng.choice(choices)


def pick_run_voices(
    channel_id: str | None,
    roles=(ROLE_NARRATOR,),
    *,
    previous_narrator: str = "",
    rng=None,
) -> dict[str, str]:
    """{role: voice_id} for one run - the narrator first, every other role distinct.

    With `tts.rotate` the narrator is a weighted pick from the pool that skips the
    previous run's; without it the channel's fixed voice stays the narrator. Other roles
    take unused pool voices, then the catalog (config/voices.json), then repeat.
    """
    from core.tts import _dead_voices

    rng = rng or random
    profile = get_channel_profile(channel_id)
    pool = {str(v): int(w) for v, w in (profile.tts_voice_pool or {}).items()}
    live_pool = {v: w for v, w in pool.items() if v not in _dead_voices} or pool
    fixed = str(profile.tts_voice_id or "")
    if fixed and not (getattr(profile, "tts_rotate", False) and live_pool):
        narrator = fixed
    else:
        candidates = dict(live_pool) or _catalog()
        if previous_narrator and len(candidates) > 1:
            candidates.pop(previous_narrator, None)
        narrator = _weighted(candidates, rng) if candidates else fixed
    voices = {ROLE_NARRATOR: narrator}
    used = [narrator]
    for role in dict.fromkeys(str(r) for r in roles):
        if role in voices:
            continue
        spare = {v: w for v, w in live_pool.items() if v not in used}
        if not spare:
            spare = {v: w for v, w in _catalog().items() if v not in used}
        voice = _weighted(spare, rng) if spare else used[(len(voices)) % len(used)]
        voices[role] = voice
        used.append(voice)
    return voices


def _catalog() -> dict[str, int]:
    from core.tts import _dead_voices

    flat: dict[str, int] = {}
    for pool in load_voice_registry().values():
        for voice, weight in pool.items():
            if voice not in _dead_voices:
                flat[voice] = flat.get(voice, 0) + int(weight)
    return flat


def _run_repo():
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository()


def previous_narrator(channel_id: str | None, run_id: int | None = None) -> str:
    """The narrator voice of the channel's latest run before `run_id`, or ""."""
    try:
        rows = _run_repo().list_for_channel(channel_id or "")
    except Exception as exc:
        logger.debug("previous voice unreadable: %s", exc)
        return ""
    ordered = sorted(rows or [], key=lambda r: int(getattr(r, "id", 0) or 0), reverse=True)
    for row in ordered:
        rid = int(getattr(row, "id", 0) or 0)
        if run_id and rid >= int(run_id):
            continue
        try:
            voices = json.loads(getattr(row, "features_json", "") or "{}").get("voices")
        except (TypeError, ValueError, AttributeError):
            continue
        if isinstance(voices, dict) and voices.get(ROLE_NARRATOR):
            return str(voices[ROLE_NARRATOR])
    return ""


def plan_for_run(
    script: str,
    channel_id: str | None,
    run_id: int | None,
    *,
    features: dict[str, Any] | None = None,
) -> tuple[dict[str, str], list[Segment] | None]:
    """(voices, segments) for a render. Segments is None when one voice reads it all.

    `features` is an unsaved run's dict; otherwise the saved run's are read.
    """
    if features is None:
        features = load_features(run_id) if run_id else {}
    mode = normalize_mode(features.get("voice_mode"))
    chapters = None
    if mode == "chapters":
        from core.angle_chapters import chapters_from_features

        chapters = chapters_from_features(features.get("angle_chapters"))
    turns = (
        features.get("speaker_turns") if isinstance(features.get("speaker_turns"), list) else None
    )
    segments = plan_segments(script, mode, chapters=chapters, turns=turns)
    roles = list(dict.fromkeys(s.role for s in segments))
    voices = pick_run_voices(
        channel_id, roles, previous_narrator=previous_narrator(channel_id, run_id)
    )
    return voices, (segments if len(roles) > 1 else None)
