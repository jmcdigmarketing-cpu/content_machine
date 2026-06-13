"""
One-time migration of runtime files from project root into data/ and config/secrets/.

Usage:
    py -m storage.migrate_layout
"""

from __future__ import annotations

import os

from config.paths import (
    CHANNEL_MEMORY_FILE,
    DEFAULT_CLIENT_SECRETS,
    DEFAULT_OAUTH_TOKEN,
    PERFORMANCE_MEMORY_FILE,
    SECRETS_DIR,
    SIGNAL_CACHE_FILE,
    YOUTUBE_QUOTA_FILE,
    ensure_data_dir,
    ensure_secrets_dir,
    migrate_file_if_needed,
)


def main() -> int:
    ensure_data_dir()
    ensure_secrets_dir()

    moves = [
        (SIGNAL_CACHE_FILE, "signal_cache.json"),
        (CHANNEL_MEMORY_FILE, "channel_memory.json"),
        (PERFORMANCE_MEMORY_FILE, "performance_memory.json"),
        (YOUTUBE_QUOTA_FILE, "youtube_quota.json"),
        (DEFAULT_CLIENT_SECRETS, "client_secrets.json"),
        (DEFAULT_OAUTH_TOKEN, "youtube_token.json"),
        (os.path.join(SECRETS_DIR, "youtube_token_tapin.json"), "youtube_token_tapin.json"),
    ]

    done = 0
    for preferred, legacy in moves:
        before = __import__("os").path.exists(preferred)
        migrate_file_if_needed(preferred, legacy)
        if not before and __import__("os").path.exists(preferred):
            done += 1
            print(f"Moved {legacy} -> {preferred}")

    print(f"Layout migration complete ({done} file(s) moved).")
    print("Channel config: config/channels.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
