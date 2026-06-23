import re
from typing import Any

from config.seo import build_seo_prompt_block, default_tags_for_channel
from core.description_extras import apply_description_extras
from core.fact_enrichment import _fact_line_count, enrich_facts
from core.fact_grounding import find_ungrounded_entities
from core.llm_router import complete_json
from core.logging import get_logger
from core.research_brief import ResearchBrief
from core.script_brief import build_script_brief
from core.script_length import (
    count_spoken_words,
    get_length_preset,
    length_system_addendum,
)
from core.seo import normalize_youtube_tags, tags_from_topic
from core.signal_facts import format_signal_facts

logger = get_logger("core.content_engine")

PROMPT_VERSION = "content_engine_v6"
MAX_EXPAND_ATTEMPTS = 2
MAX_EXPAND_ATTEMPTS_EXTENDED = 4  # Extended format needs more passes to hit 1000+ words


def _format_signal_facts(signals):
    """Backward-compatible alias."""
    return format_signal_facts(signals)


# Operator key facts are injected straight into the prompt as ground truth, so
# bound them: cap count + length and strip control chars / line breaks so a
# pasted fact can't smuggle extra prompt structure (instruction injection).
_MAX_KEY_FACTS = 5
_MAX_KEY_FACT_CHARS = 300


def _sanitize_key_facts(key_facts: list[str] | None) -> list[str]:
    if not key_facts:
        return []
    cleaned: list[str] = []
    for raw in key_facts:
        if not isinstance(raw, str):
            continue
        # Collapse any whitespace/newlines to single spaces, drop control chars.
        flat = re.sub(r"\s+", " ", raw).strip()
        flat = "".join(ch for ch in flat if ch.isprintable())
        if not flat:
            continue
        cleaned.append(flat[:_MAX_KEY_FACT_CHARS])
        if len(cleaned) >= _MAX_KEY_FACTS:
            break
    return cleaned


# Lines that are context-only (competitor titles / labels) — not factual evidence
_CONTEXT_ONLY_PREFIXES = (
    "YouTube — real video titles",
    "  •",
    "  →",
    "YouTube video descriptions",
    "YouTube market titles",
)


_YOUTUBE_SECTION_HEADERS = (
    "YouTube — real video titles",
    "YouTube video descriptions",
    "YouTube market titles",
    "YouTube competitor performance",
)

# Bullet prefixes used inside YouTube sections
_YT_BULLET_PREFIXES = ("  •", "  →", "• ", "→ ")


def _split_facts_block(facts: str) -> tuple[str, str]:
    """
    Split the enriched facts string into two blocks:
      verified  — lines that contain actual game/news/stats data
      context   — YouTube competitor titles and description excerpts

    YouTube section headers + their indented bullet lines are context-only.
    Everything else (Blog/RSS, RAWG, News, Stats, etc.) is verified.

    Returns (verified_block, context_block). Either may be empty.
    """
    verified_lines: list[str] = []
    context_lines: list[str] = []
    in_yt_section = False

    for line in facts.splitlines():
        stripped = line.strip()

        # Detect start of a YouTube context section
        if any(stripped.startswith(h) for h in _YOUTUBE_SECTION_HEADERS):
            in_yt_section = True
            context_lines.append(line)
            continue

        # Bullet lines OR indented continuation lines that belong to the section
        if in_yt_section and (
            any(line.startswith(p) for p in _YT_BULLET_PREFIXES)
            or stripped.startswith("•")
            or stripped.startswith("→")
            or line.startswith("  ")
        ):
            context_lines.append(line)
            continue

        # Any other non-empty, non-bullet line ends the YouTube section
        in_yt_section = False
        if stripped:
            verified_lines.append(line)

    return "\n".join(verified_lines).strip(), "\n".join(context_lines).strip()


