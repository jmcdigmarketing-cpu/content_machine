"""Thumbnail impressions and click-through, from the YouTube Reporting API (#951, #948).

The YouTube Analytics API - the targeted queries the metrics sync makes - has no impressions
or click-through metric; #948 assumed it did. YouTube added them to the Reporting API (bulk
reports) on 2026-01-15: report type `channel_reach_basic_a1` gives date, channel_id, video_id,
`video_thumbnail_impressions` and `video_thumbnail_impressions_ctr` per day.

A bulk report is a job: created once (`ensure_job`), after which YouTube writes one CSV per
day. `download_new` fetches each new daily file once and keeps the numbers per video per day in
`data/reach_<channel>.json`; `merge_into_metrics` writes each video's impressions and
impression-weighted click-through into its stored metrics. Reports expire, so the weekly
`ops all` (its metrics sync) collects them, and the data starts around the day the job was
created - create it early.

Thumbnail impressions are thumbnails shown on YouTube's home, subscriptions, search and
up-next surfaces. The Shorts feed shows no thumbnail; a Short's packaging is `stayed_share`
(`analytics/packaging.py`). Same token and scope as the analytics sync; the operator enables
"YouTube Reporting API" in the Google Cloud project once.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import date
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("analytics.reach_report")

REPORT_TYPE = "channel_reach_basic_a1"
JOB_NAME = "Content OS reach"
REACH_TEMPLATE = os.path.join(DATA_DIR, "reach_{channel}.json")


def _path(channel_id: str) -> str:
    return REACH_TEMPLATE.format(channel=channel_id)


def load(channel_id: str) -> dict[str, Any]:
    try:
        with open(_path(channel_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(channel_id: str, data: dict[str, Any]) -> None:
    path = _path(channel_id)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def ensure_job(service: Any, channel_id: str) -> str:
    """The reach report job's id - the stored one, an existing job, or a new one."""
    data = load(channel_id)
    if data.get("job_id"):
        return str(data["job_id"])
    jobs = service.jobs().list().execute().get("jobs") or []
    job_id = next((str(j["id"]) for j in jobs if j.get("reportTypeId") == REPORT_TYPE), "")
    if not job_id:
        created = (
            service.jobs().create(body={"reportTypeId": REPORT_TYPE, "name": JOB_NAME}).execute()
        )
        job_id = str(created["id"])
        data["job_created"] = date.today().isoformat()
    data["job_id"] = job_id
    _save(channel_id, data)
    return job_id


def _iso(day: Any) -> str:
    text = str(day or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def parse_reach_csv(text: str) -> dict[str, dict[str, list[float]]]:
    """{video_id: {YYYY-MM-DD: [impressions, ctr]}} from one daily report."""
    out: dict[str, dict[str, list[float]]] = {}
    for row in csv.DictReader(io.StringIO(text or "")):
        video_id = str(row.get("video_id") or "").strip()
        day = _iso(row.get("date"))
        if not video_id or not day:
            continue
        try:
            impressions = int(float(row.get("video_thumbnail_impressions") or 0))
            ctr = float(row.get("video_thumbnail_impressions_ctr") or 0)
        except (TypeError, ValueError):
            continue
        out.setdefault(video_id, {})[day] = [impressions, ctr]
    return out


def _download(service: Any, url: str) -> str:
    """One report's CSV text (the Reporting API's documented media download)."""
    from googleapiclient.http import MediaIoBaseDownload

    request = service.media().download_media(resourceName="")
    request.uri = url
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=-1)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return buffer.getvalue().decode("utf-8")


