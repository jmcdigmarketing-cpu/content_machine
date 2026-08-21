"""
YouTube OAuth credentials — per-channel token files with refresh.
"""

from __future__ import annotations

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config.channels import get_channel_profile, resolve_channel_id
from config.paths import (
    DEFAULT_CLIENT_SECRETS,
    DEFAULT_OAUTH_TOKEN,
    migrate_file_if_needed,
)
from core.logging import get_logger
from youtube.constants import (
    OAUTH_SCOPES_FULL,
    OAUTH_SCOPES_UPLOAD,
    SCOPE_YT_ANALYTICS_READONLY,
)

logger = get_logger("youtube.oauth")


def oauth_scopes(*, include_analytics: bool = True) -> list[str]:
    return list(OAUTH_SCOPES_FULL if include_analytics else OAUTH_SCOPES_UPLOAD)


def _client_secrets_path() -> str:
    env = os.getenv("YOUTUBE_OAUTH_CLIENT_SECRETS")
    if env:
        return env
    migrate_file_if_needed(DEFAULT_CLIENT_SECRETS, "client_secrets.json")
    return DEFAULT_CLIENT_SECRETS


def token_path_for_channel(channel_id: str | None = None) -> str:
    channel_id = resolve_channel_id(channel_id)
    profile = get_channel_profile(channel_id)
    if profile.youtube_oauth_token_file:
        return profile.youtube_oauth_token_file
    env = os.getenv("YOUTUBE_OAUTH_TOKEN_FILE")
    if env:
        return env
    migrate_file_if_needed(DEFAULT_OAUTH_TOKEN, "youtube_token.json")
    return DEFAULT_OAUTH_TOKEN


def _scopes_from_token_file(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        scopes = data.get("scopes") or []
        return list(scopes)
    except (OSError, json.JSONDecodeError):
        return list(OAUTH_SCOPES_FULL)


def live_youtube_forbidden() -> bool:
    """Suite isolation (audit C9): never open googleapis HTTPS during tests."""
    return os.getenv("CONTENT_FORBID_LIVE_YOUTUBE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def load_credentials(channel_id: str | None = None) -> Credentials | None:
    path = token_path_for_channel(channel_id)
    if not os.path.isfile(path):
        return None

    scopes = _scopes_from_token_file(path)
    creds = Credentials.from_authorized_user_file(path, scopes)
    if creds.expired and creds.refresh_token:
        if live_youtube_forbidden():
            logger.debug("OAuth refresh skipped (live YouTube forbidden)")
            return None
        try:
            creds.refresh(Request())
            save_credentials(creds, channel_id)
            logger.info("Refreshed YouTube OAuth token for %s", resolve_channel_id(channel_id))
        except Exception as e:
            logger.error("OAuth refresh failed: %s", e)
            return None
    return creds if creds.valid else None


def token_has_scope(channel_id: str | None, scope: str) -> bool:
    path = token_path_for_channel(channel_id)
    if not os.path.isfile(path):
        return False
    return scope in _scopes_from_token_file(path)


def save_credentials(creds: Credentials, channel_id: str | None = None) -> str:
    path = token_path_for_channel(channel_id)
    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or oauth_scopes()),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def get_youtube_service(channel_id: str | None = None):
    if live_youtube_forbidden():
        logger.debug("live YouTube client forbidden (C9)")
        return None
    creds = load_credentials(channel_id)
    if not creds:
        return None
    return build("youtube", "v3", credentials=creds, cache_discovery=False, static_discovery=True)


def get_youtube_analytics_service(channel_id: str | None = None):
    if live_youtube_forbidden():
        logger.debug("live YouTube Analytics client forbidden (C9)")
        return None
    creds = load_credentials(channel_id)
    if not creds:
        return None
    if SCOPE_YT_ANALYTICS_READONLY not in (creds.scopes or []):
        logger.warning(
            "Token missing yt-analytics.readonly — re-run: "
            "py -m youtube.oauth_setup --channel %s",
            resolve_channel_id(channel_id),
        )
        return None
    return build(
        "youtubeAnalytics", "v2", credentials=creds, cache_discovery=False, static_discovery=True
    )


def run_interactive_oauth(
    channel_id: str | None = None,
    *,
    include_analytics: bool = True,
) -> str:
    """First-time OAuth — run: py -m youtube.oauth_setup --channel tapin"""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets = _client_secrets_path()
    if not os.path.isfile(secrets):
        raise FileNotFoundError(
            f"Missing {secrets}. Download OAuth client JSON from Google Cloud Console."
        )

    channel_id = resolve_channel_id(channel_id)
    scopes = oauth_scopes(include_analytics=include_analytics)
    flow = InstalledAppFlow.from_client_secrets_file(secrets, scopes)
    creds = flow.run_local_server(port=0)
    path = save_credentials(creds, channel_id)
    print(f"Token saved for channel '{channel_id}': {path}")
    print(f"  Scopes: {', '.join(scopes)}")
    return path
