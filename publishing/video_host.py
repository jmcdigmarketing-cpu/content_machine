"""Where Buffer fetches a video from: Cloudflare R2 (#1186).

Buffer takes no uploads - a video post names a public link and Buffer fetches it. R2 is
S3-compatible, so `boto3` puts the mp4 in the operator's bucket and returns either a
presigned link (valid 7 days, S3's longest) or, when `R2_PUBLIC_BASE_URL` is set (a public
bucket or custom domain), the plain address. The copy stays until Buffer reports the post sent
on every platform; `crosspost.sync_status` then removes it.

Keys: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, optional
`R2_PUBLIC_BASE_URL`. A link written to a log loses its query string (`safe_url`), so no
signature is ever stored in a log.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from core.logging import get_logger

logger = get_logger("publishing.video_host")

REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
LINK_SECONDS = 7 * 86400


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
    """`url` without its query string - a presigned link's signature never reaches a log."""
    parts = urlsplit(str(url or ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def object_key(channel_id: str, run_id: int, path: str) -> str:
    return f"{channel_id}/run{int(run_id)}-{os.path.basename(path)}"


def link(key: str, *, client: Any = None) -> str:
    """A link Buffer can fetch `key` from: the public address, or a fresh 7-day presigned one."""
    base = os.getenv("R2_PUBLIC_BASE_URL", "").strip()
    if base:
        return f"{base.rstrip('/')}/{quote(key)}"
    client = client or _client()
    return str(
        client.generate_presigned_url(
            "get_object", Params={"Bucket": _bucket(), "Key": key}, ExpiresIn=LINK_SECONDS
        )
    )


def host(path: str, key: str, *, client: Any = None) -> str:
    """Put the mp4 at `key` and return the link to it."""
    client = client or _client()
    client.upload_file(path, _bucket(), key, ExtraArgs={"ContentType": "video/mp4"})
    url = link(key, client=client)
    logger.info("video hosted for Buffer: %s", safe_url(url))
    return url


def link_expires(now: datetime | None = None) -> str:
    """When a link made now stops working; '' for a public address, which does not."""
    if os.getenv("R2_PUBLIC_BASE_URL", "").strip():
        return ""
    moment = now or datetime.now(timezone.utc)
    return datetime.fromtimestamp(moment.timestamp() + LINK_SECONDS, timezone.utc).isoformat()


def remove(key: str, *, client: Any = None) -> bool:
    try:
        (client or _client()).delete_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        logger.warning("hosted copy %s not removed: %s", key, type(exc).__name__)
        return False
    return True


def self_test(*, client: Any = None) -> str:
    """Put, link and delete a 1 KB object. '' when all three worked, else what failed."""
    if not configured():
        return "missing " + ", ".join(missing())
    key = f"selftest/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.txt"
    try:
        client = client or _client()
        client.put_object(Bucket=_bucket(), Key=key, Body=b"x" * 1024, ContentType="text/plain")
        link(key, client=client)
        client.delete_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:160]}"
    return ""
