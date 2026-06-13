"""
Recommended angle labels for topic opportunity scoring (no pipeline coupling).

Default: static angle-type labels aligned with apis/topic_variants.py.
Optional LLM titles when OPPORTUNITY_ANGLES_LLM is enabled.
"""

from __future__ import annotations

import os

from apis.draft_policy import determine_draft_status
from config.channels import resolve_channel_id


def _draft_angle_types(topic: str) -> list[str]:
    topic_lower = topic.lower()
    if "draft" not in topic_lower:
        return []

    draft_status, _year = determine_draft_status(topic)

    if draft_status == "upcoming":
        return [
            "first_overall_debate",
            "sleepers",
            "highest_ceiling",
            "lottery_implications",
            "franchise_changer",
        ]
    if draft_status == "completed":
        return [
            "early_winners",
            "early_mistakes",
            "steals",
            "team_regrade",
            "long_term_projection",
        ]
    if draft_status == "historical":
        return [
            "redraft",
            "legacy_impact",
            "biggest_mistakes",
            "hidden_gems",
            "all_time_ranking",
        ]
    return [
        "early_prospects",
        "future_superstar",
        "incoming_college_talent",
        "long_term_class_outlook",
        "lottery_projection",
    ]


def angle_type_labels(topic: str) -> list[str]:
    """Human-readable angle seeds (underscore labels → spaced phrases)."""
    draft = _draft_angle_types(topic)
    if draft:
        types = draft
    else:
        types = [
            "primary_storyline",
            "underrated_angle",
            "controversy",
            "impact_analysis",
            "long_term_outlook",
        ]
    return [t.replace("_", " ") for t in types]


def recommended_angles(
    topic: str,
    *,
    domain: str,
    channel_id: str | None = None,
) -> list[str]:
    """
    Return suggested content angles for a topic.

    Uses LLM-generated titles only when OPPORTUNITY_ANGLES_LLM is enabled;
    otherwise returns static angle-type labels (no API cost).
    """
    channel_id = resolve_channel_id(channel_id)
    use_llm = os.getenv("OPPORTUNITY_ANGLES_LLM", "").lower() in ("1", "true", "yes")

    if use_llm:
        from apis.topic_variants import generate_ai_titles

        draft = _draft_angle_types(topic)
        if draft:
            angle_types = draft
        else:
            angle_types = [
                "primary_storyline",
                "underrated_angle",
                "controversy",
                "impact_analysis",
                "long_term_outlook",
            ]
        return generate_ai_titles(topic, angle_types, channel_id=channel_id)

    _ = domain  # reserved for domain-specific angle packs later
    return angle_type_labels(topic)
