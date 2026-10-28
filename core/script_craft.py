"""#540 rhythm, #542 pre-CTA recap, #550 superlatives without a source."""

from __future__ import annotations

import os
import re
from itertools import pairwise
from typing import Any

from apis.topic_tokens import split_sentences

_CTA = re.compile(
    r"^\s*(like and subscribe|follow for more|smash (?:that )?like|tap in for more)\b",
    re.I,
)
_SUMMARY = re.compile(
    r"^\s*(in summary|to wrap up|bottom line|that'?s the recap|in conclusion)\b",
    re.I,
)
_SUPERLATIVE = (
    re.compile(r"\bfirst ever\b", re.I),
    re.compile(r"\bthe biggest\b", re.I),
    re.compile(r"\bnever before\b", re.I),
    re.compile(r"\bthe only\b", re.I),
    # #1018 (run 124's hook): "Only one team in NFL history has made the playoffs ...".
    re.compile(
        r"\bonly (?:one|two|three|four|five|\d+)\b[^.!?]{0,60}?\bin [a-z ]{0,20}history\b", re.I
    ),
    re.compile(
        r"\bno (?:team|player|fighter|club|one|quarterback|coach)\b[^.!?]{0,40}?\bever\b", re.I
    ),
    re.compile(r"\bin (?:nfl|nba|ufc|league|franchise|team|\w+) history\b", re.I),
)


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    count = len(groups)
    if word.lower().endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def reading_grade(script: str) -> float | None:
    """Flesch-Kincaid grade. None when there is nothing to measure."""
    parts = [p.strip() for p in split_sentences(script or "") if p.strip()]
    words = re.findall(r"[A-Za-z']+", script or "")
    if not parts or not words:
        return None
    syllables = sum(_syllables(word) for word in words)
    grade = 0.39 * (len(words) / len(parts)) + 11.8 * (syllables / len(words)) - 15.59
    return round(grade, 1)


def sentence_rhythm_flags(script: str) -> list[str]:
    """Uniform sentence length is the clearest LLM tell. Warn-only."""
    parts = [p.strip() for p in split_sentences(script or "") if p.strip()]
    if len(parts) < 5:
        return []
    lengths = [len(p.split()) for p in parts]
    mean = sum(lengths) / len(lengths)
    if all(abs(n - mean) <= 2 for n in lengths):
        return ["uniform sentence length"]
    return []


def strip_pre_cta_summary(script: str) -> tuple[str, dict[str, Any]]:
    """Drop a recap paragraph immediately before a CTA. Persist both counts (§25)."""
    raw = script or ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw.strip()) if p.strip()]
    report: dict[str, Any] = {
        "pre_paragraphs": len(paras),
        "post_paragraphs": len(paras),
        "stripped": False,
    }
    if len(paras) < 3:
        return raw, report
    if _CTA.match(paras[-1]) and _SUMMARY.match(paras[-2]):
        kept = paras[:-2] + paras[-1:]
        report["post_paragraphs"] = len(kept)
        report["stripped"] = True
        return "\n\n".join(kept), report
    return raw, report


def apply_script_craft(script: str) -> tuple[str, dict[str, Any], list[str]]:
    """Env-gated CTA strip plus rhythm flags. Default on; the operator still sees it."""
    raw = script or ""
    enabled = (os.getenv("CTA_SUMMARY_STRIP", "true") or "true").strip().lower() not in (
        "0",
        "false",
        "off",
        "no",
    )
    if enabled:
        cleaned, report = strip_pre_cta_summary(raw)
    else:
        paras = [p.strip() for p in re.split(r"\n\s*\n", raw.strip()) if p.strip()]
        report = {
            "pre_paragraphs": len(paras),
            "post_paragraphs": len(paras),
            "stripped": False,
        }
        cleaned = raw
    return cleaned, report, sentence_rhythm_flags(cleaned)


def find_ungrounded_superlatives(script: str, grounding_text: str) -> list[str]:
    """Flag first-ever / the biggest / the only when the facts never said so.

    `not only` is a conjunction, not a superlative — it must not fire.
    """
    text = script or ""
    grounding = (grounding_text or "").lower()
    hits: list[str] = []
    for pat in _SUPERLATIVE:
        for match in pat.finditer(text):
            span = match.group(0)
            start = match.start()
            window = text[max(0, start - 8) : start].lower()
            if span.lower() == "the only" and window.rstrip().endswith("not"):
                continue
            if span.lower() in grounding:
                continue
            hits.append(span)
    return hits


