import re

from apis.draft_policy import determine_draft_status
from apis.entity_extractor import extract_entities
from config.channels import get_channel_profile
from core.angle_intent import (
    ANGLE_COMPARISON,
    ANGLE_DEFAULT,
    ANGLE_EXPLAINER,
    ANGLE_LIST,
    ANGLE_REACTION,
    ANGLE_RETROSPECTIVE,
    ANGLE_TUTORIAL,
    detect_angle_intent,
)
from core.channel_context import channel_history_block, extract_anchors
from core.llm_router import complete
from core.logging import get_logger

logger = get_logger("apis.topic_variants")

# Strip a leading list marker the LLM sometimes prepends ("1. ", "2) ", "- ", "* ")
# so the UI's own numbering doesn't double up ("1. 1. Title").
_LIST_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)]\s*|[-*•]\s+)")

# Run 77: the free cheap-tier model answered "Here are five different angle lines…:",
# pasted two lens labels as "**whats_broken_needs_fixing**", and prefixed one "TAKE:".
# All three were shown as scored angles.
_PREAMBLE_RE = re.compile(r"^(?:here(?:'s| is| are)\b|sure\b|okay\b|certainly\b|below\b)", re.I)
_SNAKE_LABEL_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
_LABEL_HEAD_RE = re.compile(r"^(?:take|angle|hook|lens|focus|frame|option|idea)\s*\d*$", re.I)
_MIN_REAL_ANGLES = 3


def _clean_angle_lines(raw: str, angle_types) -> list[str]:
    """Angle lines out of an LLM reply: no preamble, lens labels, markdown, or label prefix."""
    labels = {str(t).strip().lower() for t in angle_types or ()}

    def _is_label(text: str) -> bool:
        key = text.strip().strip(" .:").lower()
        return bool(_SNAKE_LABEL_RE.match(key)) or key.replace(" ", "_") in labels

    out: list[str] = []
    for line in (raw or "").splitlines():
        text = _LIST_PREFIX_RE.sub("", line).strip()
        text = text.replace("**", "").replace("__", "").strip().strip("`").strip().strip('"')
        text = _LIST_PREFIX_RE.sub("", text).strip()
        if not text or text.endswith(":") or _PREAMBLE_RE.match(text) or _is_label(text):
            continue
        head, sep, rest = text.partition(":")
        if sep and rest.strip() and (_is_label(head) or _LABEL_HEAD_RE.match(head.strip())):
            text = rest.strip()
        if len(text.split()) < 2 or text in out:
            continue
        out.append(text)
    return out


def _heuristic_angles(topic: str, angle_types) -> list[str]:
    """Deterministic angles when the LLM is unavailable (e.g. the free tier is
    rate-limited). Keeps discovery alive instead of crashing the run — the seed
    topic itself leads so scoring still has a real candidate to work with."""
    base = (topic or "").strip()
    if not base:
        return []
    templates = [
        base,
        f"What {base} really means",
        f"The overlooked story in {base}",
        f"{base}: what happens next",
        f"Why {base} matters right now",
    ]
    out: list[str] = []
    for t in templates:
        if t and t not in out:
            out.append(t)
    return out[: max(1, min(5, len(angle_types) or 5))]


_ESTABLISHED_THRESHOLD = 3  # times same anchor covered before switching angles

# Frames for a reaction video. Every one is a genuine lens on "I just watched this
# and here is what I saw" — none asks what is broken or missing.
_REACTION_ANGLES = [
    "first_impressions",
    "the_detail_everyone_missed",
    "what_stood_out_most",
    "does_it_live_up",
    "what_this_means_next",
]

