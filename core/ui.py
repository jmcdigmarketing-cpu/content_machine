"""CLI presentation helpers."""

import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

from apis.signal_contract import format_health_line
from config.channels import (
    get_channel_profile,
    get_channel_profiles,
    list_channel_ids,
    resolve_channel_id,
)
from config.settings import get_settings

# ---------------------------------------------------------------------------
# Live spinner for long-running operations
# ---------------------------------------------------------------------------


class DiscoverySpinner:
    """Animated in-place spinner shown during the ~70s discovery phase."""

    _FRAMES: ClassVar[list[str]] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _STAGES: ClassVar[list[tuple[int, str]]] = [
        (0, "Fetching signals"),
        (15, "Scoring variants"),
        (45, "Finishing up"),
    ]

    def __init__(self, label: str = "Discovery"):
        self._label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._t0: float = 0.0
        self._enabled = sys.stdout.isatty()

    def _current_stage(self, elapsed: float) -> str:
        stage = self._STAGES[0][1]
        for threshold, name in self._STAGES:
            if elapsed >= threshold:
                stage = name
        return stage

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            elapsed = time.perf_counter() - self._t0
            frame = self._FRAMES[i % len(self._FRAMES)]
            stage = self._current_stage(elapsed)
            line = f"\r  {frame}  {self._label} · {stage}... {elapsed:.0f}s   "
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write(f"\r{' ' * 70}\r")
        sys.stdout.flush()

    def __enter__(self):
        self._t0 = time.perf_counter()
        if self._enabled:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Domain-specific ASCII art panels
# ---------------------------------------------------------------------------

_DOMAIN_ART: dict[str, str] = {
    "gaming": """\
  ╔═══════════════╗
  ║  ◁  ●  ▷  ●  ║
  ║   [L]   [R]  ║
  ║  ╔═══════╗   ║
  ║  ║ START ║   ║
  ║  ╚═══════╝   ║
  ╚═══════════════╝""",
    "ufc": """\
      ___   ___
     /   | |   \\
    | UFC | UFC |
    |  🥊 | 🥊  |
     \\___| |___/
      OCTAGON
      ───────""",
    "nba": """\
       .-\"\"\"-.
      /  |||  \\
     | --|--|- |
      \\   |   /
       '-...-'
      NBA TODAY""",
    "nfl": """\
      .-\"\"\"-.
     ( o   o )
      |  ▲  |
      | NFL |
     (       )
      '-----' """,
    "finance": """\
    ┌─────────┐
    │ ▲ +2.4% │
    │ ╱╲      │
    │╱  ╲  ╱  │
    │    ╲╱   │
    └─────────┘
      MARKETS """,
}


def print_domain_art(domain: str, *, print_fn=print) -> None:
    """Print a small decorative ASCII panel for the given domain."""
    from core.ascii_art import ascii_enabled
    from core.ui_theme import paint, ui_color_enabled

    if not ascii_enabled():
        return
    art = _DOMAIN_ART.get(domain)
    if not art:
        return
    color = "\033[36m"  # cyan
    for line in art.splitlines():
        print_fn(paint(line, color) if ui_color_enabled() else line)
    print_fn()


HEALTH_LEGEND = "ON=ok | ON (not active)=no match | " "QUOTA/RATE LIMITED/AUTH=issue — see detail"

SIGNAL_ORDER = (
    "youtube",
    "wikipedia",
    "live_scores",
    "stats_context",
    "api_sports",
    "blog_rss",
    "trends",
    "news",
    "youtube_competitors",
    "twitter",
    "reddit",
    "tiktok_trends",
    "sports",
    "odds",
    "autocomplete",
    "twitch",
    "igdb",
    "trendingnow",
    "steam",
    "rawg",
    "anime",
    "tmdb",
    "tvmaze",
    "lastfm",
    "musicbrainz",
    "fred",
    "finnhub",
    "sec_edgar",
    "coingecko",
    "tapology",
    "ufc_context",
)


def section(title: str, print_fn=print):
    from core.ascii_art import section_glyph
    from core.ui_theme import banner_line
    from core.ui_theme import title as theme_title

    width = 56
    print_fn()
    glyph = section_glyph(title)
    print_fn(banner_line("=", width))
    print_fn(theme_title(f"{glyph}{title}".rstrip()))
    print_fn(banner_line("=", width))


