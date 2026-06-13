"""Run once per channel to create OAuth token (upload + optional analytics)."""

import argparse

from youtube.oauth import run_interactive_oauth


def main():
    parser = argparse.ArgumentParser(description="YouTube OAuth setup for Content OS")
    parser.add_argument("--channel", default="tapin", help="Channel id from channels.json")
    parser.add_argument(
        "--upload-only",
        action="store_true",
        help="Request youtube.upload scope only (no analytics)",
    )
    args = parser.parse_args()
    run_interactive_oauth(
        args.channel,
        include_analytics=not args.upload_only,
    )


if __name__ == "__main__":
    main()
