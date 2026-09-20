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
from core.tts import generate_audio, last_tts_cache_fraction, last_tts_was_piper_mix
from core.utils import clean_script_for_tts
from core.vault_dossiers import write_run_dossier
from video.render_video import render_vertical_video

logger = get_logger("pipeline")


def copy_content_package_features(content: dict[str, Any], features: dict[str, Any]) -> None:
    """Lift package keys the rest of the run reads onto ``result.features``.

    Absence of ``script_passes`` means the ledger was not on this run (historical
    traces). An empty or all-skipped list still copies, so the report card can
    say none adopted rather than go silent.
    """
    if "script_passes" in content:
        features["script_passes"] = list(content.get("script_passes") or [])


def _tts_forecast_features() -> dict[str, int]:
    try:
        from core.tts_char_cap import last_tts_forecast

        snap = last_tts_forecast() or {}
    except Exception as exc:
        logger.debug("tts forecast features skipped: %s", exc)
        return {}
    out: dict[str, int] = {}
    forecast = snap.get("forecast_chars")
    if forecast is not None:
        out["tts_forecast_chars"] = int(forecast)
    actual = snap.get("actual_chars")
    if actual is not None:
        out["tts_actual_chars"] = int(actual)
    delta = snap.get("delta_chars")
    if delta is not None:
        out["tts_char_delta"] = int(delta)
    return out


@dataclass
class DiscoveryResult:
    """Signals + scored variants for a topic (no content generation yet)."""

    input_topic: str
    base_signals: dict[str, Any]
    evaluated: list[tuple[str, float, dict[str, Any]]]  # variant, score, signals
    timings: dict[str, float] = field(default_factory=dict)
    channel_id: str = "default"
    # Candidate 323: variant -> pre-clamp composite. The displayed score is capped at
    # 100, so on a hot topic every variant reads 100.0 and the ranking carries no
    # information. Kept beside `evaluated` (not inside it) so the 3-tuple shape that
    # batch_generation / intelligence_report unpack stays exactly as it was.
    raw_scores: dict[str, float] = field(default_factory=dict)
    # variant -> editorial score (`core/angle_ranker`). Deliberately a third dict
    # rather than folded into the composite: the composite is a trend number and
    # this is an editorial one, and averaging an unvalidated score into another
    # unvalidated score would hide both. Same reason `raw_scores` sits out here.
    angle_scores: dict[str, float] = field(default_factory=dict)
    # Run 77: the operator's typed thoughts. Angles differ by thoughts on the same seed,
    # so the cache key carries them too.
    brief: str = ""


DISCOVERY_CACHE_PREFIX = "discovery"
DISCOVERY_CACHE_TTL = 90 * 60


