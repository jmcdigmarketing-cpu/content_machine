"""Where Buffer fetches a video from: Cloudflare R2 (#1186).

Buffer takes no uploads - a video post names a public link and Buffer fetches it, at creation
and again when the post goes out. R2 is S3-compatible, so `boto3` puts the mp4 in the
operator's bucket and the link is the bucket's **public address** (`R2_PUBLIC_BASE_URL`: the
bucket's r2.dev URL or a custom domain). The copy stays until Buffer reports the post sent on
every platform; `crosspost.sync_status` then removes it.

Found live on 2026-10-15: a presigned link (the first design) downloads, but answers HEAD with
403, and Buffer refused it - "Video could not be read from its URL". Buffer's hosting guide
says the same: no signed or expiring links; for R2, public access on the bucket. Each file's
name carries a random part, so a public address cannot be guessed from the run number.

Keys: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`,
`R2_PUBLIC_BASE_URL`.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from core.logging import get_logger

logger = get_logger("publishing.video_host")

REQUIRED = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_PUBLIC_BASE_URL",
)


def missing() -> list[str]:
    return [name for name in REQUIRED if not os.getenv(name, "").strip()]


def configured() -> bool:
    return not missing()


def _bucket() -> str:
    return os.getenv("R2_BUCKET", "").strip()


def _client() -> Any:
    import boto3

    account = os.getenv("R2_ACCOUNT_ID", "").strip()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID", "").strip(),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
        region_name="auto",
    )


def safe_url(url: str) -> str:
    """`url` without its query string, for a log."""
    parts = urlsplit(str(url or ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def object_key(channel_id: str, run_id: int, path: str) -> str:
    """`tapin/run132-<random>.mp4` - public, so not guessable from the run number."""
    ext = os.path.splitext(path)[1] or ".mp4"
    return f"{channel_id}/run{int(run_id)}-{secrets.token_hex(8)}{ext}"


def link(key: str, *, client: Any = None) -> str:
    """The public address Buffer fetches `key` from."""
    base = os.getenv("R2_PUBLIC_BASE_URL", "").strip()
    if not base:
        raise ValueError("R2_PUBLIC_BASE_URL is not set - Buffer needs the bucket's public address")
    return f"{base.rstrip('/')}/{quote(key)}"


def host(path: str, key: str, *, client: Any = None) -> str:
    """Put the mp4 at `key` and return its public address."""
    client = client or _client()
    client.upload_file(path, _bucket(), key, ExtraArgs={"ContentType": "video/mp4"})
    url = link(key)
    logger.info("video hosted for Buffer: %s", safe_url(url))
    return url


def remove(key: str, *, client: Any = None) -> bool:
    try:
        (client or _client()).delete_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        logger.warning("hosted copy %s not removed: %s", key, type(exc).__name__)
        return False
    return True


def self_test(*, client: Any = None, head: Any = None, get: Any = None) -> str:
    """Put a 1 KB file, read it back from its public address the way Buffer does (HEAD, then a
    ranged GET), and delete it. '' when all of it worked, else what failed."""
    if not configured():
        return "missing " + ", ".join(missing())
    import requests

    head = head or requests.head
    get = get or requests.get
    key = f"selftest/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.mp4"
    try:
        client = client or _client()
        client.put_object(Bucket=_bucket(), Key=key, Body=b"x" * 1024, ContentType="video/mp4")
        try:
            url = link(key)
            answer = head(url, timeout=30, allow_redirects=False)
            if int(answer.status_code) != 200:
                return (
                    f"the public address answers {answer.status_code} to HEAD - Buffer cannot "
                    "read it (is public access on for the bucket?)"
                )
            answer = get(url, timeout=30, headers={"Range": "bytes=0-99"})
            if int(answer.status_code) not in (200, 206):
                return f"the public address answers {answer.status_code} to GET"
        finally:
            client.delete_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:160]}"
    return ""
