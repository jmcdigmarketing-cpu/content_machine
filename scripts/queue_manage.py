"""
Manage publish queue — re-queue after deleting a scheduled video on YouTube.

Usage:
    py -m scripts.queue_manage --channel tapin
    py -m scripts.queue_manage --channel tapin --run-id 7 --reset
    py -m scripts.queue_manage --channel tapin --run-id 7 --requeue
    py -m scripts.queue_manage --channel tapin --run-id 7 --requeue --schedule
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from analytics.post_timing import format_scheduled_local, next_optimal_post_time
from analytics.queue_manager import (
    cancel_queue_slots,
    format_requeue_menu_line,
    list_requeue_candidates,
    requeue_content_run,
    reset_publish_for_requeue,
)
from analytics.upload_queue import list_queue_entries
from config.channels import get_channel_profile, resolve_channel_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Reset and re-queue uploads after deleting videos on YouTube"
    )
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--run-id", type=int, help="Content run id")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Cancel publish_log so a new upload can run (no new job)",
    )
    parser.add_argument(
        "--requeue",
        action="store_true",
        help="Reset + enqueue upload job (use with --run-id)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="With --requeue: use next optimal YouTube publishAt slot",
    )
    parser.add_argument(
        "--privacy",
        choices=("private", "unlisted", "public"),
        default=None,
        help="Privacy for re-queue upload",
    )
    parser.add_argument(
        "--cancel",
        metavar="N",
        nargs="+",
        type=int,
        help="Cancel queue slots by number (e.g. --cancel 1 2)",
    )
    args = parser.parse_args(argv)

    channel_id = resolve_channel_id(args.channel)
    profile = get_channel_profile(channel_id)

    entries = list_queue_entries(channel_id)
    print(f"\nUpcoming publish queue ({channel_id}):")
    if entries:
        for i, e in enumerate(entries, 1):
            when = format_scheduled_local(e.publish_at, channel_id)
            print(f"  {i}. {when}  {e.title[:40]}  [{e.status}]")
    else:
        print("  (empty)")

    candidates = list_requeue_candidates(channel_id)
    print(f"\nRe-queue after YouTube delete ({len(candidates)} runs with prior upload):")
    if candidates:
        for c in candidates:
            print(f"  {format_requeue_menu_line(c, channel_id)}")
    else:
        print("  (none — use list-uploads for never-uploaded MP4s)")

    if args.cancel:
        done = cancel_queue_slots(channel_id, args.cancel)
        if done:
            print(f"\nCancelled queue slot(s): {', '.join(str(n) for n in done)}")
            print("  Slots freed for scheduling. Verify:")
            print(f"  py -m scripts.queue_manage --channel {channel_id}")
        else:
            print("\nNo slots cancelled (check numbers against list above).")
        return 0 if done else 1

    if not args.run_id:
        print(
            "\nCommands:\n"
            f"  py -m scripts.queue_manage --channel {channel_id} --cancel 1 2\n"
            f"  py -m scripts.queue_manage --channel {channel_id} --run-id ID --reset\n"
            f"  py -m scripts.queue_manage --channel {channel_id} --run-id ID --requeue\n"
            f"  py -m scripts.queue_manage --channel {channel_id} --run-id ID --requeue --schedule\n"
            "  py -m jobs.worker --loop 30\n"
        )
        return 0

    if args.reset:
        ok = reset_publish_for_requeue(args.run_id, channel_id)
        if ok:
            print(f"\nRun {args.run_id}: publish_log cancelled — safe to --requeue.")
        else:
            print(f"\nRun {args.run_id}: no active publish_log to reset.")
        return 0 if ok else 1

    if args.requeue:
        privacy = args.privacy or profile.privacy_status_default or "private"
        publish_at = None
        if args.schedule:
            run = None
            from storage.repositories.content_runs import get_content_run_repository

            run = get_content_run_repository().get(args.run_id)
            topic = (run.selected_topic or run.title) if run else ""
            publish_at = next_optimal_post_time(channel_id, topic)
            print(
                f"  Scheduling YouTube publish: "
                f"{format_scheduled_local(publish_at, channel_id)}"
            )
        try:
            job_id = requeue_content_run(
                args.run_id,
                channel_id,
                privacy_status=privacy,
                youtube_publish_at=publish_at,
                scheduled_at=datetime.now(timezone.utc),
            )
            print(f"\nQueued upload job {job_id} for run {args.run_id}.")
            print("  Run: py -m jobs.worker --loop 30")
            return 0
        except ValueError as exc:
            print(f"\nError: {exc}")
            return 1

    print("\nAdd --reset or --requeue (see commands above).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