def subsection(title: str, print_fn=print):
    from core.ui_theme import subsection_label

    print_fn()
    print_fn(subsection_label(title))


def format_timing(seconds: float) -> str:
    return f"{seconds:.1f}s"


def display_database_status(print_fn=print):
    from config.settings import get_settings

    get_settings()
    if not (os.getenv("DATABASE_URL") or os.getenv("DATABASE_KEY")):
        print_fn("  Database: JSON-only (Postgres not configured)")
        return
    try:
        from storage.db import check_database_connection, is_database_configured
    except ModuleNotFoundError:
        print_fn("  Database: missing sqlalchemy — py -m pip install sqlalchemy psycopg2-binary")
        return
    if is_database_configured():
        ok, detail = check_database_connection()
        print_fn(f"  Database: {'OK' if ok else 'ERROR'} — {detail}")
        if ok:
            try:
                from sqlalchemy import inspect

                from storage.db import get_engine

                if "assets" not in inspect(get_engine()).get_table_names():
                    print_fn("  Hint: assets table missing — run: py -m storage.migrate_schema")
            except Exception:
                pass


def display_competitor_pulse(channel_id: str, topic: str = "", *, print_fn=print) -> None:
    from analytics.competitor_context import (
        list_recent_competitor_titles,
        snapshot_age_hours,
    )

    channel_id = resolve_channel_id(channel_id)
    age = snapshot_age_hours(channel_id)
    titles = list_recent_competitor_titles(channel_id, topic=topic, limit=5)
    if not titles and age is None:
        return
    subsection("Competitor pulse", print_fn)
    if age is not None:
        print_fn(f"  Snapshot: {age:.0f}h old")
    for row in titles:
        print_fn(f"  - {row.get('channel', '?')}: {row.get('title', '')[:55]}")


def display_signal_health(signals: dict[str, Any], *, print_fn=print):
    from core.ui_theme import health_status, warn

    subsection("Signal health", print_fn)

    active, issues, inactive = [], [], []
    all_names = list(SIGNAL_ORDER) + [n for n in signals if n not in SIGNAL_ORDER]
    for name in all_names:
        if name not in signals:
            continue
        sig = signals[name]
        if not sig.get("connected"):
            status = sig.get("status", "")
            if any(k in status.lower() for k in ("quota", "rate", "auth", "key", "no api")):
                issues.append(name)
            else:
                inactive.append(name)
        elif sig.get("active"):
            active.append(name)
        else:
            inactive.append(name)

    if active:
        from core.ui_theme import ok

        print_fn(f"  {ok('Active')} ({len(active)}): " + ", ".join(s.capitalize() for s in active))
    if issues:
        print_fn(
            f"  {warn('Issues')} ({len(issues)}): " + ", ".join(s.capitalize() for s in issues)
        )
    print_fn(f"  Inactive/no match: {len(inactive)} signals  (type 'v' to expand)")
    print_fn()

    expand = input("  [Enter to continue / v to view all signals]: ").strip().lower()
    if expand == "v":
        print_fn()
        print_fn(f"  {warn(HEALTH_LEGEND)}")
        print_fn()
        for name in all_names:
            if name in signals:
                line = format_health_line(name, signals[name])
                print_fn(health_status(name.capitalize(), line.split(": ", 1)[-1]))


def display_variants(
    evaluated: list[tuple[str, float, Any]],
    *,
    print_fn=print,
) -> int:
    """Print variant list; return index of highest score."""
    best_i = max(range(len(evaluated)), key=lambda i: evaluated[i][1])
    subsection("Scored variants (Enter = best)", print_fn)
    from core.ui_theme import paint, score_badge

    for i, (variant, score, _) in enumerate(evaluated, start=1):
        marker = paint("  *", "\033[1m\033[33m") if i - 1 == best_i else "   "
        print_fn(f"{marker} {i}. {score_badge(score)} {variant}")
    return best_i


