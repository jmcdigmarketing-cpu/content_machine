"""
Pull concrete facts when signal payloads are too thin for scripting.

Uses on-hand APIs first (RAWG, News, YouTube, RSS), then optional LLM
extraction that may ONLY cite provided source text (no invention).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from core.channel_context import extract_anchors
from core.logging import get_logger
from core.signal_facts import format_signal_facts

logger = get_logger("core.fact_enrichment")

_MIN_FACT_LINES = int(os.getenv("FACT_ENRICH_MIN_LINES", "6"))

# YouTube section markers — these are context-only lines; don't count toward fact threshold
_YT_SECTION_HEADERS = (
    "YouTube — real video titles",
    "YouTube video descriptions",
    "YouTube market titles",
    "YouTube competitor performance",
)


def _fact_line_count(facts: str) -> int:
    """Count verified fact lines, excluding YouTube context-only sections."""
    if not facts or facts.strip().startswith("No structured facts"):
        return 0
    count = 0
    in_yt_section = False
    for line in facts.splitlines():
        stripped = line.strip()
        # Detect YouTube section start — skip header and all bullets within it
        if any(stripped.startswith(h) for h in _YT_SECTION_HEADERS):
            in_yt_section = True
            continue
        # Skip YouTube bullet lines (• and →) and indented continuation lines
        if in_yt_section and (
            stripped.startswith("•") or stripped.startswith("→") or line.startswith("  ")
        ):
            continue
        # Any other non-empty, non-bullet line exits YouTube section
        in_yt_section = False
        if stripped and (stripped.startswith("-") or ":" in stripped):
            count += 1
    return count


def _search_query(topic: str, seed_topic: str = "") -> str:
    anchors = extract_anchors(seed_topic or topic)
    if anchors:
        return anchors[0]
    return re.sub(r"\s+", " ", (seed_topic or topic).strip())[:80]


def _env(key: str) -> str:
    from config.settings import get_settings

    get_settings()
    return os.getenv(key, "").strip()


def _fetch_rawg_lines(query: str) -> list[str]:
    key = _env("RAWG_API_KEY")
    if not key:
        return []
    try:
        resp = requests.get(
            "https://api.rawg.io/api/games",
            params={"search": query, "page_size": 3, "key": key},
            timeout=12,
        )
        if resp.status_code != 200:
            return []
        lines: list[str] = []
        for game in resp.json().get("results") or []:
            name = game.get("name") or ""
            if not name:
                continue
            parts = [f"RAWG game: {name}"]
            if game.get("released"):
                parts.append(f"released {game['released']}")
            if game.get("rating"):
                parts.append(f"rating {game['rating']}")
            tags = [
                t.get("name")
                for t in (game.get("tags") or [])[:4]
                if isinstance(t, dict) and t.get("name")
            ]
            if tags:
                parts.append("tags: " + ", ".join(tags))
            lines.append(" — ".join(parts))
        return lines
    except Exception as exc:
        logger.debug("RAWG enrich failed: %s", exc)
        return []


def _fetch_news_lines(query: str) -> list[str]:
    key = _env("NEWS_API_KEY")
    if not key:
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "pageSize": 6, "sortBy": "publishedAt", "language": "en"},
            headers={"X-Api-Key": key},
            timeout=12,
        )
        if resp.status_code != 200:
            return []
        lines: list[str] = []
        for art in resp.json().get("articles") or []:
            title = (art.get("title") or "").strip()
            if not title or title == "[Removed]":
                continue
            source = (art.get("source") or {}).get("name") or "news"
            desc = (art.get("description") or "").strip()
            line = f"- {title} ({source})"
            if desc:
                line += f" — {desc[:160]}"
            lines.append(line)
            if len(lines) >= 6:
                break
        return lines
    except Exception as exc:
        logger.debug("News enrich failed: %s", exc)
        return []


def _fetch_youtube_lines(query: str) -> list[str]:
    skip = {
        s.strip().lower() for s in os.getenv("CONTENT_SKIP_SIGNALS", "").split(",") if s.strip()
    }
    if "youtube" in skip:
        return []
    try:
        from apis.youtube_api import search_youtube

        sig = search_youtube(query)
        if not sig.get("active"):
            return []
        data = sig.get("data") or {}
        titles = data.get("titles") or []
        if not titles and isinstance(data, list):
            titles = [
                item.get("title") or item.get("name") or ""
                for item in data
                if isinstance(item, dict)
            ]
        return [f"- YouTube: {t}" for t in titles[:6] if t]
    except Exception as exc:
        logger.debug("YouTube enrich failed: %s", exc)
        return []


def _fetch_rss_lines(topic: str, channel_id: str, query: str) -> list[str]:
    try:
        from apis.rss_feeds import fetch_rss_context

        rss = fetch_rss_context(topic, channel_id, search_query=query)
        lines: list[str] = []
        for h in rss.get("headlines") or []:
            title = h.get("title") or ""
            source = h.get("source") or "rss"
            if title:
                lines.append(f"- {title} ({source})")
        return lines[:8]
    except Exception as exc:
        logger.debug("RSS enrich failed: %s", exc)
        return []


def _llm_extract_facts(
    topic: str,
    source_blob: str,
    *,
    channel_id: str,
) -> list[str]:
    """Extract bullet facts from source text only. Returns [] on failure."""
    if not source_blob.strip():
        return []
    provider = os.getenv("RESEARCH_ENRICH_PROVIDER", "openai").strip().lower()
    if os.getenv("RESEARCH_ENRICH_LLM", "true").lower() in ("0", "false", "no"):
        return []

    prompt = f"""Extract ONLY factual bullets for a YouTube script about: {topic}

