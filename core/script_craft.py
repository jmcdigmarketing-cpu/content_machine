"""#540 rhythm, #542 pre-CTA recap, #550 superlatives without a source."""

from __future__ import annotations

import os
import re
from typing import Any

_SENTENCE = re.compile(r"[^.!?]+[.!?]+")
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


def sentence_rhythm_flags(script: str) -> list[str]:
    """Uniform sentence length is the clearest LLM tell. Warn-only."""
    parts = [p.strip() for p in _SENTENCE.findall(script or "") if p.strip()]
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
    return ""


def hard_to_say(script: str) -> list[dict[str, str]]:
    """Sentences a voice will stumble on: [{sentence, why}], in order. Free; always runs."""
    out: list[dict[str, str]] = []
    for part in _SENTENCE.findall(script or ""):
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
    for part in _SENTENCE.findall(text or "") or [text or ""]:
        words = re.findall(r"[\w'-]+", part)
        names.update(w for w in words[1:] if w[:1].isupper())
    return names


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
        "parenthetical, or a long list of names. Rewrite each so it is easy to say - split it "
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
        if _names_in(new) - _names_in(old) or _names_in(old) - _names_in(new):
            continue
        out = out.replace(old, new, 1)
        report["rewritten"] += 1
    return out, report