def display_fact_preview(
    signal_facts: str,
    research_brief=None,
    *,
    print_fn=print,
) -> bool:
    """
    Show a compact summary of the facts that went into the script.
    Splits verified facts from YouTube context-only titles for clarity.
    Returns True if facts are thin (warning condition).
    """
    from core.fact_enrichment import _fact_line_count
    from core.ui_theme import ok, warn

    # Separate YouTube context from verified game/news data
    _YT_HEADERS = (
        "YouTube — real video titles",
        "YouTube video descriptions",
        "YouTube market titles",
    )
    verified_lines: list[str] = []
    context_lines: list[str] = []
    in_yt = False
    for line in signal_facts.splitlines():
        s = line.strip()
        if any(s.startswith(h) for h in _YT_HEADERS):
            in_yt = True
            context_lines.append(s)
            continue
        if in_yt and (
            s.startswith("•")
            or s.startswith("→")
            or line.startswith("  •")
            or line.startswith("  →")
        ):
            context_lines.append(s)
            continue
        in_yt = False
        if s and not s.startswith("⚠"):
            verified_lines.append(s)

    "\n".join(verified_lines)
    is_thin = (
        not signal_facts.strip()
        or signal_facts.startswith("No structured facts")
        or signal_facts.startswith("⚠ THIN FACTS")
        or _fact_line_count(signal_facts) < 3
    )

    subsection("Fact quality", print_fn)
    if is_thin:
        print_fn(
            f"  {warn('⚠ Thin facts')} — limited verified data; script will frame as emerging coverage."
        )
    else:
        print_fn(f"  {ok('✓ Facts available')}")

    # Show verified facts first (what the LLM actually used as source-of-truth)
    if verified_lines:
        for line in verified_lines[:8]:
            short = line[:100] + ("…" if len(line) > 100 else "")
            print_fn(f"  {short}")
    else:
        print_fn("  (no verified game/news data — script based on topic angle only)")

    # Show count of context-only competitor titles
    yt_titles = [line for line in context_lines if line.startswith("•")]
    if yt_titles:
        print_fn(f"  + {len(yt_titles)} competitor title(s) in context block (not used as facts)")

    # Show supporting evidence from brief
    if research_brief and hasattr(research_brief, "supporting_evidence"):
        ev = [e for e in (research_brief.supporting_evidence or []) if e][:3]
        if ev:
            print_fn("  Brief evidence:")
            for e in ev:
                print_fn(f"    · {e[:100]}")

    return is_thin


def display_signal_breakdown(signals: dict[str, Any], *, print_fn=print):
    subsection("Signal breakdown (selected variant)", print_fn)
    print_fn("  (Used in composite = connected + active + score > 0)")
    for name in SIGNAL_ORDER:
        if name not in signals:
            continue
        sig = signals[name]
        score = sig.get("score", 0)
        if sig.get("connected") and sig.get("active") and score > 0:
            print_fn(f"  {name.capitalize()}: {score}")
        else:
            detail = sig.get("status_detail") or sig.get("status", "inactive")
            print_fn(f"  {name.capitalize()}: — ({detail})")
    for name, sig in signals.items():
        if name in SIGNAL_ORDER or name.startswith("_"):
            continue
        score = sig.get("score", 0)
        if sig.get("connected") and sig.get("active") and score > 0:
            print_fn(f"  {name.capitalize()}: {score}")


def prompt_channel_selection(*, print_fn=print, input_fn=input) -> str:
    """Interactive channel picker; returns resolved channel_id."""
    profiles = get_channel_profiles()
    ids = list_channel_ids()
    default_id = resolve_channel_id(get_settings().content_channel_id)

    subsection("Channel", print_fn)
    default_index = ids.index(default_id) if default_id in ids else 0
    for i, cid in enumerate(ids, start=1):
        profile = profiles[cid]
        marker = " *" if i - 1 == default_index else "  "
        domain = f" — {profile.domain}" if profile.domain != "neutral" else ""
        print_fn(f"{marker}{i}. {profile.name} ({cid}){domain}")

    hint = str(default_index + 1)
    choice = input_fn(f"  Select 1-{len(ids)} [Enter = {hint}]: ").strip()
    if not choice:
        return default_id
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ids):
            return ids[idx]
    return default_id


@dataclass
class UploadPlan:
    """User-selected upload behavior after render."""

    mode: str  # skip | queue
    scheduled_at: datetime | None = None
    privacy_status: str = "private"
    # YouTube publishAt — upload soon, YouTube publishes at this time (no PC at slot)
    youtube_publish_at: datetime | None = None


