"""Title-pattern attribution loop ("A/B variant loop", single-channel form).

We already generate + score multiple title variants per video; only one ships.
Rather than double-publish (cannibalizing a faceless channel), this closes the
loop by *attribution*: it joins each published title to its realized engagement
and aggregates by the title's structural pattern tags (`core/title_features`).
The result is a per-channel leaderboard — "colon titles average 18%, questions
12%" — that (a) the operator can read and (b) surfaces back at variant selection
as a "▲ proven pattern" hint, so the analytics loop biases future picks.

Confidence-aware (min sample count), read-only, best-effort (empty on any error).
"""

from __future__ import annotations

import os
from functools import lru_cache

from core import process_state
from core.engagement import engaged_rate
from core.logging import get_logger
from core.title_features import feature_tags

logger = get_logger("core.title_experiments")


def _titled_outcomes(channel_id: str) -> list[tuple[str, float]]:
    """(published_title, engaged_rate) for runs that have engagement data."""
    try:
        from storage.repositories.content_runs import get_content_run_repository
        from storage.repositories.publish_log import get_publish_log_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("title_experiments load failed: %s", exc)
        return []
    log_by_run = {log.content_run_id: log for log in logs}
    out: list[tuple[str, float]] = []
    for run in runs:
        title = (run.title or run.selected_topic or "").strip()
        log = log_by_run.get(run.id)
        if not title or not log:
            continue
        rate = engaged_rate(log.metrics_json)
        if rate is not None:
            out.append((title, float(rate)))
    return out


def _min_samples() -> int:
    try:
        return max(2, int(os.getenv("TITLE_PATTERN_MIN_SAMPLES", "3")))
    except ValueError:
        return 3


def pattern_leaderboard(channel_id: str, *, min_measured: int | None = None) -> list[tuple]:
    """[(tag, avg_engaged_rate, n)] sorted best-first, for tags with enough samples."""
    min_n = min_measured if min_measured is not None else _min_samples()
    by_tag: dict[str, list[float]] = {}
    for title, rate in _titled_outcomes(channel_id):
        for tag in feature_tags(title):
            by_tag.setdefault(tag, []).append(rate)
    board = [(tag, sum(v) / len(v), len(v)) for tag, v in by_tag.items() if len(v) >= min_n]
    board.sort(key=lambda x: x[1], reverse=True)
    return board


@lru_cache(maxsize=8)
def winning_tags(channel_id: str) -> frozenset[str]:
    """Pattern tags that beat the channel's overall engaged-rate (cached per run).

    Cached because it's consulted once per displayed variant; `reset_cache()`
    clears it for tests / a fresh run.
    """
    outcomes = _titled_outcomes(channel_id)
    if not outcomes:
        return frozenset()
    overall = sum(r for _, r in outcomes) / len(outcomes)
    board = pattern_leaderboard(channel_id)
    return frozenset(tag for tag, avg, _ in board if avg > overall)


def reset_cache() -> None:
    winning_tags.cache_clear()


def display_leaderboard(channel_id: str, *, print_fn=print) -> None:
    from core.recommender_confidence import confidence_note

    board = pattern_leaderboard(channel_id)
    if not board:
        print_fn("\n  Title patterns: (not enough measured videos yet)")
        return
    print_fn("\n  📊 Title patterns that engage (this channel):")
    for tag, avg, n in board:
        print_fn(f"    {avg:6.0%}  {tag:<11}{confidence_note(n)}")


process_state.register_reset("core.title_experiments", reset_cache)  # #827
