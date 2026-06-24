"""Human-context layer (Phase O): channel persona + continuity callbacks.

YouTube's 2026 "inauthentic content" policy rewards *human context* — a consistent
voice, a point of view, and continuity that reads like a real creator following a
story, not a fresh templated upload each time. This module builds a prompt block
that gives the script:

  1. **Persona** — the channel's configured tone / audience / perspective /
     recurring-segment / sign-off (from `channels.json` "persona"). Optional;
     empty when unconfigured.
  2. **Continuity** — a soft, data-driven callback to what this channel has
     recently covered (from real run history), so the script can acknowledge an
     ongoing storyline *if it fits* — never forced, never invented.

Both are advisory prompt context, bounded so they can't override the
anti-hallucination or grounding rules. Returns "" when there's nothing to add, so
callers can drop the block entirely.
"""

from __future__ import annotations

from config.channels import get_channel_profile
from core.channel_context import dominant_anchor, recent_input_topics
from core.logging import get_logger

logger = get_logger("core.channel_persona")

# Persona keys we surface, in a stable order, with a human label for the prompt.
_PERSONA_FIELDS: tuple[tuple[str, str], ...] = (
    ("perspective", "Point of view"),
    ("tone", "Tone"),
    ("audience", "Audience"),
    ("recurring_segment", "Recurring segment"),
    ("signoff", "Sign-off"),
)

# How many recent topics inform the continuity hint.
_CONTINUITY_LOOKBACK = 12


def _persona_lines(channel_id: str) -> list[str]:
    persona = get_channel_profile(channel_id).persona or {}
    if not persona:
        return []
    lines: list[str] = []
    for key, label in _PERSONA_FIELDS:
        val = str(persona.get(key, "")).strip()
        if val:
            lines.append(f"- {label}: {val}")
    # Allow arbitrary extra persona keys the operator added, after the known ones.
    known = {k for k, _ in _PERSONA_FIELDS}
    for key, val in persona.items():
        if key not in known and str(val).strip():
            lines.append(f"- {key.replace('_', ' ').capitalize()}: {str(val).strip()}")
    return lines


def _continuity_line(channel_id: str) -> str:
    """A soft callback hint from real recent coverage — or '' if none/too thin."""
    try:
        recent = recent_input_topics(channel_id, limit=_CONTINUITY_LOOKBACK)
    except Exception as exc:
        logger.debug("continuity lookup failed: %s", exc)
        return ""
    if len(recent) < 2:
        return ""  # not enough history to claim an "ongoing" thread
    anchor = dominant_anchor(recent)
    if anchor:
        return (
            f"CONTINUITY: This channel has been actively covering {anchor}. If it "
            "fits naturally, you may acknowledge the ongoing storyline (e.g. 'we've "
            "been tracking this') — but only if it fits, and NEVER invent a specific "
            "past video, claim, or detail that isn't in the facts."
        )
    # No single anchor — offer the recent themes as light continuity context.
    sample = "; ".join(t.strip() for t in recent[:4] if t.strip())
    if not sample:
        return ""
    return (
        f"CONTINUITY: Recent coverage on this channel includes: {sample}. You may "
        "reference the channel's ongoing interest in these themes if it fits "
        "naturally — never force it or invent a specific prior video."
    )


def human_context_block(channel_id: str | None = None) -> str:
    """Persona + continuity prompt block for the script. '' when there's nothing."""
    cid = channel_id or "default"
    sections: list[str] = []

    persona_lines = _persona_lines(cid)
    if persona_lines:
        sections.append(
            "CHANNEL PERSONA — write in this channel's established voice (stay "
            "consistent so the audience recognises the creator):\n" + "\n".join(persona_lines)
        )

    continuity = _continuity_line(cid)
    if continuity:
        sections.append(continuity)

    return "\n\n".join(sections)