# #1034: what trips a voice. Three or more number groups in one sentence ("18-0-0 with 8 KO
# and 10 SUB"); a parenthetical; three or more capitalised names in a comma list.
_NUMBER_GROUP = re.compile(r"\d[\d.,:/-]*\d|\d")
_PARENTHETICAL = re.compile(r"\([^)]{3,}\)")
_NAME_LIST = re.compile(
    r"\b[A-Z][\w'-]+(?:\s[A-Z][\w'-]+)?(?:,\s+[A-Z][\w'-]+(?:\s[A-Z][\w'-]+)?){2,}"
    r"|\b[A-Z][\w'-]+(?:,\s+[A-Z][\w'-]+)+,?\s+and\s+[A-Z][\w'-]+"
)


# #1360: 36 of 317 sentences in 23 scripts read on 2026-10-25 ran over 25 words, the longest 51.
LONG_SENTENCE_WORDS = 25


def _numbers_in(text: str) -> list[str]:
    """Every digit run, so "18-0-0" is 18, 0, 0 and a rewrite cannot quietly lose one."""
    return sorted(re.findall(r"\d+", text or ""))


def _why_hard(sentence: str) -> str:
    if _PARENTHETICAL.search(sentence):
        return "parenthetical"
    if len(re.findall(r"\d+", sentence)) >= 4 and len(_NUMBER_GROUP.findall(sentence)) >= 2:
        return "numbers"
    if _NAME_LIST.search(sentence):
        return "names"
    if len(sentence.split()) > LONG_SENTENCE_WORDS:
        return "long"
    return ""


def hard_to_say(script: str) -> list[dict[str, str]]:
    """Sentences a voice will stumble on: [{sentence, why}], in order. Free; always runs."""
    out: list[dict[str, str]] = []
    for part in split_sentences(script or ""):
        sentence = part.strip()
        why = _why_hard(sentence)
        if why:
            out.append({"sentence": sentence, "why": why})
    return out


def read_aloud_enabled() -> bool:
    raw = (os.getenv("READ_ALOUD_REWRITE", "true") or "true").strip().lower()
    return raw not in ("0", "false", "off", "no")


def _names_in(text: str) -> set[str]:
    """Capitalised words that do not merely start a sentence."""
    names: set[str] = set()
    for part in split_sentences(text or "") or [text or ""]:
        words = re.findall(r"[\w'-]+", part)
        names.update(w for w in words[1:] if w[:1].isupper())
    return names


def _names_kept(old: str, new: str) -> bool:
    """#1531 (wave 118): every name the old sentence gives is still a word of the rewrite, and
    the rewrite gives no name the old text lacks - wherever each now sits. It compared
    `_names_in` sets, which leave out a sentence's first word, so the split the prompt asks for
    ("Evloev is 19-0 ...") lost "Evloev" and was thrown away: 8 of 20 flagged sentences kept."""
    from apis.topic_tokens import COMMON_CAPITALISED

    old_words = {w.lower() for w in re.findall(r"[\w'-]+", old)}
    new_words = {w.lower() for w in re.findall(r"[\w'-]+", new)}
    if not all(n.lower() in new_words for n in _names_in(old)):
        return False
    capitals = {w for w in re.findall(r"[\w'-]+", new) if w[:1].isupper()}
    return all(w.lower() in old_words or w.lower() in COMMON_CAPITALISED for w in capitals)


