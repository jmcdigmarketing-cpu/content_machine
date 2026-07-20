"""Canonical paths for config, secrets, and local runtime data."""

from __future__ import annotations

import os
import shutil

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SECRETS_DIR = os.path.join(ROOT_DIR, "config", "secrets")
CHANNELS_FILE = os.path.join(ROOT_DIR, "config", "channels.json")
VOICES_FILE = os.path.join(ROOT_DIR, "config", "voices.json")
LUFFY_ASCII_FILE = os.path.join(ROOT_DIR, "core", "data", "luffy_ascii.txt")

SIGNAL_CACHE_FILE = os.path.join(DATA_DIR, "signal_cache.json")
CHANNEL_MEMORY_FILE = os.path.join(DATA_DIR, "channel_memory.json")
PERFORMANCE_MEMORY_FILE = os.path.join(DATA_DIR, "performance_memory.json")
YOUTUBE_QUOTA_FILE = os.path.join(DATA_DIR, "youtube_quota.json")
QUOTA_STATE_FILE = os.path.join(DATA_DIR, "quota_state.json")
CACHE_STATS_FILE = os.path.join(DATA_DIR, "cache_stats.json")
EXPERIMENTS_FILE = os.path.join(DATA_DIR, "experiments.json")
TRACES_DIR = os.path.join(DATA_DIR, "traces")

DEFAULT_CLIENT_SECRETS = os.path.join(SECRETS_DIR, "client_secrets.json")
DEFAULT_OAUTH_TOKEN = os.path.join(SECRETS_DIR, "youtube_token.json")


def ensure_data_dir() -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


def ensure_secrets_dir() -> str:
    os.makedirs(SECRETS_DIR, exist_ok=True)
    return SECRETS_DIR


def resolve_existing_path(preferred: str, *legacy_paths: str) -> str:
    """Prefer the new path; fall back to legacy root files if present."""
    if os.path.exists(preferred):
        return preferred
    for path in legacy_paths:
        if path and os.path.exists(path):
            return path
    return preferred


def migrate_file_if_needed(preferred: str, legacy_path: str) -> None:
    """Move a legacy root file into data/ or config/secrets/ once."""
    if not legacy_path or legacy_path == preferred:
        return
    if os.path.exists(preferred) or not os.path.exists(legacy_path):
        return
    os.makedirs(os.path.dirname(preferred), exist_ok=True)
    shutil.move(legacy_path, preferred)
