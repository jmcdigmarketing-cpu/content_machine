import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from apis.register_signals import build_registry
from apis.topic_scorer import composite_score
from apis.topic_variants import generate_variants
from config.channels import resolve_channel_id
from core.asset_recorder import record_render_assets
from core.channel_context import anchor_preservation_penalty, mcu_drift_penalty
from core.content_engine import generate_content_package
from core.logging import get_logger
from core.output_paths import media_paths_for_topic
from core.render_progress import RenderProgress, is_render_progress_enabled
from core.research_brief import build_research_brief
from core.run_quality import build_quality, persist_quality
from core.run_recorder import (
    record_content_run,
    record_learning_outcome,
    update_content_run_media,
)
from core.run_trace import write_run_trace
from core.script_length import count_spoken_words, get_length_preset, word_range
from core.tts import generate_audio
from core.utils import clean_script_for_tts
from core.vault_dossiers import write_run_dossier
from video.render_video import render_vertical_video

logger = get_logger("pipeline")


@dataclass
class DiscoveryResult:
    """Signals + scored variants for a topic (no content generation yet)."""

    input_topic: str
    base_signals: dict[str, Any]
    evaluated: list[tuple[str, float, dict[str, Any]]]  # variant, score, signals
    timings: dict[str, float] = field(default_factory=dict)
    channel_id: str = "default"


@dataclass
class PipelineResult:
    topic: str
    score: float
    signals: dict[str, Any]
    title: str = ""
    script: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    brief_version: str = ""
    prompt_version: str = ""
    mp3_path: str | None = None
    mp4_path: str | None = None
    variants: list[tuple[str, float]] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None
    # Mostly phase durations (float), but "length_preset" (str) rides along by
    # design — analytics/length_recommender join on timings_json.length_preset.
    timings: dict[str, Any] = field(default_factory=dict)
    channel_id: str = "default"
    run_id: int | None = None
    features: dict[str, Any] = field(default_factory=dict)


def _score_variant(
    variant: str,
    channel_id: str,
    base_signals: dict[str, Any],
    *,
    seed_topic: str = "",
):
    variant_signals = build_registry(variant, reuse_signals=base_signals, channel_id=channel_id)
    score = composite_score(variant_signals, variant, channel_id)
    if seed_topic:
        score = max(
            0.0,
            score
            - anchor_preservation_penalty(variant, seed_topic)
            - mcu_drift_penalty(variant, seed_topic),
        )
    return variant, score, variant_signals


def _word_range(length_choice: str) -> tuple[int, int]:
    return word_range(length_choice)


