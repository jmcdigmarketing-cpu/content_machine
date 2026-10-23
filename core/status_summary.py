"""One place to ask "is the machine OK" (#869).

Seven verbs each answered part of it - doctor, free-doctor, secrets-doctor, health,
status, all-checks, reliability - so the operator had to know which to run. `ops status`
ends with these lines: one per family, each naming the verb that has the detail. Every
line is fail-open; a family that raises says so and the rest still print.
"""

from __future__ import annotations

from collections.abc import Callable

from core.logging import get_logger

logger = get_logger("core.status_summary")


def _doctor(channel_id: str) -> str:
    from core.ops_doctor import gather, last_checks, save_last

    # Wave 112: a doctor result under 12 hours old - the checks cost 5 s of a 7.9 s status.
    checks = last_checks(channel_id)
    if checks is None:
        checks = gather(channel_id).get("checks") or []
        save_last(channel_id, checks)
    failing = [str(c.get("name")) for c in checks if not c.get("ok")]
    passed = len(checks) - len(failing)
    head = f"Doctor: {passed} of {len(checks)} checks pass"
    return head + (f"; failing: {', '.join(failing[:4])}" if failing else "")


def _secrets(channel_id: str) -> str:
    from core.secrets_doctor import gather

    data = gather(channel_id)
    missing = int(data.get("required_missing") or 0)
    placeholder = int(data.get("placeholder") or 0)
    if not missing and not placeholder:
        return "Keys: every required key present"
    bits = []
    if missing:
        bits.append(f"{missing} required key{'s' if missing != 1 else ''} missing")
    if placeholder:
        bits.append(f"{placeholder} placeholder{'s' if placeholder != 1 else ''}")
    return "Keys: " + ", ".join(bits)


def _health(channel_id: str) -> str:
    from core.channel_health import build_health, health_line

    return str(health_line(build_health(channel_id)))


def _budget(_channel_id: str) -> str:
    from core.reliability import summary_line

    return "Budget: " + summary_line()


def _sign_in(channel_id: str) -> str:
    """#971: the channel's YouTube sign-in, or what is wrong with it and the fix."""
    from youtube.oauth import sign_in_reminder, sign_in_status

    problem = sign_in_status(channel_id)
    if problem:
        if len(problem) > 120:  # #1165: the long one is printed once, above
            from youtube.oauth import short_sign_in

            return f"Sign-in: {short_sign_in(channel_id)}"
        return f"Sign-in: {problem}"
    reminder = sign_in_reminder(channel_id)  # #974
    if reminder:
        return f"Sign-in: ok ({channel_id}) - {reminder}"
    from youtube.oauth import sign_in_expiry_line

    lapse = sign_in_expiry_line(channel_id)  # #1437: the date, every day
    return f"Sign-in: ok ({channel_id}) - {lapse}" if lapse else f"Sign-in: ok ({channel_id})"


def _worker(channel_id: str) -> str:
    """#1402: what the upload worker last did."""
    from config import paths
    from jobs.worker_log import last_pass_line

    line = last_pass_line(paths.WORKER_TASK_LOG)
    return f"Worker: {line}" if line else "Worker: no pass logged yet (ops worker-task --install)"


def _overnight(channel_id: str) -> str:
    """#1372: when overnight last started, or that it is overdue. #1468: or that it stopped."""
    from core.nightly_task import _recorded_start, beat_gap_line, overdue_line, overnight_late_short

    stopped = beat_gap_line()
    if stopped:
        return stopped
    overdue = overdue_line()
    if overdue:
        return overdue
    late = overnight_late_short()  # #1380: late, and why - the 10-19 shutdown
    if late:
        return f"Overnight: {late}"
    started = _recorded_start()
    return (
        f"Overnight: last started {started:%a %H:%M}"
        if started
        else "Overnight: no run recorded yet"
    )


_LAPSE_SOON_HOURS = 48


def yours_text(items: list[str]) -> str:
    """#1407 (wave 118): what is yours today, or "Nothing by hand today" when nothing is."""
    return "Yours today: " + "; ".join(items) if items else "Nothing by hand today"


