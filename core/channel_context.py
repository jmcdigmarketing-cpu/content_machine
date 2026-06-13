"""Channel history and topic anchors shared by best-bet, variants, and content."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from config.channels import get_channel_profile, resolve_channel_id

# Franchise / game strings worth preserving on gaming channels (longest first).
_GAME_ANCHORS = (
    "marvel rivals",
    "call of duty",
    "gta vi",
    "gta v",
    "subnautica",
    "terraria",
    "fortnite",
    "valorant",
    "minecraft",
    "elden ring",
    "cod zombies",
    "gta",
    "cod",
    "ufc",
)

_MCU_DRIFT_MARKERS = (
    "mcu",
    "avengers",
    "loki",
    "spider-man",
    "iron man",
    "comic",
    "movie",
    "disney+",
)


def extract_anchors(text: str) -> list[str]:
    """Return canonical anchor phrases found in text (e.g. 'Marvel Rivals')."""
    lower = (text or "").lower()
    found: list[str] = []
    for anchor in _GAME_ANCHORS:
        if anchor in lower:
            found.append(anchor.title() if anchor != "ufc" else "UFC")
    return found


def dominant_anchor(topics: Iterable[str]) -> str | None:
    """Most frequent game/franchise anchor across recent channel topics."""
    counts: Counter[str] = Counter()
    for topic in topics:
        for anchor in extract_anchors(topic):
            counts[anchor.lower()] += 1
    if not counts:
        return None
    key = counts.most_common(1)[0][0]
    for anchor in _GAME_ANCHORS:
        if anchor == key:
            return anchor.title() if anchor != "ufc" else "UFC"
    return key.title()


def preserves_anchors(variant: str, seed: str) -> bool:
    """True when variant text still mentions every anchor from the seed topic."""
    seed_anchors = extract_anchors(seed)
    if not seed_anchors:
        return True
    lower = (variant or "").lower()
    return all(a.lower() in lower for a in seed_anchors)


def anchor_preservation_penalty(variant: str, seed: str) -> float:
    """Score penalty when a variant drops seed anchors (0–25)."""
    if preserves_anchors(variant, seed):
        return 0.0
    return 25.0


def mcu_drift_penalty(variant: str, seed: str) -> float:
    """Penalize MCU/comic drift when seed was a video game (e.g. Marvel Rivals)."""
    if "marvel rivals" not in (seed or "").lower():
        return 0.0
    lower = (variant or "").lower()
    if "marvel rivals" in lower:
        return 0.0
    if any(m in lower for m in _MCU_DRIFT_MARKERS):
        return 20.0
    if "marvel" in lower and "rivals" not in lower:
        return 15.0
    return 0.0


def recent_input_topics(channel_id: str, *, limit: int = 12) -> list[str]:
    """Recent user seed topics for a channel (newest first)."""
    from storage.repositories.content_runs import get_content_run_repository

    channel_id = resolve_channel_id(channel_id)
    runs = get_content_run_repository().list_for_channel(channel_id)[:limit]
    topics: list[str] = []
    for run in runs:
        seed = (run.input_topic or run.selected_topic or "").strip()
        if seed and seed not in topics:
            topics.append(seed)
    return topics


def channel_history_block(channel_id: str, *, limit: int = 6) -> str:
    """Prompt block summarizing recent channel topics."""
    topics = recent_input_topics(channel_id, limit=limit)
    if not topics:
        return ""
    lines = ["CHANNEL HISTORY (recent videos on this channel — stay on-brand):"]
    for t in topics:
        lines.append(f"  - {t}")
    anchor = dominant_anchor(topics)
    if anchor:
        lines.append(f"Primary franchise focus lately: {anchor}")
    return "\n".join(lines)


def on_brand_domains(channel_id: str) -> set[str]:
    """Domains considered on-brand for this channel."""
    profile = get_channel_profile(channel_id)
    domains = {profile.domain or "neutral"}
    if profile.domain == "gaming":
        domains.add("ufc")
    return domains


def normalize_seed_topic(topic: str) -> str:
    """Strip LLM angle prefixes accidentally stored as topics."""
    t = (topic or "").strip()
    t = re.sub(
        r"^(primary storyline|underrated angle|controversy|impact analysis|long[- ]term outlook)\s*:\s*",
        "",
        t,
        flags=re.I,
    )
    return t.strip() or topic
