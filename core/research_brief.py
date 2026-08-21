"""
Research Brief Engine (Phase H) — one structured brief per selected topic.

Runs after variant selection, before content generation. Cached by topic+channel.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

from apis.cache_manager import build_key, get_cached, set_cache
from apis.rss_feeds import fetch_rss_context
from config.channels import resolve_channel_id
from config.seo import build_seo_prompt_block
from core.channel_context import channel_history_block, extract_anchors
from core.fact_enrichment import enrich_facts
from core.llm_router import complete_json
from core.logging import get_logger
from core.script_brief import build_script_brief

logger = get_logger("core.research_brief")

BRIEF_VERSION = "research_brief_v4"
_CACHE_TTL = 60 * 60 * 3
_USE_LLM = os.getenv("RESEARCH_BRIEF_LLM", "1").lower() not in ("0", "false", "no")


@dataclass
class ResearchBrief:
    version: str = BRIEF_VERSION
    topic: str = ""
    narrative: str = ""
    audience_sentiment: str = ""
    controversy_score: float = 0.0
    debate_angles: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)
    recommended_format: str = "short_debate"
    title_direction: str = ""
    suggested_hook: str = ""
    rss_headlines: list[dict[str, str]] = field(default_factory=list)
    community_summary: str = ""
    competitor_pulse: str = ""
    stats_lines: list[str] = field(default_factory=list)
    raw_fallback: str = ""

    def to_prompt_block(self) -> str:
        lines = [
            "RESEARCH BRIEF (primary context — prefer over raw signal dumps):",
            f"Narrative: {self.narrative}",
            f"Audience sentiment: {self.audience_sentiment}",
            f"Controversy (0-1): {self.controversy_score:.2f}",
        ]
        if self.debate_angles:
            lines.append("Debate angles: " + "; ".join(self.debate_angles[:5]))
        if self.supporting_evidence:
            lines.append("Evidence:")
            for ev in self.supporting_evidence[:6]:
                lines.append(f"  - {ev}")
        if self.recommended_format:
            lines.append(f"Recommended format: {self.recommended_format}")
        if self.title_direction:
            lines.append(f"Suggested title direction: {self.title_direction}")
        if self.suggested_hook:
            lines.append(f"Suggested hook (<12 words, use or beat it): {self.suggested_hook}")
        if self.community_summary:
            lines.append(f"Community pulse (RSS):\n{self.community_summary}")
        if self.rss_headlines:
            lines.append("RSS headlines:")
            for h in self.rss_headlines[:6]:
                lines.append(f"  - {h.get('title', '')} ({h.get('source', '')})")
        if self.competitor_pulse:
            lines.append(self.competitor_pulse)
        if self.stats_lines:
            lines.append("Reference stats:")
            for s in self.stats_lines[:8]:
                lines.append(f"  - {s}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fallback_brief(
    topic: str,
    signals: dict[str, Any],
    channel_id: str,
    *,
    seed_topic: str = "",
) -> ResearchBrief:
    facts = enrich_facts(topic, signals, channel_id=channel_id, seed_topic=seed_topic)
    script_rules = build_script_brief(topic, channel_id)
    return ResearchBrief(
        topic=topic,
        narrative=f"Focus on the specific angle in the topic: {topic}",
        audience_sentiment="Neutral — limited research data",
        controversy_score=0.4,
        debate_angles=["Preview the stakes of the matchup or announcement"],
        supporting_evidence=[line for line in facts.split("\n") if line.strip()][:8],
        recommended_format="short_debate",
        raw_fallback=f"{script_rules}\n\n{facts}",
    )


def _build_with_llm(
    topic: str,
    signals: dict[str, Any],
    *,
    rss: dict[str, Any],
    channel_id: str,
    competitor_block: str = "",
    stats_lines: list[str] | None = None,
    seed_topic: str = "",
) -> ResearchBrief | None:
    facts = enrich_facts(topic, signals, channel_id=channel_id, seed_topic=seed_topic)
    rss_lines = "\n".join(
        f"- {h.get('title', '')} ({h.get('source', '')})" for h in (rss.get("headlines") or [])[:8]
    )
    seo_block = build_seo_prompt_block(channel_id)

    seed_block = ""
    if seed_topic and seed_topic.strip().lower() != topic.strip().lower():
        seed_block = f"SEED TOPIC (do not drift from this subject): {seed_topic.strip()}\n\n"
    anchor_note = ""
    anchors = extract_anchors(seed_topic or topic)
    if any("marvel rivals" in a.lower() for a in anchors):
        anchor_note = "Marvel Rivals is a competitive video game — not MCU movies or comics.\n\n"
    history = channel_history_block(channel_id)

    # Detect if the anchor has been covered many times — if so, steer brief toward
    # analysis/prediction rather than news framing.
    from apis.topic_variants import _ESTABLISHED_THRESHOLD as _EST_THRESH
    from core.channel_context import dominant_anchor, recent_input_topics

    _recent = recent_input_topics(channel_id, limit=20)
    _anchor = dominant_anchor([topic, *_recent])
    _repeat = sum(1 for t in _recent if _anchor and _anchor.lower() in t.lower()) if _anchor else 0
    _established = _repeat >= _EST_THRESH

    freshness_instruction = ""
    if _established:
        freshness_instruction = (
            f"\nFRESHNESS NOTE: This topic ({_anchor or topic}) has been covered "
            f"{_repeat} times recently on this channel. Treat it as an ESTABLISHED "
            "topic — not breaking news. The brief should push toward:\n"
            "- Analysis of what has changed and its long-term impact\n"
            "- Community debate or unresolved controversies\n"
            "- Predictions about upcoming content or balance shifts\n"
            "- Critique of what is broken or needs improvement\n"
            "DO NOT frame this as a news announcement or 'just dropped' story.\n"
            "Recommended format should be 'explainer' or 'short_debate', not 'preview'.\n"
        )

    prompt = f"""Build a structured research brief for a YouTube Short.

