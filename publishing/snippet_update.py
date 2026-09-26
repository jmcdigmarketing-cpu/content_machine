"""Update a live video's snippet without dropping what YouTube requires (#865 / #873).

`videos.update(part="snippet")` replaces the whole snippet: YouTube rejects the call
without `title` and `categoryId`, and anything writable that is not sent is cleared.
`rollback-publish` sent a description alone. Every snippet change goes through here:
read the live snippet, keep its writable fields, apply the change, send all of it.
"""

from __future__ import annotations

import os
from typing import Any

WRITABLE_KEYS = (
    "title",
    "description",
    "tags",
    "categoryId",
    "defaultLanguage",
    "defaultAudioLanguage",
)
_BATCH = 50  # videos.list takes at most 50 ids per call


def manage_scope_problem(channel_id: str | None) -> str:
    """Why an edit to a live video would be refused, or "" (#873 / #865 / #864).

    Uploading needs `youtube.upload`; editing a video's snippet or privacy needs
    `youtube`. Tokens made before #601 carry only the first, and YouTube answers 403
    "insufficient authentication scopes" - which the operator hit on go-public and
    recategorize. A missing token is left to the normal client error.
    """
    try:
        from youtube.constants import SCOPE_YOUTUBE_MANAGE
        from youtube.oauth import _scopes_from_token_file, token_path_for_channel

        path = token_path_for_channel(channel_id)
        if not os.path.isfile(path):
            return ""
        if SCOPE_YOUTUBE_MANAGE in _scopes_from_token_file(path):
            return ""
    except Exception:
        return ""
    ch = channel_id or "tapin"
    return (
        "your saved YouTube login can upload but not edit videos. Sign in again once: "
        f"py -m youtube.oauth_setup --channel {ch} (approve 'Manage your YouTube account'), "
        "then re-run this command"
    )


def edit_error_text(exc: Exception, channel_id: str | None) -> str:
    """YouTube's error, or the one-line fix when it is the missing edit permission."""
    text = str(exc)
    if "insufficient" in text.lower() and "scope" in text.lower():
        ch = channel_id or "tapin"
        return (
            "YouTube refused the edit: this login can upload but not edit videos. "
            f"Sign in again once: py -m youtube.oauth_setup --channel {ch}"
        )
    return text[:300]


def fetch_snippets(service, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """{video_id: live snippet} for the ids YouTube still has (1 quota unit per 50)."""
    out: dict[str, dict[str, Any]] = {}
    ids = [v for v in dict.fromkeys(video_ids) if v]
    for start in range(0, len(ids), _BATCH):
        chunk = ids[start : start + _BATCH]
        resp = service.videos().list(part="snippet", id=",".join(chunk)).execute() or {}
        for item in resp.get("items") or []:
            if item.get("id") and isinstance(item.get("snippet"), dict):
                out[str(item["id"])] = item["snippet"]
    return out


def writable_snippet(current: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """The live snippet's writable fields with `changes` applied; refuses a partial one."""
    merged = {k: current[k] for k in WRITABLE_KEYS if k in current}
    merged.update({k: v for k, v in changes.items() if k in WRITABLE_KEYS})
    missing = [k for k in ("title", "categoryId") if not str(merged.get(k) or "").strip()]
    if missing:
        raise ValueError(f"snippet update needs {', '.join(missing)}; refusing a partial snippet")
    return merged