def _reports(service: Any, job_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    token = None
    while True:
        query: dict[str, Any] = {"jobId": job_id}
        if token:
            query["pageToken"] = token
        resp = service.jobs().reports().list(**query).execute() or {}
        out += resp.get("reports") or []
        token = resp.get("nextPageToken")
        if not token:
            return out


def download_new(service: Any, channel_id: str) -> int:
    """Download each daily report not read before; how many were new."""
    data = load(channel_id)
    job_id = data.get("job_id")
    if not job_id:
        return 0
    seen = set(data.get("downloaded") or [])
    videos = data.setdefault("videos", {})
    new = 0
    for report in sorted(_reports(service, str(job_id)), key=lambda r: r.get("startTime") or ""):
        report_id, url = str(report.get("id") or ""), str(report.get("downloadUrl") or "")
        if not report_id or not url or report_id in seen:
            continue
        for video_id, days in parse_reach_csv(_download(service, url)).items():
            videos.setdefault(video_id, {}).update(days)
        seen.add(report_id)
        new += 1
    data["downloaded"] = sorted(seen)
    _save(channel_id, data)
    return new


def _ratio(value: Any) -> float:
    ctr = float(value or 0)
    return ctr / 100.0 if ctr > 1 else ctr


def reach_for(video_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """{thumbnail_impressions, thumbnail_ctr} over every day kept, or None."""
    days = (data.get("videos") or {}).get(video_id) or {}
    impressions = 0
    clicks = 0.0
    for value in days.values():
        try:
            shown = int(value[0])
            impressions += shown
            clicks += shown * _ratio(value[1])
        except (TypeError, ValueError, IndexError):
            continue
    if impressions <= 0:
        return None
    return {"thumbnail_impressions": impressions, "thumbnail_ctr": round(clicks / impressions, 4)}


def merge_into_metrics(channel_id: str) -> int:
    """Write impressions and click-through into each video's stored metrics; rows updated."""
    from storage.repositories.publish_log import get_publish_log_repository

    data = load(channel_id)
    if not data.get("videos"):
        return 0
    repo = get_publish_log_repository()
    updated = 0
    for row in repo.list_uploaded_for_channel(channel_id):
        reach = reach_for(str(row.youtube_video_id or ""), data)
        if not reach:
            continue
        try:
            metrics = json.loads(row.metrics_json or "{}")
        except (TypeError, ValueError):
            metrics = {}
        metrics = metrics if isinstance(metrics, dict) else {}
        metrics.update(reach)
        repo.update(row.id, {"metrics_json": json.dumps(metrics)})
        updated += 1
    return updated


_ENABLE_LINE = (
    "enable the YouTube Reporting API in Google Cloud Console (same sign-in), then sync again"
)


_ACTIVATION_URL = re.compile(
    r"https://console\.developers\.google\.com/apis/api/youtubereporting\.googleapis\.com"
    r"/overview\?project=\d+"
)


def enable_link(message: str) -> str:
    """The page Google's own 403 says enables the API, for the project the sign-in uses (#1123).

    The operator ticked "turn on the Reporting API" on 2026-10-08 and the sync still answered
    disabled on 10-10: the API is on per Cloud project, the generic line named none, and the
    answer carries the exact link.
    """
    found = _ACTIVATION_URL.search(message or "")
    return found.group(0) if found else ""


def _enable_line(link: str) -> str:
    if not link:
        return _ENABLE_LINE
    project = link.rsplit("=", 1)[-1]
    return (
        f"the YouTube Reporting API is off in the Google project this sign-in uses "
        f"({project}) - open {link} , press Enable, then sync again"
    )


def _record(channel_id: str, status: str, detail: str = "") -> None:
    """Keep what the last sync found, so `ops doctor` can say it without a network call."""
    data = load(channel_id)
    data["last_status"] = status
    data["last_detail"] = detail[:200]
    data["checked"] = date.today().isoformat()
    _save(channel_id, data)


def status(channel_id: str) -> tuple[bool, str]:
    """(ok, line) from the last sync - why there are, or are not, click-through numbers.

    #1058: for months there were none and nothing said why: the Reporting API was never
    enabled in the Cloud project, and the one line that said so sat inside `sync-metrics`.
    """
    data = load(channel_id)
    last = str(data.get("last_status") or "")
    when = str(data.get("checked") or "")
    if not last:
        return False, "click-through: never synced (py -m scripts.ops sync-metrics)"
    if last == "no_service":
        return False, (
            f"click-through: no analytics sign-in as of {when} "
            "(py -m youtube.oauth_setup --channel <id>)"
        )
    if last == "api_disabled":
        link = enable_link(str(data.get("last_detail") or ""))
        return False, f"click-through: {_enable_line(link)} (seen {when})"
    if last == "error":
        return (
            False,
            f"click-through: the reach report failed on {when} ({data.get('last_detail')})",
        )
    videos = len(data.get("videos") or {})
    if last == "waiting" or not videos:
        since = str(data.get("job_created") or when)
        return True, (
            f"click-through: report job running since {since}, no daily file yet "
            "(YouTube writes the first within about two days)"
        )
    return True, f"click-through: {videos} video(s) with impressions, synced {when}"


def sync_reach(channel_id: str) -> str:
    """Create the job if needed, collect new daily reports, merge; one line for the sync."""
    from youtube.oauth import get_youtube_reporting_service

    service = get_youtube_reporting_service(channel_id)
    if service is None:
        # The sync stays quiet here (it runs with YouTube switched off too); the doctor's
        # `reach` row is where this is said.
        _record(channel_id, "no_service")
        return ""
    try:
        ensure_job(service, channel_id)
        new = download_new(service, channel_id)
    except Exception as exc:
        message = str(exc)
        if any(
            k in message
            for k in ("accessNotConfigured", "has not been used", "SERVICE_DISABLED", "is disabled")
        ):
            link = enable_link(message)
            _record(channel_id, "api_disabled", link)
            return f"  Click-through: {_enable_line(link)} (#951)"
        logger.debug("reach report skipped: %s", exc)
        _record(channel_id, "error", message)
        return f"  Click-through: the reach report is unavailable ({message[:120]})"
    merged = merge_into_metrics(channel_id)
    _record(channel_id, "ok" if load(channel_id).get("videos") else "waiting")
    return (
        f"  Click-through: {new} new daily report(s); {merged} video(s) with impressions "
        "and CTR (ops packaging)"
    )