{seed_block}{anchor_note}TOPIC: {topic}
{freshness_instruction}
{history or ''}

SIGNAL FACTS (source of truth for names/events):
{facts}

RSS HEADLINES:
{rss_lines or '(none)'}

{competitor_block or '(none)'}

REFERENCE STATS (use for numbers — do not invent):
{chr(10).join('- ' + s for s in (stats_lines or [])) or '(none)'}

{seo_block}

Return JSON only:
{{
  "narrative": "one paragraph angle for the video",
  "audience_sentiment": "how the audience likely feels",
  "controversy_score": 0.0 to 1.0,
  "debate_angles": ["angle1", "angle2"],
  "supporting_evidence": ["fact1", "fact2"],
  "recommended_format": "short_debate|preview|reaction|explainer|analysis|prediction",
  "title_direction": "an SEO-aware angle for the title (a direction, NOT the final title)",
  "suggested_hook": "a punchy opening line under 12 words — a specific fact, number, or contradiction; no 'Today/Let's/In this video'"
}}"""

    try:
        # Research brief is product-grade reasoning → premium tier.
        data = complete_json(
            prompt, tier="premium", temperature=0.45, max_tokens=1500, stage="brief"
        )
        if not isinstance(data, dict):
            return None
        return ResearchBrief(
            version=BRIEF_VERSION,
            topic=topic,
            narrative=str(data.get("narrative", "")),
            audience_sentiment=str(data.get("audience_sentiment", "")),
            controversy_score=float(data.get("controversy_score", 0.5) or 0.5),
            debate_angles=list(data.get("debate_angles") or [])[:6],
            supporting_evidence=list(data.get("supporting_evidence") or [])[:10],
            recommended_format=str(data.get("recommended_format", "short_debate")),
            title_direction=str(data.get("title_direction", "")),
            suggested_hook=str(data.get("suggested_hook", "")),
            rss_headlines=list(rss.get("headlines") or [])[:8],
            community_summary="",
            competitor_pulse=competitor_block,
            stats_lines=list(stats_lines or [])[:8],
        )
    except Exception as exc:
        logger.warning("Research brief LLM failed: %s", exc)
        return None


def build_research_brief(
    topic: str,
    signals: dict[str, Any],
    *,
    channel_id: str | None = None,
    seed_topic: str = "",
) -> ResearchBrief:
    """
    Build or load cached research brief. Never raises — returns fallback on failure.
    """
    channel_id = resolve_channel_id(channel_id)
    cache_key = build_key("research_brief", f"{channel_id}::{topic}")
    cached = get_cached(cache_key)
    if cached and isinstance(cached, dict) and cached.get("narrative"):
        try:
            return ResearchBrief(
                **{k: v for k, v in cached.items() if k in ResearchBrief.__dataclass_fields__}
            )
        except TypeError:
            pass

    from analytics.competitor_context import get_competitor_prompt_block

    rss = fetch_rss_context(topic, channel_id)
    competitor_block = get_competitor_prompt_block(channel_id, topic)
    community_summary = "\n".join(
        f"- {h.get('title', '')} ({h.get('source', '')})" for h in (rss.get("headlines") or [])[:6]
    )

    stats_lines: list[str] = []
    try:
        from apis.stats_context_api import gather_stats_context

        stats_ctx = gather_stats_context(topic)
        stats_lines = list(stats_ctx.get("lines") or [])[:10]
    except Exception as exc:
        logger.debug("Stats context unavailable for %r: %s", topic, exc)
    if not stats_lines:
        sc = signals.get("stats_context") or {}
        if sc.get("active") and isinstance(sc.get("data"), dict):
            stats_lines = list(sc["data"].get("lines") or [])[:10]

    brief = None
    if _USE_LLM:
        brief = _build_with_llm(
            topic,
            signals,
            rss=rss,
            channel_id=channel_id,
            competitor_block=competitor_block,
            stats_lines=stats_lines,
            seed_topic=seed_topic,
        )

    if brief is None:
        brief = _fallback_brief(topic, signals, channel_id, seed_topic=seed_topic)
        brief.rss_headlines = list(rss.get("headlines") or [])[:8]
        brief.community_summary = community_summary
        brief.competitor_pulse = competitor_block
        brief.stats_lines = stats_lines

    set_cache(cache_key, brief.to_dict(), ttl_seconds=_CACHE_TTL)
    return brief
