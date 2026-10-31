"""Caption arms per platform (#1197), and TikTok's own caption (#1776).

Both arms are sentences already in the caption. The arm is `random_arm`, seeded
by the run id. The report names a winner only once `evaluate` has one, and the
interval is on that arm's views.

#1776 (decision 89): the arm was never saved - the "scheduled" write replaced the
mark that carried it - so the test read nothing in 73 posts. A post without one is
replayed from its seed and counted only when the caption it would have had opens
the way the post did. Replayed, TikTok's hook-first arm had 152 views a post (15)
against 113 (15); from 2026-10-31 TikTok's caption is hook-first always, with three
hashtags (`tiktok_caption`, arm "hook_first", outside the test). Instagram keeps it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.experiment_stats import evaluate
from core.experiments import random_arm
from core.recommender_confidence import confidence_interval

_LABEL = {"tiktok": "TikTok", "instagram": "Instagram"}
FIRST_LINE_MAX = 100  # TikTok's feed shows the caption's first line


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def caption_texts(run: Any) -> dict[str, str]:
    """The caption as posted today, and the same words with the first sentence first."""
    from publishing.crosspost import CAPTION_MAX, caption

    base = caption(run)
    parts = _sentences(str(getattr(run, "description", "") or "").strip())
    first = parts[0] if parts else ""
    if not first or first not in base:
        return {"caption": base, "first_line": base}
    rest = base.replace(first, "", 1).strip()
    swapped = f"{first}\n\n{rest}".strip()
    if len(swapped) > CAPTION_MAX:
        swapped = swapped[: CAPTION_MAX - 1].rstrip() + "…"
    return {"caption": base, "first_line": swapped}


def _split_camel(word: str) -> str:
    """ "MoicanoVsNolan" -> "Moicano Vs Nolan", "UFCFightNight" -> "UFC Fight Night"."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", word)


def domain_hashtag(channel_id: str, topic: str) -> str:
    """The topic's sport or game as one hashtag word (`domain_hashtag` in config/seo)."""
    from config.seo import _topic_domain, get_seo_profile

    table = get_seo_profile(channel_id).get("domain_hashtag") or {}
    if not isinstance(table, dict):
        return ""
    return str(table.get(_topic_domain(topic)) or table.get("default") or "")


def tiktok_tags(channel_id: str, run: Any) -> list[str]:
    """Three hashtags: two of the run's tags that name the topic (a word shared with its title or
    topic), then the sport or game. Title names fill in when the tags have fewer than two."""
    from apis.topic_tokens import content_tokens, title_phrases
    from publishing.crosspost import hashtags

    title = str(getattr(run, "title", "") or "")
    topic = str(getattr(run, "input_topic", "") or getattr(run, "selected_topic", "") or title)
    wanted = set(content_tokens(f"{title} {topic}", min_len=3))
    domain = domain_hashtag(channel_id, topic or title)
    try:
        tags = [str(t) for t in json.loads(getattr(run, "tags_json", "") or "[]")]
    except (TypeError, ValueError):
        tags = []
    candidates = [*tags, *(re.sub(r"\s+", "", p) for p in title_phrases(title))]
    picked: list[str] = []
    for tag in hashtags(candidates, limit=len(candidates) or 1):
        if tag[1:].lower() == domain.lower() or tag.lower() in (p.lower() for p in picked):
            continue
        if wanted & set(content_tokens(_split_camel(tag[1:]), min_len=3)):
            picked.append(tag)
        if len(picked) == 2:
            break
    return [*picked, *hashtags([domain])]


def tiktok_caption(channel_id: str, run: Any) -> str:
    """#1776 (B08.5): the hook first - the description's opening sentence when it fits the feed's
    first line, else the title - then the title and the rest, three hashtags, the disclosure."""
    from publishing.crosspost import CAPTION_MAX, _disclosure, caption_body

    title = str(getattr(run, "title", "") or getattr(run, "selected_topic", "") or "").strip()
    body = caption_body(run)
    parts = _sentences(body)
    first = parts[0] if parts else ""
    if first and len(first) <= FIRST_LINE_MAX:
        blocks = [first, title, body.replace(first, "", 1).strip()]
    else:
        blocks = [title, body]
    blocks += [" ".join(tiktok_tags(channel_id, run)), _disclosure()]
    text = "\n\n".join(b for b in blocks if b)
    return text if len(text) <= CAPTION_MAX else text[: CAPTION_MAX - 1].rstrip() + "…"


def choose_caption(channel_id: str, run: Any, platform: str) -> tuple[str, str]:
    if platform == "tiktok":  # decision 89: hook-first always, outside the test
        return "hook_first", tiktok_caption(channel_id, run)
    texts = caption_texts(run)
    arm = random_arm(channel_id, f"caption_{platform}", int(getattr(run, "id", 0) or 0))
    if arm not in texts:
        arm = "caption"
    return arm, texts[arm]


def _replayed_arm(channel_id: str, platform: str, run_id: str, state: dict[str, Any]) -> str:
    """The arm a post without one was given, from its seed - "" unless the caption that arm
    makes today opens as the post did, and the two arms differ."""
    from publishing import crosspost

    start = str(state.get("text_start") or "")
    if not start or not str(run_id).isdigit():
        return ""
    arm = random_arm(channel_id, f"caption_{platform}", int(run_id))
    run = crosspost._content_run(int(run_id))
    if run is None or not arm:
        return ""
    texts = caption_texts(run)
    if texts["caption"] == texts["first_line"] or not texts.get(arm, "").startswith(start):
        return ""
    return arm


def caption_outcomes(channel_id: str, platform: str) -> dict[str, list[float]]:
    """Measured views per arm - the saved arm, else the replayed one. Hand posts are left out."""
    from publishing import crosspost
    from publishing.platform_metrics import get_row

    outcomes: dict[str, list[float]] = {"caption": [], "first_line": []}
    posts = crosspost._load(channel_id).get("posts") or {}
    if not isinstance(posts, dict):
        return outcomes
    for rid, entry in posts.items():
        state = entry.get(platform) if isinstance(entry, dict) else None
        if not isinstance(state, dict) or state.get("state") == "manual":
            continue
        arm = str(state.get("arm") or "")
        if not arm:
            try:
                arm = _replayed_arm(channel_id, platform, str(rid), state)
            except Exception:
                arm = ""
        if arm not in outcomes:
            continue
        row = get_row(channel_id, str(rid), platform)
        if not row or not row.get("measured") or row.get("views") is None:
            continue
        outcomes[arm].append(float(row["views"]))
    return outcomes


def caption_report(channel_id: str, platform: str) -> str:
    """Winner and views interval, or that the arms are still collecting."""
    outcomes = caption_outcomes(channel_id, platform)
    if not any(outcomes.values()):
        return ""
    result = evaluate(outcomes)
    label = _LABEL.get(platform, platform)
    if result.get("status") != "winner":
        counts = ", ".join(f"{arm} {len(values)}" for arm, values in outcomes.items())
        return f"{label} captions: collecting ({counts})"
    winner = str(result.get("winner") or "")
    half = confidence_interval(outcomes.get(winner) or [])
    span = "n/a" if half is None else f"+/- {half:.0f} views"
    return f"{label} captions: {winner} won, {span}"