def _build_prompts(
    *,
    topic: str,
    signals: dict[str, Any],
    min_words: int,
    max_words: int,
    today: str,
    channel_id: str,
    script_brief: str,
    seo_block: str,
    signal_facts: str,
    signal_summary: str,
    brief_block: str,
    length_choice: str,
    seed_topic: str = "",
    is_thin_facts: bool = False,
    creative_brief: str = "",
    key_facts: list[str] | None = None,
) -> tuple[str, str]:
    preset = get_length_preset(length_choice)
    length_note = length_system_addendum(preset)

    retention_rule = ""
    if preset.choice in ("2", "3"):
        retention_rule = (
            "\nRETENTION RULE: At roughly the 30-second mark (~75 words in), "
            "insert a pivot — a counter-fact, unexpected angle, or reframe that "
            "stops scroll-back. Land the pivot with a concrete fact or sharp "
            "reframe, NOT a stock transition phrase."
        )

    system_prompt = f"""
You are a sports and gaming scriptwriter for vertical video (YouTube Shorts and longer vertical formats).

{length_note}

HOOK RULE: The script's FIRST sentence must be a specific fact, number, or contradiction — under 12 words.
Never open with "Today", "Let's", "In this video", "Welcome", or a direct question.
Strong hooks: "He lost $2 billion in one afternoon." / "Nobody saw this roster move coming." / "This changes everything for the division."
{retention_rule}

VOICE — write like a sharp, opinionated human creator talking to camera, NOT an analyst writing a report:
- SAY WHAT HAPPENED FIRST. Lead with the concrete facts in plain words — who did what to whom, how, and when (e.g. "Gaethje TKO'd Topuria in round 2") — BEFORE any commentary. No throat-clearing intro.
- Concrete beats abstract every time. Use names, methods, rounds, numbers from VERIFIED FACTS — not vague abstractions like "systemic issues", "the broader narrative", "the delicate balance".
- BANNED — never write these or anything like them: "grappling with the fallout", "at a crossroads", "as the dust settles", "the delicate balance between", "double-edged sword", "systemic issues", "the future of X depends on it", "it's essential to understand", "underscores a critical need", "a testament to", "the lifeblood of", "ripe with opportunities", "In conclusion", "the very foundations of", "now more than ever".
- NO both-sidesing. Do NOT write "some argue X, while others believe Y". State what YOU think and why.
- The topic is the assignment: if it says "recap / results", RECAP WHAT HAPPENED — do not drift into think-piece territory about officiating reform, "the meta", or the sport's future unless the facts are about that.
- Delete any sentence that could appear in a generic essay on this subject. Every sentence must carry a specific fact or a real opinion.

OPERATOR KEY FACTS RULE: If OPERATOR KEY FACTS are present in the user message, treat them as
verified ground truth. They override any conflicting detail from training memory or signals.
Always include them in the script — do not contradict, soften, or omit them.

ANTI-HALLUCINATION RULES (strictly enforced):
- You do NOT know which patch, season, or hero was released unless it appears verbatim in VERIFIED FACTS below.
- Do NOT infer season numbers (e.g. "Season 8.5", "Season 7") from video titles in your training data.
- Do NOT introduce hero names (e.g. Cyclops, White Fox, Hawkeye) that are not named in VERIFIED FACTS.
- Do NOT invent patch version numbers, balance changes, mode names, or release dates.
- SPORTS/MMA: Do NOT state who is champion, a fighter's record, ranking, or who they have fought/beaten from memory — titles and records change and your training data is stale. Use only statuses that appear in VERIFIED FACTS.
- Do NOT invent fight results, opponents, event cards, dates, or quotes. If the outcome of a fight or event is NOT in VERIFIED FACTS, frame it as the question or hypothetical it is ("if Topuria loses…", "fans are asking whether…") — never assert it happened.
- Competitor video titles in CONTEXT SIGNALS are NOT factual evidence — they show what's trending, not what's true.
- If the facts are silent on specifics: write at the community/opinion level ("players are frustrated that…", "the debate right now is…") without inventing the specific thing they're debating.
- A script grounded in genuine community takes beats a fabricated "news update" every time.

You must:
- Use ONLY game-specific facts (patches, heroes, seasons, results, dates, stats) that appear in VERIFIED FACTS or RESEARCH BRIEF.
- Cross-genre framing is allowed: real people, athletes, other sports, or other games introduced in the EDITORIAL ANGLE may be used as analogy, comparison, or opinion even if they are absent from VERIFIED FACTS — that is intentional creator framing, not a fabrication. Only invented GAME specifics are forbidden.
- If a game fact is missing, say "reports suggest" or skip — do not fill from memory.
- If VERIFIED FACTS lack patch/hero specifics, write an analysis/opinion angle about the game's meta or community sentiment — do not invent specifics to fill space.
- Never use stock filler transitions. Banned verbatim: "But here's the thing", "This isn't just X — it's Y", "But wait, there's more", "Here's the kicker", "Let that sink in". Pivot with a concrete fact instead.
- Write for spoken delivery; no markdown, bullet points, or headers in the script body.
- Build to a strong closing line — a hot take, implication, or open question that drives comments.
- Title and description must be SEO-friendly without misleading clickbait.
- Target {min_words}-{max_words} words (~{preset.target_words}) — but hit it with SUBSTANCE, never filler. If you run out of real facts and real takes before the minimum, STOP. A tight shorter script beats a padded one.
"""

    seed_block = ""
    if seed_topic and seed_topic.strip().lower() != topic.strip().lower():
        seed_block = (
            f"SEED TOPIC (user/channel intent — stay on this subject):\n{seed_topic.strip()}\n\n"
        )

    angle_block = ""
    if creative_brief and creative_brief.strip():
        angle_block = (
            "EDITORIAL ANGLE (the creator's deliberate take — build the entire script "
            "around THIS thesis and point of view, not a generic overview). Names, "
            "people, athletes, sports, or other genres referenced here (e.g. a fighter "
            "used as an analogy for game mechanics) are INTENTIONAL cross-genre framing — "
            "keep them and lean into the comparison; they are allowed even if not in "
            "VERIFIED FACTS. Only GAME-SPECIFIC claims (patches, heroes, seasons, dates, "
            f"numbers) must still come from VERIFIED FACTS:\n{creative_brief.strip()}\n\n"
        )

    # Split facts into verified data vs YouTube context-only titles
    verified_facts, context_signals = _split_facts_block(signal_facts)

    verified_block = verified_facts if verified_facts else "(no verified game data available)"
    context_block = (
        f"\nCONTEXT SIGNALS — competitor video titles only (shows what's trending; "
        f"NOT facts about specific events, patches, or heroes):\n{context_signals}"
        if context_signals
        else ""
    )

    operator_facts_block = ""
    clean_facts = _sanitize_key_facts(key_facts)
    if clean_facts:
        facts_lines = "\n".join(f"- {f}" for f in clean_facts)
        operator_facts_block = (
            "OPERATOR KEY FACTS (ground truth — highest priority; always include, never contradict):\n"
            f"{facts_lines}\n\n"
        )

    thin_facts_warning = ""
    if is_thin_facts:
        thin_facts_warning = (
            "\n⚠ THIN FACTS MODE: VERIFIED FACTS above contain no patch/hero specifics. "
            "DO NOT invent season numbers, hero names, patch notes, or balance changes. "
            "Write the script as a community take / analysis angle: what players are generally "
            "saying, what the meta debates look like, what questions fans have. "
            "Use 'players feel that…', 'the community is asking…', 'the debate around X is…' — "
            "not fabricated specifics. This honest framing builds trust and drives comments."
        )

    user_prompt = f"""
TODAY: {today}

{seed_block}{angle_block}TOPIC:
{topic}

{brief_block}SCRIPT BRIEF (follow exactly):
{script_brief}

{seo_block}

ACTIVE SIGNALS (scores):
{signal_summary}

{operator_facts_block}VERIFIED FACTS (source of truth — only use specifics from here):
{verified_block}
{context_block}
{thin_facts_warning}

INSTRUCTIONS:
- Script length: REQUIRED {min_words}-{max_words} words (~{preset.duration_hint()} when spoken).
- Open with a punchy hook sentence under 12 words (no "Today/Let's/In this video").
- If Long format: structure as hook → context → analysis → implications → closing take.
- If RESEARCH BRIEF says format is "analysis" or "prediction": DO NOT frame as a news announcement. Write as an informed breakdown, hot take, or prediction — not "just released" or "biggest update yet" language.
- TAKE A SIDE. Commit to one clear stance or prediction — do not both-sides it ("maybe a comeback, maybe a decline"). Pick the more interesting read and argue it.
- Cut hedging and filler ("only time will tell", "the narrative is far from over", "could be a turning point"). Every sentence advances the take.
- Close on a SPECIFIC line — a concrete prediction, a named stakes question, or a sharp opinion. NEVER the generic "what do you think? drop your thoughts in the comments".
- Generate a compelling YouTube title (SEO-aware, accurate, no ellipsis).
- Generate a concise SEO description (hook first line, call-to-action last line).
- Generate 8-15 YouTube tags (no fabricated names).

Return JSON only:
{{
  "title": "...",
  "script": "...",
  "description": "...",
  "tags": ["tag1", "tag2"]
}}
"""
    return system_prompt.strip(), user_prompt.strip()


