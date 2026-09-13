"""
Interactive CLI — thin wrapper around core.pipeline.
"""

import os
import sys


def _configure_stdout_utf8() -> None:
    """Braille mascot art needs UTF-8 on Windows consoles (Python 3.7+)."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (OSError, ValueError):
        pass


_configure_stdout_utf8()

if "--art" in sys.argv:
    os.environ["CONTENT_UI_ART"] = "1"
    sys.argv = [a for a in sys.argv if a != "--art"]

if "--gui" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--gui"]
    import config.settings
    from desktop.launch import launch

    raise SystemExit(launch())

# Must be first non-stdlib import — loads .env before any signal module reads os.getenv at module level
import config.settings  # noqa: F401
from apis.youtube_api import start_youtube_warmup_background
from config.channels import get_channel_profile
from core.ask import ask_choice, ask_confirm, ask_text
from core.logging import get_logger, setup_logging
from core.pipeline import run_discovery, run_media_only, run_pipeline
from core.script_length import PRESETS, format_length_report, get_length_preset
from core.ui import (
    DiscoverySpinner,
    display_database_status,
    display_fact_preview,
    display_grounding_report,
    display_signal_breakdown,
    display_signal_health,
    display_summary,
    display_upload_queue,
    display_variants,
    print_bonus_art,
    print_domain_art,
    prompt_channel_selection,
    prompt_key_facts_result,
    prompt_proceed_or_length,
    prompt_startup_mode,
    prompt_upload_plan,
    run_queue_manager_interactive,
    section,
    subsection,
)
from publishing.repurpose import enqueue_repurpose_jobs
from youtube.check_setup import check_channel_setup

setup_logging()

# Defined after setup_logging() (and after config.settings loaded .env above), so the
# configured CONTENT_LOG_LEVEL is what gets cached.
logger = get_logger("main")


def _run_intelligence_report_flow(channel_id: str) -> None:
    try:
        _run_intelligence_report_flow_body(channel_id)
    except KeyboardInterrupt:
        print("\n  Cancelled — back to the menu.")


def _run_intelligence_report_flow_body(channel_id: str) -> None:
    from core.intelligence_report import (
        build_intelligence_report,
        print_report_summary,
        save_report,
    )

    topic = ask_text("  Topic: ").strip()
    if not topic:
        print("  Topic required.")
        return

    section("Intelligence")
    discovery = run_discovery(topic, channel_id=channel_id)
    display_signal_health(discovery.base_signals, topic=topic, channel_id=channel_id)
    from core.angle_intent import ANGLE_DEFAULT, angle_intent_note, detect_angle_intent

    angle_intent = detect_angle_intent(topic)
    if angle_intent != ANGLE_DEFAULT:
        print(f"  {angle_intent_note(angle_intent)}")

    best_default = display_variants(
        discovery.evaluated,
        channel_id=channel_id,
        raw_scores=discovery.raw_scores,
        angle_scores=discovery.angle_scores,
    )

    choice = ask_choice("\n  Choose 1-5 for report (Enter = best): ")
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
    from core.themes import set_channel_theme

    set_channel_theme(channel_id)
    from core.pinned_status import set_pin_context

    set_pin_context(channel_id)
    from core.ascii_art import print_startup_panel

    print_startup_panel(channel_id)
    print(f"  Using: {profile.name} ({channel_id})")
    try:
        from core.human_presence import touch
        from core.operator_timer import install_input_wrapper, start_run

        start_run()
        install_input_wrapper()
        touch()
    except Exception as exc:
        logger.debug("operator timer/heartbeat skipped: %s", exc)
    try:
        from apis.youtube_quota import format_uploads_left

        print(f"  YouTube: {format_uploads_left()}")
        try:
            from core.win_notify import notify_uploads_left

            notify_uploads_left()
        except Exception as exc:
            logger.debug("uploads-left toast skipped: %s", exc)
    except Exception as exc:
        logger.debug("uploads-left startup line skipped: %s", exc)
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

    # Cost mode ($0 Free vs Standard) — only the render flows below incur provider cost.
    if not _apply_cost_mode_interactive():
        return

    if startup_mode == "idea_intake":
        _run_idea_intake_flow(channel_id)
        return

    _run_new_video_flow(channel_id)


def _apply_cost_mode_interactive() -> bool:
    """Prompt for the run's cost mode and apply it. False = stop before discovery."""
    from core.run_mode import (
        COST_MODE_FREE,
        CostModeBlocked,
        abort_if_first_call_unusable,
        apply_cost_mode,
        inspect_first_calls,
    )
    from core.ui import prompt_cost_mode

    result = apply_cost_mode(prompt_cost_mode())
    if result.mode != COST_MODE_FREE:
        for warning in inspect_first_calls().warnings:
            print(f"  ! {warning}")
        return True
    voice = result.applied.get("TTS_PROVIDER", "BLOCKED")
    llm = result.applied.get("LLM_PREMIUM_PROVIDER", "BLOCKED")
    print(f"  Free mode ($0): voice={voice}  llm={llm}  signals=free (paid signals skipped)")
    for blocker in result.blockers:
        print(f"  ! {blocker}")
    if result.blocked:
        print("  ! Free mode can't continue until the above are resolved (docs/free_mode.md).")
        print("  Stopping before discovery.")
        return False
    try:
        abort_if_first_call_unusable(result)
    except CostModeBlocked as exc:
        print(f"  ! {exc}")
        print("  Stopping before discovery.")
        return False
    return True


