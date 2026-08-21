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
  DESCRIPTION_SEO_FIRST_LINE = true (default) | false
  FTC_DISCLOSURE          = true (default) | false  # only when monetization_cta is set
"""

from __future__ import annotations

import os

from config.seo import get_seo_profile
from core.logging import get_logger

logger = get_logger("core.description_extras")

DEFAULT_AI_DISCLOSURE = "Made with AI-assisted narration and editing."
DEFAULT_FINANCE_DISCLAIMER = (
    "Not financial advice. For informational purposes only. Do your own research."
)
DEFAULT_FTC_DISCLOSURE = (
    "Some links may be affiliate links. We may earn a commission at no extra cost to you."
)


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


def finance_disclaimer_line(channel_id: str) -> str:
    """MoneyWise description disclaimer (separate from AI disclosure)."""
    if (channel_id or "").strip().lower() != "moneywise":
        return ""
    if not _flag("FINANCE_DISCLAIMER", True):
        return ""
    try:
        custom = get_seo_profile(channel_id).get("finance_disclaimer")
    except Exception:
        custom = None
    return (custom or DEFAULT_FINANCE_DISCLAIMER).strip()


def ftc_affiliate_line(channel_id: str) -> str:
    """FTC affiliate disclosure — copy only; #79 is the tracking spike."""
    if not _flag("FTC_DISCLOSURE", True):
        return ""
    ctas = monetization_ctas(channel_id)
    if not ctas:
        return ""
    try:
        custom = get_seo_profile(channel_id).get("ftc_disclosure")
    except Exception:
        custom = None
    return (custom or DEFAULT_FTC_DISCLOSURE).strip()


def ensure_seo_first_line(description: str, title: str = "") -> str:
    """First line is a search snippet (topic/title), not hashtags or Subscribe."""
    if not _flag("DESCRIPTION_SEO_FIRST_LINE", True):
        return description or ""
    body = (description or "").strip()
    headline = (title or "").strip()
    if not headline:
        return body
    first = body.splitlines()[0].strip() if body else ""
    weak = (
        not first
        or first.startswith("#")
        or first.lower().startswith("subscribe")
        or first.lower().startswith("http")
    )
    if not weak:
        return body
    if headline in body:
        return body
    return f"{headline}\n\n{body}" if body else headline


def apply_description_extras(description: str, channel_id: str, *, title: str = "") -> str:
    """
    Append the AI disclosure and any monetization CTAs to a description.
    Idempotent — lines already present are not duplicated.
    """
    body = (description or "").rstrip()
    try:
        from core.odds_language import strip_betting_ctas

        body, _n = strip_betting_ctas(body)
    except Exception as exc:
        logger.debug("description betting-cta strip skipped: %s", exc)
    body = ensure_seo_first_line(body, title).rstrip()
    additions: list[str] = []

    disclosure = ai_disclosure_line(channel_id)
    if disclosure and disclosure not in body:
        additions.append(disclosure)

    finance = finance_disclaimer_line(channel_id)
    if finance and finance not in body:
        additions.append(finance)

    ftc = ftc_affiliate_line(channel_id)
    if ftc and ftc not in body:
        additions.append(ftc)

    for cta in monetization_ctas(channel_id):
        if cta not in body and cta not in additions:
            additions.append(cta)

    if not additions:
        return body
    tail = "\n".join(additions)
    return f"{body}\n\n{tail}" if body else tail
