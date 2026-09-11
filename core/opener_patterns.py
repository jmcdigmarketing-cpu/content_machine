"""#407: enforce the recorded opener shapes instead of trusting the first draft.

`hook_score.score_hook` already *prices* an opener, but the price was the only
output: a hook could clear the threshold while opening on a shape this repo has
recorded as weak, and the operator saw a number with no named reason. The number
also nets out -- a bonus elsewhere can hide a weak opener entirely.

**Labelled as editorial judgment, not prediction.** With around ten published
videos there is no basis to claim an opener shape causes retention, so this names
which recorded pattern the opener matches and what to do instead. It never quotes
a lift, a percentage or a forecast; that would be inventing predictive evidence
from a sample that cannot carry it. Reuses `hook_score`'s own tables so the two
cannot drift into disagreeing about what "weak" means.
"""

from __future__ import annotations

import re

from core.hook_score import _CURIOSITY, _STAKES, _WEAK_OPENERS, extract_hook

# Shapes beyond the bare prefix list: a first sentence that commits to nothing.
_FILLER_OPENERS = (
    re.compile(r"^\s*(?:so|well|okay|ok|right|now)\b[\s,]", re.I),
    re.compile(r"^\s*(?:basically|essentially|obviously)\b", re.I),
    re.compile(r"^\s*(?:i|we)\s+(?:want|wanted|am going|'m going|are going)\s+to\b", re.I),
    re.compile(r"^\s*(?:this|that)\s+(?:is|was)\s+(?:a|an|the)\s+(?:video|one)\b", re.I),
)

_ADVICE = "lead with the specific thing that happened, or the claim being contradicted"


def opener_shape(hook: str) -> str:
    """The recorded pattern this opener matches: '', 'weak_prefix' or 'filler'."""
    text = (hook or "").strip()
    if not text:
        return ""
    low = text.lower()
    if any(low.startswith(word) for word in _WEAK_OPENERS):
        return "weak_prefix"
    if any(pattern.search(text) for pattern in _FILLER_OPENERS):
        return "filler"
    return ""


def opener_carries_a_specific(hook: str) -> bool:
    """A number, a named entity, a stakes marker or a contradiction cue."""
    text = (hook or "").strip()
    if not text:
        return False
    low = text.lower()
    words = text.split()
    return bool(
        re.search(r"\d", text)
        or any(w[:1].isupper() for w in words[1:])
        or _STAKES.search(text)
        or any(cue in low for cue in _CURIOSITY)
    )


def opener_advisory(hook_or_script: str) -> str:
    """A sentence when the opener matches a recorded weak shape, else ''.

    Accepts a hook or a whole script -- `extract_hook` picks the first sentence,
    so callers do not have to know which they hold.
    """
    text = (hook_or_script or "").strip()
    if not text:
        return ""
    hook = text if len(text.split()) <= 25 else extract_hook(text)
    shape = opener_shape(hook)
    if not shape:
        return ""
    if shape == "weak_prefix":
        why = "opener uses a recorded weak prefix"
    else:
        why = "opener commits to nothing in the first sentence"
    tail = "" if opener_carries_a_specific(hook) else "; it names nothing specific either"
    return f"{why}{tail} - {_ADVICE} (recorded pattern, not a measured outcome)"
