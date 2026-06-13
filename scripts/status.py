"""CLI status view — Phase J minimal."""

from __future__ import annotations

import argparse

from config.channels import resolve_channel_id
from core.status import build_status_lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Content OS channel status")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    print(f"\nStatus — {channel_id}\n")
    for line in build_status_lines(channel_id):
        print(f"  {line}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
