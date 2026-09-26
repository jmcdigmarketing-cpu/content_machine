"""Re-file already-uploaded videos under their run's YouTube category (#873).

Until wave 37, `CATEGORY_BY_DOMAIN` had no `soccer`, so every football upload - run 98
included - went out as category 20 (Gaming). New uploads read the run's domain; this
fixes the ones already live. Dry run by default, with no network call; `apply` reads
each live snippet and sends it back whole with the new `categoryId` (#865's rule).
Quota: 1 unit per 50 videos listed, 50 units per update.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from core.run_features import resolved_run_domain, run_domain

logger = get_logger("publishing.recategorize")


@dataclass
class Recategorize:
    video_id: str
    run_id: int | None
    domain: str
    category_id: str


def _run_title(run_id: int | None) -> str:
    if not run_id:
        return ""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(run_id)
    except Exception as exc:
        logger.debug("recategorize: run %s unreadable: %s", run_id, exc)
        return ""
    if run is None:
        return ""
    return str(
        getattr(run, "title", "") or getattr(run, "selected_topic", "") or run.input_topic or ""
    )


def plan_recategorize(channel_id: str, *, repo=None) -> list[Recategorize]:
    """The category each uploaded video should have, from its run (no network)."""
    from apis.topic_scorer import KNOWN_DOMAINS, infer_topic_domain
    from core.youtube_meta import category_id_for_domain

    if repo is None:
        from storage.repositories.publish_log import get_publish_log_repository

        repo = get_publish_log_repository()
    plan: list[Recategorize] = []
    seen: set[str] = set()
    for row in repo.list_uploaded_for_channel(channel_id) or []:
        vid = str(getattr(row, "youtube_video_id", "") or "").strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        run_id = getattr(row, "content_run_id", None)
        # The run's #866 answer first; for older runs the title read by today's rules,
        # because their stored `domain` predates soccer (run 98 stored gaming).
        domain = resolved_run_domain(run_id)
        if domain not in KNOWN_DOMAINS:
            domain = infer_topic_domain(_run_title(run_id))
        if domain not in KNOWN_DOMAINS:
            domain = run_domain(run_id)
        if domain in KNOWN_DOMAINS:
            plan.append(Recategorize(vid, run_id, domain, category_id_for_domain(domain)))
    return plan


def apply_recategorize(
    channel_id: str, *, plan: list[Recategorize], dry_run: bool = True
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "planned": len(plan),
        "updated": 0,
        "already": 0,
        "missing": 0,
        "failed": 0,
        "errors": [],
    }
    if dry_run or not plan:
        result["mode"] = "dry_run" if dry_run else "nothing to do"
        return result
    if os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() not in ("1", "true", "yes"):
        result["mode"] = "blocked: YOUTUBE_UPLOAD_ENABLED is not true"
        return result
    from publishing.snippet_update import fetch_snippets, manage_scope_problem, writable_snippet
    from youtube.oauth import get_youtube_service

    problem = manage_scope_problem(channel_id)
    if problem:
        result["mode"] = f"blocked: {problem}"
        return result
    service = get_youtube_service(channel_id)
    live = fetch_snippets(service, [p.video_id for p in plan])
    for item in plan:
        current = live.get(item.video_id)
        if current is None:
            result["missing"] += 1
            continue
        if str(current.get("categoryId") or "") == item.category_id:
            result["already"] += 1
            continue
        body = {
            "id": item.video_id,
            "snippet": writable_snippet(current, categoryId=item.category_id),
        }
        try:
            service.videos().update(part="snippet", body=body).execute()
        except Exception as exc:  # one refusal must not lose the rest of the batch
            result["failed"] += 1
            from publishing.snippet_update import edit_error_text

            result["errors"].append(f"{item.video_id}: {edit_error_text(exc, channel_id)}")
            logger.warning("recategorize %s failed: %s", item.video_id, exc)
            continue
        result["updated"] += 1
    result["mode"] = "applied"
    result["quota_units"] = -(-len(plan) // 50) + 50 * result["updated"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-file uploaded videos by their run's domain (#873)"
    )
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--apply", action="store_true", help="send the updates (default: dry run)")
    args = parser.parse_args(argv)
    from config.channels import resolve_channel_id

    channel_id = resolve_channel_id(args.channel)
    plan = plan_recategorize(channel_id)
    print(f"Recategorize - {channel_id}: {len(plan)} uploaded video(s) with a known domain")
    for item in plan:
        sports = " (was Gaming if uploaded before wave 37)" if item.domain == "soccer" else ""
        print(
            f"  {item.video_id}  run {item.run_id}  {item.domain} -> category {item.category_id}{sports}"
        )
    result = apply_recategorize(channel_id, plan=plan, dry_run=not args.apply)
    if not args.apply:
        print(
            "Dry run: nothing was read from or sent to YouTube. --apply reads each live "
            "category and updates only the ones that differ "
            f"(about {-(-len(plan) // 50)} + 50 per change quota units)."
        )
    else:
        print(f"  {result}")
    return 0 if not str(result.get("mode", "")).startswith("blocked") else 1


if __name__ == "__main__":
    raise SystemExit(main())