def display_upload_queue(channel_id: str | None = None, *, print_fn=print) -> None:
    """Show upcoming YouTube publish slots already reserved for this channel."""
    from analytics.post_timing import format_scheduled_local
    from analytics.upload_queue import list_queue_entries

    channel_id = resolve_channel_id(channel_id)
    entries = list_queue_entries(channel_id)
    subsection("Publish queue", print_fn)
    if not entries:
        print_fn("  (empty — no upcoming scheduled publishes)")
    else:
        if any(not e.on_youtube for e in entries):
            print_fn(
                "  awaiting_upload = target time reserved; MP4 not on YouTube yet "
                "(upload blocked if quota exhausted)"
            )
        print_fn("  #   When (local)              Title / job")
        for i, entry in enumerate(entries, 1):
            when = format_scheduled_local(entry.publish_at, channel_id)
            print_fn(f"  {i}.  {when:<26}  {entry.title[:40]}  [{entry.status}]")
    print_fn(
        "  Deleted a scheduled video on YouTube? "
        "py main.py → Queue manager, or: py -m scripts.queue_manage --channel "
        f"{channel_id}"
    )


def prompt_startup_mode(*, print_fn=print, input_fn=input) -> str:
    """new_video | queue_manager | intelligence_report | sync_analytics | idea_intake"""
    from core.intelligence_report import intelligence_mode_enabled

    if intelligence_mode_enabled():
        return "intelligence_report"

    subsection("Start", print_fn)
    print_fn("  1) Create new video (discovery pipeline)")
    print_fn("  2) Queue manager — re-queue after YouTube delete")
    print_fn("  3) Intelligence report only (no script/render)")
    print_fn("  4) Sync YouTube analytics (update performance metrics)")
    print_fn("  5) Make a video from my own idea (paste idea or a YouTube link)")
    choice = input_fn("  Select 1-5 [1]: ").strip() or "1"
    if choice == "2":
        return "queue_manager"
    if choice == "3":
        return "intelligence_report"
    if choice == "4":
        return "sync_analytics"
    if choice == "5":
        return "idea_intake"
    return "new_video"


def run_queue_manager_interactive(
    channel_id: str,
    *,
    print_fn=print,
    input_fn=input,
) -> None:
    """Interactive re-queue flow for deleted scheduled videos."""
    from datetime import datetime, timezone

    from analytics.post_timing import format_scheduled_local, next_optimal_post_time
    from analytics.queue_manager import (
        format_requeue_menu_line,
        list_requeue_candidates,
        requeue_content_run,
        reset_publish_for_requeue,
    )

    channel_id = resolve_channel_id(channel_id)
    profile = get_channel_profile(channel_id)

    section("Queue manager", print_fn)
    display_upload_queue(channel_id, print_fn=print_fn)

    candidates = list_requeue_candidates(channel_id)
    subsection("Re-queue (deleted on YouTube before publish)", print_fn)
    if not candidates:
        print_fn("  No runs with a prior upload/schedule found.")
        print_fn("  For never-uploaded MP4s: py -m scripts.requeue_upload --channel", channel_id)
        return

    for i, c in enumerate(candidates, 1):
        print_fn(f"  {i}. {format_requeue_menu_line(c, channel_id)}")

    raw = input_fn("\n  Pick run # to re-queue (Enter = cancel): ").strip()
    if not raw or not raw.isdigit():
        print_fn("  Cancelled.")
        return

    idx = int(raw) - 1
    if idx < 0 or idx >= len(candidates):
        print_fn("  Invalid selection.")
        return

    picked = candidates[idx]
    print_fn(f"\n  Selected run {picked.content_run_id}: {picked.title[:60]}")

    subsection("Re-queue action", print_fn)
    print_fn("  1) Reset only — clear publish_log (no upload job)")
    print_fn("  2) Re-queue now — upload immediately")
    print_fn("  3) Re-queue + schedule — next optimal YouTube slot")
    action = input_fn("  Select 1-3 [3]: ").strip() or "3"

    if action == "1":
        ok = reset_publish_for_requeue(picked.content_run_id, channel_id)
        print_fn("  Reset OK." if ok else "  Nothing to reset.")
        return

    privacy_map = {"1": "private", "2": "unlisted", "3": "public"}
    default_priv = profile.privacy_status_default or "private"
    default_key = next((k for k, v in privacy_map.items() if v == default_priv), "1")
    subsection("Privacy", print_fn)
    print_fn(f"  1) Private  2) Unlisted  3) Public  (default: {default_priv})")
    priv = input_fn(f"  Select 1-3 [{default_key}]: ").strip() or default_key
    privacy = privacy_map.get(priv, default_priv)

    publish_at = None
    if action == "3":
        publish_at = next_optimal_post_time(channel_id, picked.title)
        print_fn(f"  YouTube publish at: {format_scheduled_local(publish_at, channel_id)}")

    try:
        job_id = requeue_content_run(
            picked.content_run_id,
            channel_id,
            privacy_status=privacy,
            youtube_publish_at=publish_at,
            scheduled_at=datetime.now(timezone.utc),
        )
        print_fn(f"\n  Queued job {job_id}. Run: py -m jobs.worker --loop 30")
    except ValueError as exc:
        print_fn(f"\n  Error: {exc}")