def _call_content_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.65,
    tier: str = "premium",
) -> dict[str, Any] | None:
    # Final script/title/description is the product → premium tier by default.
    return complete_json(
        user_prompt,
        system=system_prompt,
        tier=tier,
        temperature=temperature,
        max_tokens=3000,
    )


def _maybe_improve_hook(script: str) -> str:
    """
    Opt-in (HOOK_REGEN_ENABLED=true): rewrite a weak opening line into a stronger
    hook. Only swaps in the rewrite if it actually scores higher; otherwise the
    original script is returned untouched.
    """
    from core.hook_score import hook_regen_enabled, score_script_hook

    if not hook_regen_enabled():
        return script
    current = score_script_hook(script)
    if current.passed or not current.hook:
        return script

    system_prompt = (
        "You rewrite ONLY the first sentence of a short-form video script into a "
        "stronger hook: a specific fact, number, or contradiction, under 12 words. "
        "Never open with 'Today', 'Let's', 'In this video', 'Welcome', or a question. "
        "Do not invent facts not already implied by the script. Keep the rest of the "
        "script identical."
    )
    user_prompt = (
        f"SCRIPT:\n{script}\n\nReturn JSON only with the full script, first sentence "
        'replaced:\n{"script": "..."}'
    )
    try:
        # Rewriting one sentence is throwaway work → cheap tier.
        payload = _call_content_llm(system_prompt, user_prompt, temperature=0.7, tier="cheap")
    except Exception as exc:
        logger.debug("hook regen failed: %s", exc)
        return script
    if isinstance(payload, dict) and payload.get("script"):
        candidate = str(payload["script"])
        if score_script_hook(candidate).score > current.score:
            logger.info("Improved hook via regeneration")
            return candidate
    return script


