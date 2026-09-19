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
import json
import os
import subprocess
import sys
from collections.abc import Callable

CommandFn = Callable[[argparse.Namespace], int]


def _emit_text(title: str, text: str, args: argparse.Namespace) -> None:
    """Print ASCII; optionally dump a themed HTML snapshot (--html). Nested try."""
    try:
        from core.html_report import ascii_safe

        printable = ascii_safe(text)
    except Exception:
        printable = str(text).encode("ascii", "replace").decode("ascii")
    print(printable)
    if not getattr(args, "html", False):
        return
    try:
        from core.html_report import dump_pre

        path = dump_pre(title, text, channel_id=str(getattr(args, "channel", "") or ""))
        print(f"HTML: {path}")
    except Exception as exc:
        print(f"HTML dump skipped: {exc}")


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


@_register(
    "ingest-clips",
    "Copy capture clips into video/backgrounds (dry-run default; --apply remuxes)",
)
def cmd_ingest_clips(args: argparse.Namespace) -> int:
    from assets.clip_ingest import ingest_clips, render_ingest

    result = ingest_clips(
        apply=bool(getattr(args, "apply", False)),
        move=bool(getattr(args, "move", False)),
    )
    print(render_ingest(result))
    if any(row.status == "failed" for row in result.rows):
        return 1
    return 0


@_register(
    "gen-skills", "Regenerate skills/content-ops/SKILL.md from the ops registry (Agent Skills)"
)
def cmd_gen_skills(_args: argparse.Namespace) -> int:
    from core.ops_skills import write_skill

    path = write_skill()
    print(f"Wrote {path} ({len(COMMANDS)} commands)")
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


@_register(
    "channel-go-live",
    "Fail until OAuth + SEO + feeds + brand kit exist (MoneyWise / any channel)",
)
def cmd_channel_go_live(args: argparse.Namespace) -> int:
    from core.channel_go_live import inspect_channel, render_report

    report = inspect_channel(args.channel)
    print(render_report(report))
    return 0 if report.ok else 1


@_register(
    "competitor-health",
    "Flag dead/unverified competitor YouTube UC ids (RSS probe, no Data API)",
)
def cmd_competitor_health(args: argparse.Namespace) -> int:
    from analytics.youtube_rss import fetch_channel_uploads_rss
    from core.competitor_health import inspect_competitors, render_report

    report = inspect_competitors(
        args.channel,
        fetch=lambda cid: fetch_channel_uploads_rss(cid, max_results=4),
    )
    print(render_report(report))
    return 0 if report.ok else 1


@_register(
    "paid-signals",
    "Attribute tiktok_trends / youtube_competitors lift; recommend keep/disable (no catalog write)",
)
def cmd_paid_signals(args: argparse.Namespace) -> int:
    from core.paid_signal_attribution import report_from_traces

    print(report_from_traces(channel_id=args.channel, limit=args.limit or 50))
    return 0


@_register("incidents", "Rank recent signal/provider failures by count x recency")
def cmd_incidents(args: argparse.Namespace) -> int:
    from core.incident_ledger import gather_and_record, render

    incidents = gather_and_record(limit=args.limit or 40)
    print(render(incidents))
    return 0


