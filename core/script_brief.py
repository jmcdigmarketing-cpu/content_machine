"""
Domain-specific script writing matrix injected into the LLM prompt.
"""

from __future__ import annotations

import re

from apis.topic_scorer import infer_domain
from config.channels import get_channel_profile
from core.channel_context import channel_history_block, extract_anchors


def _extract_event_tag(topic: str) -> str | None:
    match = re.search(r"\bUFC\s*(\d{2,4})\b", topic, re.I)
    if match:
        return f"UFC {match.group(1)}"
    return None


def build_script_brief(
    topic: str,
    channel_id: str | None = None,
    *,
    seed_topic: str | None = None,
    key_facts: list[str] | None = None,
) -> str:
    domain = infer_domain(topic, channel_id, key_facts=key_facts)
    event = _extract_event_tag(topic)
    lines = [f"DOMAIN: {domain}"]

    seed = (seed_topic or topic).strip()
    anchors = extract_anchors(seed)
    if seed_topic and seed_topic.strip().lower() != topic.strip().lower():
        lines.append(f"SEED TOPIC (user intent — do not drift): {seed_topic.strip()}")
    history = channel_history_block(channel_id) if channel_id else ""
    if history and domain not in ("nba", "nfl", "ufc", "finance"):
        lines.extend(["", history])
    elif history:
        # Recent topics are useful context but drop the gaming-franchise nudge on sports runs.
        trimmed = [
            ln
            for ln in history.splitlines()
            if not ln.startswith("Primary franchise focus lately:")
        ]
        if len(trimmed) > 1:
            lines.extend(["", "\n".join(trimmed)])

    if domain == "ufc":
        lines.extend(
            [
                "",
                "UFC SCRIPT MATRIX (mandatory):",
                "- Anchor the piece to the EXACT bout and event named in TOPIC and FACTS.",
                "- Do NOT move fighters to the wrong weight class unless FACTS say they are moving up/down.",
                "- Ilia Topuria is the featherweight (145 lb) champion unless FACTS say otherwise.",
                "- Justin Gaethje fights at lightweight (155 lb); a champion moving up to face him is a storyline — state it clearly, do not call Gaethje a random contender.",
                "- Do NOT name future opponents unless they appear in FACTS for this fight (no Dustin Poirier unless FACTS mention him).",
                "- Charles Oliveira outcomes must match FACTS/timeline — if unsure, say 'a prior meeting' without inventing results.",
                "- Retired or inactive fighters: omit or say 'retired' only if FACTS mention it.",
                "- Prefer Tapology-style facts: event number, card placement, weight class, streak, last opponent.",
                "- No generic 'landscape of the division' filler; be specific to this matchup.",
                "- If FACTS are thin, frame as preview/hype and avoid stating results or rankings as fact.",
            ]
        )
        if event:
            lines.append(f"- Event tag from topic: {event} — use this event number consistently.")

    elif domain == "nba":
        lines.extend(
            [
                "",
                "NBA SCRIPT MATRIX (mandatory):",
                "- Cover NBA teams, standings, awards (MVP, ROY, etc.) — real basketball only.",
                "- Use team/city and player names from TOPIC and FACTS; cite records/odds when given.",
                "- Do NOT write about video games, esports, Marvel Rivals, game patches, or comp meta.",
                "- Standings/predictions must name specific teams from FACTS when available.",
            ]
        )
        if channel_id and get_channel_profile(channel_id).domain == "gaming":
            lines.append(
                "- CHANNEL NOTE: TapIn sports crossover — this is NBA analysis, not a gaming video."
            )

    elif domain == "nfl":
        lines.extend(
            [
                "",
                "NFL SCRIPT MATRIX (mandatory):",
                "- Cover NFL teams, standings, and awards — real football only.",
                "- Do NOT write about video games, esports, or game patches.",
            ]
        )

    elif domain == "gaming":
        lines.extend(
            [
                "",
                "GAMING SCRIPT MATRIX:",
                "- Name the game/franchise from TOPIC, SEED TOPIC, or FACTS only.",
                "- No fabricated release dates or studio quotes.",
                "- Do NOT pivot to MCU movies, comics, or Avengers lore unless FACTS name them.",
            ]
        )
        if any("marvel rivals" in a.lower() for a in anchors):
            lines.extend(
                [
                    "- Marvel Rivals is the hero-shooter VIDEO GAME — cover patches, heroes, meta, seasons.",
                    "- Never write about Loki, Avengers alliances, or comic rivalries unless FACTS say so.",
                ]
            )

    return "\n".join(lines)
