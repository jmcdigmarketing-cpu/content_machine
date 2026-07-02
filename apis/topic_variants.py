import re

from apis.draft_policy import determine_draft_status
from apis.entity_extractor import extract_entities
from config.channels import get_channel_profile
from core.channel_context import channel_history_block, extract_anchors
from core.llm_router import complete

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


# Capitalised words that are NOT a named subject worth preserving in titles.
_SUBJECT_COMMON = {
    "the",
    "a",
    "an",
    "best",
    "top",
    "new",
    "next",
    "state",
    "gaming",
    "update",
    "rankings",
    "ranking",
    "divisional",
    "news",
    "this",
    "that",
    "what",
    "why",
    "how",
    "who",
    "is",
    "are",
    "was",
}


def _subject_terms(topic: str) -> list[str]:
    """Named proper-noun subjects in the seed (e.g. a fighter's name).

    Catches single-word names (`Kape`) that `extract_anchors` (franchise-focused)
    and the multi-word entity detector both miss, so variant generation can't
    generalise the subject away ("Kape punches his ticket" → "one fighter…").
    ALL-CAPS acronyms (UFC, MMA, NBA) are excluded — they're domains, not subjects.
    """
    terms: list[str] = []
    for w in re.findall(r"[A-Z][a-zA-Z]{2,}", topic):
        if w.isupper() or w.lower() in _SUBJECT_COMMON:
            continue
        if w not in terms:
            terms.append(w)
    return terms[:3]


def _anchor_rules(topic: str, channel_id: str | None) -> str:
    anchors = extract_anchors(topic)
    lines: list[str] = []
    if anchors:
        joined = ", ".join(anchors)
        lines.append(
            f"- MANDATORY: Every title must name {joined} exactly as written "
            "(same game/franchise as the seed topic)."
        )
    # Preserve a named subject (person/event) that isn't already an anchor, so the
    # titles stay about who/what the seed is about, not a generic "one fighter".
    subjects = [
        s for s in _subject_terms(topic) if not any(s.lower() in a.lower() for a in anchors)
    ]
    if subjects:
        lines.append(
            f"- Keep the seed's subject in every title: {', '.join(subjects)} "
            "(do not generalise to 'one fighter', 'a team', or 'someone')."
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


def generate_ai_angles(topic, angle_types, *, channel_id=None, is_established: bool = False):
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
            "Instead: focus on ANALYSIS, PREDICTION, COMMUNITY debate, or CRITIQUE.\n"
        )

    prompt = f"""
You are generating editorial ANGLES for a short-form video — NOT YouTube titles.

Topic:
{topic}
{freshness_block}
{competitor_block}

Angle types (direction only — do NOT paste these labels verbatim):
{angle_block}

{anchor_block}

Rules:
- One short angle line per item (max 12 words).
- Describe the TAKE or focus — NOT a clickbait headline.
- Do not fabricate specifics you cannot verify.
- No numbering, no markdown, no "Primary Storyline:" prefixes.
- Never drop the named subject from the seed topic.
- BANNED headline templates: "just broke the league", "nobody's talking about",
  "reshapes the entire season", "the real winner isn't", "left fans furious", "my hot take".

The publishable YouTube title is generated LATER from verified facts + script.

Return exactly {len(angle_types)} angle lines.
"""

    raw = complete(prompt, tier="cheap", temperature=0.7, max_tokens=400)

    lines = (raw or "").strip().split("\n")
    clean = [_LIST_PREFIX_RE.sub("", t).strip().strip('"') for t in lines if t.strip()]
    return [t for t in clean if t][:5]


def generate_ai_titles(topic, angle_types, *, channel_id=None, is_established: bool = False):
    """Back-compat alias — returns editorial angles, not publishable titles."""
    return generate_ai_angles(
        topic, angle_types, channel_id=channel_id, is_established=is_established
    )
