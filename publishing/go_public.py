"""#864: flip a review-held unlisted upload to public.

The review hold (#109, `YOUTUBE_UNLISTED_REVIEW`) lands an immediate public upload
unlisted so the operator can watch it once. Before this, promoting it meant YouTube
Studio by hand. Mirrors `publishing/rollback.py`: dry run by default, and the YouTube
client is never built unless `apply` *and* YOUTUBE_UPLOAD_ENABLED are both on.

A run rendered past the grounding gate - or a Short cut from one - stays unlisted until
the claim is fixed (#754), so it is refused here too.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from apis.youtube_quota import record_call
from core.logging import get_logger
from core.run_features import load_features, merge_features

logger = get_logger("publishing.go_public")


@dataclass
class GoPublicResult:
    status: str
    detail: str = ""
    video_id: str = ""
    # #1087: what is about to go public - the operator saw only an id (CGFtzpiA1so).
    run_id: int | None = None
    title: str = ""
    holds: list[str] = field(default_factory=list)
    # #1190: what went to TikTok and Instagram once it was public.
    crosspost: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        run = f"run {self.run_id}" if self.run_id else "a run not on record"
        title = f' - "{self.title}"' if self.title else ""
        return f"{run}{title} ({self.video_id})"


def go_public_plan(video_id: str) -> dict[str, Any]:
    """videos.update body - status part only, so title/description are untouched."""
    return {"id": video_id, "status": {"privacyStatus": "public"}}


def override_held(run_id: int | None) -> bool:
    """The run - or the run a Short was cut from - was rendered past the grounding gate."""
    features = load_features(run_id)
    if features.get("grounding_override"):
        return True
    parent = features.get("parent_run_id")
    try:
        return bool(parent and load_features(int(parent)).get("grounding_override"))
    except (TypeError, ValueError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log_rows(repo, channel_id: str) -> list:
    """Live uploads plus the ones YouTube holds for a later publishAt (#1299).

    `list_uploaded_for_channel` leaves out a row whose `published_at` is still ahead, so a
    scheduled video changed on YouTube and its log row kept the old time.
    """
    rows = list(repo.list_uploaded_for_channel(channel_id) or [])
    try:
        rows += list(repo.list_future_scheduled(channel_id) or [])
    except Exception as exc:
        logger.debug("go-public: scheduled rows unreadable: %s", exc)
    return rows


def _run_title(run_id: int | None) -> str:
    """The run's title from its record, or "" (#1087)."""
    if not run_id:
        return ""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(int(run_id))
        return str(getattr(record, "title", "") or "")
    except Exception as exc:
        logger.debug("go-public: title for run %s unavailable: %s", run_id, exc)
        return ""


def _holds(rows: list) -> list:
    """Unlisted uploads with a video id, newest first."""
    held = [
        r
        for r in (rows or [])
        if str(getattr(r, "youtube_video_id", "") or "").strip()
        and str(r.privacy_status or "").lower() == "unlisted"
    ]
    return sorted(held, key=lambda r: int(getattr(r, "id", 0) or 0), reverse=True)


def _run_for_hold(run_id: int | None):
    if not run_id:
        return None
    try:
        from storage.repositories.content_runs import get_content_run_repository

        return get_content_run_repository().get(int(run_id))
    except Exception as exc:
        logger.debug("watch: run %s unreadable: %s", run_id, exc)
        return None


def _after_its_game(run_id: int | None, channel_id: str, video_id: str, title: str):
    """#1547: a GoPublicResult refusing a preview whose game has started, else None. Run 181,
    the Cavaliers-76ers preview, would have been offered for go-public after its tip-off."""
    try:
        from core.batch_review import _zone_clock
        from core.stale_renders import started_event

        when = started_event(_run_for_hold(run_id), channel_id) if run_id else None
        if when is None:
            return None
        started = _zone_clock(when, channel_id, day=True)
    except Exception as exc:
        logger.debug("game check skipped for run %s: %s", run_id, exc)
        return None
    return GoPublicResult(
        "refused",
        f"run {run_id} previews a game that has been played - its game started {started}; it "
        "stays unlisted (Studio can still change it)",
        video_id,
        run_id=run_id,
        title=title,
    )


def hold_summary(row, run) -> str:
    """File, length and grade for one unlisted video (#1248)."""
    features: dict[str, Any] = {}
    quality: dict[str, Any] = {}
    path = "(no file)"
    title = ""
    if run is not None:
        path = str(getattr(run, "mp4_path", "") or "") or "(no file)"
        title = str(getattr(run, "title", "") or "")
        try:
            features = json.loads(getattr(run, "features_json", "") or "{}")
        except (TypeError, ValueError):
            features = {}
        try:
            quality = json.loads(getattr(run, "quality_json", "") or "{}")
        except (TypeError, ValueError):
            quality = {}
    qc_raw = features.get("technical_qc")
    qc = qc_raw if isinstance(qc_raw, dict) else {}
    raw = qc.get("video_duration")
    length = "length unknown"
    if isinstance(raw, int | float):
        length = f"{float(raw):.0f}s"
    elif isinstance(raw, str) and raw.strip():
        try:
            length = f"{float(raw):.0f}s"
        except ValueError:
            length = "length unknown"
    grade = quality.get("grade") or "n/a"
    video = str(getattr(row, "youtube_video_id", "") or "")
    return f"{path}  {length}  grade {grade}  {title}  {video}".strip()


def listed_holds(channel_id: str) -> list:
    """Unlisted uploads the operator has not set aside (#449)."""
    out = []
    for row in unlisted_holds(channel_id):
        if load_features(getattr(row, "content_run_id", None)).get("watch_aside"):
            continue
        out.append(row)
    return out


def watch_and_publish(channel_id: str, *, ask, print_fn) -> list[str]:
    """One pass: each unlisted video, then now / at its slot / keep / set aside.

    Nothing goes public unless the answer is now (#1255 stays the operator's call).
    A flagged claim is refused here; a grounding hold is refused by `apply_go_public`.
    """
    rows = listed_holds(channel_id)
    if not rows:
        print_fn("  No unlisted videos waiting.")
        return []
    decisions: list[str] = []
    for index, row in enumerate(rows, 1):
        run_id = getattr(row, "content_run_id", None)
        print_fn(f"  [{index}/{len(rows)}] {hold_summary(row, _run_for_hold(run_id))}")
        answer = (
            # #1270 (the operator): s schedules it public at the next free noon/10 PM slot.
            ask("  n now / s at its slot / k keep / a set aside / q quit [k]: ").strip().lower()
        )
        video_id = str(getattr(row, "youtube_video_id", "") or "")
        if answer in ("q", "quit"):
            break
        if answer in ("n", "now"):
            from core.facts.claim_confirm import run_flagged_claims

            flagged = run_flagged_claims(run_id)
            if flagged:
                print_fn(
                    f"    Refused: {len(flagged)} flagged claim(s) still open. "
                    f"py -m scripts.ops verify-claim --run-id {run_id}"
                )
                decisions.append("refused")
                continue
            result = apply_go_public(video_id, channel_id=channel_id, dry_run=False)
            said = getattr(result, "detail", "") or getattr(result, "label", "")
            print_fn(f"    {result.status}: {said}")
            decisions.append("now")
        elif answer in ("s", "slot"):
            from core.spaced_queue import slot_for_run

            run = _run_for_hold(run_id)
            when, why = slot_for_run(
                channel_id, int(run_id or 0), title=str(getattr(run, "title", "") or "")
            )
            if when is None:
                print_fn(f"    Kept unlisted: {why}.")
                decisions.append("keep")
                continue
            result = apply_schedule_public(video_id, channel_id=channel_id, when=when)
            said = getattr(result, "detail", "") or getattr(result, "label", "")
            print_fn(f"    {result.status}: {said}")
            decisions.append("slot")
        elif answer in ("a", "aside"):
            merge_features(run_id, {"watch_aside": True})
            print_fn("    Set aside. It will not be offered again.")
            decisions.append("aside")
        else:
            print_fn("    Kept unlisted.")
            decisions.append("keep")
    return decisions


def apply_schedule_public(
    video_id: str,
    *,
    channel_id: str = "tapin",
    when: datetime,
    dry_run: bool = False,
    repo=None,
) -> GoPublicResult:
    """#1270: schedule an unlisted upload to go public at `when` - YouTube's `publishAt`, which
    needs the video private until then. The log row says scheduled at that time, so the slot
    counts as taken and the worker crossposts it once it is live (#1275). Only an operator's
    action calls this (decision 60)."""
    from publishing.youtube_publisher import _to_publish_at_rfc3339

    video_id = (video_id or "").strip()
    try:
        if repo is None:
            from storage.repositories.publish_log import get_publish_log_repository

            repo = get_publish_log_repository()
        rows = _log_rows(repo, channel_id)
    except Exception as exc:
        logger.warning("schedule-public: publish log unreadable: %s", exc)
        rows = []
    record = _find(rows, video_id)
    run_id = record.content_run_id if record is not None else None
    title = _run_title(run_id)
    if record is not None and override_held(record.content_run_id):
        return GoPublicResult(
            "refused",
            f"run {record.content_run_id} was rendered past the grounding gate; it stays "
            f"unlisted until the flagged claim is fixed - py -m scripts.ops verify-claim "
            f"--run-id {record.content_run_id}",
            video_id,
            run_id=run_id,
            title=title,
        )
    played = _after_its_game(run_id, channel_id, video_id, title)
    if played is not None:
        return played
    change: dict[str, Any] = {"privacyStatus": "private", "publishAt": _to_publish_at_rfc3339(when)}
    body: dict[str, Any] = {"id": video_id, "status": change}
    if dry_run:
        return GoPublicResult("dry_run", json.dumps(body), video_id, run_id=run_id, title=title)
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        return GoPublicResult(
            "blocked", "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent", video_id,
            run_id=run_id, title=title,
        )  # fmt: skip
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return GoPublicResult("blocked", problem, video_id, run_id=run_id, title=title)
    try:
        from publishing.snippet_update import live_status, writable_status
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        # #1306: the whole status, or YouTube switches embedding and public stats off.
        body["status"] = writable_status(live_status(service, video_id), **change)
        record_call("videos.update")  # wave 113: it booked nothing
        service.videos().update(part="status", body=body).execute()
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("schedule-public update failed: %s", exc)
        return GoPublicResult(
            "error", edit_error_text(exc, channel_id), video_id, run_id=run_id, title=title
        )
    if record is not None:
        try:
            repo.update(
                record.id,
                # The privacy it goes public with, as the uploader logs a scheduled video -
                # crosspost._public_runs reads "public" once published_at passes (#1299).
                {"privacy_status": "public", "status": "scheduled", "published_at": when},
            )
        except Exception as exc:
            logger.warning("schedule-public: publish log not updated: %s", exc)
    from analytics.post_timing import format_scheduled_local

    result = GoPublicResult("scheduled", "", video_id, run_id=run_id, title=title)
    result.detail = f"{result.label} goes public {format_scheduled_local(when, channel_id)}"
    result.detail += _read_back(service, video_id, when, channel_id)
    return result


_READ_AGAIN_SECONDS = 5.0


def _read_back(service: Any, video_id: str, when: datetime, channel_id: str) -> str:
    """#1392 (wave 117): what YouTube shows after the change. Run 161 on 10-19: the first read
    returned the old time and the next one, a minute later, the new - so a stale read is read
    once more. The log row was already written; a time that did not take is said, and the next
    privacy sync corrects the record (#1520). Fail-open: ""."""
    import time

    from analytics.post_timing import format_scheduled_local
    from publishing.snippet_update import live_status

    def shown() -> datetime | None:  # fetch_statuses books the videos.list unit
        raw = str((live_status(service, video_id) or {}).get("publishAt") or "")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
        except ValueError:
            return None

    try:
        target = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        seen = shown()
        if seen is not None and seen != target:  # a stale read, as on 10-19
            time.sleep(_READ_AGAIN_SECONDS)
            seen = shown()
    except Exception as exc:
        logger.debug("schedule read-back skipped: %s", exc)
        return ""
    if seen is None:
        return ""  # unreadable - nothing to say
    if seen == target:
        return f" (YouTube shows {format_scheduled_local(seen, channel_id)})"
    old = format_scheduled_local(seen, channel_id)
    return f" - YouTube still shows {old}; the next privacy sync corrects the record"


def apply_unschedule(
    video_id: str,
    *,
    channel_id: str = "tapin",
    dry_run: bool = True,
    repo=None,
    why: str = "",
) -> GoPublicResult:
    """#1555 (2026-10-23): a scheduled video back to private with no publish time. Run 179, the
    Pistons follow-up, was scheduled for Sat noon with last season's "clinched the No. 1 seed",
    and the operator asked for it off the schedule; `rollback-publish` unlists only a published
    video. The file stays; the log row is private and uploaded, so its slot is free again."""
    video_id = (video_id or "").strip()
    try:
        if repo is None:
            from storage.repositories.publish_log import get_publish_log_repository

            repo = get_publish_log_repository()
        rows = _log_rows(repo, channel_id)
    except Exception as exc:
        logger.warning("unschedule: publish log unreadable: %s", exc)
        rows = []
    record = _find(rows, video_id) if video_id else None
    run_id = record.content_run_id if record is not None else None
    title = _run_title(run_id)
    if record is None or str(getattr(record, "status", "") or "") != "scheduled":
        return GoPublicResult(
            "invalid",
            f"{video_id or 'no video id'} is not a scheduled upload on record - nothing to unschedule",
            video_id,
            run_id=run_id,
            title=title,
        )
    body: dict[str, Any] = {
        "id": video_id,
        "status": {"privacyStatus": "private", "publishAt": None},
    }
    if dry_run:
        return GoPublicResult("dry_run", json.dumps(body), video_id, run_id=run_id, title=title)
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        return GoPublicResult(
            "blocked", "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent", video_id,
            run_id=run_id, title=title,
        )  # fmt: skip
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return GoPublicResult("blocked", problem, video_id, run_id=run_id, title=title)
    try:
        from publishing.snippet_update import live_status, writable_status
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        # #1306: the whole status; a None publishAt drops it.
        body["status"] = writable_status(
            live_status(service, video_id), privacyStatus="private", publishAt=None
        )
        record_call("videos.update")
        service.videos().update(part="status", body=body).execute()
        import time

        # #1555's first live run: read at once, YouTube still showed the old publish time; a
        # read a few seconds later did not.
        after = live_status(service, video_id)
        for _attempt in range(3):
            if not after.get("publishAt"):
                break
            time.sleep(3)
            after = live_status(service, video_id)
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("unschedule failed: %s", exc)
        return GoPublicResult("error", edit_error_text(exc, channel_id), video_id, run_id=run_id,
                              title=title)  # fmt: skip
    try:
        repo.update(record.id, {"privacy_status": "private", "status": "uploaded"})
        if run_id:
            merge_features(run_id, {"unscheduled": {"at": _now().isoformat(), "why": why}})
    except Exception as exc:
        logger.warning("unschedule: record not updated: %s", exc)
    if after.get("publishAt"):
        return GoPublicResult(
            "error",
            f"YouTube still shows a publish time ({after['publishAt']}) - check it in Studio",
            video_id,
            run_id=run_id,
            title=title,
        )
    result = GoPublicResult("updated", "", video_id, run_id=run_id, title=title)
    result.detail = f"{result.label} is private, with no publish time - the file stays"
    return result


def unlisted_holds(channel_id: str) -> list:
    """Every upload on the channel that is still unlisted, newest first (#1122)."""
    from storage.repositories.publish_log import get_publish_log_repository

    return _holds(get_publish_log_repository().list_uploaded_for_channel(channel_id) or [])


def _find(rows: list, video_id: str):
    rows = [r for r in (rows or []) if str(getattr(r, "youtube_video_id", "") or "").strip()]
    if video_id:
        matches = [r for r in rows if str(r.youtube_video_id).strip() == video_id]
    else:
        matches = [r for r in rows if str(r.privacy_status or "").lower() == "unlisted"]
    if not matches:
        return None
    return max(matches, key=lambda r: int(getattr(r, "id", 0) or 0))


def apply_go_public(
    video_id: str = "",
    *,
    channel_id: str = "tapin",
    dry_run: bool = True,
    repo=None,
) -> GoPublicResult:
    """Promote `video_id` (or the newest unlisted hold) to public."""
    video_id = (video_id or "").strip()
    try:
        if repo is None:
            from storage.repositories.publish_log import get_publish_log_repository

            repo = get_publish_log_repository()
        rows = _log_rows(repo, channel_id)
    except Exception as exc:
        logger.warning("go-public: publish log unreadable: %s", exc)
        rows = []
    record = _find(rows, video_id)
    if record is None and not video_id:
        return GoPublicResult("invalid", f"No unlisted upload on record for {channel_id}")
    target = video_id or str(record.youtube_video_id).strip()
    run_id = record.content_run_id if record is not None else None
    title = _run_title(run_id)
    # #1087: with no id and more than one hold, "the newest" is a guess the operator never
    # saw - list them on the dry run, and refuse to send until one is named.
    holds = (
        [
            f"{str(r.youtube_video_id).strip()} (run {r.content_run_id}: "
            f"{_run_title(r.content_run_id) or 'untitled'})"
            for r in _holds(rows)
        ]
        if not video_id
        else []
    )
    if len(holds) > 1 and not dry_run:
        return GoPublicResult(
            "invalid",
            f"{len(holds)} unlisted holds - name the one to publish: " + "; ".join(holds),
            target,
            holds=holds,
            run_id=run_id,
            title=title,
        )
    if record is not None and override_held(record.content_run_id):
        return GoPublicResult(
            "refused",
            f"run {record.content_run_id} was rendered past the grounding gate; it stays "
            "unlisted until the flagged claim is fixed (#754) - confirm or reject it with: "
            f"py -m scripts.ops verify-claim --run-id {record.content_run_id}",
            target,
            run_id=run_id,
            title=title,
        )
    played = _after_its_game(run_id, channel_id, target, title)
    if played is not None:
        return played
    body = go_public_plan(target)
    if dry_run:
        return GoPublicResult(
            "dry_run", json.dumps(body), target, holds=holds, run_id=run_id, title=title
        )
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        return GoPublicResult(
            "blocked",
            "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent",
            target,
            run_id=run_id,
            title=title,
        )
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return GoPublicResult("blocked", problem, target, run_id=run_id, title=title)
    try:
        from publishing.snippet_update import live_status, writable_status
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        # #1306: the whole status, or YouTube switches embedding and public stats off.
        body["status"] = writable_status(live_status(service, target), **body["status"])
        record_call("videos.update")  # wave 113: it booked nothing
        service.videos().update(part="status", body=body).execute()
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("go-public update failed: %s", exc)
        return GoPublicResult(
            "error", edit_error_text(exc, channel_id), target, run_id=run_id, title=title
        )
    if record is not None:
        try:
            fields: dict[str, Any] = {"privacy_status": "public"}
            if str(getattr(record, "status", "") or "") == "scheduled":
                # A scheduled row is live from its published_at - now, not the old slot (#1299).
                fields["published_at"] = _now()
            repo.update(record.id, fields)
        except Exception as exc:
            logger.warning("go-public: publish log not updated: %s", exc)
    result = GoPublicResult("updated", "", target, run_id=run_id, title=title)
    result.detail = f"{result.label} is public"
    try:  # #1190 (operator, 2026-10-14): once public on YouTube, to TikTok and Instagram
        from publishing import crosspost

        result.crosspost = crosspost.step(channel_id)
    except Exception as exc:
        logger.warning("go-public: crosspost skipped: %s", exc)
    return result


def repair_status_fields(channel_id: str = "tapin", *, apply: bool = False, repo=None) -> list[str]:
    """#1306: the videos a status-only update left with embedding or public view counts off
    (measured 2026-10-18: 7 of 56), and with `apply` both restored - the privacy and any slot
    as they are. Reading costs 1 quota unit per 50 videos; a dry run sends nothing."""
    from publishing.snippet_update import fetch_statuses, status_repairs

    try:
        if repo is None:
            from storage.repositories.publish_log import get_publish_log_repository

            repo = get_publish_log_repository()
        rows = _log_rows(repo, channel_id)
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        ids = [str(getattr(r, "youtube_video_id", "") or "").strip() for r in rows]
        fixes = status_repairs(fetch_statuses(service, [i for i in ids if i]))
    except Exception as exc:
        return [f"  Status fields not read: {exc}"]
    if not fixes:
        return ["  Every video keeps embedding and public view counts."]
    lines = [f"  {len(fixes)} video(s) with embedding or public view counts off (#1306):"]
    lines += [
        f"    {video_id} ({status.get('privacyStatus')})" for video_id, status in fixes.items()
    ]
    if not apply:
        return [
            *lines,
            "  Nothing sent. --apply restores both; privacy and any slot stay as they are.",
        ]
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        return [*lines, "  Not sent: YOUTUBE_UPLOAD_ENABLED is not true."]
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return [*lines, f"  Not sent: {problem}"]
    for video_id, status in fixes.items():
        try:
            record_call("videos.update")  # wave 113: it booked nothing
            service.videos().update(
                part="status", body={"id": video_id, "status": status}
            ).execute()
            lines.append(f"    {video_id}: restored")
        except Exception as exc:
            lines.append(f"    {video_id}: not restored - {exc}")
    return lines