def _read_multiline(prompt: str) -> str:
    """Read possibly-multiline pasted input; finish on a blank line or EOF."""
    print(prompt)
    print("  (paste your idea — press Enter on an empty line to finish)")
    lines: list[str] = []
    while True:
        try:
            line = ask_text()
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
    try:
        _run_idea_intake_flow_body(channel_id)
    except KeyboardInterrupt:
        print("\n  Cancelled — back to the menu.")


def _run_idea_intake_flow_body(channel_id: str) -> None:
    from apis.youtube_api import extract_youtube_video_id, fetch_video_metadata
    from core.idea_intake import (
        creative_brief_for_run,
        parse_pasted_idea,
        seed_and_brief_from_youtube,
    )

    subsection("Your video idea")
    raw = _read_multiline(
        "  Paste a video idea, a topic, or a YouTube link (watch/shorts/youtu.be):"
    )
    # Drop any scaffolding still buffered from the paste (e.g. "Develop idea",
    # "Why this could fit…") so it can't auto-answer the upcoming prompts.
    from core.console_input import drain_stdin

    drain_stdin()
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
            angle = ask_text(
                "  Your angle/idea for OUR take (Enter = use the video's topic): "
            ).strip()
            seed_topic, creative_brief = seed_and_brief_from_youtube(meta["title"], angle)
        else:
            print("  Could not fetch that video (bad link, quota, or no API key).")
            typed = ask_text("  Type your idea instead: ").strip()
            if not typed:
                print("  Nothing entered — returning.")
                return
            seed_topic = typed
            creative_brief = typed
    else:
        # Plain topic or a pasted rich idea block.
        parsed = parse_pasted_idea(raw)
        seed_topic = parsed.seed_topic
        creative_brief = creative_brief_for_run(parsed)
        if parsed.is_rich and parsed.thesis:
            print(f"\n  Title : {parsed.title}")
            print(f"  Angle : {parsed.thesis[:160]}{'…' if len(parsed.thesis) > 160 else ''}")
            print(f"  Search seed: {seed_topic}")

    print(f"\n  Using idea: {seed_topic}")
    _run_new_video_flow(channel_id, seed_topic=seed_topic, creative_brief=creative_brief)


def _run_new_video_flow(
    channel_id: str, *, seed_topic: str | None = None, creative_brief: str = ""
) -> None:
    from core.llm_router import LLMUnavailableError

    try:
        _run_new_video_flow_body(channel_id, seed_topic=seed_topic, creative_brief=creative_brief)
    except LLMUnavailableError as exc:
        # Free ($0) mode pins rate-limited free models with no paid fallback — degrade
        # to a clean message instead of a traceback when they're all unavailable.
        print("\n  LLM unavailable — every model for this step failed.")
        print(f"    {exc}")
        print(
            "    Free ($0) mode uses rate-limited free models. Wait ~30s and retry, add\n"
            "    OPENROUTER_API_KEY for higher limits (or run Ollama), or pick Standard mode."
        )
    except KeyboardInterrupt:
        print("\n  Cancelled — back to the menu.")
        return
    finally:
        from core.pipeline import finalize_run_observability

        finalize_run_observability()


