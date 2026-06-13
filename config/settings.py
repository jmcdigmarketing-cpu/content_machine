import os
from functools import lru_cache

from config.paths import DEFAULT_CLIENT_SECRETS, DEFAULT_OAUTH_TOKEN


def _load_dotenv() -> None:
    """
    Load the project .env into os.environ without overriding existing variables.

    Uses python-dotenv, which correctly handles quoting, inline comments,
    `export` prefixes, and multi-line values — previously a hand-rolled parser
    that mis-read inline comments lived here.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.isfile(path):
        return
    from dotenv import load_dotenv

    load_dotenv(path, override=False)


_load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL") or os.getenv("DATABASE_KEY") or ""
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    youtube_daily_quota: int = int(os.getenv("YOUTUBE_DAILY_QUOTA", "10000"))
    content_skip_signals: str = os.getenv("CONTENT_SKIP_SIGNALS", "")
    youtube_upload_enabled: bool = os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )
    youtube_oauth_client_secrets: str = (
        os.getenv("YOUTUBE_OAUTH_CLIENT_SECRETS") or DEFAULT_CLIENT_SECRETS
    )
    youtube_oauth_token_file: str = os.getenv("YOUTUBE_OAUTH_TOKEN_FILE") or DEFAULT_OAUTH_TOKEN
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")
    pixabay_api_key: str = os.getenv("PIXABAY_API_KEY", "")
    flux_api_key: str = os.getenv("FLUX_API_KEY", "")
    asset_provider_order: tuple = tuple(
        p.strip().lower()
        for p in os.getenv("ASSET_PROVIDER_ORDER", "local,pexels,pixabay").split(",")
        if p.strip()
    )
    background_mode: str = os.getenv("BACKGROUND_MODE", "hybrid").strip().lower() or "hybrid"
    content_channel_id: str = os.getenv("CONTENT_CHANNEL_ID", "default").strip() or "default"
    channel_intro_enabled: bool = os.getenv("CHANNEL_INTRO_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    thumbnail_scorer_enabled: bool = os.getenv("THUMBNAIL_SCORER_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )
    repurpose_publish_enabled: bool = os.getenv("REPURPOSE_PUBLISH_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
