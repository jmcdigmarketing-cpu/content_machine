import os
from typing import Any

from config.seo import build_seo_prompt_block, default_tags_for_channel
from core.description_extras import apply_description_extras
from core.fact_enrichment import _fact_line_count, enrich_facts
from core.fact_grounding import find_ungrounded_entities
from core.grounding_tiers import YOUTUBE_SECTION_HEADERS, build_tiered_corpus
from core.llm_router import complete_json
from core.logging import get_logger
from core.operator_facts import (
    facts_for_prompt as key_facts_for_prompt,
)
from core.research_brief import ResearchBrief
from core.script_brief import build_script_brief
from core.script_length import (
    count_spoken_words,
    get_length_preset,
    length_system_addendum,
    trim_overlength,
)
from core.seo import normalize_youtube_tags, tags_from_topic
from core.signal_facts import format_signal_facts

logger = get_logger("core.content_engine")

PROMPT_VERSION = "content_engine_v7"
MAX_EXPAND_ATTEMPTS = 2
MAX_EXPAND_ATTEMPTS_EXTENDED = 4  # Extended format needs more passes to hit 1000+ words


def _format_signal_facts(signals):
    """Backward-compatible alias."""
    return format_signal_facts(signals)


# Operator key facts — see core.operator_facts for parse/store/prompt packing.
_MAX_KEY_FACT_CHARS = 400


def _sanitize_key_facts(key_facts: list[str] | None) -> list[str]:
    return key_facts_for_prompt(key_facts)


# Lines that are context-only (competitor titles / labels) — not factual evidence
_CONTEXT_ONLY_PREFIXES = (
    "YouTube — real video titles",
    "  •",
    "  →",
    "YouTube video descriptions",
    "YouTube market titles",
)


# Shared with the tier layer (core/grounding_tiers.py) so both split YouTube
# context sections the same way.
_YOUTUBE_SECTION_HEADERS = YOUTUBE_SECTION_HEADERS

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
    extra_directive: str = "",
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
        # Replace the static 30s heuristic with the channel's measured drop-off
        # point once enough retention curves exist (data-driven pacing).
        try:
            from core.retention import pacing_hint

            measured = pacing_hint(channel_id)
            if measured:
                retention_rule += f"\n{measured}"
        except Exception as exc:
            logger.debug("pacing_hint skipped: %s", exc)

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

