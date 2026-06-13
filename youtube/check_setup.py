"""
Validate YouTube upload + analytics OAuth readiness for a channel.

Usage:
    py -m youtube.check_setup --channel tapin
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from config.channels import get_channel_profile, resolve_channel_id
from youtube.constants import SCOPE_YOUTUBE_UPLOAD, SCOPE_YT_ANALYTICS_READONLY
from youtube.oauth import (
    _client_secrets_path,
    load_credentials,
    token_has_scope,
    token_path_for_channel,
)
from youtube.upload import is_upload_configured


@dataclass
class SetupReport:
    channel_id: str
    ok: bool
    issues: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)


def check_channel_setup(channel_id: str | None = None) -> SetupReport:
    channel_id = resolve_channel_id(channel_id)
    profile = get_channel_profile(channel_id)
    issues: list[str] = []
    hints: list[str] = []

    secrets = _client_secrets_path()
    token_path = token_path_for_channel(channel_id)

    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        issues.append("YOUTUBE_UPLOAD_ENABLED is not true in .env")
        hints.append("Set YOUTUBE_UPLOAD_ENABLED=true in .env")

    if not os.path.isfile(secrets):
        issues.append(f"Missing OAuth client secrets: {secrets}")
        hints.append("Download OAuth 2.0 Desktop client JSON from Google Cloud Console")

    if not os.path.isfile(token_path):
        issues.append(f"Missing token file: {token_path}")
        hints.append(f"Run: py -m youtube.oauth_setup --channel {channel_id}")
    else:
        if not token_has_scope(channel_id, SCOPE_YOUTUBE_UPLOAD):
            issues.append("Token missing youtube.upload scope")
            hints.append(f"Re-run: py -m youtube.oauth_setup --channel {channel_id}")
        if not token_has_scope(channel_id, SCOPE_YT_ANALYTICS_READONLY):
            issues.append("Token missing yt-analytics.readonly scope (metrics sync)")
            hints.append(f"Re-run with analytics: py -m youtube.oauth_setup --channel {channel_id}")

    creds = load_credentials(channel_id)
    if token_path and os.path.isfile(token_path) and not creds:
        issues.append("Token file exists but credentials are invalid or expired")

    if os.getenv("YOUTUBE_ANALYTICS_SYNC", "").lower() in ("1", "true", "yes"):
        if not token_has_scope(channel_id, SCOPE_YT_ANALYTICS_READONLY):
            issues.append("YOUTUBE_ANALYTICS_SYNC is on but analytics scope missing")

    hints.append(f"Channel: {profile.name} ({channel_id})")
    hints.append(f"Token path: {token_path}")
    hints.append("Worker: py -m jobs.worker --loop 30")

    if not issues and not is_upload_configured(channel_id):
        issues.append(
            "Upload not enabled or paths incomplete "
            "(set YOUTUBE_UPLOAD_ENABLED=true and verify config/secrets/)"
        )

    return SetupReport(
        channel_id=channel_id,
        ok=len(issues) == 0,
        issues=issues,
        hints=hints,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Check YouTube OAuth/upload setup")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args()

    report = check_channel_setup(args.channel)
    print(f"\nYouTube setup — {report.channel_id}")
    print("=" * 50)
    if report.ok:
        print("  Status: READY for upload")
    else:
        print("  Status: NOT READY")
        print("\n  Issues:")
        for item in report.issues:
            print(f"    - {item}")
    print("\n  Notes:")
    for hint in report.hints:
        print(f"    {hint}")
    print()
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