def prompt_upload_plan(
    *,
    channel_id: str | None = None,
    topic: str = "",
    print_fn=print,
    input_fn=input,
) -> UploadPlan:
    """Interactive upload timing and privacy (no CLI flags)."""
    from analytics.post_timing import format_scheduled_local, next_optimal_post_time

    profile = get_channel_profile(channel_id)
    default_priv = profile.privacy_status_default or "private"

    display_upload_queue(channel_id, print_fn=print_fn)

    optimal_at = next_optimal_post_time(channel_id or "default", topic)
    optimal_label = format_scheduled_local(optimal_at, channel_id or "default")

    subsection("Upload", print_fn)
    print_fn("  1) Skip — do not upload")
    print_fn("  2) Queue now — worker uploads when you run: py -m jobs.worker")
    print_fn("  3) Queue later — enter minutes from now")
    print_fn(f"  4) Schedule on YouTube for {optimal_label} — next open slot (topic-aware)")
    print_fn("  5) Re-queue deleted video — open queue manager (same as startup option 2)")
    timing = input_fn("  Select 1-5 [1]: ").strip() or "1"

    if timing == "5":
        run_queue_manager_interactive(channel_id or "default", print_fn=print_fn, input_fn=input_fn)
        return UploadPlan(mode="skip")

    if timing == "1":
        return UploadPlan(mode="skip")

    privacy_map = {"1": "private", "2": "unlisted", "3": "public"}
    default_key = next(
        (k for k, v in privacy_map.items() if v == default_priv),
        "1",
    )
    subsection("Privacy", print_fn)
    print_fn(f"  1) Private  2) Unlisted  3) Public  (channel default: {default_priv})")
    priv = input_fn(f"  Select 1-3 [{default_key}]: ").strip() or default_key
    privacy_status = privacy_map.get(priv, default_priv)

    now = datetime.now(timezone.utc)
    if timing == "2":
        return UploadPlan(mode="queue", scheduled_at=now, privacy_status=privacy_status)

    if timing == "3":
        raw = input_fn("  Minutes until upload [60]: ").strip() or "60"
        try:
            minutes = max(1, int(raw))
        except ValueError:
            minutes = 60
        scheduled = now + timedelta(minutes=minutes)
        print_fn(f"  Scheduled for: {scheduled.astimezone().strftime('%Y-%m-%d %H:%M %Z')}")
        return UploadPlan(
            mode="queue",
            scheduled_at=scheduled,
            privacy_status=privacy_status,
        )

    if timing == "4":
        publish_at = next_optimal_post_time(channel_id or "default", topic, after=now)
        label = format_scheduled_local(publish_at, channel_id or "default")
        print_fn(f"  YouTube will publish at: {label}")
        print_fn(
            "  Run worker once to upload the file; your PC does not need to be on at publish time."
        )
        if privacy_status == "unlisted":
            print_fn(
                "  Note: YouTube scheduled API publishes as public at that time; "
                "use private + manual if you need unlisted."
            )
        return UploadPlan(
            mode="queue",
            scheduled_at=now,
            youtube_publish_at=publish_at,
            privacy_status=privacy_status,
        )

    return UploadPlan(mode="skip")


def display_summary(
    *,
    timings: dict[str, float],
    title: str,
    mp4_path: str = "",
    thumbnail_path: str = "",
    print_fn=print,
):
    subsection("Summary", print_fn)
    if timings.get("signals_and_variants"):
        print_fn(f"  Discovery: {format_timing(timings['signals_and_variants'])}")
    if timings.get("variant_scoring"):
        print_fn(f"  Variant scoring: {format_timing(timings['variant_scoring'])}")
    print_fn(f"  Title: {title}")
    if mp4_path:
        print_fn(f"  Video: {mp4_path}")
    if thumbnail_path:
        print_fn(f"  Thumbnail: {thumbnail_path}")