FRAMING — facts are EVIDENCE, not the point:
- Do NOT recite facts. Never write 3+ bare-fact sentences in a row (e.g. "It drops Nov 19. Pre-orders opened June 25. Standard is $79.99. Ultimate is $99.99."). Each fact must earn its place by advancing YOUR take — introduce it to make a point, land a consequence, or set up the argument, then move forward.
- The EDITORIAL ANGLE is the spine; facts are ammunition for it. Shape the script as hook/thesis → argue the take, pulling in facts as evidence → payoff. A viewer should walk away remembering the ARGUMENT, not a list of stats.
- Anything NOT in VERIFIED FACTS or OPERATOR KEY FACTS — rumors, leaks, projections, anything from the research brief or the wider internet — must be EXPLICITLY attributed ("reports claim…", "the rumor is…", "unconfirmed, but…") and NEVER stated as fact. Speculation dressed as fact is what gets flagged and kills trust.

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
- Include at least one explicit STANCE beat — a prediction or "why this matters" call the audience can agree or argue with (e.g. "expect…", "here's why…", "the real reason…", "my prediction…", "the bigger picture…") — grounded ONLY in the verified facts, never an invented specific.
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

    from core.channel_persona import human_context_block

    human_block = human_context_block(channel_id)
    human_block = f"{human_block}\n\n" if human_block else ""

    # Pillar 4: optional playbook/style guidance from the vault (strategy notes +
    # machine beliefs). Bounded, clearly non-factual, "" when the vault is unset.
    try:
        from core.obsidian_facts import playbook_block

        _playbook = playbook_block(channel_id)
    except Exception:
        _playbook = ""
    playbook = f"{_playbook}\n\n" if _playbook else ""

    # Pillar 7 (SkillOpt): a trial style directive under test by the skill-optimizer, or a
    # gate-proven directive applied to a run. Bounded + clearly non-factual, like the
    # playbook block; "" in normal generation.
    trial = (
        f"STYLE DIRECTIVE (apply throughout):\n{extra_directive.strip()}\n\n"
        if extra_directive.strip()
        else ""
    )

    user_prompt = f"""
TODAY: {today}

{seed_block}{angle_block}TOPIC:
{topic}

{human_block}{playbook}{trial}{brief_block}SCRIPT BRIEF (follow exactly):
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
- Do NOT write the YouTube title — title is generated in a separate pass after facts + script.
- Generate a concise SEO description (hook first line, call-to-action last line).
- Generate 8-15 YouTube tags (no fabricated names).

Return JSON only:
{{
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
        stage="script",
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


def _reground_enabled() -> bool:
    return os.getenv("GROUNDING_REGEN_ENABLED", "true").lower() not in ("0", "false", "no")


def _maybe_reground_script(
    script: str, grounding_text: str, topic: str, ungrounded: list[str]
) -> tuple[str, list[str]]:
    """Regenerate a script to strip specifics not backed by the facts, then re-check.

    Default-on (``GROUNDING_REGEN_ENABLED``). Triggered only when the post-gen
    grounding check already flagged ≥ ``GROUNDING_REGEN_MIN`` specifics — so most
    runs pay nothing. The rewrite is told to remove/generalize the flagged
    names/trades/numbers while keeping everything the facts DO support; it's only
    accepted if it actually reduces the unsupported count and doesn't gut the
    script (≥60% of the original word count). Returns (script, remaining_ungrounded)
    — "regenerate then warn": the caller still surfaces whatever remains.
    """
    if not _reground_enabled() or not ungrounded:
        return script, ungrounded
    try:
        min_flags = int(os.getenv("GROUNDING_REGEN_MIN", "1"))
    except ValueError:
        min_flags = 1
    if len(ungrounded) < min_flags:
        return script, ungrounded

    system_prompt = (
        "You rewrite a short-form video script to remove UNVERIFIED claims. You are "
        "given VERIFIED FACTS and a list of FLAGGED specifics that are NOT supported "
        "by those facts. Rewrite so the script asserts ONLY what the facts support: "
        "remove or generalize every flagged name, team, trade, signing, roster move, "
        "score, or version that is not in the facts. Do NOT introduce any new specific, "
        "and do NOT present a rumor or prediction as a fact. Keep the opening hook, the "
        "length, the tone, and all SUPPORTED content. Return JSON only: "
        '{"script": "..."}'
    )
    user_prompt = (
        f"TOPIC: {topic}\n\nVERIFIED FACTS:\n{grounding_text}\n\n"
        "FLAGGED (unsupported — remove or generalize):\n- " + "\n- ".join(ungrounded) + "\n\n"
        f"SCRIPT:\n{script}"
    )
    try:
        payload = _call_content_llm(system_prompt, user_prompt, temperature=0.3, tier="premium")
    except Exception as exc:
        logger.debug("grounding regen failed: %s", exc)
        return script, ungrounded
    if not isinstance(payload, dict) or not payload.get("script"):
        return script, ungrounded

    candidate = str(payload["script"]).strip()
    candidate_ungrounded = find_ungrounded_entities(candidate, grounding_text)
    keeps_length = count_spoken_words(candidate) >= 0.6 * max(count_spoken_words(script), 1)
    if len(candidate_ungrounded) < len(ungrounded) and keeps_length:
        logger.info(
            "Regrounded script: %d → %d unsupported specific(s)",
            len(ungrounded),
            len(candidate_ungrounded),
        )
        return candidate, candidate_ungrounded
    return script, ungrounded


def _claim_regen_enabled() -> bool:
    return os.getenv("CLAIM_REGEN_ENABLED", "true").lower() not in ("0", "false", "no")


def _maybe_rewrite_unsupported_claims(script, verification, corpus_text, topic, priority_facts):
    """Act on the claim verifier's verdict: rewrite unsupported claims out (or attribute them).

    Token grounding can pass while the *claims* are invented (e.g. real names, fabricated
    patch contents) — the verifier catches those but previously nothing acted on it. One
    premium-tier rewrite removes each unsupported claim or restates it as explicitly
    attributed speculation ("reports claim…"), then re-verifies; the rewrite is adopted
    only if the unsupported count actually drops and the script isn't gutted (≥60% of the
    original length). Default-on (``CLAIM_REGEN_ENABLED``); fail-open everywhere.

    Returns (script, verification) — possibly the originals.
    """
    if not _claim_regen_enabled() or not verification or not verification.unsupported:
        return script, verification

    claims_block = "\n".join(f"- {c.claim}" for c in verification.unsupported[:8])
    system_prompt = (
        "You are revising a short-form video script. You are given VERIFIED FACTS "
        "(the only source of truth) and a list of UNSUPPORTED CLAIMS the script "
        "asserts that are NOT backed by those facts. Rewrite the script so that each "
        "unsupported claim is either REMOVED or restated as clearly attributed "
        "speculation ('reports claim…', 'the rumor is…', 'unconfirmed, but…'). Do NOT "
        "add any new facts, names, numbers, or events. Keep the hook, voice, stance, "
        'and roughly the same length. Return JSON only: {"script": "..."}'
    )
    user_prompt = (
        f"TOPIC: {topic}\n\nVERIFIED FACTS:\n{corpus_text}\n\n"
        f"UNSUPPORTED CLAIMS (remove or attribute each):\n{claims_block}\n\nSCRIPT:\n{script}"
    )
    try:
        payload = _call_content_llm(system_prompt, user_prompt, temperature=0.3, tier="premium")
    except Exception as exc:
        logger.info("Claim rewrite failed (%s) — keeping original script", exc)
        return script, verification
    candidate = (payload.get("script") or "").strip() if isinstance(payload, dict) else ""
    if not candidate or len(candidate.split()) < int(len(script.split()) * 0.6):
        return script, verification

    from core.claim_verifier import verify_claims

    re_check = verify_claims(candidate, corpus_text, topic=topic, priority_facts=priority_facts)
    if re_check is not None and len(re_check.unsupported) < len(verification.unsupported):
        logger.info(
            "Claim rewrite adopted: unsupported %d -> %d",
            len(verification.unsupported),
            len(re_check.unsupported),
        )
        # Candidate 322: keep the pre-rewrite verdict on the record. The claims were
        # restated as attributed speculation, not evidenced, and the persisted numbers
        # would otherwise show a run that was right first time.
        re_check.rewritten = True
        re_check.pre_rewrite_unsupported = len(verification.unsupported)
        re_check.pre_rewrite_total = verification.total
        return candidate, re_check
    return script, verification


def _insight_injection_enabled() -> bool:
    return os.getenv("INSIGHT_INJECTION_ENABLED", "true").lower() not in ("0", "false", "no")


def _maybe_inject_insight(script: str, grounding_text: str, topic: str) -> str:
    """Add one opinion/prediction/'why it matters' beat when a script reads as a recap.

    Default-on (``INSIGHT_INJECTION_ENABLED``). No-op when the script already
    carries a take (same detector the authenticity gate scores on), so most runs
    pay nothing. The beat must be grounded ONLY in the verified facts — no invented
    specifics — and runs BEFORE the grounding regen so anything it slips in still
    gets cleaned. Accepted only if it now reads as having a take and didn't shrink
    the script (an injection should add words, not drop them).
    """
    if not _insight_injection_enabled():
        return script
    from core.authenticity import has_insight

    if has_insight(script):
        return script

    system_prompt = (
        "You add exactly ONE original-insight beat to a short-form video script: a "
        "clear opinion, prediction, or 'why this matters' take of 1-2 sentences, in "
        "the creator's voice, that the audience can agree or argue with. Base it ONLY "
        "on the VERIFIED FACTS — do NOT invent any new name, team, trade, number, or "
        "result, and do NOT present a rumor or prediction as a fact. Keep everything "
        "else intact and keep the length and flow; place the beat where it lands best "
        '(often just before the closing line). Return JSON only: {"script": "..."}'
    )
    user_prompt = f"TOPIC: {topic}\n\nVERIFIED FACTS:\n{grounding_text}\n\nSCRIPT:\n{script}"
    try:
        payload = _call_content_llm(system_prompt, user_prompt, temperature=0.6, tier="premium")
    except Exception as exc:
        logger.debug("insight injection failed: %s", exc)
        return script
    if not isinstance(payload, dict) or not payload.get("script"):
        return script

    candidate = str(payload["script"]).strip()
    keeps_length = count_spoken_words(candidate) >= 0.9 * max(count_spoken_words(script), 1)
    if has_insight(candidate) and keeps_length:
        logger.info("Injected original-insight beat")
        return candidate
    return script


def _key_fact_anchor_enabled() -> bool:
    return os.getenv("KEY_FACT_ANCHOR_ENABLED", "true").lower() not in ("0", "false", "no")


def _video_game_drift(script: str, key_facts: list[str], topic: str) -> bool:
    """True when key facts are real sports but the script pivoted to video games."""
    from apis.topic_scorer import infer_domain
    from core.channel_context import extract_anchors

    clean = _sanitize_key_facts(key_facts)
    if len(clean) < 2:
        return False
    facts_domain = infer_domain(topic or "", key_facts=clean, channel_id=None)
    if facts_domain not in ("nba", "nfl", "ufc"):
        return False
    blob = "\n".join(clean).lower()
    sl = (script or "").lower()
    for anchor in extract_anchors(script):
        if anchor.lower() not in blob:
            return True
    drift_phrases = (
        "marvel rivals",
        "dive comp",
        "balance patch",
        "esports leaderboard",
        "patch-proof",
    )
    return any(p in sl for p in drift_phrases)


def _maybe_recenter_on_key_facts(
    script: str, key_facts: list[str] | None, topic: str, grounding_text: str
) -> str:
    """Re-center a drifted script on the operator's key-fact subject.

    The operator's pasted facts are highest-priority ground truth (ADR §4) that the
    script must be ABOUT. A live run picked a "Kape" topic, pasted Kape facts, then
    produced a script about a different fighter entirely — the key facts were
    silently abandoned. This detects that drift: if the script mentions *none* of
    the proper-noun subjects named in the key facts, regenerate once to center it on
    them. Accepted only if the rewrite now covers a key-fact subject without gutting
    the script. Default-on (``KEY_FACT_ANCHOR_ENABLED``); no-op when there are no
    key facts or the script already references one (most runs pay nothing).
    """
    if not _key_fact_anchor_enabled() or not key_facts:
        return script
    from core.fact_grounding import mentions, specific_entities

    facts_text = "\n".join(_sanitize_key_facts(key_facts))
    subjects = specific_entities(facts_text)
    cross_domain = _video_game_drift(script, key_facts, topic)
    if not subjects and not cross_domain:
        return script  # no named subject to anchor on (e.g. purely numeric facts)
    if any(mentions(script, e) for e in subjects) and not cross_domain:
        return script  # already on-topic

    if cross_domain:
        logger.warning(
            "Script drifted to video games/esports while key facts are real sports — recentering"
        )
    else:
        logger.warning(
            "Script ignores operator key-fact subject(s): %s — recentering",
            ", ".join(subjects[:5]),
        )
    system_prompt = (
        "You rewrite a short-form video script so it is ABOUT the OPERATOR KEY FACTS. "
        "The current script drifted onto a different subject. Rewrite it to center on "
        "the people/events named in the KEY FACTS, using ONLY the verified facts given. "
        "Do not introduce a different main subject, do not invent specifics, and do not "
        "present a rumor as a fact. Keep the hook style, length, and tone."
    )
    if cross_domain:
        system_prompt += (
            " CRITICAL: The key facts are REAL SPORTS (NBA/NFL/UFC) — remove ALL "
            "video-game, esports, Marvel Rivals, patch/meta, and leaderboard content."
        )
    system_prompt += ' Return JSON only: {"script": "..."}'
    user_prompt = (
        f"TOPIC: {topic}\n\nOPERATOR KEY FACTS (the script MUST be about these):\n"
        + "\n".join(f"- {f}" for f in _sanitize_key_facts(key_facts))
        + f"\n\nVERIFIED FACTS:\n{grounding_text}\n\n"
        f"SCRIPT (drifted — rewrite to center on the key facts):\n{script}"
    )
    try:
        payload = _call_content_llm(system_prompt, user_prompt, temperature=0.4, tier="premium")
    except Exception as exc:
        logger.debug("key-fact recenter failed: %s", exc)
        return script
    if not isinstance(payload, dict) or not payload.get("script"):
        return script

    candidate = str(payload["script"]).strip()
    keeps_length = count_spoken_words(candidate) >= 0.6 * max(count_spoken_words(script), 1)
    if not keeps_length:
        return script
    if cross_domain:
        if _video_game_drift(candidate, key_facts, topic):
            return script
        logger.info("Recentered script away from video-game drift")
        return candidate
    if any(mentions(candidate, e) for e in subjects):
        logger.info("Recentered script on operator key facts")
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
        data = complete_json(
            prompt, tier="premium", temperature=0.5, max_tokens=3000, stage="script_expand"
        )
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
    extra_directive: str = "",
):
    min_words, max_words = word_range
    channel_id = channel_id or "default"
    clean_key_facts_early = _sanitize_key_facts(key_facts)
    script_brief = build_script_brief(
        topic,
        channel_id,
        seed_topic=seed_topic or topic,
        key_facts=clean_key_facts_early or None,
    )
    seo_block = build_seo_prompt_block(channel_id)
    signal_facts = enrich_facts(
        topic,
        signals,
        channel_id=channel_id,
        seed_topic=seed_topic or topic,
    )
    # Drop self-contradictory future-dated "facts" (e.g. a web line claiming an
    # event was *lost* on a date that hasn't happened yet) before they ground the
    # script — grounding stops invention, not propagation of a bad source.
    if os.getenv("FACT_FUTURE_DATE_FILTER", "true").lower() not in ("0", "false", "no"):
        import datetime

        from core.fact_recency import drop_future_dated

        signal_facts, _dropped_dates = drop_future_dated(signal_facts, datetime.date.today())
        if _dropped_dates:
            logger.info("Dropped %d future-dated fact line(s)", len(_dropped_dates))

    # Pre-script contradiction detection (Pillar 3): flag source lines that
    # disagree with the operator's key facts BEFORE the LLM sees both, and
    # (default on) keep the losing lines out of the prompt entirely.
    from core.fact_conflicts import (
        conflict_filter_enabled,
        drop_conflicting_lines,
        find_fact_conflicts,
    )

    clean_key_facts = clean_key_facts_early
    conflicts = find_fact_conflicts(clean_key_facts, signal_facts)
    conflicts_dropped = 0
    if conflicts:
        logger.warning(
            "Fact conflicts (%d): %s",
            len(conflicts),
            "; ".join(c.detail for c in conflicts),
        )
        if conflict_filter_enabled():
            signal_facts, conflicts_dropped = drop_conflicting_lines(signal_facts, conflicts)
            if conflicts_dropped:
                logger.info(
                    "Dropped %d source line(s) conflicting with operator facts",
                    conflicts_dropped,
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
        extra_directive=extra_directive,
    )

    # Short: tighter temperature for punchy focus; Extended: slightly more creative latitude
    temperature = 0.55 if length_choice == "1" else (0.72 if length_choice == "4" else 0.68)
    payload = _call_content_llm(system_prompt, user_prompt, temperature=temperature)

    if not (isinstance(payload, dict) and payload.get("script")):
        logger.warning("LLM returned non-JSON content package; using raw fallback")
        return {
            "title": topic,
            "script": payload if isinstance(payload, str) else "",
            "description": apply_description_extras(
                "", channel_id, title=topic, topic=topic, key_facts=clean_key_facts
            ),
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

    # The fact corpus the script must stay grounded in (also used by the insight
    # beat so it can't invent specifics) — built before injection + grounding.
    # Tiered (Pillar 3): every line carries a provenance tier; full_text is the
    # same flat string the token-grounding check has always seen.
    corpus = build_tiered_corpus(
        signal_facts=signal_facts,
        brief_block=brief_block,
        topic=topic,
        seed_topic=seed_topic or "",
        key_facts=clean_key_facts,
    )
    grounding_text = corpus.full_text

    # Key-fact anchor: if the script drifted off the operator's pasted subject,
    # recenter it FIRST (subject-level) — before insight/grounding tweak the prose.
    script = _maybe_recenter_on_key_facts(script, key_facts, topic, grounding_text)

    # Original-insight injection: if the script reads as a neutral recap, add one
    # opinion/prediction beat (Phase O authenticity). Runs BEFORE grounding so any
    # specifics it introduces still get caught/cleaned below.
    script = _maybe_inject_insight(script, grounding_text, topic)

    llm_tags = payload.get("tags") or []
    if isinstance(llm_tags, str):
        llm_tags = [t.strip() for t in llm_tags.split(",") if t.strip()]
    tags = normalize_youtube_tags(
        llm_tags,
        extra=default_tags_for_channel(channel_id, topic) + tags_from_topic(topic),
    )

    # Post-generation grounding check: flag specifics in the script not backed by
    # the facts the model was given (catches invented heroes/products/patches).
    ungrounded = find_ungrounded_entities(script, grounding_text)
    if ungrounded:
        # Regenerate-then-warn: try once to strip the unsupported specifics, then
        # surface whatever still remains (never silently rewrite away the warning).
        script, ungrounded = _maybe_reground_script(script, grounding_text, topic, ungrounded)
    if ungrounded:
        logger.warning(
            "Script names %s specific(s) not in the facts: %s",
            len(ungrounded),
            ", ".join(ungrounded),
        )

    # Semantic trade validation (opt-in): player→team pairings must co-occur on a
    # fact line, catching fused trades that token grounding passes.
    trade_warnings: list[str] = []
    from apis.topic_scorer import infer_domain
    from core.trade_validation import trade_validation_enabled, validate_trade_claims

    # Default-on for NBA/NFL trade topics (env still forces on/off globally). No channel
    # defaults to nba/nfl, so the channel-profile fallback can't spuriously trigger it.
    # key_facts must be passed: pasted NBA facts on the gaming/UFC channel are exactly
    # the case this check exists for, and topic+channel alone would infer "gaming".
    _trade_domain = infer_domain(
        topic or "", channel_id=channel_id, key_facts=clean_key_facts_early or None
    )
    if trade_validation_enabled(_trade_domain):
        trade_warnings = validate_trade_claims(script, grounding_text)
        if trade_warnings:
            logger.warning(
                "Trade direction check flagged %d pairing(s): %s",
                len(trade_warnings),
                "; ".join(trade_warnings),
            )

    # Tier lint (Pillar 3): specifics that only ground via YouTube titles, and
    # high-stakes claims (trades/results/records) backed only by low-tier text.
    from core.grounding_tiers import tier_warnings_for_script

    tier_warnings = tier_warnings_for_script(script, corpus)
    if tier_warnings:
        logger.warning(
            "Grounding tier check flagged %d claim(s): %s",
            len(tier_warnings),
            "; ".join(tier_warnings),
        )

    # Claim-level verification (Pillar 3): one extract-tier call decomposes the
    # script into factual claims and checks each against the NON-context corpus
    # (YouTube titles must not "support" a claim). Fail-open → None.
    from core.claim_verifier import verify_claims

    verification = verify_claims(
        script, corpus.factual_text, topic=topic, priority_facts=clean_key_facts
    )
    if verification and verification.unsupported:
        logger.warning(
            "Claim verifier: %d/%d claim(s) unsupported: %s",
            len(verification.unsupported),
            verification.total,
            "; ".join(c.claim for c in verification.unsupported[:5]),
        )
        # Act on the verdict: one rewrite pass removes/attributes the unsupported
        # claims (kept only if the re-verified count improves). "Fact slop" fix —
        # the script must be correct, not detail-stuffed with invented specifics.
        script, verification = _maybe_rewrite_unsupported_claims(
            script, verification, corpus.factual_text, topic, clean_key_facts
        )

    try:
        from core.odds_language import apply_odds_language

        script, odds_notes = apply_odds_language(script, topic=topic)
        for note in odds_notes:
            logger.info("%s", note)
    except Exception as exc:
        logger.debug("odds language skipped: %s", exc)

    tts_cap = None
    try:
        from core.tts_char_cap import max_chars as tts_max

        tts_cap = tts_max()
    except Exception as exc:
        logger.debug("tts cap for trim skipped: %s", exc)

    # Odds rewrite can add words ("will win" -> "is favored to win"); trim after
    # that so a post-trim cap check cannot refuse a script we just made fit.
    script, trimmed_n = trim_overlength(
        script, max_words=max_words, min_words=min_words, max_chars=tts_cap
    )
    if trimmed_n:
        logger.info("Script trim pass dropped %s padding word(s) (still unclipped)", trimmed_n)

    from core.title_generator import generate_title

    title = generate_title(
        script=script,
        topic=topic,
        seed_topic=seed_topic,
        key_facts=key_facts,
        channel_id=channel_id,
    )

    # Candidate 321: the title is the last thing generated and was the only operator-
    # facing string no check ever read. Verified here (not at publish time) so the
    # warning reaches the report card BEFORE the operator answers "Proceed?".
    from core.youtube_meta import lint_title_grounding

    title_warnings = lint_title_grounding(
        title,
        facts_text=corpus.factual_text,
        priority_facts=clean_key_facts,
        topic=topic,
    )
    if title_warnings:
        logger.warning(
            "Title check flagged %d claim(s): %s",
            len(title_warnings),
            "; ".join(title_warnings),
        )

    return {
        "title": title,
        "title_warnings": title_warnings,
        "script": script,
        "description": apply_description_extras(
            payload.get("description") or "",
            channel_id,
            title=title,
            topic=topic,
            key_facts=clean_key_facts,
        ),
        "tags": tags,
        "prompt_version": PROMPT_VERSION,
        "brief_version": research_brief.version if research_brief else "",
        "word_count": count_spoken_words(script),
        "ungrounded_entities": ungrounded,
        "trade_warnings": trade_warnings,
        "tier_warnings": tier_warnings,
        "fact_conflicts": [c.render() for c in conflicts],
        "fact_conflicts_dropped": conflicts_dropped,
        "claim_verification": verification.to_dict() if verification else None,
    }