def read_aloud_pass(script: str, call) -> tuple[str, dict[str, Any]]:
    """(script, report). One cheap call, only when something is flagged and the pass is on.

    `call(system, user)` returns {"rewrites": [{"old", "new"}]}. A rewrite is kept only when
    it is no longer hard to say, carries exactly the numbers it had, and names nobody new
    and nobody fewer. Anything else keeps the sentence as written.
    """
    flagged = hard_to_say(script)
    report: dict[str, Any] = {
        "flagged": len(flagged),
        "rewritten": 0,
        "why": sorted({row["why"] for row in flagged}),
    }
    if not flagged or not read_aloud_enabled():
        return script, report
    system = (
        "These sentences will be read aloud once and are hard to say: a run of numbers, a "
        "parenthetical, a long list of names, or more words than one breath holds. Rewrite each so it is easy to say - split it "
        "into short sentences, move the aside into its own sentence. Keep every number and "
        "every name exactly; add none. Same voice."
    )
    listed = "\n".join(f"- {row['sentence']}" for row in flagged)
    user = (
        f"SENTENCES:\n{listed}\n\nReturn JSON only: "
        '{"rewrites": [{"old": "<sentence exactly as given>", "new": "<rewrite>"}]}'
    )
    try:
        payload = call(system, user)
    except Exception:
        return script, report
    rows = payload.get("rewrites") if isinstance(payload, dict) else None
    out = script
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        old, new = str(row.get("old") or "").strip(), str(row.get("new") or "").strip()
        if not old or not new or old not in out:
            continue
        if hard_to_say(new) or _numbers_in(new) != _numbers_in(old):
            continue
        if not _names_kept(old, new):
            continue
        out = out.replace(old, new, 1)
        report["rewritten"] += 1
    return out, report


# ---- the finished script, checked as a whole (#1139 #1141 #1142 #1143) --------------------
#
# Operator, 2026-10-11: a clean script keeps "my idea and stance rules", has "nothing
# unsupported", and uses "my typed thoughts, closely". Each of those was checked somewhere -
# the stance on the first and last sentence only, the idea before five later passes rewrote
# the script, the claims with one rewrite and then a block. These are the free, deterministic
# halves: what to cut, what slipped, which of the operator's points are missing.

CUT_MAX = 2
# #1162: a cut of an unbacked sentence may leave the script this share of its minimum.
CUT_FLOOR_SHARE = 0.85
POINT_SHARE = 0.6


def script_sentences(text: str) -> list[str]:
    return [s.strip() for s in split_sentences(text or "") if s.strip()]  # #1532


def drop_sentences(script: str, doomed: list[str], *, min_words: int) -> tuple[str, list[str]]:
    """Remove the given sentences and keep the paragraphs. The first sentence - the hook - is
    never removed, and nothing is when the script would fall under `min_words`."""
    sentences = script_sentences(script)
    first = sentences[0] if sentences else ""
    out, cut = script, []
    for sentence in doomed:
        if not sentence or sentence == first or sentence not in out:
            continue
        out = out.replace(sentence, "", 1)
        cut.append(sentence)
    if not cut:
        return script, []
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n[ \t]+", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if len(out.split()) < min_words:
        return script, []
    return out, cut


_POSSESSIVE_RE = re.compile(r"['’]s\b")


def _carries_claim(claim: str, text: str) -> bool:
    """True when `text` says `claim`: the share of the claim's words `ops verify-claim` cuts
    by, read with possessives off - or, a little under that share, every name and number of
    the claim. Run 145: "Wemby has +200 odds for MVP." was the first sentence, "Wemby's +200
    for MVP", and was not found; so it was neither cut nor repaired."""
    from apis.topic_tokens import content_tokens
    from core.facts.claim_confirm import _SENTENCE_SHARE, _coverage

    if _coverage(claim, text) >= _SENTENCE_SHARE:
        return True
    plain = _POSSESSIVE_RE.sub("", claim)
    wanted = set(content_tokens(plain, min_len=3))
    have = set(content_tokens(_POSSESSIVE_RE.sub("", text), min_len=3))
    if not wanted:
        return False
    share = len(wanted & have) / len(wanted)
    if share >= _SENTENCE_SHARE:
        return True
    named = _specifics(plain, wanted)
    return share >= 0.6 and bool(named) and named <= have


def claim_sentences(script: str, claims: list[str]) -> list[str]:
    """The sentences that carry each claim. A claim told across two sentences in a row takes
    both (run 144: "Third, use Jake Browning. They signed the former Bengals QB")."""
    sentences = script_sentences(script)
    found: list[str] = []
    for claim in claims:
        hits = [s for s in sentences if _carries_claim(str(claim), s)]
        if not hits:
            for first, second in pairwise(sentences):
                if _carries_claim(str(claim), f"{first} {second}"):
                    hits = [first, second]
                    break
        found.extend(s for s in hits if s not in found)
    return found


def cut_unsupported_enabled() -> bool:
    return os.getenv("CUT_UNSUPPORTED", "true").strip().lower() not in ("0", "false", "no", "off")


