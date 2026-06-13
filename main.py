"""
Interactive CLI — thin wrapper around core.pipeline.
"""

import sys


def _configure_stdout_utf8() -> None:
    """Braille mascot art needs UTF-8 on Windows consoles (Python 3.7+)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):
        pass


_configure_stdout_utf8()

# Must be first non-stdlib import — loads .env before any signal module reads os.getenv at module level
import config.settings  # noqa: F401
from apis.youtube_api import start_youtube_warmup_background
from config.channels import get_channel_profile
from core.logging import setup_logging
from core.pipeline import run_discovery, run_media_only, run_pipeline
from core.script_length import PRESETS, format_length_report, get_length_preset
from core.ui import (
    DiscoverySpinner,
    display_competitor_pulse,
    display_database_status,
    display_fact_preview,
    display_signal_breakdown,
    display_signal_health,
    display_summary,
    display_upload_queue,
    display_variants,
    print_domain_art,
    prompt_channel_selection,
    prompt_startup_mode,
    prompt_upload_plan,
    run_queue_manager_interactive,
    section,
    subsection,
)
from publishing.repurpose import enqueue_repurpose_jobs
from youtube.check_setup import check_channel_setup

setup_logging()


def _run_intelligence_report_flow(channel_id: str) -> None:
    from core.intelligence_report import (
        build_intelligence_report,
        print_report_summary,
        save_report,
    )

    topic = input("  Topic: ").strip()
    if not topic:
        print("  Topic required.")
        return

    section("Intelligence")
    discovery = run_discovery(topic, channel_id=channel_id)
    display_competitor_pulse(channel_id, topic)
    display_signal_health(discovery.base_signals)
    best_default = display_variants(discovery.evaluated)

    choice = input("\n  Choose 1-5 for report (Enter = best): ").strip()
    variant_index = int(choice) - 1 if choice.isdigit() else best_default

    report = build_intelligence_report(discovery, variant_index=variant_index)
    paths = save_report(report)
    subsection("Report saved")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    print_report_summary(report)


def main():
    from core.intelligence_report import intelligence_mode_enabled, production_tail_enabled

    if production_tail_enabled():
        start_youtube_warmup_background()

    section("Content Machine")
    channel_id = prompt_channel_selection()
    profile = get_channel_profile(channel_id)
    from core.ascii_art import print_startup_panel

    print_startup_panel(channel_id)
    print(f"  Using: {profile.name} ({channel_id})")
    if intelligence_mode_enabled():
        print("  Mode: intelligence only (CONTENT_MODE=intelligence)")

    startup_mode = prompt_startup_mode()
    if startup_mode == "queue_manager":
        run_queue_manager_interactive(channel_id)
        return
    if startup_mode == "intelligence_report":
        _run_intelligence_report_flow(channel_id)
        return
    if startup_mode == "sync_analytics":
        from analytics.sync_metrics import sync_channel

        section("Analytics Sync")
        sync_channel(channel_id)
        print("\n  Run 'py main.py' again to see updated best-bet recommendations.")
        return
    if startup_mode == "idea_intake":
        _run_idea_intake_flow(channel_id)
        return

    _run_new_video_flow(channel_id)


def _read_multiline(prompt: str) -> str:
    """Read possibly-multiline pasted input; finish on a blank line or EOF."""
    print(prompt)
    print("  (paste your idea — press Enter on an empty line to finish)")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            if lines:
                break
            continue  # ignore leading blank lines
        lines.append(line)
    return "\n".join(lines)


def _run_idea_intake_flow(channel_id: str) -> None:
    """Option 5 — generate a video from a user-supplied idea or a YouTube link.

    Accepts a one-line topic, a YouTube link, or a full pasted idea block
    (title + thesis + generator scaffolding). Rich ideas keep their thesis as
    the creative angle that shapes the script.
    """
    from apis.youtube_api import extract_youtube_video_id, fetch_video_metadata
    from core.idea_intake import parse_pasted_idea

    subsection("Your video idea")
    raw = _read_multiline(
        "  Paste a video idea, a topic, or a YouTube link (watch/shorts/youtu.be):"
    )
    if not raw.strip():
        print("  Nothing entered — returning.")
        return

    first_line = raw.strip().splitlines()[0].strip()
    single_line = len(raw.strip().splitlines()) == 1
    creative_brief = ""

    # YouTube link (single line) — fetch the title to seed from.
    if single_line and extract_youtube_video_id(first_line):
        meta = fetch_video_metadata(first_line)
        if meta and meta.get("title"):
            print(f'\n  Found video: "{meta["title"]}"')
            if meta.get("channel"):
                print(f"  Channel: {meta['channel']}")
            angle = input(
                "  Your angle/idea for OUR take (Enter = use the video's topic): "
            ).strip()
            seed_topic = f"{angle} — {meta['title']}" if angle else meta["title"]
        else:
            print("  Could not fetch that video (bad link, quota, or no API key).")
            typed = input("  Type your idea instead: ").strip()
            if not typed:
                print("  Nothing entered — returning.")
                return
            seed_topic = typed
    else:
        # Plain topic or a pasted rich idea block.
        parsed = parse_pasted_idea(raw)
        seed_topic = parsed.seed_topic
        if parsed.is_rich and parsed.thesis:
            creative_brief = parsed.angle
            print(f"\n  Title : {parsed.title}")
            print(f"  Angle : {parsed.thesis[:160]}{'…' if len(parsed.thesis) > 160 else ''}")
            print(f"  Search seed: {seed_topic}")

    print(f"\n  Using idea: {seed_topic}")
    _run_new_video_flow(channel_id, seed_topic=seed_topic, creative_brief=creative_brief)


def _run_new_video_flow(
    channel_id: str, *, seed_topic: str | None = None, creative_brief: str = ""
) -> None:
    upload_report = check_channel_setup(channel_id)
    if not upload_report.ok:
        print("  YouTube upload: not configured (see issues after render)")

    display_upload_queue(channel_id)

    from core.cadence import cadence_status, display_cadence

    try:
        display_cadence(cadence_status(channel_id))
    except Exception:
        pass

    if seed_topic:
        # Idea intake (option 5) — user already gave the idea; skip best-bet.
        topic = seed_topic
    else:
        from core.best_bet import display_best_bet, get_best_bet

        best_bet = get_best_bet(channel_id)
        if best_bet:
            display_best_bet(best_bet)
            use_bet = input("  Use best bet? [y/N]: ").strip().lower()
            if use_bet == "y":
                topic = best_bet.topic
                print(f"  Using: {topic}")
            else:
                topic = input("  Topic: ").strip()
        else:
            topic = input("  Topic: ").strip()

    from analytics.post_timing import display_recommended_time, get_recommended_time

    try:
        display_recommended_time(get_recommended_time(channel_id, topic))
    except Exception:
        pass

    display_database_status()

    section("Discovery")
    profile = get_channel_profile(channel_id)
    print_domain_art(profile.domain)
    with DiscoverySpinner("Discovery"):
        discovery = run_discovery(topic, channel_id=channel_id)
    display_competitor_pulse(channel_id, topic)
    t_disc = discovery.timings.get("signals_and_variants", 0) + discovery.timings.get(
        "variant_scoring", 0
    )
    print(f"  Completed in {t_disc:.1f}s")

    display_signal_health(discovery.base_signals)

    from core.outlier import display_outlier, get_competitor_outlier

    display_outlier(get_competitor_outlier(discovery.base_signals))

    best_default = display_variants(discovery.evaluated)

    choice = input("\n  Choose 1-5 (Enter = best): ").strip()

    variant_index = int(choice) - 1 if choice.isdigit() else best_default

    best_topic, best_score, best_signals = discovery.evaluated[variant_index]

    subsection("Selected")
    print(f"  {best_topic}")
    print(f"  Score: {best_score}")
    display_signal_breakdown(best_signals)

    subsection("Length")
    for key in ("1", "2", "3", "4"):
        p = PRESETS[key]
        print(f"  {key}) {p.label} ({p.duration_hint()}, " f"{p.min_words}-{p.max_words} words)")

    from core.length_recommender import (
        display_recommended_length,
        get_recommended_length,
    )

    length_default = "2"
    try:
        length_rec = get_recommended_length(channel_id, best_topic)
        display_recommended_length(length_rec)
        length_default = length_rec.length_choice
    except Exception:
        pass

    length_choice = input(f"  Select 1-4 [{length_default}]: ").strip() or length_default

    section("Content")
    result = run_pipeline(
        topic,
        discovery=discovery,
        variant_index=variant_index,
        length_choice=length_choice,
        proceed_video=False,
        channel_id=channel_id,
        creative_brief=creative_brief,
    )

    print()
    print(result.script)
    print()
    preset = get_length_preset(length_choice)
    print(f"  Length: {format_length_report(result.script, preset)}")

    if result.run_id:
        print(f"  Run id: {result.run_id}")

    # Show what facts the script was based on — thin facts = warning before render
    from core.fact_enrichment import _fact_line_count, enrich_facts

    _facts_preview = enrich_facts(best_topic, best_signals, channel_id=channel_id, seed_topic=topic)
    display_fact_preview(_facts_preview, print_fn=print)

    # Authenticity / monetisation-safety self-check (Phase O)
    from core.authenticity import (
        display_authenticity_report,
        evaluate_authenticity,
        gate_mode,
    )

    auth = evaluate_authenticity(
        result.script,
        channel_id,
        fact_count=_fact_line_count(_facts_preview),
        exclude_run_id=result.run_id,
    )
    display_authenticity_report(auth)
    if gate_mode() == "block" and auth.verdict == "block":
        override = (
            input("  Authenticity gate flagged this video. Render anyway? [y/N]: ").strip().lower()
        )
        if override != "y":
            display_summary(timings=discovery.timings, title=result.title)
            print("\n  Stopped by authenticity gate (AUTHENTICITY_GATE=block).")
            return

    proceed = input("  Proceed with video? [y/N]: ").strip().lower()

    if proceed != "y":
        display_summary(timings=discovery.timings, title=result.title)
        print("\n  Stopped before render. Title/description saved above.")
        return

    section("Render")
    print("  Progress lines show elapsed time per stage (disable: CONTENT_RENDER_PROGRESS=0)")
    result.mp3_path, result.mp4_path, thumb_path = run_media_only(
        best_topic,
        result.script,
        channel_id=channel_id,
        content_run_id=result.run_id,
        title=result.title,
    )

    from assets.flux_thumbnail import list_channel_thumbnails
    from core.output_paths import ensure_channel_output_dirs

    thumb_dir = ensure_channel_output_dirs(channel_id)["thumbnails"]
    thumb_count = len(list_channel_thumbnails(thumb_dir))
    display_summary(
        timings=discovery.timings,
        title=result.title,
        mp4_path=result.mp4_path or "",
        thumbnail_path=thumb_path,
    )
    if thumb_path:
        print(f"  Thumbnail: {thumb_path}")
        print(f"  Thumbnail folder: {thumb_count} file(s) in {thumb_dir}")
        print("  Upload uses this file when YOUTUBE_THUMBNAIL_UPLOAD=auto (default)")
    else:
        print("  Thumbnail: not generated (set THUMBNAIL_MODE=auto)")
    print()
    print("  Description:")
    print(f"  {result.description}")
    if result.tags:
        print("  Tags:")
        print(f"  {', '.join(result.tags)}")

    upload_plan = prompt_upload_plan(channel_id=channel_id, topic=best_topic)
    thumb_for_upload = thumb_path or None
    if upload_plan.mode == "queue" and result.run_id and result.mp4_path:
        repurpose = enqueue_repurpose_jobs(
            channel_id=channel_id,
            content_run_id=result.run_id,
            file_path=result.mp4_path,
            title=result.title,
            description=result.description,
            tags=result.tags,
            privacy_status=upload_plan.privacy_status,
            scheduled_at=upload_plan.scheduled_at,
            youtube_publish_at=upload_plan.youtube_publish_at,
            thumbnail_path=thumb_for_upload,
        )
        job = repurpose.jobs[0] if repurpose.jobs else None
        if not job:
            print("\n  No publish jobs enqueued (check publishers_enabled).")
            return
        if upload_plan.youtube_publish_at:
            from analytics.post_timing import format_scheduled_local

            when = format_scheduled_local(upload_plan.youtube_publish_at, channel_id)
            print(
                f"\n  Upload queued (job {job.id}) — send to YouTube soon; "
                f"publishes {when} on YouTube."
            )
            print("  Run worker once:  py -m jobs.worker")
            print("  (PC can be off after upload finishes; YouTube handles publish time.)")
        else:
            when = "now"
            if upload_plan.scheduled_at:
                when = upload_plan.scheduled_at.astimezone().strftime("%Y-%m-%d %H:%M")
            print(f"\n  Upload queued (job {job.id}, {upload_plan.privacy_status}, {when}).")
            print("  Run worker:  py -m jobs.worker --loop 30")
        if not upload_report.ok:
            print("  Setup first: py -m youtube.check_setup --channel", channel_id)
            for issue in upload_report.issues[:3]:
                print(f"    - {issue}")

        # Background: pull analytics for previously uploaded videos so best-bet improves
        import threading

        def _bg_analytics():
            try:
                from analytics.sync_metrics import sync_channel

                sync_channel(channel_id)
            except Exception:
                pass

        threading.Thread(target=_bg_analytics, daemon=True, name="analytics-sync").start()


if __name__ == "__main__":
    main()
