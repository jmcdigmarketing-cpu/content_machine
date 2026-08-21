"""Fact-grounded YouTube title generation — runs after the script, not at discovery.

Discovery picks an editorial *angle*; the publishable title is generated here
once operator key facts and the script hook exist.
"""

from __future__ import annotations

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


def _hook_line(script: str) -> str:
    text = (script or "").strip()
    if not text:
        return ""
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return first[:200]


def _clean_title(raw: str, *, fallback: str) -> str:
    title = (raw or "").strip().strip('"').strip("'")
    title = re.sub(r"\s+", " ", title)
    if not title or _SLOP_RE.search(title):
        return fallback
    if len(title) > 100:
        title = title[:97].rsplit(" ", 1)[0] + "…"
    return title


def generate_title(
    *,
    script: str,
    topic: str,
    seed_topic: str = "",
    key_facts: list[str] | None = None,
    channel_id: str = "default",
) -> str:
    """Generate a fact-grounded title from the finished script + operator facts."""
    hook = _hook_line(script)
    facts = facts_for_prompt(key_facts)
    facts_block = (
        "\n".join(f"- {f}" for f in facts) if facts else "(none — use only what the script states)"
    )

    prompt = f"""Write ONE YouTube Shorts title for this video.

EDITORIAL ANGLE: {topic}
SEED TOPIC: {seed_topic or topic}
SCRIPT HOOK: {hook or topic}

OPERATOR FACTS (title must not contradict these):
{facts_block}

RULES:
- Prefer 50–70 characters; hard max 100.
- Name a specific person, team, or move when facts/script mention one.
- Accurate > catchy. No clickbait templates.
- BANNED phrases: {", ".join(_SLOP_PATTERNS[:8])}, etc.
- No ellipsis. No "My Hot Take" framing. No questions as the whole title.
- Return ONLY the title line — no quotes, no JSON, no explanation.

Title:"""

    fallback = hook[:70] if hook else (seed_topic or topic)[:70]

    # Fail-open: the title runs *after* the script, grounding and claim verifier have
    # already succeeded — an LLM outage here must never throw that work away. Any failure
    # degrades to the script hook, mirroring the variant path's "using heuristic angles".
    raw = _complete_or_none(prompt, temperature=0.45, max_tokens=48)
    if raw is None:
        return fallback

    title = _clean_title(raw, fallback=fallback)
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
            title = _clean_title(retry, fallback=fallback)
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