def cut_unsupported(
    script: str, claims: list[str], *, min_words: int, max_cut: int = CUT_MAX
) -> tuple[str, list[str]]:
    """#1139 (operator: "cut it, tell me which"): after the one rewrite, a sentence that still
    carries a claim the facts do not support is removed.

    13 of 31 waiting drafts were blocked by an unsupported claim, 9 of them by one sentence.
    At most `max_cut` sentences go; more than that is a script to look at, not to trim. The
    hook is never cut. Returns (script, the sentences cut).
    """
    doomed = claim_sentences(script, claims)
    if not doomed or len(doomed) > max_cut:
        return script, []
    # #1162 (operator, 2026-10-13: "cut within 15%"): run 141's one cut left 148 words against
    # a 150 minimum and was refused, so a script with an unbacked sentence waited instead.
    return drop_sentences(script, doomed, min_words=int(min_words * CUT_FLOOR_SHARE))


def hook_claims(script: str, claims: list[str]) -> list[str]:
    """The claims that sit in the script's first sentence (#1161). The cut never touches the
    hook, so a claim there was never repaired: 8 of the newest 40 runs carried one."""
    sentences = script_sentences(script)
    if not sentences:
        return []
    return [
        str(claim) for claim in claims or [] if sentences[0] in claim_sentences(script, [claim])
    ]


def stance_slips(script: str, intent: str, idea: str) -> list[tuple[str, str]]:
    """#1141: every sentence that knocks the idea's stance, with why - not only the first and
    last line, which is all that was read before."""
    if not intent:
        return []
    from core.angle_intent import stance_flip

    out: list[tuple[str, str]] = []
    for sentence in script_sentences(script):
        why = stance_flip(sentence, intent, idea=idea)
        if why:
            out.append((sentence, why))
    return out


def hold_stance(script: str, intent: str, idea: str, *, min_words: int) -> tuple[str, list[str]]:
    """Cut the sentence(s) past the opener that knock the stance. More than `CUT_MAX` is left
    for the idea check to report; the hook is the opening check's to fix."""
    slips = [sentence for sentence, _why in stance_slips(script, intent, idea)]
    if not slips or len(slips) > CUT_MAX:
        return script, []
    return drop_sentences(script, slips, min_words=min_words)


def thought_points(thoughts: str) -> list[str]:
    """#1142: the operator's own points - each line, sentence or ';' clause of what they
    typed that has three or more content words. One point is a topic, not a list: []."""
    from apis.topic_tokens import content_tokens
    from core.experiment_levers import is_directive

    if is_directive(thoughts or ""):  # an experiment's instruction, not the operator's words
        return []
    parts = re.split(r"[\n;]+|(?<=[.!?])\s+", thoughts or "")
    points = [p.strip(" -*\t") for p in parts]
    points = [p for p in points if len(content_tokens(p)) >= 3]
    return points if len(points) >= 2 else []


def points_used(script: str, points: list[str]) -> tuple[list[str], list[str]]:
    """(used, missing): a point is used when `POINT_SHARE` of its content words are in the
    script. Words come from `apis.topic_tokens`, as everywhere else."""
    from apis.topic_tokens import content_tokens

    have = set(content_tokens(script))
    used: list[str] = []
    missing: list[str] = []
    for point in points:
        want = set(content_tokens(point))
        share = len(want & have) / len(want) if want else 1.0
        (used if share >= POINT_SHARE else missing).append(point)
    return used, missing


_REPEAT_MIN_WORDS = 5
_REPEAT_SHARE = 0.7
_SIGN_OFF_RE = re.compile(r"^tap in for more\.?$", re.I)
_CALLBACK_RE = re.compile(r"^(?:that['\u2019]s|that is|this is|which is|and that|so that)\b", re.I)
_NUMBER_WORDS = frozenset({
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve", "twenty", "thirty", "forty", "fifty", "first", "second", "third", "fourth", "fifth",
})  # fmt: skip


def _specifics(sentence: str, words: set[str]) -> set[str]:
    """The names and numbers a sentence states: content words written with a capital, digits,
    and number words."""
    capitals = {
        re.sub(r"['\u2019]", "", w.lower()) for w in re.findall(r"\b[A-Z][\w'\u2019-]*", sentence)
    }
    return {w for w in words if w in capitals or w[:1].isdigit() or w in _NUMBER_WORDS}