def run_discovery(
    topic: str,
    variant_limit: int = 5,
    channel_id: str | None = None,
    *,
    progress: Callable[..., None] | None = None,
) -> DiscoveryResult:
    """Pull signals, generate variants, score in parallel.

    progress: optional callback(phase: str, done: int | None, total: int | None)
    invoked as each discovery phase advances (drives the live spinner).
    """

    def _report(
        phase: str,
        done: int | None = None,
        total: int | None = None,
        detail: str | None = None,
    ) -> None:
        if not progress:
            return
        try:
            progress(phase, done, total, detail)
        except TypeError:
            # Older 3-arg progress callbacks (custom callers) — drop the detail.
            try:
                progress(phase, done, total)
            except Exception as exc:
                logger.debug("3-arg progress callback failed at phase '%s': %s", phase, exc)
        except Exception as exc:  # never let UI reporting break discovery
            logger.debug("progress callback failed at phase '%s': %s", phase, exc)

    channel_id = resolve_channel_id(channel_id)
    t0 = time.perf_counter()

    # Start a fresh per-run LLM token ledger so cost_meter prices only this run.
    from core.llm_router import reset_usage

    reset_usage()

    _report("Loading history")

    # Quick Apify on/off check before topic research — if the key is dead or the
    # monthly limit is hit, disable Apify for the session so the social actors
    # skip instantly instead of timing out (and burning credits) on every variant.
    # Skip the preflight entirely when no paid Apify signal will actually run for
    # this topic (gated/skipped/already-disabled) — no point paying /users/me.
    if os.getenv("APIFY_CONTENT_MACHINE_KEY", "").strip():
        from apis.register_signals import will_use_apify

        if will_use_apify(topic, channel_id):
            from apis.apify_client import apify_preflight

            ok, status = apify_preflight()
            print(f"  Apify: {status}" if ok else f"  Apify: {status} — social signals skipped")

    competitor_sync = os.getenv("COMPETITOR_SYNC_ON_DISCOVERY", "auto").lower()
    if competitor_sync in ("1", "true", "yes", "auto"):
        from analytics.competitor_context import ensure_competitor_snapshot

        ensure_competitor_snapshot(channel_id)

    # Count how many recent runs share the same franchise anchor so variant
    # generation can shift from "news/update" angles to analysis/prediction
    # angles when a topic has been covered multiple times.
    from core.channel_context import dominant_anchor, recent_input_topics

    _recent = recent_input_topics(channel_id, limit=20)
    _anchor = dominant_anchor([topic, *_recent])
    repeat_count = (
        sum(1 for t in _recent if _anchor and _anchor.lower() in t.lower()) if _anchor else 0
    )

    _report("Fetching signals & variants")
    with ThreadPoolExecutor(max_workers=2) as executor:
        signals_future = executor.submit(build_registry, topic, channel_id=channel_id)
        variants_future = executor.submit(
            generate_variants,
            topic,
            channel_id=channel_id,
            repeat_count=repeat_count,
        )
        base_signals = signals_future.result()
        variants = variants_future.result()

    timings = {"signals_and_variants": time.perf_counter() - t0}

    t1 = time.perf_counter()
    candidates = variants[:variant_limit]
    total = len(candidates)
    _report("Scoring variants", 0, total)
    evaluated: list[tuple[str, float, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_score_variant, v, channel_id, base_signals, seed_topic=topic): v
            for v in candidates
        }
        for done, future in enumerate(as_completed(futures), start=1):
            evaluated.append(future.result())
            # Show which angle just finished scoring — engagement during the wait.
            _report("Scoring variants", done, total, detail=futures[future])
    # Restore deterministic candidate order (as_completed yields by completion time).
    _order = {v: i for i, v in enumerate(candidates)}
    evaluated.sort(key=lambda e: _order.get(e[0], len(candidates)))
    timings["variant_scoring"] = time.perf_counter() - t1

    # Persist this run's cache hit/miss counters for the reliability dashboard (O8).
    try:
        from apis.cache_manager import flush_cache_stats

        flush_cache_stats()
    except Exception as exc:
        logger.debug("Cache-stat flush skipped after discovery: %s", exc)

    return DiscoveryResult(
        input_topic=topic,
        base_signals=base_signals,
        evaluated=evaluated,
        timings=timings,
        channel_id=channel_id,
    )


def finalize_run_observability() -> None:
    """Merge in-process cache counters at pipeline end (O8 follow-up).

    ``run_discovery`` flushes once after signals; this second flush captures
    cache hits during script generation and fact enrichment afterward.
    """
    try:
        from apis.cache_manager import flush_cache_stats

        flush_cache_stats()
    except Exception as exc:
        logger.debug("Final cache-stat flush skipped: %s", exc)


