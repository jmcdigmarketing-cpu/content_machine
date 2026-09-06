"""
Recommended video length from engagement history.

Mirrors core.best_bet and analytics.post_timing: when enough published runs
carry real YouTube engagement, length presets are ranked by average engaged
rate and the best one is recommended. Otherwise it falls back to a sensible
per-domain default.

Each content run already persists which preset it used in timings_json
("length_preset"), so length is joined to engagement the same way best-bet
joins topics to engagement — no schema change required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from config.channels import resolve_channel_id
from core.engagement import engaged_rate as _engaged_rate
from core.engagement import safe_infer_domain as _infer_domain
from core.logging import get_logger
from core.recommender_confidence import confidence_note, interval_note
from core.script_length import PRESETS, get_length_preset

logger = get_logger("core.length_recommender")

_TOP_N = 40  # recent runs to analyse

# Fallback preset per domain when there isn't enough analytics yet.
_DEFAULT_BY_DOMAIN: dict[str, str] = {
    "gaming": "2",  # Medium — punchy gaming takes
    "ufc": "2",  # Medium
    "nba": "2",
    "nfl": "2",
    "neutral": "2",
}


@dataclass
class LengthRecommendation:
    length_choice: str  # "1".."4"
    label: str
    source: str  # "analytics" | "default"
    avg_engaged_rate: float  # 0.0 when no analytics
    supporting_runs: int
    rationale: str


def _length_choice_from_run(timings_json: str) -> str | None:
    """Extract the preset choice persisted at run time."""
    try:
        timings = json.loads(timings_json or "{}")
    except json.JSONDecodeError:
        return None
    choice = str(timings.get("length_preset") or "").strip()
    return choice if choice in PRESETS else None


def _collect_length_samples(channel_id: str) -> list[dict]:
    """Join recent runs (with a recorded length preset) to real engagement."""
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    run_repo = get_content_run_repository()
    log_repo = get_publish_log_repository()

    runs = run_repo.list_for_channel(channel_id)[:_TOP_N]
    if not runs:
        return []

    rate_by_run: dict[int, float] = {}
    for log in log_repo.list_timed_outcomes(channel_id):
        rate = _engaged_rate(log.metrics_json)
        if rate is not None and rate > 0:
            rate_by_run[log.content_run_id] = rate

    samples: list[dict] = []
    for run in runs:
        choice = _length_choice_from_run(run.timings_json)
        if not choice:
            continue
        rate = rate_by_run.get(run.id)
        if rate is None:
            continue
        samples.append({"length_choice": choice, "engaged_rate": rate})
    return samples


def get_recommended_length(
    channel_id: str,
    topic: str = "",
    *,
    min_total: int = 6,
    min_per_bucket: int = 3,
) -> LengthRecommendation:
    """
    Recommend a length preset using engagement history (analytics) when enough
    data exists, otherwise a per-domain default.
    """
    channel_id = resolve_channel_id(channel_id)
    domain = _infer_domain(topic, channel_id) if topic else "neutral"
    samples = _collect_length_samples(channel_id)

    if len(samples) >= min_total:
        rates: dict[str, list[float]] = {}
        for s in samples:
            rates.setdefault(s["length_choice"], []).append(s["engaged_rate"])

        # Only consider buckets with enough samples to be meaningful.
        eligible = {c: rs for c, rs in rates.items() if len(rs) >= min_per_bucket}
        pool = eligible or rates

        best_choice = max(pool, key=lambda c: sum(pool[c]) / len(pool[c]))
        best_rates = pool[best_choice]
        avg = sum(best_rates) / len(best_rates)
        preset = get_length_preset(best_choice)
        return LengthRecommendation(
            length_choice=best_choice,
            label=preset.label,
            source="analytics",
            avg_engaged_rate=avg,
            supporting_runs=len(best_rates),
            rationale=(
                f"{preset.label} ({preset.duration_hint()}) averages {avg:.1%} "
                f"engagement across {len(best_rates)} video(s)"
                f"{interval_note(best_rates)}"
                f"{confidence_note(len(best_rates))}"
            ),
        )

    if channel_id == "moneywise":
        donor = get_recommended_length("tapin", "")
        if donor.source == "analytics":
            return LengthRecommendation(
                length_choice=donor.length_choice,
                label=donor.label,
                source="cross_channel_prior",
                avg_engaged_rate=donor.avg_engaged_rate,
                supporting_runs=donor.supporting_runs,
                rationale=(
                    f"TapIn length shape as MoneyWise cold-start prior "
                    f"(option {donor.length_choice}) — not a gaming topic copy"
                ),
            )

    choice = _DEFAULT_BY_DOMAIN.get(domain, "2")
    preset = get_length_preset(choice)
    have = len(samples)
    need = max(0, min_total - have)
    rationale = (
        f"default {preset.label} for {domain} — {need} more measured video(s) "
        f"until length learns from analytics"
    )
    return LengthRecommendation(
        length_choice=choice,
        label=preset.label,
        source="default",
        avg_engaged_rate=0.0,
        supporting_runs=have,
        rationale=rationale,
    )


def display_recommended_length(rec: LengthRecommendation) -> None:
    """Print the recommended length, mirroring display_best_bet()."""
    tag = rec.source if rec.source in ("analytics", "cross_channel_prior") else "default"
    print(f"\n  Recommended length ({tag}): {rec.label} (option {rec.length_choice})")
    print(f"  Reason : {rec.rationale}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Recommend video length from history")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--topic", default="", help="Topic for domain-aware default")
    args = parser.parse_args()

    display_recommended_length(get_recommended_length(args.channel, args.topic))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
