"""
Hook intelligence (Phase P).

The first ~3 seconds decide a short's retention. This scores a script's opening
line 0-100 on the traits that correlate with strong hooks (specificity, brevity,
curiosity/contradiction, stakes) and penalises the weak openers our style guide
already bans. Heuristic and deterministic — no LLM call, so it's cheap enough to
run on every generation and fully testable.

`regenerate_hook` (opt-in, HOOK_REGEN_ENABLED=true) asks the LLM to rewrite just
the opening line when the score is below threshold.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# Openers our style guide bans — strong penalty.
_WEAK_OPENERS = (
    "today",
    "let's",
    "lets ",
    "in this video",
    "welcome",
    "hey",
    "so ",
    "well,",
    "guys",
    "what's up",
    "whats up",
    "have you ever",
)

# Curiosity / contradiction cues — these stop the scroll.
_CURIOSITY = (
    "nobody",
    "no one",
    "never",
    "everyone",
    "secret",
    "actually",
    "wrong",
    "stop ",
    "before you",
    "the truth",
    "here's why",
    "heres why",
    "what most",
)
# Removed: "won't believe" / "wont believe" / "nobody's talking". Each is a
# headline template `title_generator._SLOP_PATTERNS` bins and the angle prompt
# bans by name, so rewarding them here paid 28% of the report card for output
# the next stage throws away. See tests/test_gate_agreement.py.

# Stakes / scale markers.
_STAKES = re.compile(
    r"\$|\bbillion\b|\bmillion\b|biggest|first ever|changes everything|record|"
    r"\bbanned\b|\bdead\b|\bover\b 9000",
    re.IGNORECASE,
)

_DEFAULT_THRESHOLD = 60


def _is_banned_template(hook: str) -> bool:
    """Whether the hook is built on a headline template the pipeline rejects.

    `_CURIOSITY` still holds bare words ("nobody", "actually") that are fine on
    their own and appear inside banned templates by coincidence — dropping them
    outright would cost real hooks their bonus. So the templates are checked
    directly, against the one list that already defines them.

    Imported lazily: `title_generator` pulls in the LLM router, and this module
    advertises itself as heuristic and cheap enough to run on every generation.
    """
    try:
        from core.title_generator import _SLOP_RE
    except Exception:  # pragma: no cover - import guard only
        return False
    return bool(_SLOP_RE.search(hook or ""))


@dataclass
class HookScore:
    score: int
    hook: str
    reasons: list[tuple[str, int]] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.score >= 70:
            return "strong"
        if self.score >= _DEFAULT_THRESHOLD:
            return "ok"
        return "weak"

    @property
    def passed(self) -> bool:
        return self.score >= _DEFAULT_THRESHOLD


def extract_hook(script: str) -> str:
    """First sentence (or first line) of a script."""
    text = (script or "").strip()
    if not text:
        return ""
    # First line wins if the script is line-broken.
    first_line = text.splitlines()[0].strip()
    # Otherwise split on sentence terminators.
    match = re.split(r"(?<=[.!?])\s", first_line, maxsplit=1)
    return match[0].strip()


def score_hook(hook: str) -> HookScore:
    hook = (hook or "").strip()
    if not hook:
        return HookScore(score=0, hook="", reasons=[("empty", 0)])

    reasons: list[tuple[str, int]] = []
    score = 50
    low = hook.lower()
    words = hook.split()
    n = len(words)

    def add(label: str, delta: int) -> None:
        nonlocal score
        score += delta
        reasons.append((label, delta))

    if n <= 12:
        add("concise (≤12 words)", 20)
    elif n <= 18:
        add("a bit long", 5)
    else:
        add("too long (>18 words)", -12)

    if any(low.startswith(w) for w in _WEAK_OPENERS):
        add("weak opener", -25)

    if re.search(r"\d", hook):
        add("has a number", 15)

    if any(w[:1].isupper() for w in words[1:]):
        add("names a specific entity", 8)

    if hook.endswith("?"):
        add("opens as a question", -8)

    # A hook built on a banned template earns neither bonus: `_clean_title`
    # discards a title matching it, so paying for it here grades the run on
    # phrasing the pipeline refuses to publish.
    banned_template = _is_banned_template(hook)

    if any(c in low for c in _CURIOSITY) and not banned_template:
        add("curiosity / contradiction", 15)

    if _STAKES.search(hook) and not banned_template:
        add("high stakes", 10)

    if banned_template:
        # #656. No bonus was not enough: a slop hook still outscored a clean
        # specific one (93 vs 78 on the filed pair) and `_clean_title` bins it.
        add("banned template", -20)

    score = max(0, min(100, score))
    return HookScore(score=score, hook=hook, reasons=reasons)


def score_script_hook(script: str) -> HookScore:
    return score_hook(extract_hook(script))


def hook_regen_enabled() -> bool:
    return os.getenv("HOOK_REGEN_ENABLED", "").strip().lower() in ("1", "true", "yes")


def display_hook_score(hs: HookScore, *, print_fn=print) -> None:
    icon = {"strong": "✓", "ok": "✓", "weak": "✗"}.get(hs.verdict, "?")
    print_fn(f"\n  Hook {icon} {hs.score}/100 ({hs.verdict}) — first-3-seconds strength")
    print_fn(f'    "{hs.hook}"')
    if hs.verdict == "weak":
        weak_points = [label for label, delta in hs.reasons if delta < 0]
        if weak_points:
            print_fn("    Fix: " + ", ".join(weak_points))