@_register("postmortem", "Slowest phase, failed signals, ungrounded claims, cost (--run-id)")
def cmd_postmortem(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("postmortem requires --run-id")
        return 2
    from core.postmortem import as_markdown, from_store, render

    data = from_store(args.run_id)
    if getattr(args, "md", False):
        print(as_markdown(data))
    else:
        print(render(data))
    return 0


@_register("playbook-lint", "Warn when untagged strategy bullets can still feed facts")
def cmd_playbook_lint(args: argparse.Namespace) -> int:
    from core.obsidian_facts import lint_playbook, render_playbook_lint

    print(render_playbook_lint(lint_playbook(args.channel)))
    return 0


@_register("doctor", "One shot: free stack + feeds + oauth + quota + CUDA + RAM + secrets")
def cmd_doctor(args: argparse.Namespace) -> int:
    from core.ops_doctor import render

    _emit_text("ops doctor", render(channel_id=args.channel), args)
    return 0


@_register("secrets-doctor", "Keys present/missing/placeholder (never prints values)")
def cmd_secrets_doctor(args: argparse.Namespace) -> int:
    from core.secrets_doctor import render

    _emit_text("ops secrets-doctor", render(channel_id=args.channel), args)
    return 0


@_register("apify-trueup", "Compare synthetic Apify invoice vs $0.02/run model (no network)")
def cmd_apify_trueup(args: argparse.Namespace) -> int:
    from core.apify_trueup import DEFAULT_FIXTURE, parse_invoice, render, trueup

    path = args.file or str(DEFAULT_FIXTURE)
    print(render(trueup(parse_invoice(path))))
    return 0


@_register("tts-arms", "ElevenLabs vs Piper Bayesian report (no auto-switch)")
def cmd_tts_arms(args: argparse.Namespace) -> int:
    from core.tts_provider_report import render_report, report

    print(render_report(report(args.channel)))
    return 0


@_register("artifacts", "Cap output/ by GB (dry-run default; --apply deletes oldest)")
def cmd_artifacts(args: argparse.Namespace) -> int:
    from core.artifact_retention import run

    out = run(apply=bool(getattr(args, "apply", False)))
    print(out["text"])
    return 0


@_register(
    "artifact-retention",
    "Report old drafts, traces, and vault _runs clones (dry-run only; never deletes)",
)
def cmd_artifact_retention(args: argparse.Namespace) -> int:
    from core.artifact_retention import retention_report

    if getattr(args, "apply", False):
        print("NOTE: --apply ignored; artifact-retention is report-only.")
    print(retention_report())
    return 0


@_register(
    "policy-canary", "Hash YouTube inauthentic-content page (local fixture; no HTTP default)"
)
def cmd_policy_canary(args: argparse.Namespace) -> int:
    from core.policy_canary import inspect, render

    print(render(inspect(source_path=args.file, fetch=False)))
    return 0


@_register("moat-backup", "Plan pg_dump + vault + traces backup (secrets excluded; dry-run)")
def cmd_moat_backup(args: argparse.Namespace) -> int:
    from core.moat_backup import run

    print(run(dest=args.file, apply=bool(getattr(args, "apply", False)))["text"])
    return 0


@_register("ypp", "YPP / membership readiness: watch-hours proxy, disclosure, cadence")
def cmd_ypp(args: argparse.Namespace) -> int:
    from core.ypp_readiness import inspect_ypp, render_report

    print(render_report(inspect_ypp(args.channel)))
    return 0


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


@_register("backfill-cost", "Repair missing TTS cost on runs that rendered before the fix")
def cmd_backfill_cost(args: argparse.Namespace) -> int:
    extra = ["--channel", args.channel]
    if getattr(args, "dry_run", False):
        extra.append("--dry-run")
    if getattr(args, "force", False):
        extra.append("--force")
    return _run_module("analytics.backfill_cost", *extra)


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


@_register("vault-decay", "List vault notes whose expires date is in the past")
def cmd_vault_decay(args: argparse.Namespace) -> int:
    from core.fact_expiry import expired_notes

    notes = expired_notes(getattr(args, "channel", None))
    if not notes:
        print("Vault decay: no expired notes on disk.")
        return 0
    print(f"Vault decay: {len(notes)} expired note(s) still on disk (already dropped from prompts)")
    for note in notes:
        print(f"  {note.get('path')} expired {note.get('expires')} ({note.get('days_past')}d past)")
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
    from config.channels import resolve_channel_id
    from core.status import build_status_lines

    channel_id = resolve_channel_id(args.channel)
    lines = [f"Status - {channel_id}", ""] + [
        f"  {line}" for line in build_status_lines(channel_id)
    ]
    _emit_text("Status", "\n".join(lines) + "\n", args)
    return 0


@_register("caption-anchor", "Measure whether a frame's bottom band carries an overlay (#717)")
def cmd_caption_anchor(args: argparse.Namespace) -> int:
    """Lets the operator decide CAPTION_AUTO_PLACE from their OWN footage rather
    than from the synthetic fixtures the thresholds were set on."""
    from video.caption_place import overlay_reading

    path = (getattr(args, "path", None) or "").strip()
    if not path:
        print("caption-anchor requires --path VIDEO.mp4 or IMAGE.png")
        return 2
    # The "needs" figures are read from the detector, not typed: after #727 moved the
    # excess threshold to 0.18 this still printed 0.25.
    from video import caption_place as cp

    reading = overlay_reading(path, always_motion=True)
    if reading["spatial"] == "no_frame":
        print(f"{path}: no frame could be read (missing file, or not a video/image)")
        return 2
    print(f"{path}")
    if reading["spatial"] == "no_contrast" or reading["metrics"] is None:
        # A measured answer, not a failure: nothing to avoid, so nothing moves.
        print("  band has no measurable contrast (flat or black)")
    else:
        spread, step = reading["metrics"]
        print(f"  spread/median : {spread:.2f}  (needs >= {cp._MIN_SPREAD:.2f})")
        print(f"  step share    : {step:.2f}  (needs >= {cp._MIN_STEP_SHARE:.2f})")
    print(f"  spatial gate  : {'pass' if reading['step'] else 'fail'}")
    if reading["motion"] == "no_motion":
        print("  motion        : none measurable (still image, locked-off shot or clip under 1s)")
    else:
        print(f"  static excess : {reading['excess']:.2f}  (needs >= {cp._MIN_STATIC_EXCESS:.2f})")
    verdict = (
        "OVERLAY -> captions move to the top"
        if reading["overlay"]
        else "clear -> captions stay at the bottom"
    )
    print(f"  verdict       : {verdict}")
    print(
        "  CAPTION_AUTO_PLACE is off by default (#727); set it to true to let this move captions."
    )
    return 0


@_register("free-tiers", "When each provider's free window resets or ends (#378)")
def cmd_free_tiers(_args: argparse.Namespace) -> int:
    from core.free_tier_calendar import expiring_windows, render_calendar

    rows = expiring_windows()
    print(render_calendar(rows))
    # Non-zero when something has already lapsed: a closed window means the next
    # "$0" run is not $0 any more.
    return 1 if any(r.get("closed") for r in rows) else 0


@_register("cost-tower", "Every cost lane in one view: TTS, Apify, YouTube, LLM, free tiers (#158)")
def cmd_cost_tower(_args: argparse.Namespace) -> int:
    from core.cost_tower import gather_tower, render_tower

    rows = gather_tower()
    print(render_tower(rows))
    return 1 if any(row.state == "over" for row in rows) else 0


@_register(
    "cost-panel",
    'Cost Control Tower panel (#158; requires pip install -e ".[app]")',
)
def cmd_cost_panel(_args: argparse.Namespace) -> int:
    from desktop.launch import launch

    return launch(cost=True)


@_register(
    "clock-ahead", "Run the suite with the clock shifted; list tests whose result changes (#725)"
)
def cmd_clock_ahead(args: argparse.Namespace) -> int:
    from core.clock_ahead import compare

    days = int(getattr(args, "days", 0) or 365)
    print(f"Running the suite at +0 and +{days} days (two full runs)...")
    changed = compare(days)
    if not changed:
        print(f"  no test changes result {days} days ahead")
        return 0
    print(f"  {len(changed)} test(s) change result {days} days ahead:")
    for test_id in changed:
        print(f"    {test_id}")
    return 1


@_register("trace-secrets-scan", "Scan data/traces for env secrets or secret URL params (#636)")
def cmd_trace_secrets_scan(_args: argparse.Namespace) -> int:
    from core.trace_secrets import render_scan, scan_traces

    checked, hits = scan_traces()
    print(render_scan(checked, hits))
    return 1 if hits else 0


@_register("env-lint", "Env keys read in code vs documented in .env.example (#639)")
def cmd_env_lint(_args: argparse.Namespace) -> int:
    from core import env_lint

    report = env_lint.lint()
    print(env_lint.render_lint(report))
    return 1 if report.new_undocumented else 0


@_register("selftest", "Run every safety gate against fixtures; show which are armed here (#630)")
def cmd_selftest(_args: argparse.Namespace) -> int:
    from core.selftest import render_selftest, run_selftest

    results = run_selftest()
    print(render_selftest(results))
    return 0 if all(result.works for result in results) else 1


@_register(
    "package-audit", "Build the wheel and sdist; flag secrets, tokens or operator paths (#640)"
)
def cmd_package_audit(_args: argparse.Namespace) -> int:
    from core import package_audit

    try:
        reports = package_audit.audit()
    except RuntimeError as exc:
        print(f"package-audit could not build: {exc}")
        return 2
    print(package_audit.render_audit(reports))
    return 1 if any(report.hits for report in reports) else 0


@_register("reliability", "Credit/quota dashboard (Apify + LLM budgets, breakers, cache hit-rate)")
def cmd_reliability(args: argparse.Namespace) -> int:
    from core.reliability import gather, render

    if getattr(args, "vacuum", False):
        from config.paths import DATA_DIR
        from core.sqlite_vacuum import vacuum_sqlite

        path = (getattr(args, "path", None) or "").strip() or os.path.join(
            DATA_DIR, "content_os.db"
        )
        try:
            result = vacuum_sqlite(path)
        except FileNotFoundError:
            print(f"VACUUM skipped: {path} not found")
            return 1
        print(f"VACUUM {result['path']}: {result['before']} -> {result['after']} bytes")
    data = gather()
    chunks = [render(data)]
    # Recording on view means the trend builds itself — no separate job to forget.
    try:
        from core.reliability_history import record
        from core.reliability_history import render as render_trend

        record(data)
        chunks.append(render_trend())
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("Reliability trend not recorded: %s", exc)
    try:
        from core.incident_ledger import gather_and_record
        from core.incident_ledger import render as render_incidents

        incidents = gather_and_record()
        blob = render_incidents(incidents)
        if blob:
            chunks.append(blob)
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("Incident ledger skipped: %s", exc)
    _emit_text("Reliability", "\n".join(chunks), args)
    return 0


@_register(
    "signal-canary",
    "Probe every signal at $0 — a dead source found before a real run needs it",
)
def cmd_signal_canary(_args: argparse.Namespace) -> int:
    from core.signal_canary import check_signals, render, save_results, warnings

    results = check_signals()
    save_results(results)
    print(render(results))
    # Non-zero on a dead signal so a scheduled overnight / a manual probe fails
    # loudly rather than quietly. Not part of `all-checks` (CI has no network).
    return 1 if warnings(results) else 0


@_register("feeds", "Check every configured RSS feed — dead/stale sources starve grounding")
def cmd_feeds(_args: argparse.Namespace) -> int:
    from core.feed_health import check_feeds, render, save_results, summarize

    results = check_feeds()
    save_results(results)
    print(render(results))
    # Non-zero on a dead feed so `all-checks` fails loudly instead of printing quietly.
    return 1 if summarize(results).get("dead") else 0


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

    Single HTTP helper: delegates to ``llm_router.ollama_probe`` so we cannot drift
    into a second, weaker ``/api/tags`` client. ``timeout`` is accepted for call-site
    compatibility; the router probe uses its own 3s bound.
    """
    del timeout  # router probe owns the timeout; kept so existing callers stay valid.
    try:
        from core.llm_router import ollama_probe

        up, tags = ollama_probe(refresh=True)
        return up, len(tags)
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
    configured = os.getenv("OLLAMA_MODEL", "").strip()
    if ready:
        print(f"  LLM        : OK  ollama (local, unlimited) - model {model}")
    elif configured:
        # Reachable is not usable (run 70): distinguish down vs empty vs wrong model.
        up, n_models = _ollama_server_probe()
        if not up:
            print(f"  LLM        : X   OLLAMA_MODEL={configured} set, server unreachable")
            print("                   start it: `ollama serve` (+ `ollama pull <model>`)")
        elif n_models == 0:
            print(f"  LLM        : X   OLLAMA_MODEL={configured} set, nothing pulled")
            print(f"                   pull it: `ollama pull {configured}`")
        else:
            print(f"  LLM        : X   OLLAMA_MODEL={configured} is not among the pulled models")
            print(f"                   pull it: `ollama pull {configured}`")
        if os.getenv("OPENROUTER_API_KEY", "").strip():
            print(
                "  LLM        : ~   openrouter :free available as throttled fallback (not truly free)"
            )
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
    from core.unit_economics import channel_economics, to_csv
    from core.unit_economics import render as render_economics

    limit = args.limit or 25
    _emit_text("Unit economics", render_economics(args.channel, limit=limit), args)
    try:
        from core.operator_minutes import trend_line

        print(trend_line(args.channel))
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("minutes trend skipped: %s", exc)
    if getattr(args, "csv", False):
        try:
            from core.html_report import html_dir

            econ = channel_economics(args.channel, limit=limit)
            dest = os.path.join(html_dir(), "economics.csv")
            with open(dest, "w", encoding="utf-8", newline="") as fh:
                fh.write(to_csv(econ))
            print(f"CSV: {dest}")
        except Exception as exc:
            print(f"CSV skipped: {exc}")
    return 0


@_register("grade", "Pre-publish report card for a run (--run-id required, Pillar 2)")
def cmd_grade(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("grade requires --run-id (see 'ops traces' for recent ids)")
        return 1
    from core.video_grade import grade_from_record, render_grade
    from storage.repositories.content_runs import get_content_run_repository

    record = get_content_run_repository().get(args.run_id)  # one fetch for grade + panel
    grade = grade_from_record(record)
    if grade is None:
        print(f"No persisted quality for run #{args.run_id} (pre-ledger run?)")
        return 1
    print(render_grade(grade))
    if getattr(args, "md", False):
        from core.video_grade import grade_as_markdown

        print()
        print(grade_as_markdown(grade))
    from core.video_grade import expert_panel_for_run

    panel = expert_panel_for_run(args.run_id)  # EXPERT_PANEL_ENABLED-gated; prefers persisted
    if panel:
        print()
        print(panel)
    text = render_grade(grade)
    if panel:
        text = f"{text}\n\n{panel}"
    if getattr(args, "html", False):
        try:
            from core.html_report import dump_pre

            path = dump_pre(
                "Report card",
                text,
                channel_id=str(getattr(args, "channel", "") or ""),
            )
            print(f"HTML: {path}")
        except Exception as exc:
            print(f"HTML dump skipped: {exc}")
    return 0


@_register("calibration", "Pre-publish grade vs realized engaged-rate (Pillar 2)")
def cmd_calibration(args: argparse.Namespace) -> int:
    from core.grade_calibration import render as render_calibration

    print(render_calibration(args.channel))
    return 0


@_register("vault-eval", "Vault subject-relevance evals: precision/recall, or compare last two")
def cmd_vault_eval(args: argparse.Namespace) -> int:
    """Frozen labelled cases (329 P1). No LLM cost - deterministic, safe to re-run."""
    from core.vault_evals import main as vault_main

    forwarded: list[str] = []
    if getattr(args, "compare", False):
        forwarded.append("--compare")
    if getattr(args, "vault_eval_mode", ""):
        forwarded.extend(["--mode", args.vault_eval_mode])
    if getattr(args, "tune", False):
        forwarded.append("--tune")
    if getattr(args, "no_save", False):
        forwarded.append("--no-save")
    if getattr(args, "output_dir", ""):
        forwarded.extend(["--output-dir", args.output_dir])
    return vault_main(forwarded)


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

    result = run_overnight(
        args.channel,
        count=args.count or 3,
        file=getattr(args, "file", None),
        facts_file=getattr(args, "facts_file", None),
    )
    print(render_overnight(result))
    return 0


@_register(
    "skillopt", "SkillOpt-Sleep — gated skill-directive optimizer (frozen prompt-evals gate)"
)
def cmd_skillopt(args: argparse.Namespace) -> int:
    from core.skillopt import render_skillopt, run_skillopt

    print(render_skillopt(run_skillopt(args.channel)))
    return 0


@_register("topic-clone", "Seed a new draft from a winner run (--run-id; angles/facts refresh)")
def cmd_topic_clone(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("topic-clone requires --run-id")
        return 1
    from core.topic_clone import clone_from_run

    result = clone_from_run(args.run_id, channel_id=args.channel)
    if not result.ok:
        print(result.error or "clone failed")
        return 1
    print(f"Cloned run #{args.run_id} -> draft run #{result.run_id} ({result.topic})")
    return 0


@_register("studio-deleted", "Cancel publish_log rows whose YouTube videos were Studio-deleted")
def cmd_studio_deleted(args: argparse.Namespace) -> int:
    from youtube.studio_deleted import detect_studio_deleted

    report: dict = {}
    cancelled = detect_studio_deleted(args.channel, report=report)
    if report.get("error"):
        print(f"Studio-deleted: could not check {args.channel} - {report['error']}")
        return 1
    if not cancelled:
        print(
            f"Studio-deleted: none for {args.channel} - {report.get('checked', 0)} uploaded "
            "video(s) checked, all still on YouTube"
        )
        for vid in report.get("still_live") or []:
            print(f"  live: https://youtu.be/{vid}")
        return 0
    print(f"Studio-deleted: cancelled {len(cancelled)} publish_log row(s)")
    for row in cancelled:
        print(f"  #{row.id} {row.youtube_video_id}")
    return 0


@_register("batch-review", "Review waiting drafts in one pass; render the yeses; space them (#760)")
def cmd_batch_review(args: argparse.Namespace) -> int:
    from core.batch_review import review_drafts

    summary = review_drafts(args.channel)
    print(
        f"\nReview: {len(summary.accepted)} accepted, {len(summary.rejected)} rejected, "
        f"{len(summary.later)} later; {len(summary.rendered)} rendered, "
        f"{len(summary.queued)} queued"
    )
    return 0


@_register("retire-renders", "Stop counting unuploaded renders past their news date (--apply)")
def cmd_retire_renders(args: argparse.Namespace) -> int:
    from core.stale_renders import find_stale_renders, render_age_days, retire_renders

    run_id = int(getattr(args, "run_id", 0) or 0)
    if run_id:
        # By id, age does not apply: a test render is retired the day it is made.
        from scripts.requeue_upload import list_recyclable

        stale = [run for run in list_recyclable(args.channel) if int(run.id) == run_id]
        if not stale:
            print(f"Retire renders: run {run_id} is not an unuploaded render on {args.channel}")
            return 1
        marked = retire_renders(stale) if getattr(args, "apply", False) else []
        if marked:
            print(f"Retired run {run_id}. The file stays on disk.")
        else:
            print(f"Would retire run {run_id}. Add --apply.")
        return 0

    days = int(getattr(args, "days", 0) or 30)
    stale = find_stale_renders(args.channel, days=days)
    if not stale:
        print(f"Retire renders: nothing unuploaded older than {days} days on {args.channel}")
        return 0
    print(f"Unuploaded renders older than {days} days ({args.channel}):")
    for run in stale:
        age = render_age_days(run) or 0.0
        print(f"  [{run.id}] {age:.0f}d  {getattr(run, 'title', '')}")
    if not getattr(args, "apply", False):
        print("Dry run. Add --apply to retire them (files stay on disk).")
        return 0
    marked = retire_renders(stale)
    print(f"Retired {len(marked)}. Still queueable by id: py -m scripts.requeue_upload --run-id N")
    return 0


@_register("chapters", "All-angles chapter report: placement path, length, Shorts cap (#755)")
def cmd_chapters(args: argparse.Namespace) -> int:
    from core.chapter_shorts import chapter_report

    run_id = int(getattr(args, "run_id", 0) or 0)
    if not run_id:
        print("chapters needs --run-id N")
        return 2
    lines = chapter_report(run_id)
    if not lines:
        print(f"Run {run_id} has no angle chapters (not an all-angles render).")
        return 1
    print(f"Chapters for run {run_id}:")
    for line in lines:
        print(f"  {line}")
    return 0


@_register("schedule-drafts", "Nightly overnight drafts via Task Scheduler (--install / --remove)")
def cmd_schedule_drafts(args: argparse.Namespace) -> int:
    from core import nightly_task

    channel = str(getattr(args, "channel", "") or "tapin")
    if getattr(args, "install", False):
        code, out = nightly_task.run_schtasks(nightly_task.install_argv(channel))
        print(out or f"schtasks exit {code}")
        if code == 0:
            print(
                f"Installed: `ops overnight --channel {channel}` daily at "
                f"{nightly_task.DEFAULT_TIME}. Review in the morning: "
                f"py -m scripts.ops batch-review --channel {channel}"
            )
        return 0 if code == 0 else 1
    if getattr(args, "remove", False):
        code, out = nightly_task.run_schtasks(nightly_task.remove_argv())
        print(out or f"schtasks exit {code}")
        return 0 if code == 0 else 1
    code, out = nightly_task.run_schtasks(nightly_task.query_argv())
    if code == 0:
        print(out)
    else:
        print(f"Nightly drafts: not installed ({nightly_task.TASK_NAME}).")
        print(f"Install: py -m scripts.ops schedule-drafts --install --channel {channel}")
        print(f"It would run: {nightly_task.task_command(channel)}")
    return 0


@_register(
    "mutate-gates", "Mutation-test the publish/grounding gates; list untested mutants (#627)"
)
def cmd_mutate_gates(args: argparse.Namespace) -> int:
    from scripts.mutate_gates import main as mutate_main

    extra = ["--target", args.target] if getattr(args, "target", "") else []
    return mutate_main(extra)


@_register("playlists", "Franchise playlists: show the map; --apply creates missing (#601)")
def cmd_playlists(args: argparse.Namespace) -> int:
    from core.playlists import (
        SCOPE_YOUTUBE_MANAGE,
        playlist_map,
        store_path_for,
        sync_playlists,
    )

    channel = args.channel
    try:
        with open(store_path_for(channel), encoding="utf-8") as f:
            ids = json.load(f).get("ids") or {}
    except (OSError, ValueError):
        ids = {}
    print(f"Franchise playlists ({channel}), most specific first:")
    for row in playlist_map(channel):
        name = row["name"]
        parent = f" (+ {row['parent']})" if row.get("parent") else ""
        print(f"  {name}{parent}: {ids.get(name) or 'not created'}")
    if not getattr(args, "apply", False):
        print("Add --apply to create the missing ones (50 quota units each).")
        return 0
    from youtube.oauth import get_youtube_service, token_has_scope

    if not token_has_scope(channel, SCOPE_YOUTUBE_MANAGE):
        print(
            "Needs the YouTube manage permission first: "
            f"py -m youtube.oauth_setup --channel {channel}"
        )
        return 1
    created = sync_playlists(get_youtube_service(channel), channel)
    print(f"Created {len(created)}: {', '.join(created) or 'none'}")
    return 0


@_register(
    "preview-render", "Re-render a voiced Short with today's background, $0 (--path mp3 --topic)"
)
def cmd_preview_render(args: argparse.Namespace) -> int:
    from assets.fast_cut import render_preview

    audio = str(getattr(args, "path", "") or "")
    if not audio or not os.path.isfile(audio):
        print("preview-render needs --path <an existing voiced mp3>")
        return 2
    topic = str(getattr(args, "topic", "") or "") or os.path.basename(audio)
    path = render_preview(audio, topic, args.channel)
    print(f"Preview (never queued): {path}")
    return 0


@_register("publish-ics", "Write an .ics of scheduled publishes beside HTML dumps")
def cmd_publish_ics(args: argparse.Namespace) -> int:
    from core.publish_ics import write_scheduled_ics

    path = write_scheduled_ics(args.channel)
    print(path)
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
    if getattr(args, "sku", False):
        extra.append("--sku")
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
    return _run_module("unittest", "discover", "-s", "tests", "-t", ".", "-v")


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


@_register("pick-thumbnail", "Pick text_on or face_forward for a dual-thumbnail run")
def cmd_pick_thumbnail(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("pick-thumbnail requires --run-id")
        return 2
    if not getattr(args, "arm", "") and not getattr(args, "path", ""):
        print("pick-thumbnail requires --arm text_on|face_forward or --path")
        return 2
    from core.thumbnail_pick import pick_thumbnail
    from storage.repositories.content_runs import get_content_run_repository

    record = get_content_run_repository().get(args.run_id)
    if record is None:
        print(f"No content run #{args.run_id}")
        return 1
    try:
        selected = pick_thumbnail(
            args.run_id,
            getattr(args, "path", "") or None,
            arm=getattr(args, "arm", "") or None,
            channel_id=record.channel_id,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc))
        return 1
    print(
        f"Picked {selected['arm']} ({selected['provider']}) for run "
        f"#{args.run_id}: {selected['path']}"
    )
    return 0


@_register(
    "tray",
    "System-tray / quota chip (uploads-left + TTS chars + Apify breaker)",
)
def cmd_tray(args: argparse.Namespace) -> int:
    from core.win_notify import run_tray

    pause_overnight = bool(getattr(args, "pause_overnight", False))
    resume_overnight = bool(getattr(args, "resume_overnight", False))
    if pause_overnight and resume_overnight:
        print("Choose only one of --pause-overnight or --resume-overnight.")
        return 1
    return run_tray(
        stay=bool(getattr(args, "stay", False)),
        open_output=bool(getattr(args, "open_output", False)),
        doctor_html=bool(getattr(args, "doctor_html", False)),
        pause_overnight=pause_overnight,
        resume_overnight=resume_overnight,
        channel_id=getattr(args, "channel", None) or "tapin",
    )


@_register("booth", "Last-run review booth (play + grade + authenticity + cost)")
def cmd_booth(args: argparse.Namespace) -> int:
    from core.review_booth import serve_booth, write_booth

    if getattr(args, "serve", False):
        url = serve_booth(args.channel)
        print(url)
        print("Serving review booth. Ctrl+C to stop.")
        try:
            import time

            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("Stopped.")
        return 0
    path = write_booth(args.channel)
    print(path)
    return 0


@_register(
    "review-room",
    'Stage 3 Qt review room (J/K/L + Approve; requires pip install -e ".[app]")',
)
def cmd_review_room(_args: argparse.Namespace) -> int:
    from desktop.launch import launch

    return launch(review=True)


@_register(
    "studio",
    'Stage 4 Qt thumbnail canvas (last thumb + overlay; requires pip install -e ".[app]")',
)
def cmd_studio(_args: argparse.Namespace) -> int:
    from desktop.launch import launch

    return launch(studio=True)


@_register(
    "queue-panel",
    'Stage 3 job queue (drag-reorder; requires pip install -e ".[app]")',
)
def cmd_queue_panel(_args: argparse.Namespace) -> int:
    from desktop.launch import launch

    return launch(queue=True)


@_register(
    "brand-panel",
    'Compiled brand kit per channel (requires pip install -e ".[app]")',
)
def cmd_brand_panel(args: argparse.Namespace) -> int:
    from desktop.launch import launch

    return launch(brand=True, channel_id=getattr(args, "channel", None) or "tapin")


@_register("brand-kit", "Print the compiled brand kit and what is missing")
def cmd_brand_kit(args: argparse.Namespace) -> int:
    from core.brand_kit import compile_kit

    kit = compile_kit(getattr(args, "channel", None) or "tapin")
    print(kit.render())
    return 0 if kit.complete else 1


@_register("why-slow", "Rank last-run phase timings (slowest first)")
def cmd_why_slow(args: argparse.Namespace) -> int:
    from core.review_booth import last_trace
    from core.why_slow import why_slow_lines

    trace = last_trace(getattr(args, "channel", None)) or {}
    print("\n".join(why_slow_lines(trace.get("timings"))))
    return 0


@_register("config-diff", "channels.json sha256 vs last-run fingerprint")
def cmd_config_diff(args: argparse.Namespace) -> int:
    from core.config_diff import diff_against
    from core.review_booth import last_trace

    print("\n".join(diff_against(last_trace(getattr(args, "channel", None)) or {})))
    return 0


@_register("retraction-watch", "Re-fetch last-run source URLs for a retraction")
def cmd_retraction_watch(args: argparse.Namespace) -> int:
    from core.retraction_watch import pairs_from_trace, watch_urls
    from core.review_booth import last_trace

    pairs = pairs_from_trace(last_trace(getattr(args, "channel", None)) or {})
    if not pairs:
        print("no source URLs on the last trace")
        return 0
    hits = watch_urls(pairs)
    if not hits:
        print(f"checked {len(pairs)} URL(s); no retraction hits")
        return 0
    print("\n".join(hits))
    return 0


@_register("corrections", "Re-check published videos' sources and file a correction dossier")
def cmd_corrections(args: argparse.Namespace) -> int:
    """#112. Post-publish, unlike `retraction-watch`, which only reads the last
    draft's trace. Writes a vault dossier and records a negative fact; it never
    touches the published video."""
    from core.correction_dossier import scan_published_for_corrections

    channel = getattr(args, "channel", None) or "tapin"
    found = scan_published_for_corrections(
        channel,
        window_days=int(getattr(args, "days", 30) or 30),
        force=True,
    )
    if not found:
        print(f"{channel}: no reversed claims on published videos in the window")
        return 0
    for dossier in found:
        print(f"[{dossier.severity}] {dossier.video_id}: {dossier.claim}")
        print(f"    source  : {dossier.source_url}")
        print(f"    evidence: {dossier.changed_evidence[:160]}")
    print(f"{len(found)} dossier(s) written to the vault. Nothing was changed on YouTube.")
    return 0


@_register("grain-grade", "Encode a flat frame with the channel look and print stddev")
def cmd_grain_grade(args: argparse.Namespace) -> int:
    import tempfile

    from video.grain_grade import measure_look_noise

    with tempfile.TemporaryDirectory() as tmp:
        result = measure_look_noise(tmp, channel_id=getattr(args, "channel", None) or "tapin")
    if result is None:
        print("grain-grade n/a (no noise look or ffmpeg failed)")
        return 1
    print(f"plain {result['plain']:.3f}  with_look {result['with_look']:.3f}")
    return 0


@_register("technical-qc", "Inspect a finished video for stream, frame and loudness defects")
def cmd_technical_qc(args: argparse.Namespace) -> int:
    from core.technical_qc import inspect_technical_qc, render_technical_qc

    path = str(getattr(args, "path", "") or "")
    if not path:
        print("technical-qc requires --path VIDEO.mp4")
        return 2
    result = inspect_technical_qc(path)
    print(render_technical_qc(result))
    return 0 if result.passed else 2 if result.status == "unavailable" else 1


@_register("shell", "Localhost FastAPI operator shell (GET only; no TTS/Apify/publish)")
def cmd_shell(args: argparse.Namespace) -> int:
    from core.operator_shell import DEFAULT_PORT, serve

    port = int(getattr(args, "port", 0) or DEFAULT_PORT)
    return serve(port=port, channel_id=getattr(args, "channel", None) or "tapin")


@_register(
    "render-preview",
    "Render a 480p ultrafast review copy without changing publish media (--run-id)",
)
def cmd_render_preview(args: argparse.Namespace) -> int:
    if not args.run_id:
        print("render-preview requires --run-id")
        return 2
    from core.pipeline import run_media_only
    from storage.repositories.content_runs import get_content_run_repository

    record = get_content_run_repository().get(args.run_id)
    if record is None:
        print(f"No content run #{args.run_id}")
        return 1
    script = str(record.script_preview or "")
    source_file = getattr(args, "file", None)
    if source_file:
        with open(source_file, encoding="utf-8") as handle:
            script = handle.read().strip()
    elif len(script) >= 2000:
        print(
            "Stored script is truncated at 2,000 characters; pass --file with the full "
            "script so the preview cannot silently omit the ending."
        )
        return 2
    if not script:
        print(f"Run #{args.run_id} has no stored script")
        return 1
    _mp3, mp4, _thumb = run_media_only(
        record.selected_topic or record.input_topic,
        script,
        channel_id=record.channel_id,
        content_run_id=record.id,
        title=record.title,
        render_preset="draft",
    )
    print(f"Draft preview: {mp4}")
    print("Publish media unchanged; previews are never queued or uploaded.")
    return 0


@_register(
    "caption-still",
    "Overlay captions on a still so names can be proofread before burn (--path image, --file script)",
)
def cmd_caption_still(args: argparse.Namespace) -> int:
    frame = (getattr(args, "path", None) or "").strip()
    script_file = (getattr(args, "file", None) or "").strip()
    if not frame or not script_file:
        print("caption-still requires --path <image> and --file <script.txt>")
        return 2
    from pathlib import Path

    script = Path(script_file).read_text(encoding="utf-8")
    dest = str(Path(frame).with_name(Path(frame).stem + "_captions.png"))
    from video.caption_overlay import overlay_captions_on_still

    result = overlay_captions_on_still(
        frame, script, dest, channel_id=getattr(args, "channel", None) or "tapin"
    )
    print(result.path)
    for line in result.lines[:8]:
        print(f"  {line}")
    return 0


@_register(
    "end-card-preview",
    "Render the channel end card as a PNG still before a full encode (--path dest.png)",
)
def cmd_end_card_preview(args: argparse.Namespace) -> int:
    dest = (getattr(args, "path", None) or "").strip()
    if not dest:
        print("end-card-preview requires --path <dest.png>")
        return 2
    from video.end_card_preview import render_end_card_preview

    try:
        result = render_end_card_preview(dest, channel_id=getattr(args, "channel", None) or "tapin")
    except ValueError as exc:
        print(str(exc))
        return 1
    print(result.path)
    print(f"  {result.text}")
    return 0


@_register("run-window", 'Stage 2 Qt run window (requires pip install -e ".[app]")')
def cmd_run_window(_args: argparse.Namespace) -> int:
    from desktop.launch import launch

    return launch()


@_register(
    "contact-sheet",
    "2x2 PNG collage of the last thumbnails (--path dest.png)",
)
def cmd_contact_sheet(args: argparse.Namespace) -> int:
    dest = (getattr(args, "path", None) or "").strip()
    if not dest:
        print("contact-sheet requires --path <dest.png>")
        return 2
    from core.contact_sheet import render_contact_sheet
    from core.output_paths import ensure_channel_output_dirs

    cid = getattr(args, "channel", None) or "tapin"
    thumbs = ensure_channel_output_dirs(cid)["thumbnails"]
    result = render_contact_sheet(dest, thumbs_dir=thumbs, channel_id=cid)
    if not result.ok:
        print(result.detail)
        return 1
    print(result.path)
    print(f"  {len(result.paths)} thumbs")
    if result.html_path:
        print(result.html_path)
    return 0


@_register(
    "negative-fact",
    "Record a walked-back claim so a later run cannot re-assert it (--topic franchise)",
)
def cmd_negative_fact(args: argparse.Namespace) -> int:
    claim = (getattr(args, "source", None) or getattr(args, "target", None) or "").strip()
    if not claim:
        print("negative-fact requires a claim (positional or --source)")
        return 2
    from core.negative_facts import franchise_for, record_negative

    topic = (getattr(args, "topic", None) or "").strip()
    cid = getattr(args, "channel", None) or "tapin"
    key = franchise_for(topic or cid, cid)
    record_negative(key, claim, reason="ops negative-fact")
    print(f"recorded negative fact for {key}")
    return 0


@_register(
    "intro-waveform",
    "Draw a waveform of the intro sting and print duration vs the 2.15s offset (--path audio)",
)
def cmd_intro_waveform(args: argparse.Namespace) -> int:
    audio = (getattr(args, "path", None) or "").strip()
    if not audio:
        print("intro-waveform requires --path <audio.wav|mp3>")
        return 2
    from video.intro_waveform import describe_intro_waveform

    result = describe_intro_waveform(audio, channel_id=getattr(args, "channel", None) or "tapin")
    print(result.line)
    return 0 if result.ok else 1


@_register("lightbox", "Thumbnail lightbox for the last Pillow thumb")
def cmd_lightbox(args: argparse.Namespace) -> int:
    from core.review_booth import write_lightbox
    from core.win_shell import last_media_file

    path = write_lightbox(last_media_file("thumb", channel_id=args.channel))
    print(path)
    return 0


@_register("reveal", "Reveal last mp4 (or --kind thumb|trace) in Explorer")
def cmd_reveal(args: argparse.Namespace) -> int:
    from core.win_shell import reveal_last

    path = reveal_last(kind=getattr(args, "kind", None) or "mp4", channel_id=args.channel)
    if not path:
        print("Nothing on disk to reveal.")
        return 1
    print(path)
    return 0


@_register("shortcut", "Install Start Menu shortcut via pythonw / content_os.pyw")
def cmd_shortcut(_args: argparse.Namespace) -> int:
    from core.win_shell import install_start_menu_shortcut

    path = install_start_menu_shortcut()
    print(path)
    return 0


@_register("booth-shortcut", "Install Desktop shortcut for the persistent review booth")
def cmd_booth_shortcut(_args: argparse.Namespace) -> int:
    from core.win_shell import install_booth_desktop_shortcut

    path = install_booth_desktop_shortcut()
    print(path)
    return 0


@_register("policy-runbook", "Print the strike / Content ID / appeal runbook path")
def cmd_policy_runbook(args: argparse.Namespace) -> int:
    from core.policy_runbook import runbook_path, runbook_text

    path = runbook_path()
    print(path)
    if getattr(args, "html", False):
        try:
            from core.html_report import dump_pre

            dump_pre("Policy runbook", runbook_text(), filename="policy_runbook.html")
        except Exception as exc:
            print(f"HTML dump skipped: {exc}")
    return 0


@_register("demonetization", "estimatedRevenue cliff vs channel baseline (missing is unmeasured)")
def cmd_demonetization(args: argparse.Namespace) -> int:
    from core.demonetization import detect_revenue_cliff

    result = detect_revenue_cliff(args.channel)
    if result:
        print(result)
    else:
        print("Revenue unmeasured — not treated as zero.")
    return 0


@_register("sendto-facts", "Install Explorer Send-to shortcut targeting facts.txt")
def cmd_sendto_facts(args: argparse.Namespace) -> int:
    from core.win_shell import install_sendto_facts_shortcut

    dest = install_sendto_facts_shortcut(
        sendto_dir=getattr(args, "sendto_dir", None) or None,
        facts_path=getattr(args, "facts_file", None) or None,
    )
    print(dest)
    return 0


@_register("blocking", "One-sentence: what's blocking publish (existing gates only)")
def cmd_blocking(args: argparse.Namespace) -> int:
    from core.publish_blockers import publish_status_sentence

    # #734: read the real last run. A bare channel id graded an empty dict as an F.
    line = publish_status_sentence(args.channel)
    _emit_text("What's blocking publish", line, args)
    return 0


@_register("grounding-corpus", "Replay frozen grounding verdicts (no LLM)")
def cmd_grounding_corpus(_args: argparse.Namespace) -> int:
    from core.grounding_corpus import main as grounding_main

    return grounding_main()


@_register("roadmap-index", "Counts per roadmap file and by size, read from the docs")
def cmd_roadmap_index(args: argparse.Namespace) -> int:
    from core.roadmap_index import render

    _emit_text("Roadmap index", render(), args)
    return 0


@_register("agents", "Agent hand-off: who signed what, and whether the mailbox is stale")
def cmd_agents(args: argparse.Namespace) -> int:
    from core.agent_comms import render

    _emit_text("Agent hand-off", render(), args)
    return 0


@_register("title-card", "Write a 2-line title-card still (--path dest.png, --topic text)")
def cmd_title_card(args: argparse.Namespace) -> int:
    dest = (getattr(args, "path", None) or "").strip()
    text = (getattr(args, "topic", None) or "").strip() or "Title card"
    if not dest:
        print("title-card requires --path <dest.png>")
        return 2
    from core.title_card_wrap import write_title_card_still

    print(write_title_card_still(text, dest, max_lines=2))
    return 0


@_register(
    "log-override",
    "Record that a recommendation was ignored (--topic offered, --source chosen)",
)
def cmd_log_override(args: argparse.Namespace) -> int:
    offered = (getattr(args, "topic", None) or "").strip()
    chosen = (getattr(args, "source", None) or getattr(args, "target", None) or "").strip()
    if not offered or not chosen:
        print("log-override needs --topic <offered> and a chosen topic (--source or positional)")
        return 2
    from core.counterfactual import record_override

    row = record_override(offered, chosen)
    print(f"recorded override: {row['offered']} -> {row['chosen']}")
    return 0


@_register("command-ref", "Write docs/ops_commands.md from the live ops list")
def cmd_command_ref(_args: argparse.Namespace) -> int:
    from core.ops_command_ref import write_command_ref

    path = write_command_ref()
    print(path)
    return 0


@_register("diff-runs", "Compare grade/cost/ungrounded/disputed for two run ids")
def cmd_diff_runs(args: argparse.Namespace) -> int:
    if not args.run_id or not args.target:
        print("diff-runs needs --run-id A and a second id (positional target)")
        return 1
    from core.diff_runs import diff_run_ids

    print(diff_run_ids(int(args.run_id), int(args.target)))
    return 0


@_register("free-cost", "Prove the $0/Piper path billed $0 (or say that it did not)")
def cmd_free_cost(args: argparse.Namespace) -> int:
    from core.cost_meter import estimate_run_cost, free_mode_cost_proof

    script = ""
    cost = None
    try:
        from core.review_booth import last_trace

        trace = last_trace(args.channel)
        if trace:
            script = str(trace.get("script") or "")
            raw = trace.get("cost")
            if isinstance(raw, dict):
                cost = raw
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("free-cost last-run skipped: %s", exc)
    if cost is None:
        cost = estimate_run_cost(script=script or "word " * 150, signals={}, rendered=True)
    print(free_mode_cost_proof(cost))
    print(f"  tts ${float(cost.get('tts') or 0):.4f}  total ${float(cost.get('total') or 0):.4f}")
    return 0


@_register("desc-fold", "Dry-render the description above/below YouTube's Show more fold")
def cmd_desc_fold(args: argparse.Namespace) -> int:
    from core.description_fold import format_fold_preview

    description = ""
    try:
        from core.review_booth import last_trace

        trace = last_trace(args.channel)
        if trace:
            description = str(trace.get("description") or "")
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("desc-fold last-run skipped: %s", exc)
    if not description.strip():
        print("No description on the last run. Pass a draft through the pipeline first.")
        return 1
    print(format_fold_preview(description))
    return 0


@_register("digest", "This week's three operator decisions, written to the vault")
def cmd_digest(args: argparse.Namespace) -> int:
    from analytics.weekly_report import build_report, operator_digest, write_operator_digest

    report = build_report(args.channel)
    text = operator_digest(report)
    if not text:
        print(f"{args.channel}: not enough analytics for a digest yet")
        return 0
    print(text)
    path = write_operator_digest(args.channel, report)
    if path:
        print(f"\n  (saved to vault: {path})")
    return 0


@_register(
    "rollback-publish",
    "Unlist a published video + correction description + dossier (dry-run default; --apply sends)",
)
def cmd_rollback_publish(args: argparse.Namespace) -> int:
    from publishing.rollback import apply_rollback

    video_id = (getattr(args, "target", None) or "").strip()
    if not video_id:
        print("Usage: py -m scripts.ops rollback-publish <youtube-video-id> [--apply]")
        return 2
    correction = (getattr(args, "topic", None) or "").strip() or "Source walked this back."
    result = apply_rollback(
        video_id,
        correction=correction,
        channel_id=args.channel,
        dry_run=not bool(getattr(args, "apply", False)),
    )
    print(f"{result.status}: {result.detail}")
    if result.dossier_path:
        print(f"  dossier: {result.dossier_path}")
    if result.status == "dry_run":
        print("  Nothing was sent to YouTube. Re-run with --apply to unlist.")
    return 0 if result.status in ("dry_run", "updated") else 1


@_register("publish-dry-run", "Print the YouTube videos.insert body (no upload; tokens redacted)")
def cmd_publish_dry_run(args: argparse.Namespace) -> int:
    from publishing.base import PublishRequest
    from publishing.youtube_publisher import dry_run_insert_body, redact_publish_payload

    title = "Dry-run title"
    description = ""
    tags: list[str] = []
    file_path = "out.mp4"
    try:
        from core.review_booth import last_trace

        trace = last_trace(args.channel)
        if trace:
            title = str(trace.get("title") or title)
            description = str(trace.get("description") or "")
            file_path = str(trace.get("mp4_path") or file_path)
            tags = list(trace.get("tags") or [])
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("publish-dry-run last-run skipped: %s", exc)
    req = PublishRequest(
        file_path=file_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status="private",
    )
    body = redact_publish_payload(dry_run_insert_body(req, channel_id=args.channel))
    print(json.dumps(body, indent=2))
    return 0


@_register("next", "One action to take now across gates, quota, and vault decay")
def cmd_next(args: argparse.Namespace) -> int:
    from core.operator_shell import next_sentence

    print(next_sentence(getattr(args, "channel", None)))
    return 0


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
    print("  all-checks         validate + test + feeds")
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


@_register("all-checks", "Validate channels + unit tests + feed health")
def cmd_all_checks(args: argparse.Namespace) -> int:
    return _run_batch(["validate", "test", "feeds"], args)


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
    parser.add_argument("--arm", default="", help="pick-thumbnail: text_on or face_forward")
    parser.add_argument("--path", default="", help="pick-thumbnail: exact candidate image path")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Row limit (traces / economics; 0 = command default)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="clock-ahead: days to shift the clock (0 = 365)",
    )
    parser.add_argument(
        "--topic",
        default="",
        help="Topic for intelligence-report (required) or tapology-test",
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
        "--mode",
        dest="vault_eval_mode",
        choices=("legacy", "shadow", "scored", "both"),
        default="",
        help="vault-eval: legacy, shadow, scored, or both (default)",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="vault-eval: print an advisory calibration without changing config",
    )
    parser.add_argument(
        "--no-save",
        dest="no_save",
        action="store_true",
        help="vault-eval: report without writing data/vault_evals",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="vault-eval: save results outside the default data directory",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="overnight: file of topics (one per line) instead of best-bet",
    )
    parser.add_argument(
        "--facts-file",
        dest="facts_file",
        default=None,
        help="overnight: operator key facts (same as auto_generate --facts-file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="backfill-cost: show what would change without writing",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "artifacts / moat-backup / ingest-clips / rollback-publish: "
            "actually delete, copy, remux, or unlist (default is dry-run)"
        ),
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="ingest-clips: delete the capture file after a successful remux",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Write a themed HTML snapshot and open it (reliability/economics/doctor/status/grade)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="economics: write a CSV next to HTML dumps (not under data/)",
    )
    parser.add_argument(
        "--stay",
        action="store_true",
        help="tray: keep the on-top quota chip window",
    )
    parser.add_argument(
        "--open-output",
        action="store_true",
        help="tray: open the last channel output folder",
    )
    parser.add_argument(
        "--doctor-html",
        action="store_true",
        help="tray: write ops doctor as themed HTML",
    )
    parser.add_argument(
        "--pause-overnight",
        action="store_true",
        help="tray: pause future scheduled overnight batches",
    )
    parser.add_argument(
        "--resume-overnight",
        action="store_true",
        help="tray: resume future scheduled overnight batches",
    )
    parser.add_argument(
        "--md",
        action="store_true",
        help="grade / postmortem: print copy-as-markdown instead of ASCII",
    )
    parser.add_argument(
        "--kind",
        default="mp4",
        help="reveal: mp4, thumb, or trace (default: mp4)",
    )
    parser.add_argument(
        "--sku",
        action="store_true",
        help="intelligence-report: write the no-video SKU markdown",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="shell: localhost port (default 8765)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="booth: tiny stdlib localhost host (not FastAPI)",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="reliability: VACUUM the sqlite at --path (default data/content_os.db)",
    )
    parser.add_argument(
        "--sendto-dir",
        dest="sendto_dir",
        default=None,
        help="sendto-facts: write the shortcut here (tests; default is %%APPDATA%%/SendTo)",
    )
    parser.add_argument(
        "--install", action="store_true", help="schedule-drafts: create the nightly task"
    )
    parser.add_argument(
        "--remove", action="store_true", help="schedule-drafts: delete the nightly task"
    )
    parser.add_argument(
        "--target",
        default="",
        help="mutate-gates: only targets whose module.function contains this text",
    )
    args = parser.parse_args(argv)
    args.queue_upload = False
    args.queue_requeue = False
    args.queue_reset = False
    args.queue_schedule = False
    args.force = False

    try:
        from core.human_presence import maybe_touch_ops

        maybe_touch_ops(args.command)
    except Exception as exc:
        from core.logging import get_logger

        get_logger("scripts.ops").debug("ops heartbeat skipped: %s", exc)

    _, fn = COMMANDS[args.command]
    return fn(args)


if __name__ == "__main__":
    from core.console_encoding import ensure_utf8_stdout

    ensure_utf8_stdout()  # #767: redirected / scheduled runs are cp1252
    raise SystemExit(main())
