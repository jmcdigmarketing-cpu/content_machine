"""Buffer's GraphQL API: the calls TikTok and Instagram posting needs (#1185).

Operator, 2026-10-14: a `BUFFER_API_KEY` in `.env` and "automated instagram and tiktok
posting". Buffer's API (developers.buffer.com) is one POST endpoint taking a Bearer key. It
answers HTTP 200 for nearly everything, so success and failure are read from the body:

- a typed error in `data` (a `MutationError` with a `message`) is Buffer refusing the input -
  never retried as it is;
- `errors[].extensions.code` `UNAUTHORIZED` / `FORBIDDEN` is the key - stop, do not retry;
- HTTP 429 or `RATE_LIMIT_EXCEEDED` is the 100-per-15-minutes limit - wait `Retry-After`
  once, then leave it to the next run;
- anything else is unexpected - the next run tries again.

Media is never uploaded here: Buffer fetches a video from a public link (`video_host`).
`createPost` has no idempotency key, so `crosspost` records a call before it is made.
The key is never logged or put in an error message.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("publishing.buffer_api")

ENDPOINT = "https://api.buffer.com"
TIMEOUT_SECONDS = 30
# Longer than this and the wait is left to the next run rather than held here.
MAX_WAIT_SECONDS = 60.0


class BufferError(Exception):
    """kind: auth | rate_limited | input | not_found | unexpected | not_configured."""

    def __init__(self, kind: str, message: str = "", retry_after: float | None = None):
        super().__init__(message or kind)
        self.kind = kind
        self.message = message or kind
        self.retry_after = retry_after


def api_key() -> str:
    return os.getenv("BUFFER_API_KEY", "").strip()


def configured() -> bool:
    return bool(api_key())


def _retry_after(resp: Any) -> float:
    try:
        return max(0.0, float((getattr(resp, "headers", None) or {}).get("Retry-After") or 0))
    except (TypeError, ValueError):
        return 0.0


def _error_from_body(errors: list[dict[str, Any]]) -> BufferError:
    first = errors[0] if errors else {}
    code = str(((first or {}).get("extensions") or {}).get("code") or "").upper()
    message = str((first or {}).get("message") or code or "error")
    if code in ("UNAUTHORIZED", "FORBIDDEN"):
        return BufferError("auth", f"{code}: {message}")
    if code == "RATE_LIMIT_EXCEEDED":
        return BufferError("rate_limited", message)
    if code == "NOT_FOUND":
        return BufferError("not_found", message)
    return BufferError("unexpected", f"{code or 'error'}: {message}")


def graphql(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    post: Callable[..., Any] | None = None,
    sleep: Callable[[float], Any] = time.sleep,
) -> dict[str, Any]:
    """`data` of one GraphQL call; raises `BufferError`. Network errors propagate as
    `requests` exceptions - the caller decides whether a call may have gone through."""
    key = api_key()
    if not key:
        raise BufferError("not_configured", "BUFFER_API_KEY is not set")
    if post is None:
        import requests

        post = requests.post
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"query": query, "variables": variables or {}}
    resp = post(ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    if getattr(resp, "status_code", 200) == 429:
        wait = _retry_after(resp)
        if wait > MAX_WAIT_SECONDS:
            raise BufferError("rate_limited", f"Buffer asks to wait {wait:.0f}s", wait)
        sleep(wait)
        resp = post(ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
        if getattr(resp, "status_code", 200) == 429:
            raise BufferError("rate_limited", "Buffer's request limit", _retry_after(resp))
    status = int(getattr(resp, "status_code", 200) or 200)
    if status in (401, 403):
        raise BufferError("auth", f"HTTP {status}")
    try:
        body = resp.json()
    except ValueError as exc:
        raise BufferError("unexpected", f"HTTP {status}: not JSON") from exc
    if not isinstance(body, dict):
        raise BufferError("unexpected", f"HTTP {status}: unexpected body")
    errors = body.get("errors")
    data = body.get("data")
    if errors and not data:
        raise _error_from_body(list(errors))
    if status >= 400:
        raise BufferError("unexpected", f"HTTP {status}")
    if errors:  # data and warnings together: keep the data, note the warning
        logger.info("Buffer answered with a warning: %s", str(errors)[:200])
    return dict(data or {})


def organizations(**kw: Any) -> list[dict[str, Any]]:
    data = graphql("query { account { organizations { id name } } }", **kw)
    return list(((data.get("account") or {}).get("organizations")) or [])


_CHANNEL_FIELDS = "id name service type isDisconnected isLocked isQueuePaused timezone"


def channels(organization_id: str, **kw: Any) -> list[dict[str, Any]]:
    query = (
        "query Channels($input: ChannelsInput!) { channels(input: $input) { "
        f"{_CHANNEL_FIELDS} }} }}"
    )
    data = graphql(query, {"input": {"organizationId": organization_id}}, **kw)
    return list(data.get("channels") or [])


def due_text(when: datetime) -> str:
    """UTC ISO with milliseconds and Z, as Buffer's examples write `dueAt`."""
    utc = when.astimezone(timezone.utc) if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def post_input(
    channel_id: str,
    *,
    text: str,
    video_url: str,
    due_at: datetime,
    service: str,
    thumbnail_ms: int | None = None,
    draft: bool = False,
) -> dict[str, Any]:
    """The `CreatePostInput` for one video: scheduled at `due_at`, published by Buffer, the AI
    label on - the captions carry the disclosure line too. Instagram gets a Reel that is also
    shared to the feed."""
    video: dict[str, Any] = {"url": video_url}
    if thumbnail_ms is not None and service in ("instagram", "tiktok"):
        video["metadata"] = {"thumbnailOffset": int(thumbnail_ms)}
    metadata: dict[str, Any]
    if service == "instagram":
        metadata = {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}}
    elif service == "tiktok":
        metadata = {"tiktok": {"isAiGenerated": True}}
    else:
        metadata = {}
    body: dict[str, Any] = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": due_text(due_at),
        "aiAssisted": True,
        "assets": [{"video": video}],
    }
    if metadata:
        body["metadata"] = metadata
    if draft:  # saved in Buffer, never published until someone schedules it there
        body["saveToDraft"] = True
    return body


