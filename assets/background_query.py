"""
Turn vague topics into concrete stock/local background search queries.

Vague prompts like "trendy nba finals video" often return abstract fog/bokeh B-roll
from Pexels/Pixabay. This module prefers literal sports/game footage terms.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import List, Optional

from apis.topic_scorer import infer_domain

# Stock metadata tags that usually mean abstract filler, not topic footage
ABSTRACT_STOCK_TERMS = frozenset(
    {
        "fog",
        "foggy",
        "haze",
        "mist",
        "smoke",
        "bokeh",
        "blur",
        "abstract",
        "particles",
        "light leak",
        "overlay",
        "texture",
        "gradient",
        "dream",
        "cinematic background",
    }
)

_DOMAIN_QUERIES = {
    "nba": [
        "nba basketball game arena crowd",
        "basketball court gameplay",
        "nba finals basketball",
    ],
    "nfl": [
        "nfl football game stadium",
        "american football field action",
    ],
    "ufc": [
        "mma octagon fight cage",
        "mixed martial arts training",
    ],
    "gaming": [
        "video game gameplay screen",
        "gaming setup neon",
        "esports arena",
    ],
}


def is_abstract_stock_text(text: str) -> bool:
    lower = (text or "").lower()
    return any(term in lower for term in ABSTRACT_STOCK_TERMS)


def _extract_entities(topic: str) -> List[str]:
    """Team/player-like tokens from topic."""
    tokens = re.findall(
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|knicks|spurs|lakers|celtics|"
        r"warriors|chiefs|rams|cowboys|ufc|nba|nfl)\b",
        topic,
        flags=re.I,
    )
    out: List[str] = []
    for t in tokens:
        low = t.lower()
        if low in ("the", "for", "and", "video", "trendy", "finals"):
            continue
        if t not in out:
            out.append(t)
    return out[:4]


def _rule_based_query(topic: str, category: str, channel_id: Optional[str]) -> str:
    domain = infer_domain(topic, channel_id)
    entities = _extract_entities(topic)

    if domain in _DOMAIN_QUERIES:
        base = _DOMAIN_QUERIES[domain][0]
        if entities:
            return f"{' '.join(entities)} {base.split()[-2]} {base.split()[-1]}"
        return base

    if category == "sports":
        return "basketball football sports arena gameplay"
    if category == "gaming":
        return "video game gameplay esports"
    words = [w for w in re.findall(r"[a-z0-9]{3,}", topic.lower()) if w not in (
        "the", "and", "for", "with", "video", "trendy", "about"
    )]
    return " ".join(words[:5]) or topic[:40]


def _llm_query(topic: str, category: str) -> Optional[str]:
    """Stock-video search query via the cheap tier (throwaway rewriting work)."""
    if os.getenv("BACKGROUND_QUERY_LLM", "true").lower() in ("0", "false", "no"):
        return None
    # BACKGROUND_LLM_PROVIDER stays honored as a per-call provider override.
    provider = os.getenv("BACKGROUND_LLM_PROVIDER", "").strip().lower() or None
    try:
        from core.llm_router import complete

        text = complete(
            f"Topic: {topic}\nCategory: {category}\nSearch query:",
            tier="cheap",
            system=(
                "You write stock-video search queries. Return ONE short line only. "
                "Prefer literal footage: real games, courts, arenas, gameplay screens. "
                "Never: fog, haze, bokeh, abstract particles, empty gradients."
            ),
            temperature=0.2,
            max_tokens=60,
            provider=provider,
        )
        q = (text or "").strip().strip('"')
        return q[:80] if q else None
    except Exception:
        return None


def sanitize_trademark_stock_query(query: str) -> str:
    """Never Pexels-search the UFC trademark — use generic MMA footage terms."""
    if os.getenv("STOCK_QUERY_UFC_REWRITE", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return (query or "").strip()
    text = query or ""
    cleaned = re.sub(r"\bufc\b", "mma", text, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "mixed martial arts octagon"


@lru_cache(maxsize=128)
def resolve_background_query(
    topic: str,
    category: str,
    channel_id: Optional[str] = None,
) -> str:
    """
    Best search string for local folder pick + Pexels/Pixabay.
    """
    llm_q = _llm_query(topic, category)
    rule_q = _rule_based_query(topic, category, channel_id)
    query = llm_q or rule_q
    if is_abstract_stock_text(query):
        query = rule_q
    return sanitize_trademark_stock_query(query)