def _expand_script(
    *,
    script: str,
    topic: str,
    min_words: int,
    max_words: int,
    length_choice: str,
) -> str:
    current = count_spoken_words(script)
    preset = get_length_preset(length_choice)
    prompt = f"""Expand this video script for TOPIC: {topic}

Current script ({current} words) is short of the {min_words}-word target (max {max_words}).
Format: {preset.label} video ({preset.duration_hint()}).
{length_system_addendum(preset)}

Add LENGTH WITH SUBSTANCE ONLY: more specific facts about what happened, concrete detail, and
sharper opinion/analysis. Keep all facts from the original.
BANNED filler — do NOT add any of this to pad the count: "fans are divided", "the lifeblood of
the sport", "the future of X depends on it", "in conclusion", "a testament to", restating points
already made, or vague abstractions. If you cannot reach {min_words} words HONESTLY with real
substance, return the script unchanged rather than padding.
Do not repeat the opening verbatim. Return JSON only: {{"script": "..."}}

ORIGINAL:
{script}
"""
    try:
        # Expansion adds substance to the final script → premium tier.
        data = complete_json(prompt, tier="premium", temperature=0.5, max_tokens=3000)
        if isinstance(data, dict) and data.get("script"):
            expanded = str(data["script"]).strip()
            if count_spoken_words(expanded) > current:
                return expanded
    except Exception as exc:
        logger.warning("Script expand failed: %s", exc)
    return script


