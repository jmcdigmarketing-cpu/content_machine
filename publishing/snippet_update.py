"""Update a live video's snippet without dropping what YouTube requires (#865 / #873).

`videos.update(part="snippet")` replaces the whole snippet: YouTube rejects the call
without `title` and `categoryId`, and anything writable that is not sent is cleared.
`rollback-publish` sent a description alone. Every snippet change goes through here:
read the live snippet, keep its writable fields, apply the change, send all of it.
"""

from __future__ import annotations

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
