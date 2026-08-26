"""
Pre-upload authenticity self-check (Phase O).

YouTube's "inauthentic content" policy (Jul 2025) demonetises templated,
mass-produced, low-insight uploads. This module scores a freshly generated
script against three policy-aligned checks before render/upload:

  1. variation — lexical difflib (copy-paste / stamped opening) plus a stdlib
     content-word cosine check for paraphrased rehash. ``AUTHENTICITY_SEMANTIC=false``
     disables the cosine arm; exact duplicates still fail lexical first.
  2. original_insight — does it contain an opinion / analysis / prediction
     beat, not just a neutral recap?
  3. substance — enough spoken length and at least one verified fact behind it?

It is advisory by default (warn). Set AUTHENTICITY_GATE=block to have the
pipeline treat a "block" verdict as a hard stop the operator must override.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from config.channels import resolve_channel_id
from core.logging import get_logger
from core.script_length import count_spoken_words

logger = get_logger("core.authenticity")

# How many recent uploads to compare against for the variation check.
_RECENT_RUNS = 12
# Full-script similarity above this vs any recent upload = templated.
_FULL_SIM_LIMIT = 0.60
# Opening-line similarity above this = same intro stamped on every video.
_OPENING_SIM_LIMIT = 0.80
# Content-word cosine above this vs any recent upload = the same video rehashed
# (paraphrase, not copy-paste). Measured against the suite fixtures: a same-facts
# rewrite of GOOD_SCRIPT vs GOOD_SCRIPT is high; an unrelated topic is near 0.
# 0.45 sits between with room on both sides.
_SEMANTIC_SIM_LIMIT = 0.45
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_CONTENT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "his",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "out",
        "she",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "up",
        "was",
        "we",
        "were",
        "what",
        "when",
        "who",
        "will",
        "with",
        "you",
        "your",
    }
)
# Substance floors.
_MIN_WORDS = 55
_MIN_FACTS = 1

# Opinion / analysis / prediction cues — presence of an authorial "take".
_INSIGHT_MARKERS = (
    "i think",
    "i'd argue",
    "i would argue",
    "my take",
    "my prediction",
    "i predict",
    "here's why",
    "heres why",
    "the real reason",
    "what this means",
    "what it means",
    "the bigger picture",
    "in my opinion",
    "if you ask me",
    "the truth is",
    "this matters because",
    "what most people miss",
    "underrated",
    "overrated",
    "mark my words",
    "calling it now",
    "bold prediction",
    "hot take",
    "the problem is",
    "expect",
    "will likely",
    "my bet",
    "here's the thing",
    "heres the thing",
)


@dataclass
class AuthenticityCheck:
    name: str
    passed: bool
    weight: int
    detail: str


@dataclass
class AuthenticityReport:
    score: int  # 0-100
    verdict: str  # "ok" | "review" | "block"
    checks: list[AuthenticityCheck]
    semantic_overlap: float = 0.0  # peak content-word cosine vs recent (0-1)

    @property
    def passed(self) -> bool:
        return self.verdict == "ok"


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _opening(text: str, *, words: int = 12) -> str:
    return " ".join(_normalise(text).split()[:words])


def _semantic_enabled() -> bool:
    return os.getenv("AUTHENTICITY_SEMANTIC", "true").strip().lower() in ("1", "true", "yes")


def _content_tokens(text: str) -> Counter[str]:
    return Counter(
        tok
        for tok in _TOKEN_RE.findall(_normalise(text))
        if tok not in _CONTENT_STOPWORDS and len(tok) > 1
    )


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(left[k] * right[k] for k in left.keys() & right.keys())
    na = math.sqrt(sum(v * v for v in left.values()))
    nb = math.sqrt(sum(v * v for v in right.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _content_cosine(script: str, other: str) -> float:
    return _cosine(_content_tokens(script), _content_tokens(other))


def _recent_scripts(channel_id: str, *, exclude_run_id: int | None) -> list[str]:
    """Recent uploads' script text (script_preview), newest first."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
    except Exception as exc:
        logger.debug("authenticity: could not load recent runs: %s", exc)
        return []

    scripts: list[str] = []
    for run in runs[: _RECENT_RUNS + 1]:
        if exclude_run_id is not None and run.id == exclude_run_id:
            continue
        text = (run.script_preview or "").strip()
        if text:
            scripts.append(text)
        if len(scripts) >= _RECENT_RUNS:
            break
    return scripts


