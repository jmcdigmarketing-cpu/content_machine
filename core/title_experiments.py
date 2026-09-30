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
from typing import Any

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


# #566: a pattern is "proven" only when its shrunk lift over the channel clears this.
_MIN_LIFT = 0.01


def pattern_lifts(channel_id: str, *, min_measured: int | None = None) -> list[dict[str, Any]]:
    """[{tag, avg, n, lift, baseline}] best-first by lift over the channel (#566).

    `avg` is the raw mean (what happened); `lift` is the tag's mean shrunk toward the
    channel (#352's `shrunk_mean`) minus the channel mean, so three lucky videos cannot
    outrank twelve steady ones.
    """
    from core.recommender_confidence import shrunk_mean

    min_n = min_measured if min_measured is not None else _min_samples()
    outcomes = _titled_outcomes(channel_id)
    if not outcomes:
        return []
    baseline = sum(r for _, r in outcomes) / len(outcomes)
    by_tag: dict[str, list[float]] = {}
    for title, rate in outcomes:
        for tag in feature_tags(title):
            by_tag.setdefault(tag, []).append(rate)
    rows: list[dict[str, Any]] = [
        {
            "tag": tag,
            "avg": sum(v) / len(v),
            "n": len(v),
            "lift": shrunk_mean(v, baseline) - baseline,
            "baseline": baseline,
        }
        for tag, v in by_tag.items()
        if len(v) >= min_n
    ]
    rows.sort(key=lambda r: float(r["lift"]), reverse=True)
    return rows


def pattern_leaderboard(channel_id: str, *, min_measured: int | None = None) -> list[tuple]:
    """[(tag, avg_engaged_rate, n)] best-first by lift over the channel, enough samples."""
    return [
        (r["tag"], r["avg"], r["n"]) for r in pattern_lifts(channel_id, min_measured=min_measured)
    ]


@lru_cache(maxsize=8)
def winning_tags(channel_id: str) -> frozenset[str]:
    """Pattern tags whose shrunk lift over the channel clears `_MIN_LIFT` (cached per run).

    Cached because it's consulted once per displayed variant; `reset_cache()`
    clears it for tests / a fresh run.
    """
    return frozenset(r["tag"] for r in pattern_lifts(channel_id) if r["lift"] >= _MIN_LIFT)


def reset_cache() -> None:
    winning_tags.cache_clear()


def display_leaderboard(channel_id: str, *, print_fn=print) -> None:
    from core.recommender_confidence import confidence_note

    rows = pattern_lifts(channel_id)
    if not rows:
        print_fn("\n  Title patterns: (not enough measured videos yet)")
        return
    print_fn(f"\n  📊 Title patterns vs this channel ({rows[0]['baseline']:.0%} average):")
    for r in rows:
        print_fn(
            f"    {r['lift'] * 100:+5.1f}pp vs channel  {r['tag']:<11} "
            f"(raw {r['avg']:.0%}){confidence_note(r['n'])}"
        )


process_state.register_reset("core.title_experiments", reset_cache)  # #827
