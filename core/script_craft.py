"""#540 rhythm, #542 pre-CTA recap, #550 superlatives without a source."""

from __future__ import annotations

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
