"""
Automated content pipeline — generate + queue without manual input.

Picks the best-bet topic (or a supplied seed), runs full discovery → script →
render → enqueue. Designed for cron / Task Scheduler daily runs.

Usage:
    py -m scripts.auto_generate --channel tapin
    py -m scripts.auto_generate --channel tapin --topic "Marvel Rivals meta"
    py -m scripts.auto_generate --channel tapin --length 2 --dry-run
    py -m scripts.auto_generate --channel tapin --sync-analytics

Options:
    --channel     Channel ID (default: tapin)
    --topic       Override best-bet with a specific seed topic
    --length      1=Short 2=Medium 3=Long 4=Extended (default: 2)
    --privacy     unlisted | private | public (default: private)
    --dry-run     Run discovery + script but skip render and queue
    --sync-analytics  Sync YouTube metrics for previously uploaded videos first
    --no-best-bet Skip best-bet and always prompt for or use --topic
    --facts-file  Path to a text file of operator key facts (paste-block format —
                  same parser as the interactive `paste` mode; trade blocks OK)
    --fact        A single key-fact line; repeatable (--fact "..." --fact "...")
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone


def _sync_analytics(channel_id: str) -> None:
    try:
        from analytics.sync_metrics import sync_channel

        print(f"  Syncing analytics for {channel_id}...")
        sync_channel(channel_id)
    except Exception as exc:
        print(f"  Analytics sync skipped: {exc}")


def _pick_topic(channel_id: str, topic_override: str, use_best_bet: bool) -> str:
    if topic_override:
        return topic_override.strip()

    if use_best_bet:
        try:
            from core.best_bet import get_best_bet

            bet = get_best_bet(channel_id)
            if bet:
                print(f"\n  Best Bet: {bet.topic}")
                print(f"  Reason  : {bet.rationale}")
                return bet.topic
        except Exception as exc:
            print(f"  Best-bet failed ({exc}), falling back to input")

    return input("  Topic: ").strip()


def _collect_key_facts(facts_file: str, fact_lines: list[str]) -> list[str]:
    """Headless key facts: a paste-block file and/or repeated --fact lines."""
    from core.operator_facts import load_key_facts

    return load_key_facts(facts_file, fact_lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Automated content generation")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--topic", default="", help="Seed topic (bypasses best-bet)")
    parser.add_argument(
        "--length",
        default="auto",
        choices=["auto", "1", "2", "3", "4"],
        help="auto = learn from engagement history (default)",
    )
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument(
        "--dry-run", action="store_true", help="Discovery + script only — skip render and queue"
    )
    parser.add_argument(
        "--sync-analytics", action="store_true", help="Pull YouTube metrics before generating"
    )
    parser.add_argument(
        "--no-best-bet", action="store_true", help="Always require --topic or manual input"
    )
    parser.add_argument(
        "--force", action="store_true", help="Bypass the cadence cap and authenticity gate"
    )
    parser.add_argument(
        "--facts-file",
        default="",
        help="Text file of operator key facts (paste-block format, e.g. a trade tracker)",
    )
    parser.add_argument(
        "--fact",
        action="append",
        default=[],
        help="Single key-fact line (repeatable)",
    )
    args = parser.parse_args(argv)

    from config.channels import get_channel_profile, resolve_channel_id
    from core.pipeline import run_discovery, run_media_only, run_pipeline
    from core.script_length import PRESETS, format_length_report, get_length_preset

    channel_id = resolve_channel_id(args.channel)
    profile = get_channel_profile(channel_id)

    print(f"\n{'='*56}")
    print(f"  Auto Generate — {profile.name} ({channel_id})")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*56}\n")

    # Optional analytics sync before deciding topic
    if args.sync_analytics:
        _sync_analytics(channel_id)

    # Topic selection
    topic = _pick_topic(channel_id, args.topic, not args.no_best_bet)
    if not topic:
        print("  No topic — exiting.")
        return 1

    # Cadence guardrail — don't flood the channel (policy: variation over volume)
    from core.cadence import cadence_status, display_cadence

    cadence = cadence_status(channel_id)
    display_cadence(cadence)
    if not cadence.ok and not args.force:
        print("  Skipping to protect cadence. Use --force or raise MAX_VIDEOS_PER_WEEK.")
        return 0

    # Length selection — learn from engagement history when --length auto
    length_choice = args.length
    if length_choice == "auto":
        from core.length_recommender import (
            display_recommended_length,
            get_recommended_length,
        )

        length_rec = get_recommended_length(channel_id, topic)
        display_recommended_length(length_rec)
        length_choice = length_rec.length_choice

    print(f"\n  Topic: {topic}")
    print(f"  Length: {PRESETS[length_choice].label} ({PRESETS[length_choice].duration_hint()})")

    from core.run_mode import CostModeBlocked, apply_and_guard

    try:
        apply_and_guard()
    except CostModeBlocked as exc:
        print(f"  {exc}")
        return 2

    # Discovery
    print("\n  Running discovery...")
    from core.ui import DiscoverySpinner

    with DiscoverySpinner("Auto") as spinner:
        discovery = run_discovery(topic, channel_id=channel_id, progress=spinner.report)

    if not discovery.evaluated:
        print("  No variants scored — exiting.")
        return 1

    best_topic, best_score, best_signals = discovery.evaluated[0]
    print(f"  Selected variant: {best_topic} [score={best_score:.1f}]")

    from core.outlier import display_outlier, get_competitor_outlier

    display_outlier(get_competitor_outlier(discovery.base_signals))

    # Operator key facts (headless): file and/or repeated --fact lines — same
    # ground-truth priority as the interactive prompt, saved in full to the vault.
    key_facts = _collect_key_facts(args.facts_file, args.fact)
    if key_facts:
        from core.content_engine import key_facts_for_prompt
        from core.operator_facts import capture_facts_to_vault

        capture_facts_to_vault(channel_id, topic, key_facts)
        sent = key_facts_for_prompt(key_facts)
        print(f"\n  Key facts: {len(key_facts)} collected, {len(sent)} packed for the LLM")

    # Script
    print("\n  Generating script...")
    result = run_pipeline(
        topic,
        discovery=discovery,
        variant_index=0,
        length_choice=length_choice,
        proceed_video=False,
        channel_id=channel_id,
        key_facts=key_facts or None,
    )

    preset = get_length_preset(length_choice)
    length_report = format_length_report(result.script, preset)
    print(f"\n  Title : {result.title}")
    print(f"  Length: {length_report}")
    print(f"  Run id: {result.run_id}")

    from core.hook_score import display_hook_score, score_script_hook
    from core.ui import display_grounding_report

    display_hook_score(score_script_hook(result.script))

    _ungrounded = result.features.get("ungrounded_entities") or []
    needs_grounding_review = display_grounding_report(
        _ungrounded, key_facts=key_facts or None, print_fn=print
    )

    from core.trade_validation import display_trade_validation

    display_trade_validation(result.features.get("trade_warnings") or [], print_fn=print)

    # Fact Engine (Pillar 3): pre-script conflicts, tier lint, claim verifier.
    from core.ui import display_fact_engine_report

    display_fact_engine_report(result.features, print_fn=print)

    # Authenticity / monetisation-safety gate (Phase O)
    from core.authenticity import (
        display_authenticity_report,
        evaluate_authenticity,
        gate_mode,
    )
    from core.fact_enrichment import _fact_line_count, enrich_facts

    facts_preview = enrich_facts(best_topic, best_signals, channel_id=channel_id, seed_topic=topic)
    auth = evaluate_authenticity(
        result.script,
        channel_id,
        fact_count=_fact_line_count(facts_preview),
        exclude_run_id=result.run_id,
    )
    display_authenticity_report(auth)
    if gate_mode() == "block" and auth.verdict == "block" and not args.force:
        print(
            "\n  Blocked by authenticity gate (AUTHENTICITY_GATE=block). Use --force to override."
        )
        return 0

    if needs_grounding_review and not args.force:
        print(
            "\n  Grounding check flagged unsupported specifics (see Fact grounding above). "
            "Use --force to render anyway."
        )
        return 0

    # Grounding gate (Pillar 3, opt-in): GROUNDING_GATE=block stops the render
    # when the claim verifier found unsupported claims — mirrors authenticity.
    from core.claim_verifier import gate_blocks

    if gate_blocks(result.features.get("claim_verification")) and not args.force:
        print("\n  Blocked by grounding gate (GROUNDING_GATE=block). Use --force to override.")
        return 0

    if args.dry_run:
        print("\n  [DRY RUN] Stopping before render.")
        print("\n--- Script preview ---")
        print(result.script[:600] + ("..." if len(result.script) > 600 else ""))
        return 0

    # Render
    print("\n  Rendering...")
    result.mp3_path, result.mp4_path, thumb_path = run_media_only(
        best_topic,
        result.script,
        channel_id=channel_id,
        content_run_id=result.run_id,
        title=result.title,
    )

    if not result.mp4_path:
        print("  Render failed — no mp4 produced.")
        return 1

    print(f"  MP4: {result.mp4_path}")

    # Enqueue upload
    from analytics.post_timing import (
        display_recommended_time,
        get_recommended_time,
        next_optimal_post_time,
    )
    from publishing.repurpose import enqueue_repurpose_jobs

    try:
        display_recommended_time(get_recommended_time(channel_id, topic))
    except Exception as exc:
        # Local import: see the note in scripts/ops.py — .env loads after this module.
        from core.logging import get_logger

        get_logger("scripts.auto_generate").debug("Post-time display skipped: %s", exc)

    pub_at = next_optimal_post_time(channel_id, topic)
    repurpose = enqueue_repurpose_jobs(
        channel_id=channel_id,
        content_run_id=result.run_id,
        file_path=result.mp4_path,
        title=result.title,
        description=result.description,
        tags=result.tags,
        privacy_status=args.privacy,
        youtube_publish_at=pub_at,
        thumbnail_path=thumb_path or None,
    )

    if repurpose.jobs:
        job = repurpose.jobs[0]
        from analytics.post_timing import format_scheduled_local

        when = format_scheduled_local(pub_at, channel_id)
        print(f"\n  Queued job {job.id} — publishes {when}")
        print("  Run worker: py -m jobs.worker --loop 30")
    else:
        print("  No publish jobs enqueued (check publishers_enabled).")

    print("\n  Done.\n")
    return 0


def _main_with_observability(argv=None) -> int:
    try:
        return main(argv)
    finally:
        from core.pipeline import finalize_run_observability

        finalize_run_observability()


if __name__ == "__main__":
    raise SystemExit(_main_with_observability())
