"""Caption arms per platform (#1197).

Both arms are sentences already in the caption. The arm is `random_arm`, seeded
by the run id. The report names a winner only once `evaluate` has one, and the
interval is on that arm's views.
"""

from __future__ import annotations

import re
from typing import Any

from core.experiment_stats import evaluate
from core.experiments import random_arm
from core.recommender_confidence import confidence_interval

_LABEL = {"tiktok": "TikTok", "instagram": "Instagram"}


def caption_texts(run: Any) -> dict[str, str]:
    """The caption as posted today, and the same words with the first sentence first."""
    from publishing.crosspost import CAPTION_MAX, caption

    base = caption(run)
    body = str(getattr(run, "description", "") or "").strip()
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", body) if part.strip()]
    first = parts[0] if parts else ""
    if not first or first not in base:
        return {"caption": base, "first_line": base}
    rest = base.replace(first, "", 1).strip()
    swapped = f"{first}\n\n{rest}".strip()
    if len(swapped) > CAPTION_MAX:
        swapped = swapped[: CAPTION_MAX - 1].rstrip() + "…"
    return {"caption": base, "first_line": swapped}


def choose_caption(channel_id: str, run: Any, platform: str) -> tuple[str, str]:
    texts = caption_texts(run)
    arm = random_arm(channel_id, f"caption_{platform}", int(getattr(run, "id", 0) or 0))
    if arm not in texts:
        arm = "caption"
    return arm, texts[arm]


def caption_report(channel_id: str, platform: str) -> str:
    """Winner and views interval, or that the arms are still collecting."""
    from publishing import crosspost
    from publishing.platform_metrics import get_row

    outcomes: dict[str, list[float]] = {"caption": [], "first_line": []}
    posts = crosspost._load(channel_id).get("posts") or {}
    if not isinstance(posts, dict):
        return ""
    for rid, entry in posts.items():
        if not isinstance(entry, dict):
            continue
        state = entry.get(platform)
        if not isinstance(state, dict):
            continue
        arm = str(state.get("arm") or "")
        if arm not in outcomes:
            continue
        row = get_row(channel_id, str(rid), platform)
        if not row or not row.get("measured") or row.get("views") is None:
            continue
        outcomes[arm].append(float(row["views"]))
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