def _variation_check(script: str, recent: list[str]) -> AuthenticityCheck:
    if not recent:
        return AuthenticityCheck(
            "variation", True, 40, "no prior uploads to compare — assumed unique"
        )

    norm = _normalise(script)
    opening = _opening(script)
    max_full = 0.0
    max_open = 0.0
    for other in recent:
        max_full = max(max_full, SequenceMatcher(None, norm, _normalise(other)).ratio())
        max_open = max(max_open, SequenceMatcher(None, opening, _opening(other)).ratio())

    if max_full >= _FULL_SIM_LIMIT:
        return AuthenticityCheck(
            "variation",
            False,
            40,
            f"{max_full:.0%} similar to a recent upload — looks template-stamped",
        )
    if max_open >= _OPENING_SIM_LIMIT:
        return AuthenticityCheck(
            "variation",
            False,
            40,
            f"opening {max_open:.0%} like a recent video — vary the hook",
        )
    if _semantic_enabled():
        max_sem = 0.0
        for other in recent:
            max_sem = max(max_sem, _content_cosine(script, other))
        if max_sem >= _SEMANTIC_SIM_LIMIT:
            return AuthenticityCheck(
                "variation",
                False,
                40,
                f"content overlap {max_sem:.0%} with a recent upload — looks like a rehash",
            )
    return AuthenticityCheck(
        "variation", True, 40, f"distinct from recent uploads (peak {max_full:.0%})"
    )


def _insight_check(script: str) -> AuthenticityCheck:
    norm = _normalise(script)
    found = [m for m in _INSIGHT_MARKERS if m in norm]
    if found:
        return AuthenticityCheck(
            "original_insight", True, 35, f"has an authorial take ('{found[0]}')"
        )
    return AuthenticityCheck(
        "original_insight",
        False,
        35,
        "no opinion/prediction/analysis beat — reads as a neutral recap",
    )


def has_insight(script: str) -> bool:
    """True if the script carries an opinion/prediction/analysis beat (a 'take').

    Public wrapper over the insight detector so generation can inject a beat when
    a script reads as a neutral recap, using the same signal the gate scores on.
    """
    return _insight_check(script).passed


def _substance_check(script: str, fact_count: int) -> AuthenticityCheck:
    words = count_spoken_words(script)
    if words < _MIN_WORDS:
        return AuthenticityCheck("substance", False, 25, f"only {words} spoken words — too thin")
    if fact_count < _MIN_FACTS:
        return AuthenticityCheck("substance", False, 25, "no verified facts behind the script")
    return AuthenticityCheck("substance", True, 25, f"{words} words, {fact_count} verified fact(s)")


def evaluate_authenticity(
    script: str,
    channel_id: str,
    *,
    fact_count: int = 0,
    exclude_run_id: int | None = None,
) -> AuthenticityReport:
    """Score a script against the three policy-aligned checks."""
    channel_id = resolve_channel_id(channel_id)
    recent = _recent_scripts(channel_id, exclude_run_id=exclude_run_id)

    checks = [
        _variation_check(script, recent),
        _insight_check(script),
        _substance_check(script, fact_count),
    ]
    score = sum(c.weight for c in checks if c.passed)

    if score >= 75:
        verdict = "ok"
    elif score >= 40:
        verdict = "review"
    else:
        verdict = "block"

    overlap = 0.0
    if _semantic_enabled() and recent:
        overlap = max(_content_cosine(script, other) for other in recent)

    return AuthenticityReport(score=score, verdict=verdict, checks=checks, semantic_overlap=overlap)


def gate_mode() -> str:
    """warn (default) | block — how the pipeline treats a 'block' verdict."""
    return os.getenv("AUTHENTICITY_GATE", "warn").strip().lower() or "warn"


def display_authenticity_report(report: AuthenticityReport, *, print_fn=print) -> None:
    icon = {"ok": "✓", "review": "!", "block": "✗"}.get(report.verdict, "?")
    print_fn(
        f"\n  Authenticity {icon} {report.score}/100 ({report.verdict}) "
        f"— monetisation safety check"
    )
    for c in report.checks:
        mark = "✓" if c.passed else "✗"
        print_fn(f"    {mark} {c.name}: {c.detail}")
    if report.verdict != "ok":
        print_fn(
            "    Tip: add an opinion/prediction, vary the hook, or cite more "
            "verified facts to avoid 'inauthentic content' flags."
        )
