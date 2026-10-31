"""The link-in-bio page (#1750, B07.4; decision 88) - one address for the TikTok, Instagram and
Facebook bios.

The operator chose what it shows: the newest public long video (where the watch hours are), the
week's three Shorts with the most organic views, and the affiliate links of `config/affiliates.json`
with the FTC line - only once `AFFILIATE_AMAZON_TAG` is set. No personal data. Overnight rebuilds it
and puts it on the R2 bucket Buffer already reads (`<channel>/links.html`); `ops links` prints the
address to paste into the bios once.
"""

from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("publishing.link_page")

_TOP_SHORTS = 3


def links_html(
    name: str,
    *,
    long_video: dict[str, str] | None,
    shorts: list[dict[str, str]],
    affiliates: list[dict[str, str]],
    ftc: str,
) -> str:
    """The page, escaped throughout; an empty section is left out."""

    def link(row: dict[str, str]) -> str:
        return (f'<a class="row" href="{html.escape(row["url"], quote=True)}" rel="noopener">'
                f"{html.escape(row['title'])}</a>")  # fmt: skip

    parts = [f"<h1>{html.escape(name)}</h1>"]
    if long_video:
        parts += ["<h2>The latest long video</h2>", link(long_video)]
    if shorts:
        parts += ["<h2>This week's top Shorts</h2>", *(link(s) for s in shorts)]
    if affiliates:
        parts += ["<h2>Links</h2>",
                  *(link({"title": a["label"], "url": a["url"]}) for a in affiliates)]  # fmt: skip
        if ftc:
            parts.append(f'<p class="note">{html.escape(ftc)}</p>')
    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(name)} - links</title>
<style>
:root {{ --bg:#0f1115; --fg:#f2f2f2; --muted:#a7adb7; --row:#1b1f27; --accent:#e94b3c; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.4 system-ui, sans-serif; }}
main {{ max-width:520px; margin:0 auto; padding:28px 16px 40px; }}
h1 {{ font-size:24px; margin:0 0 18px; }} h2 {{ font-size:14px; color:var(--muted);
 text-transform:uppercase; letter-spacing:.06em; margin:22px 0 8px; }}
.row {{ display:block; background:var(--row); color:var(--fg); text-decoration:none;
 padding:14px 16px; border-radius:10px; margin:8px 0; border-left:4px solid var(--accent); }}
.note {{ color:var(--muted); font-size:13px; }}
</style></head>
<body><main>
{body}
</main></body></html>
"""


def _organic(metrics: dict[str, Any]) -> int:
    total = metrics.get("lifetime_views") or metrics.get("views") or 0
    return max(0, int(total) - int(metrics.get("paid_views") or 0))


def collect(channel_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """What the page shows, read from the publish log, the runs and the affiliates map."""
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    moment = now or datetime.now(timezone.utc)
    runs = get_content_run_repository()
    longs: list[tuple[datetime, dict[str, str]]] = []
    week: list[tuple[int, dict[str, str]]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        if str(getattr(row, "privacy_status", "") or "").lower() != "public":
            continue
        video = str(getattr(row, "youtube_video_id", "") or "")
        when = getattr(row, "published_at", None)
        if not video or when is None:
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        run_id = getattr(row, "content_run_id", None)
        run = runs.get(int(run_id)) if run_id else None
        try:
            features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}") or {}
        except ValueError:
            features, metrics = {}, {}
        item = {"title": str(getattr(run, "title", "") or getattr(row, "title", "") or video),
                "url": f"https://youtu.be/{video}"}  # fmt: skip
        if features.get("compilation") or features.get("long_form"):
            longs.append((when, item))
        elif moment - when <= timedelta(days=7):
            week.append((_organic(metrics), item))
    from core.description_extras import _tagged, affiliate_rows, ftc_affiliate_line

    tag = os.getenv("AFFILIATE_AMAZON_TAG", "").strip()
    affiliates = []
    for aff in affiliate_rows(channel_id):
        url = _tagged(str(aff["url"]), tag)
        if url:
            affiliates.append({"label": str(aff.get("label") or "Link"), "url": url})
    return {
        "long_video": max(longs, key=lambda pair: pair[0])[1] if longs else None,
        "shorts": [item for _n, item in sorted(week, key=lambda p: -p[0])[:_TOP_SHORTS]],
        "affiliates": affiliates,
        "ftc": ftc_affiliate_line(channel_id, affiliate=True) if affiliates else "",
    }


def _out_dir(channel_id: str) -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "output", channel_id, "links")


def page_key(channel_id: str) -> str:
    return f"{channel_id}/links.html"


def build_and_host(channel_id: str) -> str:
    """Write the page and put it on R2; its public address."""
    from config.channels import get_channel_profile
    from publishing import video_host

    try:
        name = str(get_channel_profile(channel_id).name or channel_id)
    except Exception:
        name = channel_id
    page = links_html(name, **collect(channel_id))
    out = _out_dir(channel_id)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "links.html")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(page)
    return video_host.host(path, page_key(channel_id), content_type="text/html; charset=utf-8")