# #533. One table per detected intent. Every pre-existing non-reaction table
# contained `controversy` or `community_controversy`, so a calm idea could only
# come back as a take — see docs/idea_quality_diagnosis.md. None of these frames
# asks what is broken; that is the point.
INTENT_ANGLES = {
    ANGLE_REACTION: _REACTION_ANGLES,
    ANGLE_EXPLAINER: [
        "how_it_actually_works",
        "the_part_people_get_wrong",
        "why_it_is_built_this_way",
        "what_it_means_in_practice",
        "the_detail_that_makes_it_click",
    ],
    ANGLE_LIST: [
        "the_top_of_the_list",
        "the_one_everyone_forgets",
        "the_criteria_that_decide_it",
        "the_close_calls",
        "the_honourable_mention",
    ],
    ANGLE_TUTORIAL: [
        "the_core_method",
        "the_common_mistake",
        "the_setup_that_makes_it_easy",
        "when_it_does_not_work",
        "the_next_step_after_this",
    ],
    ANGLE_COMPARISON: [
        "what_each_does_best",
        "where_they_actually_differ",
        "which_one_for_which_person",
        "the_difference_that_decides_it",
        "what_changed_between_them",
    ],
    ANGLE_RETROSPECTIVE: [
        "what_it_got_right",
        "how_it_holds_up_now",
        "what_it_changed",
        "the_moment_it_peaked",
        "what_came_after",
    ],
}


_LENS_EXAMPLES = {
    ANGLE_DEFAULT: (
        "a factual read, a contrarian counter-take, a forward prediction, a "
        "human/stakes angle, an analytical breakdown"
    ),
    ANGLE_REACTION: (
        "what struck you first, a detail most viewers missed, how it compares to "
        "expectations, what it signals for what comes next, the standout moment"
    ),
    ANGLE_EXPLAINER: (
        "the mechanism itself, the common misconception, the reason it was built "
        "this way, a concrete worked example, what it changes in practice"
    ),
    ANGLE_LIST: (
        "the pick at the top, the omission people will argue with, the criterion "
        "that decided it, the closest call, the one that just missed"
    ),
    ANGLE_TUTORIAL: (
        "the core method, the mistake most people make, the setup that makes it "
        "easy, the case where it fails, what to learn next"
    ),
    ANGLE_COMPARISON: (
        "what each does best, where they genuinely differ, who each one suits, "
        "the single difference that decides it, what changed between them"
    ),
    ANGLE_RETROSPECTIVE: (
        "what it got right, how it holds up now, what it changed, the moment it "
        "peaked, what came after"
    ),
}


def generate_variants(
    topic, autocomplete=None, *, channel_id=None, repeat_count: int = 0, brief: str = ""
):
    """Five editorial angles for ``topic``. ``brief`` is the operator's own thoughts
    (run 77) — they reach the angle prompt and choose the frame when the seed names none."""
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

        return generate_ai_titles(topic, angle_types, channel_id=channel_id, brief=brief)

    profile = get_channel_profile(channel_id) if channel_id else None
    is_established = repeat_count >= _ESTABLISHED_THRESHOLD

    # What the operator asked for beats what the repeat counter assumes. Run 73:
    # three reaction-shaped topics in a row were steered into critique because the
    # topic string never reached this decision. Run 77: the ask lives in the typed
    # thoughts once the search seed is just "GTA 6".
    intent = detect_angle_intent(topic)
    if intent == ANGLE_DEFAULT and brief:
        intent = detect_angle_intent(brief)
    if intent in INTENT_ANGLES:
        return generate_ai_titles(
            topic,
            INTENT_ANGLES[intent],
            channel_id=channel_id,
            is_established=is_established,
            intent=intent,
            brief=brief,
        )

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
        topic, angle_types, channel_id=channel_id, is_established=is_established, brief=brief
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