def _finalize_run(
    *,
    channel_id: str,
    input_topic: str,
    result: PipelineResult,
    discovery: DiscoveryResult,
) -> None:
    if result.aborted and result.abort_reason == "no_variants":
        status = "aborted"
    elif result.aborted:
        status = "drafted" if result.abort_reason == "proceed_video=False" else "aborted"
    elif result.mp4_path:
        status = "rendered"
    else:
        status = "drafted"

    run_id = record_content_run(
        channel_id=channel_id,
        input_topic=input_topic,
        selected_topic=result.topic,
        status=status,
        composite_score=result.score,
        signals=result.signals,
        variants=result.variants,
        title=result.title,
        description=result.description,
        tags_json=json.dumps(result.tags or []),
        brief_version=result.brief_version or "",
        prompt_version=result.prompt_version or "",
        script=result.script,
        mp3_path=result.mp3_path or "",
        mp4_path=result.mp4_path or "",
        timings={**discovery.timings, **result.timings},
        abort_reason=result.abort_reason or "",
        features=result.features or {},
    )
    result.run_id = run_id

    # Pillar 1 (Run Ledger): persist the quality scores every path used to
    # print-and-discard, then drop the full per-run trace. Both fail-open.
    quality: dict[str, Any] = {}
    try:
        quality = build_quality(
            script=result.script,
            channel_id=channel_id,
            features=result.features,
            exclude_run_id=run_id,
        )
        persist_quality(run_id, quality)
    except Exception:
        quality = {}
    try:
        write_run_trace(
            run_id=run_id,
            channel_id=channel_id,
            input_topic=input_topic,
            selected_topic=result.topic,
            status=status,
            timings={**discovery.timings, **result.timings},
            signals=result.signals,
            features=result.features,
            quality=quality,
        )
    except Exception as exc:
        # Warning, not debug: the trace is what `ops traces`, `ops dossier` and
        # data_quality's per-signal failure rates read. A missing one blinds the
        # observability layer for this run without anything else noticing.
        logger.warning("Run trace not written for run %s: %s", run_id, exc)

    # Pillar 4: mirror the run into the Obsidian vault (no-op without a vault).
    if status in ("drafted", "rendered"):
        try:
            write_run_dossier(run_id)
        except Exception as exc:
            logger.debug("Vault dossier skipped for run %s: %s", run_id, exc)

    if result.score > 0 and status in ("drafted", "rendered"):
        record_learning_outcome(
            channel_id=channel_id,
            topic=result.topic,
            score=result.score,
            content_run_id=run_id,
        )

    try:
        from core.events import emit_event

        emit_event(
            "run_completed",
            {
                "channel_id": channel_id,
                "run_id": run_id,
                "status": status,
                "topic": result.topic,
                "title": result.title,
                "score": result.score,
                "abort_reason": result.abort_reason or "",
            },
        )
    except Exception as exc:
        logger.debug("run_completed webhook event not emitted for run %s: %s", run_id, exc)


