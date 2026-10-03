"""Your verdict per video, against the audience's (#935).

Every video gets a report card from the engine; until now none got one from you. A
verdict is a 1-5 rating and a line of why, given in `ops review-week` (#936). Set against
the views, it says where your gut and the audience agree - and the two lists worth a look:
videos you loved that the audience did not, and ones you rated low that did well.

Views are ranked into thirds among the measured videos (views > 0); a rating of 4-5 agrees
with the top third, 3 with the middle, 1-2 with the bottom.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from config.paths import DATA_DIR

VERDICTS_FILE = os.path.join(DATA_DIR, "verdicts.json")
MIN_RATED = 3


def _read() -> dict[str, Any]:
    try:
        with open(VERDICTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(channel_id: str) -> dict[str, dict[str, Any]]:
    """{video_id: {rating, note, title, at}} for the channel."""
    entry = _read().get(channel_id)
    return entry if isinstance(entry, dict) else {}


def record(channel_id: str, video_id: str, rating: int, *, note: str = "", title: str = "") -> None:
    rating = int(rating)
    if not 1 <= rating <= 5:
        raise ValueError(f"a verdict is 1-5, got {rating}")
    data = _read()
    channel = data.setdefault(channel_id, {})
    channel[video_id] = {
        "rating": rating,
        "note": note.strip(),
        "title": title.strip(),
        "at": date.today().isoformat(),
    }
    os.makedirs(os.path.dirname(VERDICTS_FILE) or ".", exist_ok=True)
    tmp = f"{VERDICTS_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, VERDICTS_FILE)


def _third(rank: int, total: int) -> str:
    """ "top" / "middle" / "bottom" for a 0-based views rank (0 = most views)."""
    if rank < total / 3:
        return "top"
    if rank >= total - total / 3:
        return "bottom"
    return "middle"


def _agrees(rating: int, third: str) -> bool:
    return {"top": rating >= 4, "middle": rating == 3, "bottom": rating <= 2}[third]


def _scored(channel_id: str) -> dict[str, Any]:
    """Your ratings set against the views ranking (#940: the comparable measure)."""
    from core.success.videos import channel_videos, comparable_views

    verdicts = load(channel_id)
    ranked, heading, unit = comparable_views(channel_videos(channel_id))
    rated = [(i, v, value) for i, (v, value) in enumerate(ranked) if v.video_id in verdicts]
    agreed = 0
    loved, doubted = [], []
    for rank, video, value in rated:
        rating = int(verdicts[video.video_id]["rating"])
        third = _third(rank, len(ranked))
        agreed += _agrees(rating, third)
        if rating >= 4 and third == "bottom":
            loved.append(f'"{video.title}" (you: {rating}, {value:,} {unit})')
        if rating <= 2 and third == "top":
            doubted.append(f'"{video.title}" (you: {rating}, {value:,} {unit})')
    return {"measured": len(ranked), "rated": len(rated), "agreed": agreed, "loved": loved,
            "doubted": doubted, "heading": heading}  # fmt: skip


def agreement(channel_id: str) -> tuple[int, int]:
    """(agreed, rated) for the review history (#943)."""
    scored = _scored(channel_id)
    return scored["agreed"], scored["rated"]


def verdict_report(channel_id: str) -> list[str]:
    scored = _scored(channel_id)
    head = f"Your verdicts vs the audience - {channel_id}"
    rated, agreed = scored["rated"], scored["agreed"]
    if rated < MIN_RATED:
        return [
            head,
            f"  {rated} rated video(s) with views; rate {MIN_RATED - rated} more "
            "(py -m scripts.ops review-week) and this compares your gut with the views.",
        ]
    lines = [
        f"{head} ({rated} rated videos with views)",
        f"  agreed on {agreed} of {rated} ({agreed / rated:.0%}) - {scored['heading']} ranked "
        f"in thirds over {scored['measured']} measured videos",
    ]
    if scored["loved"]:
        lines.append("  rated 4-5, landed in the bottom third: " + "; ".join(scored["loved"]))
    if scored["doubted"]:
        lines.append("  rated 1-2, landed in the top third: " + "; ".join(scored["doubted"]))
    return lines