def _discovery_ttl_seconds() -> int:
    raw = (os.getenv("DISCOVERY_CACHE_TTL_SECONDS") or "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return DISCOVERY_CACHE_TTL


def _discovery_cache_enabled() -> bool:
    return (os.getenv("DISCOVERY_CACHE", "true") or "").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _discovery_cache_key(channel_id: str, topic: str, brief: str = "") -> str:
    from apis.cache_manager import build_key

    thoughts = (brief or "").strip()
    return build_key(
        f"{DISCOVERY_CACHE_PREFIX}::{channel_id}", f"{topic}\n\n{thoughts}" if thoughts else topic
    )


def _discovery_from_payload(data: object) -> DiscoveryResult | None:
    if not isinstance(data, dict):
        return None
    evaluated_raw = data.get("evaluated") or []
    evaluated: list[tuple[str, float, dict[str, Any]]] = []
    for row in evaluated_raw:
        if not isinstance(row, list | tuple) or len(row) < 3:
            continue
        signals = row[2] if isinstance(row[2], dict) else {}
        evaluated.append((str(row[0]), float(row[1]), signals))
    if not evaluated:
        return None
    raw_obj = data.get("raw_scores")
    raw: dict[str, Any] = raw_obj if isinstance(raw_obj, dict) else {}
    angle_obj = data.get("angle_scores")
    angle: dict[str, Any] = angle_obj if isinstance(angle_obj, dict) else {}
    timings_obj = data.get("timings")
    timings: dict[str, Any] = timings_obj if isinstance(timings_obj, dict) else {}
    base_obj = data.get("base_signals")
    base_signals: dict[str, Any] = base_obj if isinstance(base_obj, dict) else {}
    return DiscoveryResult(
        input_topic=str(data.get("input_topic") or ""),
        base_signals=base_signals,
        evaluated=evaluated,
        timings={str(k): float(v) for k, v in timings.items() if isinstance(v, int | float)},
        channel_id=str(data.get("channel_id") or "default"),
        raw_scores={str(k): float(v) for k, v in raw.items() if isinstance(v, int | float)},
        angle_scores={str(k): float(v) for k, v in angle.items() if isinstance(v, int | float)},
        brief=str(data.get("brief") or ""),
    )


def _discovery_age_note(channel_id: str, topic: str, brief: str = "") -> str:
    """`" - 12m old"`, or `""` when the age cannot be read. Never raises."""
    try:
        from apis.cache_manager import cache_age_seconds

        age = cache_age_seconds(_discovery_cache_key(channel_id, topic, brief))
    except Exception as exc:
        logger.debug("discovery cache age unavailable: %s", exc)
        return ""
    if age is None:
        return ""
    return f" - {int(age)}s old" if age < 90 else f" - {int(age // 60)}m old"


def _load_discovery_cache(channel_id: str, topic: str, brief: str = "") -> DiscoveryResult | None:
    if not _discovery_cache_enabled():
        return None
    try:
        from apis.cache_manager import get_cached

        return _discovery_from_payload(get_cached(_discovery_cache_key(channel_id, topic, brief)))
    except Exception as exc:
        logger.debug("discovery cache load skipped: %s", exc)
        return None


def _store_discovery_cache(result: DiscoveryResult) -> None:
    if not _discovery_cache_enabled() or not result.evaluated:
        return
    try:
        from apis.cache_manager import set_cache

        payload = {
            "input_topic": result.input_topic,
            "channel_id": result.channel_id,
            "base_signals": result.base_signals,
            "evaluated": result.evaluated,
            "raw_scores": result.raw_scores,
            "angle_scores": result.angle_scores,
            "timings": result.timings,
            "brief": result.brief,
        }
        set_cache(
            _discovery_cache_key(result.channel_id, result.input_topic, result.brief),
            payload,
            ttl_seconds=_discovery_ttl_seconds(),
        )
    except Exception as exc:
        logger.debug("discovery cache store skipped: %s", exc)


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
    menu_path: str | None = None
    angle_intent: str | None = None


def best_variant_index(
    evaluated: list[tuple[str, float, Any]],
    raw_scores: dict[str, float] | None = None,
    angle_scores: dict[str, float] | None = None,
) -> int:
    """Index of the best variant. Three keys, in descending order of authority.

    1. the displayed composite;
    2. the pre-clamp composite (323) — `composite_score` caps at 100, so on a hot
       topic every variant reads 100.0 and the ranking carries no information;
    3. the editorial score (`core/angle_ranker`).

    323 assumed the pre-clamp numbers differ. They do not: `_score_variant` scores
    every variant against the *same* pinned signals, and the variant string reaches
    `composite_score_raw` only through `infer_domain` and an exact-string history
    lookup. Run 72 tied at 92.14 — below the ceiling, after 323 shipped — so key 2
    had nothing to break either. Key 3 reads the angle text itself.
    """
    if not evaluated:
        raise ValueError("evaluated must be non-empty")
    raw = raw_scores or {}
    angle = angle_scores or {}
    return max(
        range(len(evaluated)),
        key=lambda i: (
            evaluated[i][1],
            raw.get(evaluated[i][0], evaluated[i][1]),
            angle.get(evaluated[i][0], 0.0),
        ),
    )


def chosen_variant(
    discovery: DiscoveryResult,
    variant_index: int | None,
) -> tuple[str, float, Any]:
    """#664. `variant_index == -1` means keep the operator's typed idea."""
    evaluated = discovery.evaluated
    if variant_index == -1:
        return discovery.input_topic, 0.0, discovery.base_signals
    if variant_index is not None and 0 <= variant_index < len(evaluated):
        return evaluated[variant_index]
    index = best_variant_index(evaluated, discovery.raw_scores, discovery.angle_scores)
    return evaluated[index]


def _score_variant(
    variant: str,
    channel_id: str,
    base_signals: dict[str, Any],
    *,
    seed_topic: str = "",
):
    from apis.topic_scorer import composite_score_raw

    variant_signals = build_registry(variant, reuse_signals=base_signals, channel_id=channel_id)
    score = composite_score(variant_signals, variant, channel_id)
    # Candidate 323: same number without the 0-100 clamp, for tie-breaking only.
    raw = composite_score_raw(variant_signals, variant, channel_id)
    if seed_topic:
        penalty = anchor_preservation_penalty(variant, seed_topic) + mcu_drift_penalty(
            variant, seed_topic
        )
        score = max(0.0, score - penalty)
        raw = raw - penalty
    return variant, score, variant_signals, raw


def _word_range(length_choice: str) -> tuple[int, int]:
    return word_range(length_choice)


def run_discovery(
    topic: str,
    variant_limit: int = 5,
    channel_id: str | None = None,
    *,
    progress: Callable[..., None] | None = None,
    brief: str = "",
) -> DiscoveryResult:
    """Pull signals, generate variants, score in parallel.

    progress: optional callback(phase: str, done: int | None, total: int | None)
    invoked as each discovery phase advances (drives the live spinner).
    brief: the operator's own thoughts. Signals search ``topic``; the angles are
    generated and ranked against the thoughts.
    """
    brief = (brief or "").strip()
    if brief.lower() == (topic or "").strip().lower():
        brief = ""

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

    # Pre-run completion gate: Free fail-closed if the first LLM/TTS call would 404
    # a missing Ollama (run 70). Standard may warn. Cheap — uses the cached tags probe.
    from core.run_mode import guard_before_discovery

    for warning in guard_before_discovery():
        print(f"  ! {warning}")

    # Start a fresh per-run LLM token ledger so cost_meter prices only this run.
    from core.llm_router import reset_usage

    reset_usage()

    cached = _load_discovery_cache(channel_id, topic, brief)
    if cached is not None:
        # Name the age, not just the fact. The TTL is 90 minutes, and on a moving
        # topic an 89-minute-old discovery is a different thing from a 2-minute-old
        # one -- run 73's recorded failure was exactly freshness decaying quietly.
        # Same convention as feed_health ("check is Nd old") and the competitor
        # snapshot age.
        age = _discovery_age_note(channel_id, topic, brief)
        print(f"  Reused discovery from cache ({topic}){age}")
        _report("Reused discovery")
        return cached

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
    variant_kwargs: dict[str, Any] = {"channel_id": channel_id, "repeat_count": repeat_count}
    if brief:
        variant_kwargs["brief"] = brief
    with ThreadPoolExecutor(max_workers=2) as executor:
        signals_future = executor.submit(build_registry, topic, channel_id=channel_id)
        variants_future = executor.submit(generate_variants, topic, **variant_kwargs)
        base_signals = signals_future.result()
        variants = variants_future.result()

    timings = {"signals_and_variants": time.perf_counter() - t0}

    t1 = time.perf_counter()
    candidates = variants[:variant_limit]
    total = len(candidates)
    _report("Scoring variants", 0, total)
    evaluated: list[tuple[str, float, dict[str, Any]]] = []
    raw_scores: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_score_variant, v, channel_id, base_signals, seed_topic=topic): v
            for v in candidates
        }
        for done, future in enumerate(as_completed(futures), start=1):
            variant, score, variant_signals, raw = future.result()
            evaluated.append((variant, score, variant_signals))
            raw_scores[variant] = raw
            # Show which angle just finished scoring — engagement during the wait.
            _report("Scoring variants", done, total, detail=futures[future])
    # Restore deterministic candidate order (as_completed yields by completion time).
    _order = {v: i for i, v in enumerate(candidates)}
    evaluated.sort(key=lambda e: _order.get(e[0], len(candidates)))
    timings["variant_scoring"] = time.perf_counter() - t1

    # Editorial ranking of the angle text, scored over the whole candidate set at once
    # (distinctness is relative), so it runs after the loop rather than inside
    # `_score_variant`. ANGLE_LLM_JUDGE (default on) adds one cheap-tier call that
    # blends a thesis-fit score in; off, the ranking is deterministic and network-free.
    # Fail-open: a missing editorial score costs a tiebreaker, never the run.
    angle_scores: dict[str, float] = {}
    try:
        from core.angle_ranker import rank_angles
        from core.providers import flag_enabled

        angle_scores = rank_angles(
            [v for v, *_ in evaluated],
            seed_topic=f"{topic}. {brief}" if brief else topic,
            llm_judge=flag_enabled("ANGLE_LLM_JUDGE", default=True),
        )
    except Exception as exc:
        logger.warning("Angle ranking skipped (%s) — variants keep the composite tie", exc)

    # Persist this run's cache hit/miss counters for the reliability dashboard (O8).
    try:
        from apis.cache_manager import flush_cache_stats

        flush_cache_stats()
    except Exception as exc:
        logger.debug("Cache-stat flush skipped after discovery: %s", exc)

    result = DiscoveryResult(
        input_topic=topic,
        base_signals=base_signals,
        evaluated=evaluated,
        raw_scores=raw_scores,
        angle_scores=angle_scores,
        timings=timings,
        channel_id=channel_id,
        brief=brief,
    )
    _store_discovery_cache(result)
    return result


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

    if result.mp4_path:
        try:
            from core.render_artifacts import write_render_sidecars

            side = write_render_sidecars(
                result.mp4_path,
                script=result.script or "",
                features=result.features,
                quality={},
            )
            if side.get("mp4_sha256") or side.get("script_sha256"):
                result.features["artifact_manifest"] = {
                    "mp4_sha256": side.get("mp4_sha256"),
                    "script_sha256": side.get("script_sha256"),
                }
        except Exception as exc:
            logger.warning("render sidecars skipped: %s", exc)

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
        from core.grade import expert_panel_review, persist_expert_panel
        from core.providers import flag_enabled

        if flag_enabled("EXPERT_PANEL_ENABLED") and run_id and (result.script or "").strip():
            panel = expert_panel_review(result.script, channel_id)
            if panel.ok and panel.data:
                persist_expert_panel(run_id, panel.data)
    except Exception as exc:
        logger.debug("expert panel persistence skipped: %s", exc)
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
            composite_score=result.score,
            menu_path=result.menu_path,
            angle_intent=result.angle_intent,
        )
        # #774: the row's script_preview stops at 2,000 chars, so a drafted run could not be
        # rendered later without paying for generation again.
        from core.run_trace import write_full_script

        write_full_script(run_id, result.script)
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

    try:
        from core.spend_anomaly import maybe_toast_spend_anomaly

        total = 0.0
        cost = (result.features or {}).get("cost") or {}
        if isinstance(cost, dict):
            total = float(cost.get("total") or 0.0)
        trailing: list[float] = []
        try:
            from storage.repositories.content_runs import get_content_run_repository

            for rec in get_content_run_repository().list_for_channel(channel_id)[-20:]:
                try:
                    feats = json.loads(getattr(rec, "features_json", None) or "{}")
                    prev = (feats.get("cost") or {}).get("total")
                    if prev:
                        trailing.append(float(prev))
                except Exception as exc:
                    # One unreadable historical row must not cost us the median.
                    logger.debug("trailing cost row skipped: %s", exc)
                    continue
        except Exception as exc:
            logger.debug("trailing costs skipped: %s", exc)
        maybe_toast_spend_anomaly(total, trailing)
    except Exception as exc:
        logger.debug("spend anomaly skipped: %s", exc)


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
    vault_relevance_audit: list[dict[str, Any]] | None = None,
    source_urls: list[str] | None = None,
    relevance_corpus: str = "",
    menu_path: str | None = None,
    chapter_angles: list[str] | None = None,
) -> PipelineResult:
    """
    End-to-end content pipeline without CLI I/O.
    Pass discovery= to reuse a prior run_discovery() and avoid duplicate API calls.
    """
    channel_id = resolve_channel_id(channel_id or (discovery.channel_id if discovery else None))
    result = PipelineResult(topic=topic, score=0.0, signals={}, channel_id=channel_id)
    result.menu_path = menu_path
    from core.angle_intent import detect_angle_intent

    result.angle_intent = detect_angle_intent(topic)

    if discovery is None:
        from core.run_mode import guard_before_discovery

        guard_before_discovery()
        discovery = run_discovery(
            topic, variant_limit=variant_limit, channel_id=channel_id, brief=creative_brief
        )
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

    best_topic, best_score, best_signals = chosen_variant(discovery, variant_index)
    result.topic = best_topic
    result.score = best_score
    result.signals = best_signals

    # Run 78: every angle in one long video, one chapter each. The writer gets the seed
    # topic plus a directive listing the angles; chapters are located after the script
    # is final (see core/angle_chapters.py).
    angles = [str(a) for a in (chapter_angles or []) if str(a).strip()]
    content_topic = best_topic
    content_brief = creative_brief
    if len(angles) >= 2:
        from core.angle_chapters import multi_angle_directive

        content_topic = input_topic or topic
        content_brief = "\n\n".join(
            part for part in ((creative_brief or "").strip(), multi_angle_directive(angles)) if part
        )
        best_topic = f"{content_topic} - all {len(angles)} angles"
        result.topic = best_topic

    try:
        from core.cross_channel_dup import cross_channel_dup_block_reason

        why = cross_channel_dup_block_reason(best_topic, channel_id, key_facts=key_facts)
    except Exception as exc:
        logger.debug("cross-channel dup skipped: %s", exc)
        why = None
    if why:
        result.aborted = True
        result.abort_reason = why
        _finalize_run(
            channel_id=channel_id, input_topic=input_topic, result=result, discovery=discovery
        )
        return result

    preset = get_length_preset(length_choice)
    wr = _word_range(length_choice)
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info("Building research brief for: %s", best_topic)
    t_brief = time.perf_counter()
    research_brief = build_research_brief(
        content_topic,
        best_signals,
        channel_id=channel_id,
        seed_topic=input_topic,
    )
    result.timings["research_brief"] = time.perf_counter() - t_brief

    logger.info("Generating content package for: %s", best_topic)
    t_content = time.perf_counter()
    content = generate_content_package(
        topic=content_topic,
        signals=best_signals,
        word_range=wr,
        today=today,
        channel_id=channel_id,
        research_brief=research_brief,
        length_choice=length_choice,
        seed_topic=input_topic,
        creative_brief=content_brief,
        key_facts=key_facts or [],
        source_urls=source_urls or [],
        relevance_corpus=relevance_corpus,
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
        vault_relevance_audit=vault_relevance_audit,
    )
    if result.menu_path:
        result.features["menu_path"] = str(result.menu_path)
    if result.angle_intent:
        result.features["angle_intent"] = result.angle_intent
    if len(angles) >= 2:
        from core.angle_chapters import (
            chapter_lines,
            features_from_chapters,
            locate_chapters,
            trim_chapter_openers,
        )
        from core.chapters import _replace_chapter_lines
        from core.script_length import WORDS_PER_SECOND

        chapters = locate_chapters(result.script, angles)
        if chapters:
            # #770: each chapter is also cut into its own Short, so its first word cannot
            # point back at the chapter before it. Runs before TTS, so the cut inherits it.
            result.script, chapters, opener_notes = trim_chapter_openers(result.script, chapters)
            for note in opener_notes:
                logger.info("%s", note)
            if opener_notes:
                result.features["chapter_opener_notes"] = opener_notes
            spoken = count_spoken_words(result.script)
            result.features["all_angles"] = True
            result.features["angle_chapters"] = features_from_chapters(chapters)
            # Sentence-labelled chapters ("1:16 That's the whole story") become the angles.
            result.description = _replace_chapter_lines(
                result.description,
                "",
                chapter_lines(
                    chapters, duration=spoken / max(WORDS_PER_SECOND, 0.1), total_words=spoken
                ),
            )

    result.features["ungrounded_entities"] = content.get("ungrounded_entities") or []
    result.features["trade_warnings"] = content.get("trade_warnings") or []
    # Pillar 3 (Fact Engine): tier lint, pre-script conflicts, claim verifier.
    result.features["tier_warnings"] = content.get("tier_warnings") or []
    # Candidate 321: title claim check (generated after every other gate has passed).
    result.features["title_warnings"] = content.get("title_warnings") or []
    result.features["fact_conflicts"] = content.get("fact_conflicts") or []
    result.features["fact_conflicts_dropped"] = int(content.get("fact_conflicts_dropped") or 0)
    result.features["disputed"] = bool(content.get("disputed"))
    result.features["disputed_claims"] = list(content.get("disputed_claims") or [])
    result.features["lower_thirds"] = list(content.get("lower_thirds") or [])
    result.features["operator_quotes"] = list(content.get("operator_quotes") or [])
    result.features["operator_quote_used"] = bool(content.get("operator_quote_used"))
    result.features["persona_lint"] = list(content.get("persona_lint") or [])
    result.features["cta_summary"] = dict(content.get("cta_summary") or {})
    result.features["sentence_rhythm"] = list(content.get("sentence_rhythm") or [])
    if content.get("claim_verification"):
        result.features["claim_verification"] = content["claim_verification"]
    if content.get("quote_attribution"):
        result.features["quote_attribution"] = content["quote_attribution"]
    copy_content_package_features(content, result.features)

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
    result.features["projected_cost"] = estimate_run_cost(
        script=result.script, signals=best_signals, rendered=True, length_choice=length_choice
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
        lower_thirds=result.features.get("lower_thirds"),
        length_choice=length_choice,
    )
    result.mp3_path = mp3_path
    result.mp4_path = mp4_path

    # Recompute cost now that TTS/render actually ran (adds the TTS line).
    result.features["cost"] = estimate_run_cost(
        script=result.script, signals=best_signals, rendered=True, length_choice=length_choice
    )

    _finalize_run(
        channel_id=channel_id, input_topic=input_topic, result=result, discovery=discovery
    )
    if result.run_id and result.mp3_path and os.path.isfile(result.mp3_path + ".words.json"):
        try:
            from core.chapters import refine_run_chapters

            refined = refine_run_chapters(result.run_id, result.script, result.mp3_path)
            if refined is not None:
                result.description = refined
        except Exception as exc:
            logger.debug("verified chapters skipped for run %s: %s", result.run_id, exc)
    return result


