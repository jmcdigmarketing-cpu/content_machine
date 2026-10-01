"""
Competitor "outlier" surface.

Every credible 2026 faceless-creator guide says the same thing: analyse the
competitor videos that are *over-performing* before you make anything. The
`youtube_competitors` Apify signal already computes view velocity (views/day);
this surfaces the single surging video as an explicit content prompt so the
operator can riff on a proven angle (with our own verified facts + take).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CompetitorOutlier:
    title: str
    channel: str
    velocity: float  # views/day
    views: int
    url: str

    def prompt_line(self) -> str:
        ch = f" — {self.channel}" if self.channel else ""
        return f'"{self.title}"{ch} ({self.velocity:,.0f} views/day)'


# #926: "surging" needs a floor. Run 109 showed a 2016 IGN video at 28 views/day - the
# fastest in its list, but neither recent nor ahead of anything.
SURGE_MAX_AGE_DAYS = 30
SURGE_MIN_RATIO = 2.0


def get_competitor_outlier(signals: dict[str, Any]) -> CompetitorOutlier | None:
    """The competitor video that is actually surging, if any.

    The fastest video counts only when it is at most `SURGE_MAX_AGE_DAYS` old (a video
    without an age is kept, as before) and at least `SURGE_MIN_RATIO` times the median
    velocity of the others; alone in its list it needs the age test only.
    """
    sig = (signals or {}).get("youtube_competitors")
    if not isinstance(sig, dict) or not sig.get("active"):
        return None
    data = sig.get("data") or {}
    videos = [v for v in data.get("videos") or [] if isinstance(v, dict) and v.get("title")]
    best = None
    for v in videos:
        if best is None or (v.get("velocity") or 0) > (best.get("velocity") or 0):
            best = v
    if not best or not (best.get("velocity") or 0):
        return None
    age = best.get("age_days")
    if age is not None and float(age) > SURGE_MAX_AGE_DAYS:
        return None
    others = sorted(float(v.get("velocity") or 0) for v in videos if v is not best)
    if others:
        mid = len(others) // 2
        median = others[mid] if len(others) % 2 else (others[mid - 1] + others[mid]) / 2
        if float(best.get("velocity") or 0) < SURGE_MIN_RATIO * median:
            return None
    return CompetitorOutlier(
        title=str(best.get("title") or "")[:140],
        channel=str(best.get("channel") or ""),
        velocity=float(best.get("velocity") or 0),
        views=int(best.get("views") or 0),
        url=str(best.get("url") or ""),
    )


def display_outlier(outlier: CompetitorOutlier | None, *, print_fn=print) -> None:
    if not outlier:
        return
    print_fn(f"\n  Surging competitor angle: {outlier.prompt_line()}")
    print_fn("    Riff on this angle with your own take + verified facts (don't copy).")
