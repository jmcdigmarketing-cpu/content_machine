"""
Content OS operator commands — run individually or in batches.

Usage:
    py -m scripts.ops --help
    py -m scripts.ops list
    py -m scripts.ops all-setup --channel tapin
    py -m scripts.ops validate
    py -m scripts.ops test
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable

CommandFn = Callable[[argparse.Namespace], int]

COMMANDS: dict[str, tuple[str, CommandFn]] = {}


def _register(name: str, help_text: str):
    def decorator(fn: CommandFn):
        COMMANDS[name] = (help_text, fn)
        return fn

    return decorator


def _run_module(module: str, *args: str) -> int:
    cmd = [sys.executable, "-m", module, *args]
    print(f"\n>> {' '.join(cmd)}")
    return subprocess.call(cmd)


@_register("migrate-layout", "Move root runtime files into data/ and config/secrets/")
def cmd_migrate_layout(_args: argparse.Namespace) -> int:
    return _run_module("storage.migrate_layout")


@_register("ingest", "Ingest a URL / PDF path / YouTube link into the vault as a provenance note")
def cmd_ingest(args: argparse.Namespace) -> int:
    source = getattr(args, "source", None) or getattr(args, "target", None)
    if not source:
        print("Usage: py -m scripts.ops ingest <url|pdf-path|youtube-link> [--channel tapin]")
        return 2
    from core.vault_ingest import ingest, save_to_vault

    record = ingest(source)
    lines = len([ln for ln in (record.get("text") or "").splitlines() if ln.strip()])
    print(f"Ingested [{record.get('kind')}] {source}")
    print(f"  extracted {lines} line(s), confidence={record.get('confidence')}")
    path = save_to_vault(record, args.channel)
    if path:
        print(f"  saved -> {path}")
    else:
        print("  not saved (set OBSIDIAN_VAULT_PATH, or nothing was extracted)")
    return 0


@_register("init-db", "Create SQL tables (Postgres)")
def cmd_init_db(_args: argparse.Namespace) -> int:
    return _run_module("storage.init_db")


@_register("migrate-schema", "Apply incremental DDL on existing Postgres")
def cmd_migrate_schema(_args: argparse.Namespace) -> int:
    return _run_module("storage.migrate_schema")


@_register("seed", "Seed TapIn performance + publish history")
def cmd_seed(args: argparse.Namespace) -> int:
    extra = ["--channel", args.channel]
    if args.init_db:
        extra.append("--init-db")
    return _run_module("analytics.seed_tapin", *extra)


@_register("validate", "Validate config/channels.json")
def cmd_validate(args: argparse.Namespace) -> int:
    extra = []
    if args.channel:
        extra.extend(["--channel", args.channel])
    return _run_module("config.validate_channels", *extra)


@_register("learn-schedule", "Show static vs learned post slots")
def cmd_learn_schedule(args: argparse.Namespace) -> int:
    return _run_module("analytics.learn_schedule", "--channel", args.channel)


@_register("recommend-time", "Recommend next post time from engagement history")
def cmd_recommend_time(args: argparse.Namespace) -> int:
    return _run_module("analytics.post_timing", "--channel", args.channel, "--topic", args.topic)


@_register("recommend-length", "Recommend video length from engagement history")
def cmd_recommend_length(args: argparse.Namespace) -> int:
    return _run_module("core.length_recommender", "--channel", args.channel, "--topic", args.topic)


@_register("weights", "Print learned signal weights for channel")
def cmd_weights(args: argparse.Namespace) -> int:
    return _run_module(
        "analytics.compute_weights", "--channel", args.channel, "--domain", args.domain
    )


@_register("check-youtube", "Verify YouTube OAuth + upload env")
def cmd_check_youtube(args: argparse.Namespace) -> int:
    return _run_module("youtube.check_setup", "--channel", args.channel)


@_register("sync-metrics", "Pull YouTube Analytics into performance memory")
def cmd_sync_metrics(args: argparse.Namespace) -> int:
    return _run_module("analytics.sync_metrics", "--channel", args.channel)


@_register("seo-refresh", "Refresh trending tag hints (YouTube + RSS)")
def cmd_seo_refresh(args: argparse.Namespace) -> int:
    return _run_module("analytics.seo_refresh", "--channel", args.channel)


@_register("weekly-report", "Rules-based weekly intelligence (winners/losers by feature)")
def cmd_weekly_report(args: argparse.Namespace) -> int:
    return _run_module("analytics.weekly_report", "--channel", args.channel)


@_register("backfill-features", "Reconstruct features_json for historical runs")
def cmd_backfill_features(args: argparse.Namespace) -> int:
    return _run_module("analytics.backfill_features", "--channel", args.channel)


@_register("vault-sync", "Write machine beliefs + run dossiers into the Obsidian vault")
def cmd_vault_sync(args: argparse.Namespace) -> int:
    from core.vault_dossiers import refresh_dossiers
    from core.vault_writeback import write_channel_beliefs

    path = write_channel_beliefs(args.channel)
    if path:
        print(f"Wrote machine beliefs to {path}")
    else:
        print("Beliefs: nothing written (OBSIDIAN_VAULT_PATH unset or no analytics yet).")
    n_doss = refresh_dossiers(args.channel)
    print(f"Dossiers: {n_doss} run note(s) refreshed" if n_doss else "Dossiers: none written.")
    return 0


@_register("queue-manage", "Re-queue after deleting scheduled YouTube video")
def cmd_queue_manage(args: argparse.Namespace) -> int:
    extra = ["--channel", args.channel]
    if args.run_id:
        extra.extend(["--run-id", str(args.run_id)])
    if getattr(args, "queue_requeue", False):
        extra.append("--requeue")
    if getattr(args, "queue_reset", False):
        extra.append("--reset")
    if getattr(args, "queue_schedule", False):
        extra.append("--schedule")
    return _run_module("scripts.queue_manage", *extra)


@_register("status", "Queue, uploads, recent runs, SEO/competitors")
def cmd_status(args: argparse.Namespace) -> int:
    return _run_module("scripts.status", "--channel", args.channel)


@_register("reliability", "Credit/quota dashboard (Apify + LLM budgets, breakers, cache hit-rate)")
def cmd_reliability(_args: argparse.Namespace) -> int:
    from core.reliability import render

    print(render())
    return 0


@_register(
    "voices", "List TTS voices — ElevenLabs account + local Piper — and what each channel uses"
)
def cmd_voices(_args: argparse.Namespace) -> int:
    from core.voice_catalog import render

    print(render())
    return 0


def _ollama_server_probe(timeout: float = 2.0) -> tuple[bool, int]:
    """(reachable, model_count) for the local Ollama server. Never raises.

    Unlike run_mode._ollama_ready() - which returns False when OLLAMA_MODEL is unset -
    this reports the server being up even before a model is chosen, so free-doctor can
    tell "Ollama running, just pick a model" apart from "no free LLM installed at all".
    """
    import os

    base = (os.getenv("OLLAMA_BASE_URL", "") or "http://localhost:11434/v1").strip()
    root = base.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    try:
        import requests

        resp = requests.get(f"{root}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return False, 0
        models = resp.json().get("models", []) or []
        return True, len(models)
    except Exception:
        return False, 0


@_register("free-doctor", "Check the truly-free ($0) stack: Ollama, Piper, signals, DuckDuckGo")
def cmd_free_doctor(_args: argparse.Namespace) -> int:
    import importlib.util
    import os

    import config.settings  # noqa: F401  # load .env so configured keys are seen
    from core.run_mode import _ollama_ready, free_backend_readiness

    r = free_backend_readiness()
    print("Truly-free ($0) readiness")
    print("=" * 48)

    ready, model = _ollama_ready()
    if ready:
        print(f"  LLM        : OK  ollama (local, unlimited) - model {model}")
    elif os.getenv("OLLAMA_MODEL", "").strip():
        print(
            f"  LLM        : X   OLLAMA_MODEL={os.getenv('OLLAMA_MODEL')} set, server unreachable"
        )
        print("                   start it: `ollama serve` (+ `ollama pull <model>`)")
    else:
        # OLLAMA_MODEL unset. Tell "Ollama running, just pick a model" apart from the
        # rate-limited cloud fallback and "nothing installed".
        up, n_models = _ollama_server_probe()
        if up:
            print("  LLM        : X   Ollama running, but OLLAMA_MODEL not set")
            if n_models:
                print("                   a model is already pulled - set OLLAMA_MODEL=<name>")
            else:
                print("                   pull one: `ollama pull llama3.1:8b`, set OLLAMA_MODEL")
        elif os.getenv("OPENROUTER_API_KEY", "").strip():
            print("  LLM        : ~   openrouter :free (cloud, RATE-LIMITED) - not truly free")
            print("                   for unlimited $0: install Ollama, `ollama pull llama3.1:8b`,")
            print("                   then set OLLAMA_MODEL=llama3.1:8b")
        else:
            print("  LLM        : X   no free LLM")
            print("                   install Ollama, `ollama pull llama3.1:8b`, set OLLAMA_MODEL")

    if r.tts_provider:
        print(f"  Voice      : OK  {r.tts_provider} (local)")
    elif importlib.util.find_spec("piper") is not None:
        print("  Voice      : X   piper installed, but PIPER_VOICE not set / file missing")
        print("                   download a voice .onnx (Piper releases), set PIPER_VOICE=<path>")
    else:
        print('  Voice      : X   pip install -e ".[free]" ; set PIPER_VOICE=<voice.onnx>')

    if r.youtube_free:
        print("  YouTube    : OK  yt-dlp (keyless)")
    else:
        print("  YouTube    : X   pip install yt-dlp")

    if r.reddit_free:
        print("  Reddit     : OK  official OAuth (free)")
    else:
        print("  Reddit     : -   optional; set REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET (free app)")

    ddgs_ok = (
        importlib.util.find_spec("ddgs") is not None
        or importlib.util.find_spec("duckduckgo_search") is not None
    )
    if ddgs_ok:
        print("  Web search : OK  duckduckgo (keyless)")
    else:
        print('  Web search : X   pip install -e ".[free]"  (or: pip install ddgs)')

    truly_free = bool(ready and r.tts_provider and r.youtube_free and ddgs_ok)
    print("=" * 48)
    if truly_free:
        print("  Ready for a truly-free ($0) run:  py main.py -> Free ($0)")
    else:
        print("  Not fully free yet - resolve the X lines above (docs/free_mode.md).")
    return 0


@_register("traces", "Recent run traces — timings, LLM cost, quality, hotspots (Pillar 1)")
def cmd_traces(args: argparse.Namespace) -> int:
    from core.run_ledger import render_traces

    print(render_traces(limit=args.limit or 10, channel_id=args.channel))
    return 0


@_register("dossier", "One run end-to-end: quality, cost, metrics, trace (--run-id required)")
def cmd_dossier(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("dossier requires --run-id (see 'ops traces' for recent ids)")
        return 1
    from core.run_ledger import render_dossier

    print(render_dossier(args.run_id))
    return 0


@_register("economics", "Per-video cost vs revenue -> contribution margin (Pillar 1)")
def cmd_economics(args: argparse.Namespace) -> int:
    from core.unit_economics import render as render_economics

    print(render_economics(args.channel, limit=args.limit or 25))
    return 0


@_register("grade", "Pre-publish report card for a run (--run-id required, Pillar 2)")
def cmd_grade(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("grade requires --run-id (see 'ops traces' for recent ids)")
        return 1
    from core.video_grade import grade_from_record, render_expert_panel, render_grade
    from storage.repositories.content_runs import get_content_run_repository

    record = get_content_run_repository().get(args.run_id)  # one fetch for grade + panel
    grade = grade_from_record(record)
    if grade is None:
        print(f"No persisted quality for run #{args.run_id} (pre-ledger run?)")
        return 1
    print(render_grade(grade))
    panel = render_expert_panel(
        record.script_preview, record.channel_id
    )  # EXPERT_PANEL_ENABLED-gated
    if panel:
        print()
        print(panel)
    return 0


@_register("calibration", "Pre-publish grade vs realized engaged-rate (Pillar 2)")
def cmd_calibration(args: argparse.Namespace) -> int:
    from core.grade_calibration import render as render_calibration

    print(render_calibration(args.channel))
    return 0


@_register("prompt-eval", "Golden-topic prompt evals: run (LLM cost) or compare last two")
def cmd_prompt_eval(args: argparse.Namespace) -> int:
    from core.prompt_evals import main as evals_main

    action = "compare" if getattr(args, "compare", False) else "run"
    extra = ["--channel", args.channel] if action == "run" else []
    return evals_main([action, *extra])


@_register("coach", "Daily creator coach — ranked ideas + why, post time, length, patterns")
def cmd_coach(args: argparse.Namespace) -> int:
    from core.creator_coach import build_coach, render_coach

    print(render_coach(build_coach(args.channel)))
    return 0


@_register("health", "Channel health — Green/Yellow/Red across engagement/cadence/cost (Pillar 5)")
def cmd_health(args: argparse.Namespace) -> int:
    from core.channel_health import build_health, render_health

    print(render_health(build_health(args.channel)))
    return 0


@_register("analyst", "Weekly analyst briefing — LLM over the pillars -> lever changes (Pillar 5)")
def cmd_analyst(args: argparse.Namespace) -> int:
    from core.analyst_agent import run_analyst

    print(run_analyst(args.channel))
    return 0


@_register("overnight", "Overnight operator — best-bet drafts + grade + vault dossiers (Pillar 5)")
def cmd_overnight(args: argparse.Namespace) -> int:
    from core.overnight import render_overnight, run_overnight

    result = run_overnight(args.channel, count=args.count or 3, file=getattr(args, "file", None))
    print(render_overnight(result))
    return 0


@_register("topic-db", "Topic Winners (clone these) + Graveyard (avoided flops)")
def cmd_topic_db(args: argparse.Namespace) -> int:
    from core.topic_db import display_graveyard, display_winners, graveyard, winners

    display_winners(winners(args.channel), print_fn=print)
    display_graveyard(graveyard(args.channel), print_fn=print)
    return 0


@_register("title-patterns", "Title patterns that engage (A/B variant loop leaderboard)")
def cmd_title_patterns(args: argparse.Namespace) -> int:
    from core.title_experiments import display_leaderboard

    display_leaderboard(args.channel, print_fn=print)
    return 0


@_register("retention", "Audience-retention curve + drop-off point (pacing intelligence)")
def cmd_retention(args: argparse.Namespace) -> int:
    from core.retention import display_retention

    display_retention(args.channel, print_fn=print)
    return 0


@_register(
    "intelligence-report",
    "Content Intelligence Report (signals + brief + competitors, no render)",
)
def cmd_intelligence_report(args: argparse.Namespace) -> int:
    topic = getattr(args, "topic", None) or ""
    if not topic:
        print("intelligence-report requires --topic")
        return 1
    extra = ["--topic", topic, "--channel", args.channel]
    if getattr(args, "no_brief", False):
        extra.append("--no-brief")
    return _run_module("core.intelligence_report", *extra)


@_register("competitor-sync", "Fetch recent videos from competitor channels")
def cmd_competitor_sync(args: argparse.Namespace) -> int:
    extra = ["--channel", args.channel]
    if getattr(args, "force", False):
        extra.append("--force")
    return _run_module("analytics.competitor_sync", *extra)


@_register("daily-sync", "Daily competitor + SEO refresh (run once per day)")
def cmd_daily_sync(args: argparse.Namespace) -> int:
    extra = ["--channel", args.channel]
    if getattr(args, "force", False):
        extra.append("--force")
    return _run_module("scripts.daily_sync", *extra)


@_register("worker", "Process one upload/render job (or use --loop N)")
def cmd_worker(args: argparse.Namespace) -> int:
    extra = []
    if args.loop and args.loop > 0:
        extra.extend(["--loop", str(args.loop)])
    return _run_module("jobs.worker", *extra)


@_register("test", "Run unit tests")
def cmd_test(_args: argparse.Namespace) -> int:
    return _run_module("unittest", "discover", "-s", "tests", "-v")


@_register("list-uploads", "Rendered MP4s not yet on YouTube")
def cmd_list_uploads(args: argparse.Namespace) -> int:
    extra = ["--channel", args.channel]
    if args.run_id:
        extra.extend(["--run-id", str(args.run_id)])
    if getattr(args, "queue_upload", False):
        extra.append("--queue")
    return _run_module("scripts.requeue_upload", *extra)


@_register("tapology-test", "Scrape Tapology fight card for a topic string")
def cmd_tapology_test(args: argparse.Namespace) -> int:
    topic = getattr(args, "topic", None) or "UFC 250 Topuria Gaethje"
    return _run_module("apis.tapology_api", topic)


@_register("requeue-upload", "Queue upload for a rendered run (--run-id required)")
def cmd_requeue_upload(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("requeue-upload requires --run-id (use list-uploads to see ids)")
        return 1
    return _run_module(
        "scripts.requeue_upload",
        "--channel",
        args.channel,
        "--run-id",
        str(args.run_id),
        "--queue",
    )


@_register("list", "List all operator commands")
def cmd_list(_args: argparse.Namespace) -> int:
    print("\nContent OS operator commands\n")
    for name, (help_text, _) in sorted(COMMANDS.items()):
        if name == "list":
            continue
        print(f"  {name:18} {help_text}")
    print("\nBatches:")
    print(
        "  all-setup          migrate-layout, init-db, migrate-schema, seed, validate, check-youtube"
    )
    print("  all-checks         validate + test")
    print("  all-analytics      seed, learn-schedule, weights, sync-metrics")
    print("  daily-sync         competitor-sync + seo-refresh (daily)")
    print(
        "  daily-brief        daily-sync + coach + health + reliability + status (morning one-shot)"
    )
    print("\nInteractive (not batched): py main.py")
    return 0


def _run_batch(names: list[str], args: argparse.Namespace) -> int:
    code = 0
    for name in names:
        if name not in COMMANDS or name in ("list",):
            print(f"Unknown batch step: {name}")
            return 1
        step_code = COMMANDS[name][1](args)
        if step_code != 0:
            print(f"Stopped: '{name}' exited with {step_code}")
            return step_code
    return code


@_register("all-setup", "First-time / fresh machine setup (non-interactive)")
def cmd_all_setup(args: argparse.Namespace) -> int:
    steps = [
        "migrate-layout",
        "init-db",
        "migrate-schema",
        "seed",
        "validate",
        "check-youtube",
    ]
    return _run_batch(steps, args)


@_register("all-checks", "Validate channels + unit tests")
def cmd_all_checks(args: argparse.Namespace) -> int:
    return _run_batch(["validate", "test"], args)


@_register("all-analytics", "Seed, schedules, weights, sync metrics")
def cmd_all_analytics(args: argparse.Namespace) -> int:
    return _run_batch(
        ["seed", "learn-schedule", "weights", "sync-metrics"],
        args,
    )


@_register("daily-brief", "Morning one-shot: fresh data, coach ideas, quota health, queue")
def cmd_daily_brief(args: argparse.Namespace) -> int:
    """The 'what should I do today' batch: refresh competitor/SEO data, then the
    coach's ranked ideas, channel health, the credit/quota dashboard, and the queue."""
    return _run_batch(["daily-sync", "coach", "health", "reliability", "status"], args)