def yours_items(channel_id: str) -> list[str]:
    """The time-sensitive things only: a sign-in that lapses within 48 h, finished videos that
    wait (overnight renders nothing while 3 do), and drafts with the soonest deadline. On 10-20
    they sat in four commands' output - 3 drafts, 3 finished videos and a Wednesday lapse."""
    import os
    import re
    from datetime import datetime, timezone

    items: list[str] = []
    try:
        from youtube.oauth import sign_in_status

        if sign_in_status(channel_id):  # #1537: lapsed - the 48 h line below goes quiet then
            items.append(
                f"sign in again - uploads wait: py -m youtube.oauth_setup --channel {channel_id} "
                "(publish the app first, or it lapses again in 7 days)"
            )
    except Exception as exc:
        logger.debug("yours: sign-in status skipped: %s", exc)
    try:
        from analytics.post_timing import format_scheduled_local
        from youtube.oauth import sign_in_expiry, sign_in_mode

        when = sign_in_expiry(channel_id)
        left = (when - datetime.now(timezone.utc)).total_seconds() if when else -1
        soon = 0 < left <= _LAPSE_SOON_HOURS * 3600
        if when is not None and soon and sign_in_mode(channel_id) == "testing":
            items.append(
                f"publish the Google app before {format_scheduled_local(when, channel_id)} "
                "(ops check-youtube)"
            )
    except Exception as exc:
        logger.debug("yours: sign-in skipped: %s", exc)
    try:
        from core.batch_review import shelf_max, shelf_pause
        from core.stale_renders import shelf_rows

        rows = [row for row in shelf_rows(channel_id) if not row.get("stale")]
        if rows:
            noun = "video" if len(rows) == 1 else "videos"
            text = f"decide {len(rows)} finished {noun} (ops shelf)"
            if shelf_pause(channel_id, waiting=len(rows)):
                text += f" - overnight renders nothing until fewer than {shelf_max()} wait"
            items.append(text)
    except Exception as exc:
        logger.debug("yours: shelf skipped: %s", exc)
    try:
        from core.batch_review import deadline_line, pending_drafts
        from core.output_paths import channel_output_root

        root = os.path.join(channel_output_root(channel_id), "drafts")  # read, never made here
        waiting = (
            [d for d in pending_drafts(channel_id, root=root) if not d.decision]
            if os.path.isdir(root)
            else []
        )
        if waiting:
            noun = "draft" if len(waiting) == 1 else "drafts"
            text = f"review {len(waiting)} {noun} (ops batch-review)"
            found = re.search(
                r"Decide first: (.+?) - kicks off .*?review it by (.+?) for its",
                deadline_line(channel_id, root=root),
            )
            if found:
                title = found.group(1)
                if len(title) > 48:  # at a word, never mid-word
                    title = title[:48].rsplit(" ", 1)[0] + "..."
                text += f" - {title} by {found.group(2)}"
            items.append(text)
    except Exception as exc:
        logger.debug("yours: drafts skipped: %s", exc)
    return items


def _yours(channel_id: str) -> str:
    return yours_text(yours_items(channel_id))


def _tonight(channel_id: str) -> str:
    """#1337: what overnight will do at 5:00 (or at the next power-on, decision 69)."""
    from core.nightly_task import tonight_line

    return tonight_line(channel_id) or "Tonight: overnight has nothing to do"


FAMILIES: list[tuple[str, str, Callable[[str], str]]] = [
    ("Yours today", "ops batch-review", _yours),  # #1407
    ("Sign-in", "ops check-youtube", _sign_in),
    ("Worker", "ops worker-task", _worker),
    ("Overnight", "ops overnight-last", _overnight),
    ("Tonight", "ops overnight-last", _tonight),
    ("Doctor", "ops doctor", _doctor),
    ("Keys", "ops secrets-doctor", _secrets),
    ("Health", "ops health", _health),
    ("Budget", "ops reliability", _budget),
]


def machine_lines(channel_id: str) -> list[str]:
    lines: list[str] = []
    for label, verb, fn in FAMILIES:
        try:
            lines.append(f"{fn(channel_id)}  (detail: {verb})")
        except Exception as exc:
            logger.debug("status %s line skipped: %s", label, exc)
            lines.append(f"{label}: unavailable (see {verb})")
    return lines
