"""
Description extras — AI-content disclosure + alt-monetization CTAs.

YouTube's inauthentic-content policy lists "disclose AI usage" as a top
compliance step. The public Data API does not reliably expose the in-player
"altered/synthetic content" toggle, but YouTube accepts an **in-description
disclosure**, which we can set on every upload. We also append optional
channel-configured monetization CTAs (affiliate / sponsor lines), since
gaming/UFC is a low-CPM niche where ad revenue alone underperforms.

Config (per-channel `config/seo/{channel}.json`, all optional):
  "ai_disclosure":   "<custom disclosure line>"   # overrides the default
  "monetization_cta": ["line one", "line two"]    # appended verbatim

Env toggles:
  AI_DISCLOSURE_ENABLED   = true (default) | false
"""

from __future__ import annotations

import os

from config.seo import get_seo_profile
from core.logging import get_logger

logger = get_logger("core.description_extras")

DEFAULT_AI_DISCLOSURE = "Made with AI-assisted narration and editing."


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def ai_disclosure_line(channel_id: str) -> str:
    """The disclosure line for a channel, or '' when disabled."""
    if not _flag("AI_DISCLOSURE_ENABLED", True):
        return ""
    try:
        custom = get_seo_profile(channel_id).get("ai_disclosure")
    except Exception:
        custom = None
    return (custom or DEFAULT_AI_DISCLOSURE).strip()


def monetization_ctas(channel_id: str) -> list[str]:
    """Channel-configured monetization/affiliate CTA lines (may be empty)."""
    try:
        raw = get_seo_profile(channel_id).get("monetization_cta")
    except Exception:
        raw = None
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def apply_description_extras(description: str, channel_id: str) -> str:
    """
    Append the AI disclosure and any monetization CTAs to a description.
    Idempotent — lines already present are not duplicated.
    """
    body = (description or "").rstrip()
    additions: list[str] = []

    disclosure = ai_disclosure_line(channel_id)
    if disclosure and disclosure not in body:
        additions.append(disclosure)

    for cta in monetization_ctas(channel_id):
        if cta not in body and cta not in additions:
            additions.append(cta)

    if not additions:
        return body
    tail = "\n".join(additions)
    return f"{body}\n\n{tail}" if body else tail
