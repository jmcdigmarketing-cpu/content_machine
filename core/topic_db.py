"""Topic Winners + Graveyard — a per-topic performance view over run history.

The data already exists (`content_runs` joined to `publish_log` engagement); this
aggregates it *by topic* so the operator can see:

  - **Winners** — topics whose published videos actually engaged, ranked. The
    "clone a winner" surface.
  - **Graveyard** — topics that measurably flopped (avg engaged-rate below a
    floor). Wired into best-bet as an avoid-list so discovery stops re-pitching
    proven losers.

Confidence still matters (a 1-video average is thin), so callers see the measured
sample count and can raise `min_measured`. Read-only and best-effort: any storage
error yields an empty view rather than raising.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.channel_context import normalize_seed_topic
from core.engagement import engaged_rate, safe_infer_domain
from core.logging import get_logger

logger = get_logger("core.topic_db")


@dataclass
class TopicRecord:
    topic: str
    domain: str
    runs: int  # total runs for this topic seed
    measured: int  # runs with engagement data behind them
    avg_engaged_rate: float | None
    best_engaged_rate: float | None
    last_status: str


def _topic_records(channel_id: str) -> list[TopicRecord]:
    try:
        from storage.repositories.content_runs import get_content_run_repository
        from storage.repositories.publish_log import get_publish_log_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("topic_db load failed: %s", exc)
        return []
    if not runs:
        return []

    log_by_run = {log.content_run_id: log for log in logs}
    agg: dict[str, dict] = {}
    for run in runs:  # newest first
        seed = normalize_seed_topic(run.input_topic or run.selected_topic or "")
        if not seed:
            continue
        bucket = agg.setdefault(seed, {"rates": [], "runs": 0, "status": "", "domain": None})
        bucket["runs"] += 1
        if not bucket["status"]:  # newest run sets the last-known status
            bucket["status"] = run.status or ""
        if bucket["domain"] is None:
            bucket["domain"] = safe_infer_domain(seed, channel_id)
        log = log_by_run.get(run.id)
        rate = engaged_rate(log.metrics_json) if log else None
        if rate is not None:
            bucket["rates"].append(rate)

    records: list[TopicRecord] = []
    for topic, b in agg.items():
        rates = b["rates"]
        records.append(
            TopicRecord(
                topic=topic,
                domain=b["domain"] or "neutral",
                runs=b["runs"],
                measured=len(rates),
                avg_engaged_rate=(sum(rates) / len(rates)) if rates else None,
                best_engaged_rate=max(rates) if rates else None,
                last_status=b["status"],
            )
        )
    return records


def _graveyard_floor() -> float:
    try:
        return float(os.getenv("GRAVEYARD_RATE_FLOOR", "0.04"))
    except ValueError:
        return 0.04


def winners(channel_id: str, n: int = 10, *, min_measured: int = 1) -> list[TopicRecord]:
    """Top topics by average engaged-rate (only those with engagement data)."""
    recs = [
        r
        for r in _topic_records(channel_id)
        if r.measured >= min_measured and r.avg_engaged_rate is not None
    ]
    recs.sort(key=lambda r: (r.avg_engaged_rate or 0.0, r.measured), reverse=True)
    return recs[:n]


def graveyard(channel_id: str, n: int = 25, *, min_measured: int = 1) -> list[TopicRecord]:
    """Topics that measurably flopped — avg engaged-rate below the floor."""
    floor = _graveyard_floor()
    recs = [
        r
        for r in _topic_records(channel_id)
        if r.measured >= min_measured
        and r.avg_engaged_rate is not None
        and r.avg_engaged_rate < floor
    ]
    recs.sort(key=lambda r: r.avg_engaged_rate or 0.0)  # worst first
    return recs[:n]


def graveyard_topics(channel_id: str) -> set[str]:
    """Normalized topics to avoid re-suggesting. Empty when the avoid-list is off."""
    if os.getenv("GRAVEYARD_AVOID", "true").lower() not in ("1", "true", "yes"):
        return set()
    return {r.topic for r in graveyard(channel_id, n=200)}


def display_winners(recs: list[TopicRecord], *, print_fn=print) -> None:
    from core.recommender_confidence import confidence_note

    if not recs:
        print_fn("\n  Topic Winners: (no engagement data yet)")
        return
    print_fn("\n  🏆 Topic Winners (clone these):")
    for i, r in enumerate(recs, 1):
        rate = f"{r.avg_engaged_rate:.0%}" if r.avg_engaged_rate is not None else "—"
        print_fn(
            f"    {i}. [{r.domain}] {r.topic}\n"
            f"       {rate} avg engagement{confidence_note(r.measured)}"
        )


def display_graveyard(recs: list[TopicRecord], *, print_fn=print) -> None:
    if not recs:
        print_fn("\n  ⚰ Topic Graveyard: (nothing below the floor — good)")
        return
    floor = _graveyard_floor()
    print_fn(f"\n  ⚰ Topic Graveyard (avoided — below {floor:.0%} engagement):")
    for i, r in enumerate(recs, 1):
        rate = f"{r.avg_engaged_rate:.0%}" if r.avg_engaged_rate is not None else "—"
        print_fn(f"    {i}. [{r.domain}] {r.topic} — {rate}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Topic Winners + Graveyard")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args(argv)
    display_winners(winners(args.channel, args.n), print_fn=print)
    display_graveyard(graveyard(args.channel), print_fn=print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
