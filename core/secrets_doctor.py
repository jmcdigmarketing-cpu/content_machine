"""ops secrets-doctor (candidate 96).

Keys present / missing / placeholder. Never copies values into traces, HTML, or
logs. Nested try. File presence only for OAuth — token contents are not read.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.secrets_doctor")

# Env names only — values are never returned from gather/render.
# Required: Standard-mode floor (router + paid TTS + Apify + YouTube).
# Optional: unused slots must not FAIL `ops doctor`.
REQUIRED_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
    "ELEVEN_API_KEY",
    "APIFY_CONTENT_MACHINE_KEY",
    "YOUTUBE_API_KEY",
)
OPTIONAL_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "NEWS_API_KEY",
)
_ENV_KEYS = REQUIRED_ENV_KEYS + OPTIONAL_ENV_KEYS

_PLACEHOLDERS = frozenset(
    {
        "",
        "changeme",
        "change-me",
        "your-key",
        "your_key",
        "xxx",
        "todo",
        "none",
        "null",
        "example",
        "placeholder",
    }
)


def classify_secret(value: str | None) -> str:
    """present | missing | placeholder. Never echoes the value."""
    raw = "" if value is None else str(value).strip()
    if not raw:
        return "missing"
    low = raw.lower()
    if low in _PLACEHOLDERS or low.startswith("your-") or "example.com" in low:
        return "placeholder"
    if len(raw) < 8:
        return "placeholder"
    return "present"


def _oauth_files(channel_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from youtube.oauth import _client_secrets_path, token_path_for_channel

        secrets = _client_secrets_path()
        token = token_path_for_channel(channel_id)
        rows.append(
            {
                "name": "client_secrets.json",
                "status": "present" if os.path.isfile(secrets) else "missing",
            }
        )
        rows.append(
            {
                "name": f"oauth token ({channel_id})",
                "status": "present" if os.path.isfile(token) else "missing",
            }
        )
    except Exception as exc:
        logger.debug("secrets-doctor oauth paths skipped: %s", exc)
        rows.append({"name": "oauth files", "status": "n/a"})
    return rows


def gather(channel_id: str = "tapin") -> dict[str, Any]:
    keys: list[dict[str, str]] = []
    required = frozenset(REQUIRED_ENV_KEYS)
    for name in _ENV_KEYS:
        status = classify_secret(os.getenv(name))
        keys.append(
            {
                "name": name,
                "status": status,
                "required": "yes" if name in required else "no",
            }
        )
    files = _oauth_files(channel_id)
    present = sum(1 for k in keys if k["status"] == "present")
    missing = sum(1 for k in keys if k["status"] == "missing")
    placeholder = sum(1 for k in keys if k["status"] == "placeholder")
    required_missing = sum(1 for k in keys if k["required"] == "yes" and k["status"] == "missing")
    optional_missing = sum(1 for k in keys if k["required"] == "no" and k["status"] == "missing")
    return {
        "channel_id": channel_id,
        "keys": keys,
        "files": files,
        "present": present,
        "missing": missing,
        "placeholder": placeholder,
        "required_missing": required_missing,
        "optional_missing": optional_missing,
    }


def render(data: dict[str, Any] | None = None, *, channel_id: str = "tapin") -> str:
    data = data or gather(channel_id)
    lines = [
        f"ops secrets-doctor - {data.get('channel_id') or channel_id}",
        "=" * 48,
        (
            f"  env keys: {data.get('present', 0)} present, "
            f"{data.get('required_missing', 0)} required missing, "
            f"{data.get('optional_missing', 0)} optional missing, "
            f"{data.get('placeholder', 0)} placeholder"
        ),
        "  (values never printed)",
    ]
    for row in data.get("keys") or []:
        opt = "" if row.get("required") == "yes" else " (optional)"
        lines.append(f"  [{row.get('status')}] {row.get('name')}{opt}")
    for row in data.get("files") or []:
        lines.append(f"  [{row.get('status')}] {row.get('name')}")
    blob = "\n".join(lines)
    for row in data.get("keys") or []:
        val = os.getenv(str(row.get("name") or ""), "")
        if val and val in blob:
            return "ops secrets-doctor: refused to render (value leak guarded)"
    return blob
