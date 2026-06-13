"""
Show analytics-learned post schedule vs static channels.json schedule.

Usage:
    py -m analytics.learn_schedule --channel tapin
"""

from __future__ import annotations

import argparse
import json

from analytics.post_timing import (
    _load_static_post_schedule,
    learn_slots_from_analytics,
)
from config.channels import resolve_channel_id


def _slots_to_json(schedule) -> dict:
    return {
        "timezone": schedule.timezone,
        "default_slots": [
            {"weekday": s.weekday, "hour": s.hour, "minute": s.minute} for s in schedule.slots
        ],
        "domain_slots": {
            domain: [{"weekday": s.weekday, "hour": s.hour, "minute": s.minute} for s in slots]
            for domain, slots in (schedule.domain_slots or {}).items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Show learned post schedule")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args()

    channel_id = resolve_channel_id(args.channel)
    static = _load_static_post_schedule(channel_id)
    learned = learn_slots_from_analytics(channel_id)

    print(f"\nChannel: {channel_id}")
    print("=" * 50)
    print("Static (channels.json):")
    print(json.dumps(_slots_to_json(static), indent=2))
    print()
    if learned:
        print("Learned (publish_log engagement by hour):")
        print(json.dumps(_slots_to_json(learned), indent=2))
    else:
        print("Learned: not enough timed publish outcomes (need 8+ with published_at).")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
