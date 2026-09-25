"""#433 cross-channel duplicate-upload guard — same domain lens, not same topic.

MoneyWise covering GTA 6's market impact is a finance angle and is allowed.
MoneyWise reviewing GTA 6 is TapIn's job and is not. Identity is a shared
franchise family (or an exact normalized topic); the lens is `_lens_for` --
infer_domain plus finance TREATMENT cues, because infer_domain reads by subject.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.cross_channel_dup")

_LIVE_STATUSES = frozenset({"drafted", "rendered", "scheduled", "published"})

# Treatment cues that make a topic a FINANCE lens whatever the franchise is.
#
# `infer_domain` classifies by subject, and it checks its gaming/sport words before
# its finance words -- so "GTA 6 economic impact on the games market" reads `gaming`,
# and keying this guard on infer_domain alone refused the one MoneyWise angle the
# operator explicitly permitted ("economic impact of GTA 6 hitting the market ...
# but reviews or commentary should stop there"). Only this guard's LENS is widened;
# `infer_domain` itself is untouched because it also drives the YouTube category
# (#102), per-domain signal weights, and scoring.
_FINANCE_TREATMENT = (
    "economic impact",
    "market impact",
    "impact on the market",
    "market cap",
    "sales figures",
    "revenue",
    "valuation",
    "investor",
    "shareholder",
    "consumer spending",
    "the economy",
)


def _lens_for(topic: str, channel_id: str, key_facts: list[str] | None = None) -> str:
    """The angle a channel is taking, not the subject it is about."""
    from apis.topic_scorer import infer_domain

    low = (topic or "").lower()
    if any(cue in low for cue in _FINANCE_TREATMENT):
        return "finance"
    return infer_domain(topic, channel_id, key_facts=key_facts)


def dup_mode() -> str:
    raw = (os.getenv("CROSS_CHANNEL_DUP", "block") or "block").strip().lower()
    if raw in ("0", "off", "false", "no"):
        return "off"
    if raw in ("warn",):
        return "warn"
    return "block"


def _topic_of(row: Any) -> str:
    return str(getattr(row, "selected_topic", "") or getattr(row, "input_topic", "") or "").strip()


def _same_identity(left: str, right: str) -> bool:
    from core.channel_context import anchor_families
    from core.youtube_meta import normalize_title

    fams_l = anchor_families(left)
    fams_r = anchor_families(right)
    if fams_l and fams_r and (fams_l & fams_r):
        return True
    a = normalize_title(left)
    b = normalize_title(right)
    return bool(a and a == b)


def cross_channel_lens_collision(
    topic: str,
    channel_id: str,
    *,
    key_facts: list[str] | None = None,
    exclude_run_id: int | None = None,
) -> str | None:
    """Sentence describing a same-lens collision on another channel, or None."""
    if dup_mode() == "off":
        return None
    topic = (topic or "").strip()
    if not topic:
        return None
    try:
        from config.channels import list_channel_ids, resolve_channel_id
        from storage.repositories.content_runs import get_content_run_repository
    except Exception as exc:
        logger.debug("cross-channel dup imports skipped: %s", exc)
        return None

    cid = resolve_channel_id(channel_id)
    this_lens = _lens_for(topic, cid, key_facts)
    try:
        repo = get_content_run_repository()
    except Exception as exc:
        logger.debug("cross-channel dup repo skipped: %s", exc)
        return None

    for other_id in list_channel_ids():
        if other_id == cid:
            continue
        try:
            rows = repo.list_for_channel(other_id)
        except Exception as exc:
            logger.debug("cross-channel dup list skipped (%s): %s", other_id, exc)
            continue
        for row in rows:
            rid = getattr(row, "id", None)
            if exclude_run_id is not None and rid == exclude_run_id:
                continue
            if str(getattr(row, "status", "") or "") not in _LIVE_STATUSES:
                continue
            other_topic = _topic_of(row)
            if not other_topic or not _same_identity(topic, other_topic):
                continue
            other_lens = _lens_for(other_topic, other_id)
            if other_lens != this_lens:
                continue
            return (
                f"cross-channel lens collision: {cid} and {other_id} both treat this "
                f"as {this_lens} (vs run #{rid}: {other_topic[:80]})"
            )
    return None


def cross_channel_dup_block_reason(
    topic: str,
    channel_id: str,
    *,
    key_facts: list[str] | None = None,
    exclude_run_id: int | None = None,
) -> str | None:
    """Blocking sentence, or None. Warn mode logs and lets the run continue."""
    hit = cross_channel_lens_collision(
        topic, channel_id, key_facts=key_facts, exclude_run_id=exclude_run_id
    )
    if not hit:
        return None
    if dup_mode() == "warn":
        logger.warning("%s", hit)
        return None
    return hit