def run_pipeline(
    topic: str,
    *,
    discovery: DiscoveryResult | None = None,
    variant_index: int | None = None,
    length_choice: str = "2",
    proceed_video: bool = True,
    variant_limit: int = 5,
    channel_id: str | None = None,
    creative_brief: str = "",
    key_facts: list[str] | None = None,
) -> PipelineResult:
    """
    End-to-end content pipeline without CLI I/O.
    Pass discovery= to reuse a prior run_discovery() and avoid duplicate API calls.
    """
    channel_id = resolve_channel_id(channel_id or (discovery.channel_id if discovery else None))
    result = PipelineResult(topic=topic, score=0.0, signals={}, channel_id=channel_id)

    if discovery is None:
        discovery = run_discovery(topic, variant_limit=variant_limit, channel_id=channel_id)
        result.timings.update(discovery.timings)
    else:
        result.timings.update(discovery.timings)
        channel_id = discovery.channel_id

    result.channel_id = channel_id
    input_topic = discovery.input_topic

    evaluated = discovery.evaluated
    if not evaluated:
        result.aborted = True
        result.abort_reason = "no_variants"
        _finalize_run(
            channel_id=channel_id, input_topic=input_topic, result=result, discovery=discovery
        )
        return result

    result.variants = [(v, s) for v, s, _ in evaluated]

    if variant_index is not None and 0 <= variant_index < len(evaluated):
        index = variant_index
    else:
        index = max(range(len(evaluated)), key=lambda i: evaluated[i][1])

    best_topic, best_score, best_signals = evaluated[index]
    result.topic = best_topic
    result.score = best_score
    result.signals = best_signals

    preset = get_length_preset(length_choice)
    wr = _word_range(length_choice)
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info("Building research brief for: %s", best_topic)
    t_brief = time.perf_counter()
    research_brief = build_research_brief(
        best_topic,
        best_signals,
        channel_id=channel_id,
        seed_topic=input_topic,
    )
    result.timings["research_brief"] = time.perf_counter() - t_brief

    logger.info("Generating content package for: %s", best_topic)
    t_content = time.perf_counter()
    content = generate_content_package(
        topic=best_topic,
        signals=best_signals,
        word_range=wr,
        today=today,
        channel_id=channel_id,
        research_brief=research_brief,
        length_choice=length_choice,
        seed_topic=input_topic,
        creative_brief=creative_brief,
        key_facts=key_facts or [],
    )
    result.timings["length_preset"] = preset.choice
    result.timings["content_package"] = time.perf_counter() - t_content

    result.title = content.get("title", best_topic)
    result.script = clean_script_for_tts(content.get("script", ""))
    result.timings["word_count"] = count_spoken_words(result.script)
    result.description = content.get("description", "")
    result.tags = list(content.get("tags") or [])
    result.brief_version = content.get("brief_version") or research_brief.version
    result.prompt_version = content.get("prompt_version") or ""

    from core.run_features import build_features

    result.features = build_features(
        topic=best_topic,
        channel_id=channel_id,
        content_package=content,
        research_brief=research_brief,
        length_choice=length_choice,
        key_facts=key_facts,
        fact_source="manual" if key_facts else "signals",
    )

    result.features["ungrounded_entities"] = content.get("ungrounded_entities") or []
    result.features["trade_warnings"] = content.get("trade_warnings") or []
    # Pillar 3 (Fact Engine): tier lint, pre-script conflicts, claim verifier.
    result.features["tier_warnings"] = content.get("tier_warnings") or []
    result.features["fact_conflicts"] = content.get("fact_conflicts") or []
    result.features["fact_conflicts_dropped"] = int(content.get("fact_conflicts_dropped") or 0)
    if content.get("claim_verification"):
        result.features["claim_verification"] = content["claim_verification"]

    # Quick win (Pillar 3): web-search result URLs become reusable research in
    # the vault (_sources.md) instead of evaporating with the run. Fail-open.
    try:
        from core.source_capture import capture_web_sources

        capture_web_sources(channel_id, best_topic, best_signals)
    except Exception as exc:
        logger.debug("Web-source capture skipped for '%s': %s", best_topic, exc)

    from core.cost_meter import estimate_run_cost

    result.features["cost"] = estimate_run_cost(
        script=result.script, signals=best_signals, rendered=False
    )

    if not proceed_video:
        result.aborted = True
        result.abort_reason = "proceed_video=False"
        _finalize_run(
            channel_id=channel_id, input_topic=input_topic, result=result, discovery=discovery
        )
        return result

    mp3_path, mp4_path, _thumb = run_media_only(
        best_topic,
        result.script,
        channel_id=channel_id,
        title=result.title,
    )
    result.mp3_path = mp3_path
    result.mp4_path = mp4_path

    # Recompute cost now that TTS/render actually ran (adds the TTS line).
    result.features["cost"] = estimate_run_cost(
        script=result.script, signals=best_signals, rendered=True
    )

    _finalize_run(
        channel_id=channel_id, input_topic=input_topic, result=result, discovery=discovery
    )
    return result


