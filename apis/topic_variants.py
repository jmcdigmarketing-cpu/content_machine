import re

from apis.draft_policy import determine_draft_status
from apis.entity_extractor import extract_entities
from config.channels import get_channel_profile
from core.channel_context import channel_history_block, extract_anchors
from core.llm_client import get_model, get_openai_client

client = get_openai_client()

# Strip a leading list marker the LLM sometimes prepends ("1. ", "2) ", "- ", "* ")
# so the UI's own numbering doesn't double up ("1. 1. Title").
_LIST_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)]\s*|[-*•]\s+)")


_ESTABLISHED_THRESHOLD = 3  # times same anchor covered before switching angles


def generate_variants(topic, autocomplete=None, *, channel_id=None, repeat_count: int = 0):
    extract_entities(topic)
    topic_lower = topic.lower()

    # Draft Handling
    if "draft" in topic_lower:
        draft_status, year = determine_draft_status(topic)

        if draft_status == "future_projection":
            print(
                f"\n⚠ The {year} NBA Draft has not occurred yet. "
                "This will be treated as a projection."
            )

        if draft_status == "upcoming":
            angle_types = [
                "first_overall_debate",
                "sleepers",
                "highest_ceiling",
                "lottery_implications",
                "franchise_changer",
            ]

        elif draft_status == "completed":
            angle_types = [
                "early_winners",
                "early_mistakes",
                "steals",
                "team_regrade",
                "long_term_projection",
            ]

        elif draft_status == "historical":
            angle_types = [
                "redraft",
                "legacy_impact",
                "biggest_mistakes",
                "hidden_gems",
                "all_time_ranking",
            ]

        else:
            angle_types = [
                "early_prospects",
                "future_superstar",
                "incoming_college_talent",
                "long_term_class_outlook",
                "lottery_projection",
            ]

        return generate_ai_titles(topic, angle_types, channel_id=channel_id)

    profile = get_channel_profile(channel_id) if channel_id else None
    is_established = repeat_count >= _ESTABLISHED_THRESHOLD

    if profile and profile.domain == "gaming":
        if is_established:
            # Topic has been covered multiple times — pivot to analysis/prediction
            angle_types = [
                "whats_broken_needs_fixing",  # current patch complaints
                "upcoming_content_predictions",  # roadmap / leaks / future heroes
                "meta_evolution_analysis",  # how the game has changed over time
                "community_wishlist",  # what players want next
                "is_it_still_worth_playing",  # retention / health of the game
            ]
        else:
            angle_types = [
                "patch_or_update_hook",
                "meta_or_balance_take",
                "underrated_feature",
                "community_controversy",
                "long_term_outlook",
            ]
    else:
        angle_types = [
            "primary_storyline",
            "underrated_angle",
            "controversy",
            "impact_analysis",
            "long_term_outlook",
        ]

    return generate_ai_titles(
        topic, angle_types, channel_id=channel_id, is_established=is_established
    )


def _anchor_rules(topic: str, channel_id: str | None) -> str:
    anchors = extract_anchors(topic)
    lines: list[str] = []
    if anchors:
        joined = ", ".join(anchors)
        lines.append(
            f"- MANDATORY: Every title must name {joined} exactly as written "
            "(same game/franchise as the seed topic)."
        )
        if any("marvel rivals" in a.lower() for a in anchors):
            lines.append(
                "- Marvel Rivals is a competitive VIDEO GAME — not the MCU, "
                "movies, comics, or Avengers team-ups."
            )
    profile = get_channel_profile(channel_id) if channel_id else None
    if profile and profile.domain == "gaming":
        lines.append(
            "- Titles must be about the game/update named in the seed — "
            "not generic franchise lore."
        )
    history = channel_history_block(channel_id) if channel_id else ""
    if history:
        lines.append(history)
    return "\n".join(lines)


def generate_ai_titles(topic, angle_types, *, channel_id=None, is_established: bool = False):
    angle_block = "\n".join(angle_types)

    competitor_block = ""
    if channel_id:
        from analytics.competitor_context import get_competitor_prompt_block

        competitor_block = get_competitor_prompt_block(channel_id, topic)

    anchor_block = _anchor_rules(topic, channel_id)

    freshness_block = ""
    if is_established:
        freshness_block = (
            "\nFRESHNESS CONTEXT: This game/franchise has been covered multiple times "
            "on this channel already. DO NOT use 'just released', 'biggest update yet', "
            "or 'what you need to know' framing — that angle is stale.\n"
            "Instead: focus on ANALYSIS (what's changed and why it matters), "
            "PREDICTION (what's coming next, leaks, roadmap), "
            "COMMUNITY (what players are debating or demanding), "
            "or CRITIQUE (what's broken, what needs fixing).\n"
            "Titles should feel like hot takes or informed breakdowns, not news summaries.\n"
        )

    prompt = f"""
You are generating YouTube titles.

Topic:
{topic}
{freshness_block}
{competitor_block}

Angles (use as creative direction only — do NOT paste angle names into titles):
{angle_block}

{anchor_block}

Rules:
- One strong title per angle.
- Do not fabricate specific patch notes, hero names, or version numbers you cannot verify.
- Do not repeat topic verbatim.
- Keep titles natural and compelling.
- No numbering, no markdown, no "Primary Storyline:" prefixes.
- Never drop the game/franchise name from the seed topic.

Return exactly {len(angle_types)} titles.
"""

    response = client.chat.completions.create(
        model=get_model(), temperature=0.8, messages=[{"role": "user", "content": prompt}]
    )

    titles = response.choices[0].message.content.strip().split("\n")

    clean = [_LIST_PREFIX_RE.sub("", t).strip().strip('"') for t in titles if t.strip()]
    clean = [t for t in clean if t]

    return clean[:5]
