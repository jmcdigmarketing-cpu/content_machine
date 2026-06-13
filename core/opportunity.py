"""
Topic opportunity scorer — standalone decision layer (CLI / API ready).

Gathers signals and computes the same composite score as the content pipeline,
without stdin or interactive CLI coupling.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from apis.register_signals import build_registry
from apis.topic_scorer import composite_score, get_weights, infer_domain
from config.channels import resolve_channel_id
from core.logging import get_logger, setup_logging
from core.opportunity_angles import recommended_angles

logger = get_logger("opportunity")


@dataclass
class OpportunityScore:
    """Public result of score_topic — suitable for HTTP serialization later."""

    topic: str
    channel_id: str
    composite_score: float
    domain: str
    signal_breakdown: dict[str, float]
    recommended_angles: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def signal_breakdown(
    signals: dict[str, Any],
    topic: str,
    channel_id: str | None = None,
) -> dict[str, float]:
    """
    Per-signal weighted contribution toward the composite (before memory/domain boosts).

    Values are ``score * weight / total_weight`` for each active connected signal.
    Mirrors the weighting loop in apis.topic_scorer.composite_score.
    """
    channel_id = resolve_channel_id(channel_id)
    domain = infer_domain(topic, channel_id)
    weights = get_weights(domain, channel_id)

    weighted_parts: dict[str, float] = {}
    total_weight = 0.0

    for key, weight in weights.items():
        signal = signals.get(key)
        if not signal or not signal.get("connected") or not signal.get("active"):
            continue

        score = max(0, min(float(signal.get("score", 0)), 100))
        total_weight += weight
        weighted_parts[key] = score * weight

    if total_weight == 0:
        return {}

    return {
        key: round((score_part / total_weight), 4) for key, score_part in weighted_parts.items()
    }


def score_topic(topic: str, channel_id: str | None = None) -> OpportunityScore:
    """
    Score a single topic for a channel: signals + composite + angles.

    Uses build_registry and composite_score — same inputs as run_discovery's
    base-topic scoring path.
    """
    channel_id = resolve_channel_id(channel_id)
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic must be non-empty")

    t0 = time.perf_counter()
    signals = build_registry(topic)
    timings = {"signals": time.perf_counter() - t0}

    domain = infer_domain(topic, channel_id)
    breakdown = signal_breakdown(signals, topic, channel_id)
    score = composite_score(signals, topic, channel_id)

    t1 = time.perf_counter()
    angles = recommended_angles(topic, domain=domain, channel_id=channel_id)
    timings["angles"] = time.perf_counter() - t1

    return OpportunityScore(
        topic=topic,
        channel_id=channel_id,
        composite_score=score,
        domain=domain,
        signal_breakdown=breakdown,
        recommended_angles=angles,
        timings=timings,
    )


def _cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a topic opportunity (signals + composite)")
    parser.add_argument("--topic", required=True, help="Topic string to score")
    parser.add_argument(
        "--channel",
        default=None,
        help="Channel profile id (default: CONTENT_CHANNEL_ID or default)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON to stdout (default: pretty JSON via logging)",
    )
    args = parser.parse_args(argv)

    setup_logging()
    result = score_topic(args.topic, channel_id=args.channel)
    payload = result.to_dict()

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        logger.info("%s", json.dumps(payload, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
