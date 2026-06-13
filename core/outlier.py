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


def get_competitor_outlier(signals: dict[str, Any]) -> CompetitorOutlier | None:
    """Return the highest view-velocity competitor video from the signals, if any."""
    sig = (signals or {}).get("youtube_competitors")
    if not isinstance(sig, dict) or not sig.get("active"):
        return None
    data = sig.get("data") or {}
    videos = data.get("videos") or []
    best = None
    for v in videos:
        if not isinstance(v, dict) or not v.get("title"):
            continue
        if best is None or (v.get("velocity") or 0) > (best.get("velocity") or 0):
            best = v
    if not best or not (best.get("velocity") or 0):
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
