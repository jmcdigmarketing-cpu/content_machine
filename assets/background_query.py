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
        "ufc mma octagon fight",
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


def _llm_query_openai(topic: str, category: str) -> Optional[str]:
    if os.getenv("BACKGROUND_QUERY_LLM", "true").lower() in ("0", "false", "no"):
        return None
    try:
        from core.llm_client import get_model, get_openai_client

        client = get_openai_client()
        response = client.chat.completions.create(
            model=get_model(),
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write stock-video search queries. Return ONE short line only. "
                        "Prefer literal footage: real games, courts, arenas, gameplay screens. "
                        "Never: fog, haze, bokeh, abstract particles, empty gradients."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Topic: {topic}\nCategory: {category}\nSearch query:",
                },
            ],
        )
        q = (response.choices[0].message.content or "").strip().strip('"')
        return q[:80] if q else None
    except Exception:
        return None


def _llm_query_anthropic(topic: str, category: str) -> Optional[str]:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    if os.getenv("BACKGROUND_QUERY_LLM", "true").lower() in ("0", "false", "no"):
        return None
    try:
        import requests

        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 60,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Stock video search query for topic '{topic}' ({category}). "
                            "One line only. Literal game/sports/gameplay footage. "
                            "No fog, haze, bokeh, or abstract backgrounds."
                        ),
                    }
                ],
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        q = text.strip().strip('"')
        return q[:80] if q else None
    except Exception:
        return None


@lru_cache(maxsize=128)
def resolve_background_query(
    topic: str,
    category: str,
    channel_id: Optional[str] = None,
) -> str:
    """
    Best search string for local folder pick + Pexels/Pixabay.
    """
    provider = os.getenv("BACKGROUND_LLM_PROVIDER", "openai").strip().lower()
    llm_q = None
    if provider == "anthropic":
        llm_q = _llm_query_anthropic(topic, category)
    if not llm_q:
        llm_q = _llm_query_openai(topic, category)

    rule_q = _rule_based_query(topic, category, channel_id)
    query = llm_q or rule_q
    if is_abstract_stock_text(query):
        query = rule_q
    return query