def run_media_only(
    topic: str,
    script: str,
    *,
    channel_id: str | None = None,
    content_run_id: int | None = None,
    title: str | None = None,
) -> tuple[str, str, str]:
    """Generate audio + video (+ thumbnail). Returns (mp3, mp4, thumbnail_path)."""
    channel_id = resolve_channel_id(channel_id)
    display_title = title or topic
    progress = RenderProgress(enabled=is_render_progress_enabled())

    progress.stage("Preparing output paths...")
    mp3_path, mp4_filename, mp4_path = media_paths_for_topic(topic, channel_id=channel_id)
    progress.note(f"MP3 → {mp3_path}")
    progress.note(f"MP4 → {mp4_path}")

    progress.stage("ElevenLabs TTS...")
    t_tts = time.perf_counter()
    generate_audio(script, mp3_path, channel_id=channel_id)
    progress.note(f"TTS finished in {time.perf_counter() - t_tts:.1f}s")

    _, background = render_vertical_video(
        mp3_path,
        topic,
        mp4_filename,
        script,
        channel_id,
        progress=progress,
    )

    thumb_path = ""
    if os.getenv("THUMBNAIL_MODE", "auto").lower() != "off":
        progress.stage("Thumbnail (Flux or Pillow)...")
        t_thumb = time.perf_counter()
        from assets.flux_thumbnail import generate_thumbnail
        from core.output_paths import ensure_channel_output_dirs

        thumb_dir = ensure_channel_output_dirs(channel_id)["thumbnails"]
        thumb = generate_thumbnail(
            topic,
            display_title,
            output_dir=thumb_dir,
            content_run_id=content_run_id,
            channel_id=channel_id,
        )
        if thumb.path:
            thumb_path = thumb.path
            from assets.flux_thumbnail import list_channel_thumbnails

            total = len(list_channel_thumbnails(thumb_dir))
            progress.note(f"{thumb.detail or 'thumbnail'} — {thumb_path}")
            progress.note(f"Thumbnails in folder: {total} ({thumb_dir})")
        else:
            progress.note(thumb.detail or "thumbnail skipped")
        progress.note(f"Thumbnail step {time.perf_counter() - t_thumb:.1f}s")

        if thumb_path:
            from assets.thumbnail_scorer import maybe_score_after_render

            scored = maybe_score_after_render(
                thumbnail_path=thumb_path,
                topic=topic,
                channel_id=channel_id,
                content_run_id=content_run_id,
            )
            if scored:
                progress.note(f"Thumbnail score {scored.overall}/100 ({scored.source})")
                if content_run_id:
                    from core.run_quality import merge_quality

                    merge_quality(
                        content_run_id,
                        {"thumbnail_overall": scored.overall, "thumbnail_source": scored.source},
                    )

    if content_run_id:
        update_content_run_media(
            content_run_id, mp3_path=mp3_path, mp4_path=mp4_path, status="rendered"
        )
        # The run was finalized before this render (both operator flows call
        # run_pipeline with proceed_video=False, then render here), so its stored cost
        # still says tts=0 and its trace still says "drafted". Correct both now —
        # unit_economics computes contribution margin off features_json.cost.total,
        # and TTS is the largest line on a rendered run. Fail-open: a bookkeeping
        # error must never fail a render that already succeeded.
        try:
            from core.cost_meter import merge_render_cost
            from core.run_features import load_features, merge_features
            from core.run_trace import update_trace

            cost = merge_render_cost((load_features(content_run_id) or {}).get("cost"), script)
            merge_features(content_run_id, {"cost": cost})
            update_trace(content_run_id, {"status": "rendered", "cost": cost})
        except Exception as exc:
            logger.debug("post-render cost update skipped for run %s: %s", content_run_id, exc)

        record_render_assets(
            channel_id=channel_id,
            content_run_id=content_run_id,
            topic=topic,
            title=display_title,
            mp4_path=mp4_path,
            background=background,
            thumbnail_path=thumb_path or None,
        )

    progress.done("Render complete")
    return mp3_path, mp4_path, thumb_path