@_register("batch-drafts", "N ideas -> N draft scripts, unattended (no render/publish)")
def cmd_batch_drafts(args: argparse.Namespace) -> int:
    """Headless volume-with-variation: best-bet topics (or py -m core.batch_generation
    with explicit topics/--file) -> scripts + quality checks in output/<ch>/drafts/."""
    return _run_module(
        "core.batch_generation", "--channel", args.channel, "--count", str(args.count)
    )


@_register("experiment", "Script-lever A/B report (start/stop: py -m core.experiments)")
def cmd_experiment(args: argparse.Namespace) -> int:
    from core.experiments import display_report

    display_report(args.channel)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Content OS operator commands (individual or batch)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  py -m scripts.ops all-setup --channel tapin\n"
        "  py -m scripts.ops validate\n"
        "  py -m scripts.ops list\n",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="list",
        choices=list(COMMANDS.keys()),
        help="Command to run (default: list)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Positional argument for some commands (e.g. ingest: a URL / PDF path / YouTube link)",
    )
    parser.add_argument("--source", default=None, help="ingest: URL / PDF path / YouTube link")
    parser.add_argument("--channel", default="tapin", help="Channel id (default: tapin)")
    parser.add_argument(
        "--domain", default="gaming", help="Domain for compute_weights (default: gaming)"
    )
    parser.add_argument("--init-db", action="store_true", help="Pass --init-db to seed")
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        help="Worker poll interval in seconds (jobs.worker only)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="How many drafts to generate (batch-drafts only)",
    )
    parser.add_argument(
        "--run-id",
        type=int,
        default=0,
        help="Content run id (list-uploads / requeue-upload / dossier)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Row limit (traces / economics; 0 = command default)",
    )
    parser.add_argument(
        "--topic",
        default="UFC 250 Topuria Gaethje",
        help="Topic for tapology-test or intelligence-report",
    )
    parser.add_argument(
        "--no-brief",
        action="store_true",
        help="Skip LLM brief in intelligence-report",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="prompt-eval: compare the two most recent eval runs instead of generating",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="overnight: file of topics (one per line) instead of best-bet",
    )
    args = parser.parse_args(argv)
    args.queue_upload = False
    args.queue_requeue = False
    args.queue_reset = False
    args.queue_schedule = False
    args.force = False

    _, fn = COMMANDS[args.command]
    return fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
