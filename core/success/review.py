"""The 10-minute weekly review (#936; operator, 2026-10-03: the ritual).

`ops review-week` prints the scoreboard, then each video published in the last seven days
with its views, engaged rate and time to the first views; asks your rating (1-5, Enter
skips) and one line of why for each (#935); asks next week's focus, which the startup
banner then shows; and writes a scorecard to `output/<channel>/reviews/<YYYY>-W<ww>.md`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, timedelta

from config.paths import ROOT_DIR
from core.success import goals, verdicts
from core.success.videos import Video, channel_videos

REVIEWS_ROOT = os.path.join(ROOT_DIR, "output")


def week_videos(channel_id: str, *, today: date) -> list[Video]:
    """This machine's videos published in the seven days up to `today`, oldest first."""
    start = today - timedelta(days=7)
    week = [
        v
        for v in channel_videos(channel_id, include_seeded=False)
        if v.published_at is not None and start < v.published_at.date() <= today
    ]
    return list(reversed(week))


def _describe(video: Video) -> str:
    parts = [f"{video.views:,} views"]
    if video.engaged_rate is not None:
        parts.append(f"engaged {video.engaged_rate:.0%}")
    if video.first_views_days is not None:
        parts.append(f"first views in {video.first_views_days} day(s)")
    return " · ".join(parts)


def _history_table(channel_id: str) -> list[str]:
    rows = goals.review_history(channel_id)[-8:]
    if not rows:
        return ["No reviews recorded yet."]

    def _n(value: object) -> str:
        return f"{round(value):,}" if isinstance(value, int | float) else "-"

    out = [
        "| week | views so far | pace / week | need / week | on track | uploads | you agreed |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        agreed = f"{r.get('agreed')} of {r.get('rated')}" if r.get("rated") else "-"
        out.append(
            f"| {r['week']} | {_n(r.get('so_far'))} | {_n(r.get('pace'))} | {_n(r.get('need'))} | "
            f"{'yes' if r.get('on_track') else 'no'} | {_n(r.get('uploads'))} | {agreed} |"
        )
    return out


def scorecard_path(channel_id: str, today: date) -> str:
    year, week, _ = today.isocalendar()
    return os.path.join(REVIEWS_ROOT, channel_id, "reviews", f"{year}-W{week:02d}.md")


def run_review(
    channel_id: str,
    *,
    today: date | None = None,
    ask: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] = print,
) -> str:
    """Run the review; returns the scorecard's path."""
    if ask is None:
        from core.ask import ask_text

        ask = ask_text
    today = today or goals._today()
    board = goals.scoreboard_lines(channel_id, today=today)
    for line in board:
        print_fn(line)
    week = week_videos(channel_id, today=today)
    print_fn("")
    print_fn(f"This week's videos ({len(week)}):" if week else "No videos published this week.")
    rows: list[tuple[Video, str, str]] = []
    for i, video in enumerate(week, 1):
        print_fn(f"  {i}. {video.title} - {_describe(video)}")
        raw = ask("     Your rating 1-5 (Enter skips): ").strip()
        if raw in ("1", "2", "3", "4", "5"):
            note = ask("     One line - why: ").strip()
            verdicts.record(channel_id, video.video_id, int(raw), note=note, title=video.title)
            rows.append((video, raw, note))
        else:
            rows.append((video, "", ""))
    old = goals.focus(channel_id)
    keep = f" (Enter keeps: {old})" if old else " (Enter skips)"
    new_focus = ask(f"Focus for next week{keep}: ").strip()
    if new_focus:
        goals.set_focus(channel_id, new_focus)
    report = verdicts.verdict_report(channel_id)
    for line in report:
        print_fn(line)

    year, week_no, _ = today.isocalendar()
    # #943: one row per ISO week, so the scoreboard can say "on pace N reviews running".
    numbers = goals.scoreboard(channel_id, today=today) or {}
    agreed, rated = verdicts.agreement(channel_id)
    goals.record_week(
        channel_id,
        {
            "week": f"{year}-W{week_no:02d}",
            "so_far": numbers.get("so_far"),
            "pace": numbers.get("pace_per_week"),
            "need": numbers.get("need_per_week"),
            "on_track": bool(numbers.get("on_track")),
            "uploads": numbers.get("uploads_week"),
            "agreed": agreed,
            "rated": rated,
        },
    )
    card = [f"# Weekly review - {channel_id} - {year}-W{week_no:02d}", "", "```", *board, "```", ""]
    card += ["## This week's videos", ""]
    if rows:
        card += ["| video | numbers | your rating | why |", "|---|---|---|---|"]
        for video, rating, note in rows:
            title = video.title.replace("|", "/")
            card.append(f"| {title} | {_describe(video)} | {rating or '-'} | {note or '-'} |")
    else:
        card.append("No videos published this week.")
    card += ["", "## Your verdicts vs the audience", "", "```", *report, "```", ""]
    card += ["## Week over week", "", *_history_table(channel_id), ""]
    card += ["## Focus for next week", "", new_focus or old or "(none set)", ""]
    path = scorecard_path(channel_id, today)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(card))
    print_fn(f"Scorecard written: {path}")
    return path
