"""
YouTube OAuth credentials — per-channel token files with refresh.
"""

from __future__ import annotations

import json
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from config.channels import get_channel_profile, resolve_channel_id
from config.paths import (
    DEFAULT_CLIENT_SECRETS,
    DEFAULT_OAUTH_TOKEN,
    migrate_file_if_needed,
)
from core import process_state
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


# #961: token file path -> (its mtime, what to tell the operator) after Google refused the
# token for good (`invalid_grant`). A refused token never comes back, so this process does not
# ask again - one error, not one per video - until the token file changes (oauth_setup).
_SIGN_IN_PROBLEMS: dict[str, tuple[float, str]] = {}


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return -1.0


def _revoked_message(channel_id: str) -> str:
    return (
        f"YouTube sign-in for {channel_id} has expired or been revoked - run: "
        f"py -m youtube.oauth_setup --channel {channel_id}. If it expires again in about a "
        "week, the Google Cloud OAuth consent screen is in Testing: publish it (In production) "
        "with the policy site's home page and privacy links (docs/platform_publish_setup.md)."
    )


def _reset_sign_in_problems() -> None:
    _SIGN_IN_PROBLEMS.clear()


process_state.register_reset("youtube.oauth", _reset_sign_in_problems)


def sign_in_problem(channel_id: str | None = None) -> str:
    """Why the channel's YouTube sign-in is refused (#961), or "" - cleared when the token
    file changes."""
    path = token_path_for_channel(channel_id)
    known = _SIGN_IN_PROBLEMS.get(path)
    if known and known[0] == _mtime(path):
        return known[1]
    return ""


def load_credentials(channel_id: str | None = None) -> Credentials | None:
    path = token_path_for_channel(channel_id)
    if not os.path.isfile(path):
        return None
    if sign_in_problem(channel_id):
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
        except RefreshError as e:
            if "invalid_grant" not in str(e):
                logger.error("OAuth refresh failed: %s", e)
                return None
            message = _revoked_message(resolve_channel_id(channel_id))
            _SIGN_IN_PROBLEMS[path] = (_mtime(path), message)
            logger.error("%s", message)
            return None
        except Exception as e:
            logger.error("OAuth refresh failed: %s", e)
            return None
    return creds if creds.valid else None


def sign_in_status(channel_id: str | None = None) -> str:
    """#971: "" when the channel's YouTube sign-in works for uploads and analytics, else one
    line naming what is wrong and the command that fixes it. May refresh the token."""
    cid = resolve_channel_id(channel_id)
    fix = f"py -m youtube.oauth_setup --channel {cid}"
    path = token_path_for_channel(cid)
    if not os.path.isfile(path):
        return f"No YouTube sign-in for {cid} ({path}) - run: {fix}"
    if SCOPE_YT_ANALYTICS_READONLY not in _scopes_from_token_file(path):
        return f"YouTube sign-in for {cid} lacks the analytics permission - run: {fix}"
    if load_credentials(cid) is None:
        return sign_in_problem(cid) or f"YouTube sign-in for {cid} is not usable - run: {fix}"
    return ""


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
    _SIGN_IN_PROBLEMS.pop(path, None)
    return path


def get_youtube_service(channel_id: str | None = None):
    if live_youtube_forbidden():
        logger.debug("live YouTube client forbidden (C9)")
        return None
    creds = load_credentials(channel_id)
    if not creds:
        return None
    from googleapiclient.discovery import build

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
            "Token missing yt-analytics.readonly — re-run: py -m youtube.oauth_setup --channel %s",
            resolve_channel_id(channel_id),
        )
        return None
    from googleapiclient.discovery import build

    return build(
        "youtubeAnalytics", "v2", credentials=creds, cache_discovery=False, static_discovery=True
    )


def get_youtube_reporting_service(channel_id: str | None = None):
    """The YouTube Reporting API (bulk reports) - thumbnail impressions and click-through
    (#951). Same token and `yt-analytics.readonly` scope as the Analytics client."""
    if live_youtube_forbidden():
        logger.debug("live YouTube Reporting client forbidden (C9)")
        return None
    creds = load_credentials(channel_id)
    if not creds:
        return None
    if SCOPE_YT_ANALYTICS_READONLY not in (creds.scopes or []):
        return None
    from googleapiclient.discovery import build

    return build(
        "youtubereporting", "v1", credentials=creds, cache_discovery=False, static_discovery=True
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