def said_twice(script: str) -> list[str]:
    """The sentences that tell a fact the script has already told (#1155).

    Run 136, rendered 2026-10-13: "Houston has won three straight against Tennessee,
    including a shutout last season." and, five sentences on, "Houston has dominated this
    matchup, winning three straight, including a shutout last season." A sentence is a second
    telling when 70% of its content words are in an earlier one, it has five or more, and it
    names nothing the earlier one did not: no new name, no new number.

    Measured on the newest 34 scripts before it was let near a cut. A looser rule flagged
    eight: a parallel line about the other fighter ("Duncan entered on a five-fight win
    streak" after "Allen entered on a three-fight"), a callback ("That's how you go 0-4"),
    and lines that shared a subject and added a fact. Those are not repeats and are left.
    """
    from apis.topic_tokens import content_tokens

    seen: list[tuple[set[str], set[str]]] = []
    repeats: list[str] = []
    for sentence in script_sentences(script):
        text = sentence.strip()
        if _SIGN_OFF_RE.match(text):
            continue
        words = set(content_tokens(text))
        named = _specifics(text, words)
        again = (
            len(words) >= _REPEAT_MIN_WORDS
            and not _CALLBACK_RE.match(text)
            and any(
                len(words & earlier) >= _REPEAT_SHARE * len(words) and named <= earlier_named
                for earlier, earlier_named in seen
            )
        )
        if again:
            repeats.append(sentence)
        else:
            seen.append((words, named))
    return repeats


_ENDS_SENTENCE = re.compile(r"[.!?]['\"\u201d\u2019)]*$")
_LOWER_WORD = re.compile(r"\b[a-z][a-z]+\b")
_RUN_ON_SIDE = 6  # words on each side of the missing stop


def mid_thought_starts(script: str) -> list[str]:
    """#1587: sentences that begin in lower case after a full stop - a fragment a rewrite left
    behind (run 187: "...will pay for it. and Manchester City's perfect start is gone."). A word
    written with a capital inside ("iPhone"), a number or a quote is not one."""
    out: list[str] = []
    for sentence in script_sentences(script or "")[1:]:  # after a full stop: not the first
        text = sentence.strip().lstrip("*_")
        first = text.split(" ", 1)[0] if text else ""
        if first[:1].islower() and not any(ch.isupper() for ch in first):
            out.append(sentence.strip())
    return out


def unfinished_ending(script: str) -> list[str]:
    """#1334 (wave 116): what is wrong with how the script ends - [] when nothing.

    Run 136 (pulled 2026-10-13, "garbled last line") ended "...for the Texans to emerge
    victorious in convincing fashion on tennessee." Measured on the 78 stored tapin scripts
    before it was let near a render: every last line ends with a stop (the two shortest are whole:
    "Neither does Silva."), and a team's city or state in lowercase is run 136 alone - nicknames
    and "city" gave three false hits, so it is places only. "On the topic" by shared words is
    not checked: 29 of the 78 closing lines share no word with the title and read fine ("That's
    where this game gets decided.")."""
    from apis.topic_tokens import place_words

    sentences = [s for s in script_sentences(script) if not _SIGN_OFF_RE.match(s.strip())]
    if not sentences:
        return []
    problems: list[str] = []
    last = sentences[-1].strip()
    if not _ENDS_SENTENCE.search(last):
        problems.append(f'the last sentence has no stop ("...{last[-50:]}")')
    places = place_words()
    lowered = sorted({w for s in sentences for w in _LOWER_WORD.findall(s) if w in places})
    if lowered:
        problems.append(f'a place written in lowercase ("{lowered[0]}")')
    return problems


