"""
Print learned signal weights for a channel (from performance memory).

Usage:
    py -m analytics.compute_weights --channel tapin
"""

from __future__ import annotations

import argparse
import json

from apis.learned_weights import compute_profile_from_performance
from apis.topic_scorer import get_weights
from config.channels import resolve_channel_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Show learned signal weights")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--domain", default="gaming")
    args = parser.parse_args()

    channel_id = resolve_channel_id(args.channel)
    learned = compute_profile_from_performance(channel_id)
    active = get_weights(args.domain, channel_id)

    print(f"\nChannel: {channel_id} | domain: {args.domain}")
    print("=" * 50)
    if learned:
        print("Performance-derived profile:")
        print(json.dumps(learned, indent=2, sort_keys=True))
    else:
        print("No performance-derived profile (need seed/analytics data).")

    print("\nActive weights used in scoring:")
    print(json.dumps(active, indent=2, sort_keys=True))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