def generate_ai_angles(
    topic,
    angle_types,
    *,
    channel_id=None,
    is_established: bool = False,
    intent=None,
    brief: str = "",
):
    angle_block = "\n".join(angle_types)

    thoughts_block = ""
    thoughts = (brief or "").strip()
    if thoughts and thoughts.lower() != str(topic or "").strip().lower():
        thoughts_block = (
            "\nOPERATOR'S THOUGHTS (their idea in their own words - every angle must "
            "answer or take a position on these questions and claims, not drift into "
            f"generic coverage of the topic):\n{thoughts[:1500]}\n"
        )

    competitor_block = ""
    if channel_id:
        from analytics.competitor_context import get_competitor_prompt_block

        competitor_block = get_competitor_prompt_block(channel_id, topic)

    anchor_block = _anchor_rules(topic, channel_id)

    freshness_block = ""
    if intent is None:
        intent = detect_angle_intent(topic)
    # "Focus on CRITIQUE" contradicts every frame the operator can actually ask
    # for - a reaction, an explainer, a tutorial and a ranking are all steered
    # wrong by it. Only an unlabelled topic keeps the staleness pivot, which is
    # correct for genuinely repeated coverage ("GTA 6 meta breakdown").
    if is_established and intent == ANGLE_DEFAULT:
        freshness_block = (
            "\nFRESHNESS CONTEXT: This game/franchise has been covered multiple times "
            "on this channel already. DO NOT use 'just released', 'biggest update yet', "
            "or 'what you need to know' framing — that angle is stale.\n"
            "Instead: focus on ANALYSIS, PREDICTION, COMMUNITY debate, or CRITIQUE.\n"
        )

    # Every frame still needs five distinct lenses, but "contrarian counter-take"
    # is not one of them unless the operator actually asked for a take.
    lens_examples = _LENS_EXAMPLES.get(intent, _LENS_EXAMPLES[ANGLE_DEFAULT])

    prompt = f"""
You are generating editorial ANGLES for a short-form video — NOT YouTube titles.

Topic:
{topic}
{thoughts_block}{freshness_block}
{competitor_block}

Angle types (direction only — do NOT paste these labels verbatim):
{angle_block}

{anchor_block}

Rules:
- One short angle line per item (max 12 words).
- DISTINCT LENSES: the {len(angle_types)} angles must each take a genuinely different frame
  — {lens_examples}. Do NOT return variations of one take; if two angles could
  share the same thumbnail, rewrite one.
- Describe the TAKE or focus — NOT a clickbait headline.
- Do not fabricate specifics you cannot verify.
- No numbering, no markdown, no "Primary Storyline:" prefixes.
- Never drop the named subject from the seed topic.
- BANNED headline templates: "just broke the league", "nobody's talking about",
  "reshapes the entire season", "the real winner isn't", "left fans furious", "my hot take".

The publishable YouTube title is generated LATER from verified facts + script.

Return exactly {len(angle_types)} angle lines.
"""

    try:
        raw = complete(prompt, tier="cheap", temperature=0.7, max_tokens=400)
    except Exception as exc:
        # Best-effort: a rate-limited/unavailable LLM must not crash discovery.
        logger.warning("Variant LLM unavailable (%s) — using heuristic angles", exc)
        return _heuristic_angles(topic, angle_types)

    clean = _clean_angle_lines(raw, angle_types)
    if len(clean) < _MIN_REAL_ANGLES:
        # One re-ask, not a loop: run 77 kept 3 of 5 lines as junk, leaving 2 real angles.
        try:
            retry = complete(
                prompt + "\nReturn ONLY the angle lines: no intro sentence, no labels, "
                "no markdown.\n",
                tier="cheap",
                temperature=0.7,
                max_tokens=400,
            )
            for line in _clean_angle_lines(retry, angle_types):
                if line not in clean:
                    clean.append(line)
        except Exception as exc:
            logger.warning("Variant LLM re-ask failed (%s) — keeping %d angle(s)", exc, len(clean))
    return clean[:5] or _heuristic_angles(topic, angle_types)


def generate_ai_titles(
    topic,
    angle_types,
    *,
    channel_id=None,
    is_established: bool = False,
    intent=None,
    brief: str = "",
):
    """Back-compat alias — returns editorial angles, not publishable titles."""
    return generate_ai_angles(
        topic,
        angle_types,
        channel_id=channel_id,
        is_established=is_established,
        intent=intent,
        brief=brief,
    )