SOURCE MATERIAL (do not use knowledge outside this block):
{source_blob[:6000]}

Rules:
- Each bullet must cite a specific name, date, version, hero, mode, or quote from the sources.
- If sources lack patch/character specifics, return fewer bullets — do not invent.
- No opinions, no filler, no MCU/comic lore unless explicitly in sources.
- Marvel Rivals is a video game when mentioned.

Return JSON only: {{"facts": ["bullet1", "bullet2"]}}"""

    try:
        if provider == "anthropic":
            key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not key:
                return []
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
                    "max_tokens": 800,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=45,
            )
            if resp.status_code != 200:
                return []
            blocks = resp.json().get("content") or []
            raw = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        else:
            from core.llm_client import get_model, get_openai_client

            client = get_openai_client()
            response = client.chat.completions.create(
                model=get_model(),
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content or ""

        data = json.loads(raw)
        facts = data.get("facts") if isinstance(data, dict) else []
        return [str(f).strip() for f in facts if str(f).strip()][:10]
    except Exception as exc:
        logger.debug("LLM fact extract failed: %s", exc)
        return []


def enrich_facts(
    topic: str,
    signals: dict[str, Any],
    *,
    channel_id: str,
    seed_topic: str = "",
) -> str:
    """
    Return fact block for prompts — base signal facts plus targeted fetches
    when the base block is too thin.
    """
    base = format_signal_facts(signals)
    if _fact_line_count(base) >= _MIN_FACT_LINES:
        return base

    query = _search_query(topic, seed_topic)
    sections: list[str] = []
    if base and not base.startswith("No structured"):
        sections.append(base)

    rawg = _fetch_rawg_lines(query)
    if rawg:
        sections.append("Game database:\n" + "\n".join(f"- {x}" for x in rawg))

    news = _fetch_news_lines(query)
    if news:
        sections.append("News API:\n" + "\n".join(news))

    yt = _fetch_youtube_lines(query)
    if yt:
        sections.append("YouTube market titles:\n" + "\n".join(yt))

    rss = _fetch_rss_lines(topic, channel_id, query)
    if rss:
        sections.append("RSS headlines:\n" + "\n".join(rss))

    combined = "\n\n".join(sections)
    if _fact_line_count(combined) < _MIN_FACT_LINES:
        llm_facts = _llm_extract_facts(topic, combined, channel_id=channel_id)
        if llm_facts:
            sections.append(
                "Extracted facts (from sources above only):\n"
                + "\n".join(f"- {f}" for f in llm_facts)
            )
            combined = "\n\n".join(sections)

    if not combined.strip():
        return (
            f"⚠ THIN FACTS: No structured data found for '{query}'. "
            "Do NOT invent hero names, patch version numbers, balance changes, "
            "release dates, or specific game modes. "
            "Frame the script as an emerging/anticipated story using only what the "
            "topic title implies. Say 'reports suggest' or 'details are emerging'."
        )
    return combined