def run_on_sentences(script: str) -> list[str]:
    """#1352 (wave 116): the sentences that run into the next one with no stop between.

    Run 150's opener (2026-10-14): "...only 17 second-half points last game The Chargers' Super
    Bowl path is ...". The sign is a capitalised function word right after a lowercase word that
    is not itself one, with six or more words on each side inside the sentence - so a title
    stays ("the same guy who led The Lost Legacy.", run 109). Topic words come from
    `apis.topic_tokens.FUNCTION_WORDS`."""
    from apis.topic_tokens import FUNCTION_WORDS

    starters = {w.capitalize() for w in FUNCTION_WORDS if w.isalpha() and len(w) > 1}
    hits: list[str] = []
    for sentence in script_sentences(script):
        words = sentence.split()
        for i in range(_RUN_ON_SIDE, len(words) - _RUN_ON_SIDE + 1):
            before, word = words[i - 1], words[i]
            if (
                word in starters
                and re.fullmatch(r"[a-z][\w'\u2019-]*", before)
                and before.lower() not in FUNCTION_WORDS
            ):
                hits.append(sentence)
                break
    return hits


def drop_repeats(script: str, *, min_words: int, max_cut: int = 2) -> tuple[str, list[str]]:
    """Cut the second telling of a fact, while the script keeps its length. (script, cut)."""
    repeats = said_twice(script)[:max_cut]
    if not repeats:
        return script, []
    return drop_sentences(script, repeats, min_words=min_words)


def script_check(
    *,
    script: str,
    title: str = "",
    idea: str = "",
    thoughts: str = "",
    intent: str = "",
    unsupported: list[str] | None = None,
    cut: list[str] | None = None,
    short_by: int = 0,
    reading_target: float | None = None,
) -> dict[str, Any]:
    """#1143: the finished script against what the operator asked for, in one result.

    {ok, why: [...], points: {total, used, missing}, cut: [...]}. `ok` is what an unattended
    render requires.
    """
    from core.title_generator import SPOKEN_SPLIT_PLACES, broken_place_name, title_label

    why: list[str] = []
    blocking = [str(c) for c in unsupported or []]
    if blocking:
        why.append(f"{len(blocking)} claim(s) the facts do not support")
    slips = stance_slips(script, intent, idea or thoughts)
    if slips:
        why.append(f"a sentence knocks the stance ({slips[0][1]})")
    points = thought_points(thoughts)
    used, missing = points_used(script, points)
    if missing:
        why.append(f'{len(missing)} of your {len(points)} points missing: "{missing[0][:70]}"')
    label = title_label(title)
    if label:
        why.append(f'the title starts with a label ("{label}")')
    hard = len(hard_to_say(script))
    if hard:
        why.append(f"{hard} sentence(s) hard to say")
    twice = len(said_twice(script))
    if twice:
        why.append(f"{twice} thing{'s' if twice > 1 else ''} said twice")  # #1155
    run_on = run_on_sentences(script)
    if run_on:  # #1352
        why.append(f'a sentence runs into the next ("{run_on[0][:60]}")')
    why.extend(unfinished_ending(script))  # #1334
    stranded = mid_thought_starts(script)
    if stranded:  # #1587
        why.append(f'a sentence starts mid-thought ("{stranded[0][:60]}")')
    broken = broken_place_name(script, places=SPOKEN_SPLIT_PLACES)
    if broken:  # #1482: the captions show the script's words as written
        why.append(f'the script breaks a name: "{broken}" has lost a word, and so do the captions')
    if reading_target is not None:
        grade = reading_grade(script)
        if grade is not None and grade > float(reading_target):
            why.append(f"reading grade {grade:.1f} is above {float(reading_target):.0f}")
    check: dict[str, Any] = {
        "ok": not why,
        "why": why,
        "points": {"total": len(points), "used": len(used), "missing": missing[:3]},
        "cut": [str(c) for c in cut or []],
    }
    if short_by > 0:
        check["short_by"] = int(short_by)  # #1162: a cut left it under its minimum
    return check


def script_check_line(check: dict[str, Any] | None) -> str:
    """One line for the review screen, or "" when there is no check."""
    if not isinstance(check, dict) or "ok" not in check:
        return ""
    parts = ["clean" if check.get("ok") else f"{len(check.get('why') or [])} to look at"]
    parts.extend(str(w) for w in check.get("why") or [])
    points = check.get("points") or {}
    if points.get("total") and not points.get("missing"):
        parts.append(f"your points: {points.get('used')} of {points.get('total')} used")
    cut = check.get("cut") or []
    if cut:
        parts.append(f'cut {len(cut)} sentence(s): "{str(cut[0])[:70]}"')
    short = int(check.get("short_by") or 0)
    if short:
        parts.append(f"{short} words under its minimum after the cut")
    return "Script check: " + " - ".join(parts)
