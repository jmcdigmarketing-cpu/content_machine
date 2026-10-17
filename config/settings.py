import logging
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
    # #930: the test suite sets this, so it sees what CI sees (no keys), not the operator's .env.
    if os.getenv("CONTENT_SKIP_DOTENV", "").strip().lower() in ("1", "true", "yes"):
        return
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.isfile(path):
        return
    load_env_file(path)


def _not_dotenv_parse_warning(record: logging.LogRecord) -> bool:
    return "could not parse" not in str(record.msg)


def load_env_file(path: str) -> None:
    """Load ``path`` into os.environ without overriding what is set (#1218).

    python-dotenv's own "could not parse statement starting at line N" names the line *before*
    a bad one - line 34 of the operator's .env is blank; the lines that are not NAME=value are
    35, 36 and 39 - and it said so on every command. Its record is muted; the lines are named
    once, by number, by the check `ops doctor` runs (`core/secrets_doctor`, #1193).
    """
    from dotenv import load_dotenv

    dotenv_log = logging.getLogger("dotenv.main")
    dotenv_log.addFilter(_not_dotenv_parse_warning)
    try:
        load_dotenv(path, override=False)
    finally:
        dotenv_log.removeFilter(_not_dotenv_parse_warning)
    # #1265: once a run - overnight's log said it four times, once per draft child. The marker
    # is in the environment, so the children the run starts inherit it.
    if os.environ.get("CONTENT_ENV_LINES_SAID") == "1":
        return
    try:
        from core.secrets_doctor import env_file_line, env_file_problems

        line = env_file_line(env_file_problems(path))
    except Exception:
        line = ""
    if line:
        logging.getLogger("config.settings").warning(line)
        os.environ["CONTENT_ENV_LINES_SAID"] = "1"


_load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL") or os.getenv("DATABASE_KEY") or ""
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    # Multi-provider LLM keys (routed via core/llm_router.py). Free-first:
    # DeepSeek + Doubao anchor the cheap/extract/premium tiers; OpenAI/Anthropic
    # stay as opt-in premium upgrades. All optional — router degrades gracefully.
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    doubao_api_key: str = os.getenv("DOUBAO_API_KEY", "") or os.getenv("ARK_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
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
    coverr_api_key: str = os.getenv("COVERR_API_KEY", "")
    flux_api_key: str = os.getenv("FLUX_API_KEY", "")
    asset_provider_order: tuple = tuple(
        p.strip().lower()
        for p in os.getenv("ASSET_PROVIDER_ORDER", "local,pexels,pixabay,coverr").split(",")
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