def _ask_topic_or_thoughts(creative_brief: str = "") -> tuple[str, str]:
    """Option 1 type-your-own: a topic, or the idea in your own words (run 77).

    Thoughts typed (or pasted over several lines) are not a search string. Discovery
    searches the short subject pulled out of them; the full thoughts become the brief
    the angles, the ranking and the script answer.
    """
    from core.console_input import input_pending, read_pending_lines
    from core.idea_intake import creative_brief_for_run, parse_pasted_idea

    typed = ask_text("  Topic (or your thoughts on the idea): ").strip()
    if typed and input_pending():
        extra = [line for line in read_pending_lines() if line.strip()]
        if extra:
            typed = "\n".join([typed, *extra])
    if not typed:
        return "", creative_brief

    parsed = parse_pasted_idea(typed)
    topic = parsed.seed_topic or typed
    brief = creative_brief or creative_brief_for_run(parsed)
    if topic.lower() != " ".join(typed.split()).lower():
        print(f"  Search seed: {topic}")
        print("  Your thoughts steer the angles, their ranking, and the script.")
    return topic, brief


def _run_new_video_flow_body(
    channel_id: str, *, seed_topic: str | None = None, creative_brief: str = ""
) -> None:
    upload_report = check_channel_setup(channel_id)
    if not upload_report.ok:
        print("  YouTube upload: not configured (see issues after render)")

    display_upload_queue(channel_id)

    from core.cadence import cadence_status, display_cadence

    try:
        display_cadence(cadence_status(channel_id))
    except Exception as exc:
        logger.debug("display_cadence skipped: %s", exc)

    from core.metrics_gate import metrics_gate_reason

    metrics_reason = metrics_gate_reason(channel_id)
    if metrics_reason:
        print(f"\n  ! {metrics_reason}")
        if not ask_confirm("  Start the next video anyway? [y/N]: ", default=False):
            print("  Stopped — sync analytics first: py -m scripts.ops sync-metrics")
            return

    if seed_topic:
        # Idea intake (option 5) — user already gave the idea; skip best-bet.
        topic = seed_topic
    else:
        from core.best_bet import best_bet_option_count, display_best_bets, get_best_bets

        options = get_best_bets(channel_id, best_bet_option_count())
        if options:
            display_best_bets(options)
            sel = ask_choice(f"  Use a best bet? [1-{len(options)} / Enter = type your own]: ")
            if sel.isdigit() and 1 <= int(sel) <= len(options):
                topic = options[int(sel) - 1].topic
                print(f"  Using: {topic}")
            else:
                topic, creative_brief = _ask_topic_or_thoughts(creative_brief)
        else:
            topic, creative_brief = _ask_topic_or_thoughts(creative_brief)

    from analytics.post_timing import display_recommended_time, get_recommended_time

    try:
        display_recommended_time(get_recommended_time(channel_id, topic))
    except Exception as exc:
        logger.debug("display_recommended_time skipped: %s", exc)

    display_database_status()

    section("Discovery")
    profile = get_channel_profile(channel_id)
    print_domain_art(profile.domain, topic=topic)
    with DiscoverySpinner("Discovery") as spinner:
        discovery = run_discovery(
            topic, channel_id=channel_id, progress=spinner.report, brief=creative_brief
        )
    t_disc = discovery.timings.get("signals_and_variants", 0) + discovery.timings.get(
        "variant_scoring", 0
    )
    print(f"  Completed in {t_disc:.1f}s")

    display_signal_health(discovery.base_signals, topic=topic, channel_id=channel_id)

    from core.outlier import display_outlier, get_competitor_outlier

    display_outlier(get_competitor_outlier(discovery.base_signals))

    from core.angle_intent import ANGLE_DEFAULT as _ANGLE_DEFAULT
    from core.angle_intent import angle_intent_note as _intent_note
    from core.angle_intent import detect_angle_intent as _detect_intent

    _intent = _detect_intent(topic)
    if _intent == _ANGLE_DEFAULT and creative_brief:
        _intent = _detect_intent(creative_brief)
    if _intent != _ANGLE_DEFAULT:
        print(f"  {_intent_note(_intent)}")

    best_default = display_variants(
        discovery.evaluated,
        channel_id=channel_id,
        raw_scores=discovery.raw_scores,
        angle_scores=discovery.angle_scores,
        own_idea=seed_topic,
    )

    prompt = "\n  Choose 1-5 (Enter = best"
    if seed_topic:
        prompt += ", 0 = your idea"
    prompt += "): "
    choice = ask_choice(prompt)

    if seed_topic and choice == "0":
        best_topic, best_score, best_signals = seed_topic, 0.0, discovery.base_signals
        variant_index = -1
    else:
        variant_index = int(choice) - 1 if choice.isdigit() else best_default
        best_topic, best_score, best_signals = discovery.evaluated[variant_index]

    subsection("Selected angle")
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
    except Exception as exc:
        logger.debug("get_recommended_length skipped: %s", exc)

    _len_in = ask_choice(f"  Select 1-4 [{length_default}]: ")
    length_choice = _len_in if _len_in in ("1", "2", "3", "4") else length_default

    fact_selection = prompt_key_facts_result(
        topic,
        channel_id,
        signals=best_signals,
    )
    key_facts = fact_selection.facts

    section("Content")
    print_bonus_art(key="mario")

    # Generate → review → decide loop. The operator can regenerate the script at a
    # different length (+ longer / - shorter / 1-4) without re-running discovery —
    # run_pipeline reuses the discovery passed in, so only the script + checks re-run.
    tts_force = False
    while True:
        result = run_pipeline(
            topic,
            discovery=discovery,
            variant_index=variant_index,
            length_choice=length_choice,
            proceed_video=False,
            channel_id=channel_id,
            creative_brief=creative_brief,
            key_facts=key_facts or None,
            vault_relevance_audit=fact_selection.vault_audit,
            source_urls=fact_selection.source_urls,
            relevance_corpus=fact_selection.relevance_corpus,
            menu_path="5" if seed_topic else "1",
        )

        print()
        print(result.script)
        print()
        if result.title:
            print(f"  Title: {result.title}")
            print()
        preset = get_length_preset(length_choice)
        print(f"  Length: {format_length_report(result.script, preset)}")

        from core.hook_score import display_hook_score, score_script_hook

        display_hook_score(score_script_hook(result.script))

        if result.run_id:
            print(f"  Run id: {result.run_id}")

        # Show what facts the script was based on — thin facts = warning before render
        from core.fact_enrichment import _fact_line_count, enrich_facts

        _facts_preview = enrich_facts(
            best_topic, best_signals, channel_id=channel_id, seed_topic=topic
        )
        display_fact_preview(_facts_preview, print_fn=print)

        _ungrounded = result.features.get("ungrounded_entities") or []
        needs_grounding_review = display_grounding_report(
            _ungrounded, key_facts=key_facts or None, print_fn=print
        )

        # Semantic trade validation (opt-in, SEMANTIC_TRADE_VALIDATION)
        from core.trade_validation import display_trade_validation

        display_trade_validation(result.features.get("trade_warnings") or [], print_fn=print)

        # Fact Engine (Pillar 3): pre-script conflicts, tier lint, claim verifier.
        from core.ui import display_fact_engine_report

        needs_fact_review = display_fact_engine_report(result.features, print_fn=print)

        # Authenticity / monetisation-safety self-check (Phase O)
        from core.authenticity import (
            blocks_render,
            display_authenticity_report,
            evaluate_authenticity,
        )

        auth = evaluate_authenticity(
            result.script,
            channel_id,
            fact_count=_fact_line_count(_facts_preview),
            exclude_run_id=result.run_id,
        )
        display_authenticity_report(auth)
        if blocks_render(auth):
            if not ask_confirm(
                "  Authenticity gate flagged this video. Render anyway? [y/N]: ",
                default=False,
            ):
                display_summary(
                    timings=discovery.timings,
                    title=result.title,
                    cost=result.features.get("cost"),
                )
                print("\n  Stopped by authenticity gate (AUTHENTICITY_GATE=block).")
                return

        # Negative-fact veto (#333). A claim the operator already paid to correct
        # is not a warning: the recorded decision was a hard block, so this gate
        # defaults to `block` rather than `warn`. NEGATIVE_FACT_GATE=warn opts out.
        from core.negative_facts import negative_gate_blocks

        if negative_gate_blocks(result.features.get("ungrounded_entities")):
            retracted = [
                item
                for item in (result.features.get("ungrounded_entities") or [])
                if str(item).startswith("negative-fact: ")
            ]
            print("\n  ! Re-asserts a claim you already walked back:")
            for item in retracted:
                print(f"      {item}")
            if not ask_confirm(
                "  Negative-fact veto. Render anyway? [y/N]: ",
                default=False,
            ):
                print("\n  Stopped by the negative-fact gate (NEGATIVE_FACT_GATE=block).")
                return

        # Grounding gate (Pillar 3, opt-in): unsupported claims become a hard stop
        # the operator must override — mirrors the authenticity gate above.
        from core.claim_verifier import gate_blocks

        if gate_blocks(result.features.get("claim_verification")):
            if not ask_confirm(
                "  Grounding gate flagged unsupported claims. Render anyway? [y/N]: ",
                default=False,
            ):
                display_summary(
                    timings=discovery.timings,
                    title=result.title,
                    cost=result.features.get("cost"),
                )
                print("\n  Stopped by grounding gate (GROUNDING_GATE=block).")
                return

        from core.thin_facts import thin_facts_abort_reason

        thin_reason = thin_facts_abort_reason(
            fact_count=_fact_line_count(_facts_preview),
            features=result.features,
        )
        if thin_reason:
            print(f"\n  ! {thin_reason}")
            try:
                from core.review_booth import write_thin_facts_screen

                write_thin_facts_screen(thin_reason, fact_count=_fact_line_count(_facts_preview))
            except Exception as exc:
                from core.logging import get_logger

                get_logger("main").debug("thin-facts HTML skipped: %s", exc)
            if not ask_confirm("  Thin facts — render anyway and pay TTS? [y/N]: ", default=False):
                display_summary(
                    timings=discovery.timings,
                    title=result.title,
                    cost=result.features.get("cost"),
                )
                print("\n  Stopped before TTS (thin facts). Draft is saved.")
                return

        from core.tts_char_cap import tts_char_cap_reason, tts_char_cap_warn

        cap_reason = tts_char_cap_reason(result.script, length_choice=length_choice)
        cap_warn = tts_char_cap_warn(result.script, length_choice=length_choice)
        tts_force = False
        if cap_warn:
            print(f"\n  ! {cap_warn}")
        if cap_reason:
            print(f"\n  ! {cap_reason}")
            if not ask_confirm("  Over length for TTS — render anyway? [y/N]: ", default=False):
                display_summary(
                    timings=discovery.timings,
                    title=result.title,
                    cost=result.features.get("cost"),
                    script=result.script,
                )
                print("\n  Stopped before TTS (character cap). Draft is saved.")
                return
            tts_force = True

        if needs_grounding_review:
            print(
                "\n  Grounding check flagged unsupported specifics (see Fact grounding above). "
                "Rendering without fixing risks shipping hallucinations."
            )
        if needs_fact_review:
            print(
                "\n  Fact Engine flagged items above (conflicts / tiers / claims). "
                "Verify before publishing."
            )

        # Pillar 2: one weighted report card over the scores above (read-only).
        from core.video_grade import display_grade_for_run

        display_grade_for_run(result.run_id)

        decision, length_choice = prompt_proceed_or_length(length_choice)
        if decision == "render":
            break
        if decision == "relength":
            new_preset = get_length_preset(length_choice)
            print(f"\n  Regenerating at {new_preset.label} target (new LLM call)...")
            continue
        # stop
        display_summary(
            timings=discovery.timings,
            title=result.title,
            cost=result.features.get("cost"),
        )
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
        force=tts_force,
        length_choice=length_choice,
    )

    from assets.flux_thumbnail import list_channel_thumbnails
    from core.output_paths import ensure_channel_output_dirs

    thumb_dir = ensure_channel_output_dirs(channel_id)["thumbnails"]
    thumb_count = len(list_channel_thumbnails(thumb_dir))

    # Render happened here (not via the pipeline). run_media_only has just persisted the
    # render-inclusive cost, so read it back rather than recomputing: this used to be a
    # display-only recompute that was never written anywhere, which is exactly how the
    # ledger ended up with tts=0 on every rendered run. Reading back keeps the number
    # the operator sees identical to the one economics will report.
    from core.run_features import load_features

    persisted_cost = (load_features(result.run_id) or {}).get("cost")
    if persisted_cost:
        result.features["cost"] = persisted_cost
    else:  # no run id (or DB unavailable) — fall back to an in-memory estimate
        from core.cost_meter import estimate_run_cost

        result.features["cost"] = estimate_run_cost(
            script=result.script, signals=best_signals, rendered=True
        )
    display_summary(
        timings=discovery.timings,
        title=result.title,
        mp4_path=result.mp4_path or "",
        thumbnail_path=thumb_path,
        cost=result.features.get("cost"),
        script=result.script,
    )
    from core.ui import print_celebration

    print_celebration()  # themed celebratory flourish (random when unthemed)
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
            # Report what will actually happen: an immediate public upload is held
            # unlisted for review by default, so echoing the request would promise
            # public and deliver unlisted (run 69).
            from publishing.youtube_publisher import queued_privacy_label

            privacy_label = queued_privacy_label(
                upload_plan.privacy_status, upload_plan.youtube_publish_at
            )
            print(f"\n  Upload queued (job {job.id}, {privacy_label}, {when}).")
            print("  Run worker:  py -m jobs.worker --loop 30")
        from core.ui import maybe_print_milestone

        maybe_print_milestone(channel_id)
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
            except Exception as exc:
                logger.debug("sync_channel skipped: %s", exc)

        threading.Thread(target=_bg_analytics, daemon=True, name="analytics-sync").start()


if __name__ == "__main__":
    main()