def run_media_only(
    topic: str,
    script: str,
    *,
    channel_id: str | None = None,
    content_run_id: int | None = None,
    title: str | None = None,
    render_preset: str = "publish",
    lower_thirds: list[str] | None = None,
    force: bool = False,
    length_choice: str = "",
) -> tuple[str, str, str]:
    """Generate audio + video (+ publish thumbnail). Draft preset never updates upload media."""
    channel_id = resolve_channel_id(channel_id)
    display_title = title or topic
    render_preset = str(render_preset or "publish").strip().lower()
    if render_preset not in {"publish", "draft"}:
        raise ValueError(f"Unknown render preset: {render_preset}")
    progress = RenderProgress(enabled=is_render_progress_enabled())
    if lower_thirds is None and content_run_id:
        try:
            from core.run_features import load_features

            stored_labels = (load_features(content_run_id) or {}).get("lower_thirds")
            if isinstance(stored_labels, list):
                lower_thirds = [str(label) for label in stored_labels if str(label).strip()]
        except Exception as exc:
            logger.debug("stored lower thirds unavailable for run %s: %s", content_run_id, exc)

    progress.stage("Preparing output paths...")
    mp3_path, mp4_filename, mp4_path = media_paths_for_topic(topic, channel_id=channel_id)
    if render_preset == "draft":
        audio_stem, audio_ext = os.path.splitext(mp3_path)
        mp3_path = f"{audio_stem}_preview{audio_ext}"
        stem, ext = os.path.splitext(mp4_filename)
        mp4_filename = f"{stem}_preview{ext}"
        mp4_path = os.path.join(os.path.dirname(mp4_path), mp4_filename)
    progress.note(f"MP3 → {mp3_path}")
    progress.note(f"MP4 → {mp4_path}")

    from core.tts_char_cap import tts_char_cap_reason

    cap_reason = tts_char_cap_reason(script, force=force, length_choice=length_choice)
    if cap_reason:
        raise RuntimeError(cap_reason)

    from core.tts import voice_stage_label

    progress.stage(voice_stage_label(length_choice))
    t_tts = time.perf_counter()
    generate_audio(script, mp3_path, channel_id=channel_id, length_choice=length_choice)
    progress.note(f"TTS finished in {time.perf_counter() - t_tts:.1f}s")
    if content_run_id and os.path.isfile(mp3_path + ".words.json"):
        try:
            from core.chapters import refine_run_chapters

            if refine_run_chapters(content_run_id, script, mp3_path) is not None:
                progress.note("Extended chapters updated from real word timings")
        except Exception as exc:
            logger.debug("verified chapters skipped for run %s: %s", content_run_id, exc)
    try:
        from core.voice_consistency import voice_mix_warning

        mix = voice_mix_warning()
        if mix:
            logger.warning("%s", mix)
    except Exception as exc:
        logger.debug("voice consistency skipped: %s", exc)

    ffmpeg_commands: dict[str, list[str]] = {}
    ffmpeg_attempts: dict[str, list[list[str]]] = {}

    def _capture_ffmpeg_command(kind: str, argv: list[str]) -> None:
        label = str(kind)
        command = [str(part) for part in argv]
        if label.endswith("_attempt"):
            base = label.removesuffix("_attempt")
            ffmpeg_attempts.setdefault(base, []).append(command)
        elif label.endswith("_success"):
            ffmpeg_commands[label.removesuffix("_success")] = command
        else:
            # Compatibility for callers/tests using the original callback contract:
            # an unqualified command means the caller reports it as successful.
            ffmpeg_commands[label] = command

    _, background = render_vertical_video(
        mp3_path,
        topic,
        mp4_filename,
        script,
        channel_id,
        progress=progress,
        command_callback=_capture_ffmpeg_command,
        render_preset=render_preset,
        lower_thirds=lower_thirds,
    )
    technical_qc_data: dict[str, Any] = {}
    if os.path.isfile(mp4_path):
        try:
            from core.technical_qc import inspect_technical_qc, render_technical_qc

            expected_size = (480, 854) if render_preset == "draft" else (1080, 1920)
            technical_qc = inspect_technical_qc(mp4_path, expected_size=expected_size)
            technical_qc_data = technical_qc.to_dict()
            qc_line = render_technical_qc(technical_qc)
            progress.note(qc_line)
            if not technical_qc.passed:
                logger.warning("%s", qc_line)
        except Exception as exc:
            # The render already exists, but the acceptance guarantee was lost.
            logger.warning("technical QC skipped for %s: %s", mp4_path, exc)
    try:
        from core.first_frame import inspect_video
        from core.first_frame import render_check as first_frame_render_check
        from scripts.probe_sync import intro_offset_seconds

        offset = 0.0 if render_preset == "draft" else intro_offset_seconds(channel_id)
        frame_check = inspect_video(mp4_path, intro_offset=offset)
        if frame_check is not None:
            progress.note(first_frame_render_check(frame_check))
            if frame_check.black or frame_check.frozen:
                logger.warning("%s", first_frame_render_check(frame_check))
    except Exception as exc:
        logger.warning("first-frame check skipped: %s", exc)

    try:
        import tempfile as _tmp

        from core.caption_contrast import fill_hex_for_channel, inspect_caption_band
        from core.caption_contrast import render_check as contrast_render_check
        from scripts.probe_sync import grab_frame, intro_offset_seconds

        offset = 0.0 if render_preset == "draft" else intro_offset_seconds(channel_id)
        with _tmp.TemporaryDirectory() as tmp:
            still = os.path.join(tmp, "contrast.png")
            if grab_frame(mp4_path, max(0.0, offset) + 1.0, still):
                contrast = inspect_caption_band(still, fill_hex=fill_hex_for_channel(channel_id))
                progress.note(contrast_render_check(contrast))
                if not contrast.passed:
                    logger.warning("%s", contrast_render_check(contrast))
    except Exception as exc:
        logger.warning("caption contrast check skipped: %s", exc)

    thumb_path = ""
    thumb_provider: str | None = None
    thumb_safe_area: dict[str, Any] = {}
    thumbnail_candidates: list[dict[str, Any]] = []
    if render_preset == "publish" and os.getenv("THUMBNAIL_MODE", "auto").lower() != "off":
        progress.stage("Thumbnail (Flux or Pillow)...")
        t_thumb = time.perf_counter()
        from assets.flux_thumbnail import generate_dual_thumbnails, generate_thumbnail
        from core.output_paths import ensure_channel_output_dirs
        from core.thumbnail_pick import dual_thumbnail_enabled

        thumb_dir = ensure_channel_output_dirs(channel_id)["thumbnails"]
        grade_letter = None
        if content_run_id:
            try:
                from core.video_grade import grade_run

                graded = grade_run(content_run_id)
                grade_letter = graded.letter if graded else None
            except Exception as exc:
                logger.debug("thumbnail grade lookup skipped: %s", exc)
        if dual_thumbnail_enabled(channel_id) and content_run_id:
            thumbnail_candidates = generate_dual_thumbnails(
                topic,
                display_title,
                output_dir=thumb_dir,
                content_run_id=content_run_id,
                channel_id=channel_id,
                grade_letter=grade_letter,
            )
            for candidate in thumbnail_candidates:
                progress.note(
                    "Thumbnail "
                    f"{candidate.get('arm')}: {candidate.get('provider')} — "
                    f"{candidate.get('path')}"
                )
            progress.note("Dual thumbnails generated; operator pick required before publish")
            thumb = None
        else:
            if dual_thumbnail_enabled(channel_id) and not content_run_id:
                progress.note(
                    "Dual thumbnails skipped: run id unavailable; generated one safe thumbnail"
                )
            thumb = generate_thumbnail(
                topic,
                display_title,
                output_dir=thumb_dir,
                content_run_id=content_run_id,
                channel_id=channel_id,
                grade_letter=grade_letter,
            )
        if thumb is not None and thumb.path:
            thumb_path = thumb.path
            thumb_provider = thumb.provider or ""
            from assets.flux_thumbnail import list_channel_thumbnails

            total = len(list_channel_thumbnails(thumb_dir))
            progress.note(f"{thumb.detail or 'thumbnail'} — {thumb_path}")
            progress.note(f"Thumbnails in folder: {total} ({thumb_dir})")
            try:
                from core.thumbnail_safe_area import inspect_thumbnail
                from core.thumbnail_safe_area import render_check as thumb_render_check

                thumb_check = inspect_thumbnail(thumb_path)
                thumb_safe_area = {
                    "bottom_quiet": thumb_check.bottom_quiet,
                    "bottom_detail": thumb_check.bottom_detail,
                    "detail": thumb_check.detail,
                    "method": "bottom_20_percent_edge_density",
                }
                progress.note(thumb_render_check(thumb_check))
            except Exception as exc:
                logger.warning("Thumbnail safe-area check failed for %s: %s", thumb_path, exc)
        elif thumb is not None:
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

    if content_run_id and render_preset == "publish":
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

            cost = merge_render_cost(
                (load_features(content_run_id) or {}).get("cost"),
                script,
                thumbnail_provider=thumb_provider,
                tts_cached=(1.0 if last_tts_was_piper_mix() else last_tts_cache_fraction()),
                length_choice=length_choice,
            )
            if thumbnail_candidates:
                cost["thumbnail"] = round(
                    sum(
                        float((candidate.get("cost") or {}).get("known_incurred_usd") or 0)
                        for candidate in thumbnail_candidates
                    ),
                    4,
                )
                cost["total"] = round(
                    sum(float(value) for key, value in cost.items() if key != "total"),
                    4,
                )
            from core.tts_char_cap import tts_char_count

            merge_features(
                content_run_id,
                {
                    "cost": cost,
                    "tts_cached": (1.0 if last_tts_was_piper_mix() else last_tts_cache_fraction()),
                    "tts_char_count": tts_char_count(script),
                    "tts_force": bool(force),
                    "tts_length_choice": length_choice or "",
                    **_tts_forecast_features(),
                    "thumbnail_provider": thumb_provider or "",
                    "thumbnail_safe_area": thumb_safe_area,
                    "thumbnail_candidates": thumbnail_candidates,
                    **({"technical_qc": technical_qc_data} if technical_qc_data else {}),
                },
            )
            update_trace(
                content_run_id,
                {
                    "status": "rendered",
                    "cost": cost,
                    "tts_cached": (1.0 if last_tts_was_piper_mix() else last_tts_cache_fraction()),
                    "thumbnail_provider": thumb_provider or "",
                    "thumbnail_safe_area": thumb_safe_area,
                    "thumbnail_candidates": thumbnail_candidates,
                    **({"technical_qc": technical_qc_data} if technical_qc_data else {}),
                    **(
                        {"ffmpeg_command": ffmpeg_commands["primary"]}
                        if ffmpeg_commands.get("primary")
                        else {}
                    ),
                    **(
                        {"ffmpeg_intro_command": ffmpeg_commands["intro"]}
                        if ffmpeg_commands.get("intro")
                        else {}
                    ),
                    **(
                        {"ffmpeg_outro_command": ffmpeg_commands["outro"]}
                        if ffmpeg_commands.get("outro")
                        else {}
                    ),
                    **({"ffmpeg_attempted_commands": ffmpeg_attempts} if ffmpeg_attempts else {}),
                },
            )
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
    try:
        from core.win_notify import notify_ffmpeg_done

        notify_ffmpeg_done(mp4_path)
    except Exception as exc:
        logger.debug("ffmpeg toast skipped: %s", exc)
    return mp3_path, mp4_path, thumb_path