_POST_FIELDS = "id status dueAt sentAt externalLink channelId text error { message }"


def create_video_post(
    channel_id: str,
    *,
    text: str,
    video_url: str,
    due_at: datetime,
    service: str,
    thumbnail_ms: int | None = None,
    draft: bool = False,
    **kw: Any,
) -> dict[str, Any]:
    """The scheduled post (`id`, `status`, `dueAt`); raises `BufferError("input", message)`
    when Buffer refuses it."""
    query = (
        "mutation CreatePost($input: CreatePostInput!) { createPost(input: $input) { "
        "... on PostActionSuccess { post { id status dueAt } } "
        "... on MutationError { message } } }"
    )
    body = post_input(channel_id, text=text, video_url=video_url, due_at=due_at,
                      service=service, thumbnail_ms=thumbnail_ms, draft=draft)  # fmt: skip
    data = graphql(query, {"input": body}, **kw)
    result = data.get("createPost") or {}
    post = result.get("post") if isinstance(result, dict) else None
    if isinstance(post, dict) and post.get("id"):
        return post
    message = str((result or {}).get("message") or "Buffer did not create the post")
    raise BufferError("input", message)


def get_post(post_id: str, **kw: Any) -> dict[str, Any]:
    query = f"query Post($input: PostInput!) {{ post(input: $input) {{ {_POST_FIELDS} }} }}"
    data = graphql(query, {"input": {"id": post_id}}, **kw)
    return dict(data.get("post") or {})


def delete_post(post_id: str, **kw: Any) -> bool:
    query = (
        "mutation DeletePost($input: DeletePostInput!) { deletePost(input: $input) { "
        "... on DeletePostSuccess { id } ... on MutationError { message } } }"
    )
    data = graphql(query, {"input": {"id": post_id}}, **kw)
    result = data.get("deletePost") or {}
    if isinstance(result, dict) and result.get("id"):
        return True
    raise BufferError("input", str((result or {}).get("message") or "not deleted"))


def find_posts(organization_id: str, channel_id: str, **kw: Any) -> list[dict[str, Any]]:
    """The channel's scheduled and sent posts, newest first - to find a post whose create
    call got no answer before it is ever sent again."""
    query = (
        "query Posts($input: PostsInput!) { posts(input: $input, first: 50) { "
        f"edges {{ node {{ {_POST_FIELDS} }} }} }} }}"
    )
    variables = {
        "input": {
            "organizationId": organization_id,
            "filter": {"channelIds": [channel_id], "status": ["scheduled", "sending", "sent"]},
        }
    }
    data = graphql(query, variables, **kw)
    edges = ((data.get("posts") or {}).get("edges")) or []
    return [dict(edge.get("node") or {}) for edge in edges if isinstance(edge, dict)]