def generate_content_package(
    topic,
    signals,
    word_range,
    today,
    *,
    channel_id=None,
    research_brief: ResearchBrief | None = None,
    length_choice: str = "2",
    seed_topic: str = "",
    creative_brief: str = "",
    key_facts: list[str] | None = None,
):
    min_words, max_words = word_range
    channel_id = channel_id or "default"
    script_brief = build_script_brief(topic, channel_id, seed_topic=seed_topic or topic)
    seo_block = build_seo_prompt_block(channel_id)
    signal_facts = enrich_facts(
        topic,
        signals,
        channel_id=channel_id,
        seed_topic=seed_topic or topic,
    )

    # Detect thin-facts mode — warn the LLM when verified (non-YouTube) data is sparse.
    # _fact_line_count counts only lines with "-" or ":" (not YouTube bullet "•" lines),
    # so YouTube titles alone cannot mask a thin-facts situation.
    _verified_facts, _ = _split_facts_block(signal_facts)
    _is_thin_facts = (
        not signal_facts.strip()
        or signal_facts.startswith("No structured facts")
        or signal_facts.startswith("⚠ THIN FACTS")
        or _fact_line_count(_verified_facts) < 3
    )

    brief_block = ""
    if research_brief:
        brief_block = research_brief.to_prompt_block() + "\n\n"

    signal_summary = ""
    for name, signal in signals.items():
        if signal.get("connected") and signal.get("active"):
            signal_summary += f"{name}: score {signal.get('score', 0)}\n"

    system_prompt, user_prompt = _build_prompts(
        topic=topic,
        signals=signals,
        min_words=min_words,
        max_words=max_words,
        today=today,
        channel_id=channel_id,
        script_brief=script_brief,
        seo_block=seo_block,
        signal_facts=signal_facts,
        signal_summary=signal_summary,
        brief_block=brief_block,
        length_choice=length_choice,
        seed_topic=seed_topic,
        is_thin_facts=_is_thin_facts,
        creative_brief=creative_brief,
        key_facts=key_facts,
    )

    # Short: tighter temperature for punchy focus; Extended: slightly more creative latitude
    temperature = 0.55 if length_choice == "1" else (0.72 if length_choice == "4" else 0.68)
    payload = _call_content_llm(system_prompt, user_prompt, temperature=temperature)

    if not (isinstance(payload, dict) and payload.get("script")):
        logger.warning("LLM returned non-JSON content package; using raw fallback")
        return {
            "title": topic,
            "script": payload if isinstance(payload, str) else "",
            "description": apply_description_extras("", channel_id),
            "tags": normalize_youtube_tags(
                default_tags_for_channel(channel_id, topic) + tags_from_topic(topic)
            ),
            "prompt_version": PROMPT_VERSION,
            "brief_version": research_brief.version if research_brief else "",
            "word_count": 0,
        }

    script = str(payload["script"])
    attempts = 0
    max_attempts = MAX_EXPAND_ATTEMPTS_EXTENDED if length_choice == "4" else MAX_EXPAND_ATTEMPTS
    while count_spoken_words(script) < min_words and attempts < max_attempts:
        logger.info(
            "Script short (%s words, need %s+); expanding (attempt %s)",
            count_spoken_words(script),
            min_words,
            attempts + 1,
        )
        script = _expand_script(
            script=script,
            topic=topic,
            min_words=min_words,
            max_words=max_words,
            length_choice=length_choice,
        )
        attempts += 1

    script = _maybe_improve_hook(script)

    llm_tags = payload.get("tags") or []
    if isinstance(llm_tags, str):
        llm_tags = [t.strip() for t in llm_tags.split(",") if t.strip()]
    tags = normalize_youtube_tags(
        llm_tags,
        extra=default_tags_for_channel(channel_id, topic) + tags_from_topic(topic),
    )

    # Post-generation grounding check: flag specifics in the script not backed by
    # the facts the model was given (catches invented heroes/products/patches).
    grounding_text = "\n".join(
        [signal_facts, brief_block, topic, seed_topic or "", *(_sanitize_key_facts(key_facts))]
    )
    ungrounded = find_ungrounded_entities(script, grounding_text)
    if ungrounded:
        logger.warning(
            "Script names %s specific(s) not in the facts: %s",
            len(ungrounded),
            ", ".join(ungrounded),
        )

    return {
        "title": payload.get("title") or topic,
        "script": script,
        "description": apply_description_extras(payload.get("description") or "", channel_id),
        "tags": tags,
        "prompt_version": PROMPT_VERSION,
        "brief_version": research_brief.version if research_brief else "",
        "word_count": count_spoken_words(script),
        "ungrounded_entities": ungrounded,
    }
