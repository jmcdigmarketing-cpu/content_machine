"""A run's stored subject against today's reading of its title (#1947, decision 94).

A run's domain is fixed when it is drafted. Run 120 (Minecraft inside Elden Ring) was stored as
nba and run 126 (Ben Affleck in Fortnite) as popculture - 476 organic views the gaming counts
missed - and seven early runs (17-98) were stored as gaming while being UFC, soccer or NBA
stories. `drift` lists each video whose stored subject today's reading of its title disputes
(a topic's own reading, never the channel's fallback; a neutral reading disputes nothing), and
`apply` stores the corrected one as `domains.effective`, the field S15, the conversion line,
the gaming floor's lead and the category fix read, keeping the old one as `was`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger("core.runs.domains")


@dataclass
class Correction:
    run_id: int
    title: str
    stored: str
    read: str
    views: int


def _stored(features: dict[str, Any]) -> str:
    domains = features.get("domains")
    if isinstance(domains, dict) and domains.get("effective"):
        return str(domains["effective"])
    return str(features.get("domain") or "")


def drift(channel_id: str) -> list[Correction]:
    """Each live video whose stored subject its title reads otherwise, newest first."""
    from apis.topic_scorer import KNOWN_DOMAINS, infer_topic_domain
    from core import run_features
    from core.success import videos

    out: list[Correction] = []
    seen: set[int] = set()
    for video in videos.channel_videos(channel_id, include_seeded=False):
        run_id = video.run_id
        if not run_id or run_id in seen:
            continue
        seen.add(run_id)
        features = run_features.load_features(run_id)
        if not features or features.get("parent_run_id"):
            continue  # a chapter Short is its parent's subject (#1945)
        stored = _stored(features)
        if not stored:
            continue  # a Week in Review names several
        read = infer_topic_domain(video.title)
        if read == stored or read == "neutral" or read not in KNOWN_DOMAINS:
            continue
        out.append(Correction(int(run_id), video.title, stored, read, video.organic_views))
    return out


def apply(corrections: list[Correction], *, day: str | None = None) -> int:
    """Store each correction; how many were written."""
    from core import run_features

    when = day or date.today().isoformat()
    written = 0
    for fix in corrections:
        features = run_features.load_features(fix.run_id)
        if not features:
            continue
        old = features.get("domains")
        domains = dict(old) if isinstance(old, dict) else {}
        domains.update({"effective": fix.read, "topic": fix.read, "was": fix.stored,
                        "corrected": when})  # fmt: skip
        run_features.merge_features(fix.run_id, {"domains": domains})
        written += 1
    return written


def drift_lines(channel_id: str, *, apply_fixes: bool = False) -> list[str]:
    """`ops domains`: the disputed subjects, and with `apply_fixes` the count corrected."""
    found = drift(channel_id)
    if not found:
        return ["Every stored subject matches today's reading of its title."]
    lines = [f"{len(found)} run(s) stored under another subject than their title reads:"]
    for fix in found:
        lines.append(f"  run {fix.run_id}: {fix.stored} -> {fix.read} ({fix.views:,} organic "
                     f"views)  {fix.title[:70]}")  # fmt: skip
    if not apply_fixes:
        lines.append("Dry run - --apply stores the corrected subject (the old one kept as `was`).")
        return lines
    lines.append(f"Corrected {apply(found)} - S15, the conversion line and the gaming floor read "
                 "them now.")  # fmt: skip
    return lines
