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


@_register("reliability", "Credit/quota dashboard (Apify + LLM budgets, breakers, cache hit-rate)")
def cmd_reliability(args: argparse.Namespace) -> int:
    from core.reliability import gather, render

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
    # Non-zero on a dead signal so `all-checks` fails loudly rather than quietly.
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

    cancelled = detect_studio_deleted(args.channel)
    if not cancelled:
        print(f"Studio-deleted: none for {args.channel}")
        return 0
    print(f"Studio-deleted: cancelled {len(cancelled)} publish_log row(s)")
    for row in cancelled:
        print(f"  #{row.id} {row.youtube_video_id}")
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
    from core.publish_blockers import blocking_publish_sentence

    line = blocking_publish_sentence(channel_id=args.channel)
    _emit_text("What's blocking publish", line, args)
    return 0


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
        help="artifacts / moat-backup / ingest-clips: actually delete, copy, or remux (default is dry-run)",
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
        "--sendto-dir",
        dest="sendto_dir",
        default=None,
        help="sendto-facts: write the shortcut here (tests; default is %%APPDATA%%/SendTo)",
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
    raise SystemExit(main())
