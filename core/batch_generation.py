"""Batch generation — N ideas → N draft scripts in one unattended pass.

Roadmap "Efficiency & integrations": feeds A/B and volume-with-variation
without babysitting the interactive flow. Strictly headless (no input()) and
render-free: each topic runs discovery → best variant → recommended length →
script/title/description, then saves a review-ready draft folder under
output/<channel>/drafts/<timestamp>-<slug>/ with the same quality checks the
interactive flow shows (hook score, authenticity verdict, grounding flags).

Nothing is rendered or published — drafts are cheap (LLM + signals only), so
an unattended batch can't burn TTS credits or trip the cadence guardrail.

    py -m core.batch_generation --channel tapin --count 3
    py -m core.batch_generation --channel moneywise "Fed rate cut" "CPI print"
    py -m core.batch_generation --file ideas.txt        # one topic per line
    py -m scripts.ops batch-drafts --channel tapin --count 3

Topic sources, in priority order: explicit CLI topics → --file lines →
best-bet recommendations for the channel.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from core.logging import get_logger

logger = get_logger("core.batch_generation")


@dataclass
class DraftOutcome:
    topic: str
    ok: bool = False
    title: str = ""
    variant: str = ""
    score: float = 0.0
    hook_score: int | None = None
    hook_verdict: str = ""
    authenticity_verdict: str = ""
    experiment_arm: str = ""
    ungrounded: list[str] = field(default_factory=list)
    unsupported_claims: int = 0
    fact_conflicts: int = 0
    run_id: int | None = None
    path: str = ""
    error: str = ""
    seconds: float = 0.0
    reused: bool = False  # #760 - an unreviewed draft for this topic already existed


def _slug(topic: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "draft"


def _drafts_dir(channel_id: str) -> str:
    from core.output_paths import channel_output_root

    path = os.path.join(channel_output_root(channel_id), "drafts")
    os.makedirs(path, exist_ok=True)
    return path


_REUSE_DAYS = 3


def unreviewed_draft(channel_id: str, topic: str, *, max_age_days: float = _REUSE_DAYS):
    """(folder, meta) of a recent draft for this topic nobody has reviewed, else None.

    A second batch the same week used to pay for discovery and the script again for a
    topic already waiting in `ops batch-review` (#760).
    """
    key = " ".join((topic or "").lower().split())
    try:
        root = _drafts_dir(channel_id)
        names = sorted(os.listdir(root), reverse=True)
    except OSError:
        return None
    for name in names:
        folder = os.path.join(root, name)
        try:
            with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or meta.get("review"):
            continue
        if " ".join(str(meta.get("topic") or "").lower().split()) != key:
            continue
        try:
            age = datetime.now() - datetime.fromisoformat(str(meta.get("created_at")))
        except (TypeError, ValueError):
            continue
        if age.total_seconds() <= max_age_days * 86400:
            return folder, meta
    return None


def collect_topics(
    channel_id: str,
    topics: list[str] | None = None,
    file: str | None = None,
    count: int = 3,
) -> list[str]:
    """Explicit topics → file lines → best bets, capped at `count` for implicit sources."""
    if topics:
        return [t.strip() for t in topics if t.strip()]
    if file:
        with open(file, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        return lines
    try:
        from core.best_bet import get_best_bets

        return [b.topic for b in get_best_bets(channel_id, count)]
    except Exception as exc:
        logger.warning("No topics given and best bets unavailable: %s", exc)
        return []


def _length_choice(channel_id: str, topic: str) -> str:
    try:
        from core.length_recommender import get_recommended_length

        return get_recommended_length(channel_id, topic).length_choice
    except Exception:
        return "2"


def generate_draft(
    topic: str, channel_id: str, *, key_facts: list[str] | None = None
) -> DraftOutcome:
    """One headless draft: discovery → best variant → script → saved folder.

    ``key_facts`` (optional) are shared operator ground truth applied to this
    topic — same ``run_pipeline(key_facts=)`` path as ``auto_generate --facts-file``.
    """
    from core.pipeline import run_discovery, run_pipeline

    out = DraftOutcome(topic=topic)
    started = time.time()

    discovery = run_discovery(topic, channel_id=channel_id)
    if not discovery.evaluated:
        out.error = "discovery returned no scored variants"
        return out
    # The one ranking rule — this used to `max` on the displayed score alone and
    # so picked arbitrarily whenever the composites tied, which is every run.
    from core.pipeline import best_variant_index

    variant_index = best_variant_index(
        discovery.evaluated, discovery.raw_scores, discovery.angle_scores
    )
    best_topic, best_score, best_signals = discovery.evaluated[variant_index]
    out.variant, out.score = best_topic, float(best_score or 0)

    # Active script-lever A/B experiment: the least-used arm's directive
    # shapes this draft (thumbnail levers apply at render, not here).
    experiment: tuple[str, str, str] | None = None
    try:
        from core.experiments import next_arm

        experiment = next_arm(channel_id, kind="script")
    except Exception as exc:
        logger.debug("next_arm skipped: %s", exc)

    from core.fact_selection import select_headless_facts
    from core.vault_relevance import build_relevance_corpus

    corpus = build_relevance_corpus(best_signals, operator_facts=key_facts or [])
    packed = select_headless_facts(key_facts, topic=topic, corpus=corpus) if key_facts else None
    length_choice = _length_choice(channel_id, best_topic)
    result = run_pipeline(
        topic,
        discovery=discovery,
        variant_index=variant_index,
        length_choice=length_choice,
        proceed_video=False,
        channel_id=channel_id,
        creative_brief=experiment[2] if experiment else "",
        key_facts=packed,
        relevance_corpus=corpus,
    )
    if result.aborted or not (result.script or "").strip():
        out.error = result.abort_reason or "pipeline produced no script"
        return out
    out.title, out.run_id = result.title, result.run_id

    if experiment:
        lever, arm, _ = experiment
        out.experiment_arm = f"{lever}={arm}"
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, lever, arm)
        except Exception as exc:
            logger.debug("record_assignment skipped: %s", exc)

    # Same quality surface the interactive flow prints, persisted instead.
    try:
        from core.hook_score import score_script_hook

        hook = score_script_hook(result.script)
        out.hook_score, out.hook_verdict = hook.score, hook.verdict
    except Exception as exc:
        logger.debug("score_script_hook skipped: %s", exc)
    fact_count = 0
    try:
        from core.fact_enrichment import _fact_line_count, enrich_facts

        fact_count = _fact_line_count(
            enrich_facts(best_topic, best_signals, channel_id=channel_id, seed_topic=topic)
        )
    except Exception as exc:
        logger.debug("_fact_line_count skipped: %s", exc)
    try:
        from core.authenticity import evaluate_authenticity

        out.authenticity_verdict = evaluate_authenticity(
            result.script, channel_id, fact_count=fact_count, exclude_run_id=result.run_id
        ).verdict
    except Exception as exc:
        logger.debug("evaluate_authenticity skipped: %s", exc)
    out.ungrounded = list(result.features.get("ungrounded_entities") or [])
    out.unsupported_claims = len(
        (result.features.get("claim_verification") or {}).get("unsupported") or []
    )
    out.fact_conflicts = len(result.features.get("fact_conflicts") or [])

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = os.path.join(_drafts_dir(channel_id), f"{stamp}-{_slug(best_topic)}")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
        f.write(f"# {result.title or best_topic}\n\n")
        f.write(f"**Topic:** {topic}\n**Angle:** {best_topic} (score {best_score})\n\n")
        f.write("## Script\n\n")
        f.write(result.script.strip() + "\n\n")
        f.write("## Description\n\n")
        f.write((result.description or "").strip() + "\n")
        if result.tags:
            f.write("\n## Tags\n\n" + ", ".join(result.tags) + "\n")
    meta = {
        "topic": topic,
        "variant": best_topic,
        "variant_score": best_score,
        "title": result.title,
        "run_id": result.run_id,
        "channel_id": channel_id,
        "length_choice": length_choice,
        "hook_score": out.hook_score,
        "hook_verdict": out.hook_verdict,
        "authenticity_verdict": out.authenticity_verdict,
        "fact_count": fact_count,
        "ungrounded_entities": out.ungrounded,
        "tier_warnings": result.features.get("tier_warnings") or [],
        "fact_conflicts": result.features.get("fact_conflicts") or [],
        "claim_verification": result.features.get("claim_verification"),
        "experiment": out.experiment_arm or None,
        "cost": result.features.get("cost"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)

    out.path, out.ok, out.seconds = folder, True, round(time.time() - started, 1)
    return out


def run_batch(
    channel_id: str, topics: list[str], *, key_facts: list[str] | None = None
) -> list[DraftOutcome]:
    """Generate a draft per topic; one failure never kills the batch.

    ``key_facts`` apply to every topic (one overnight digest, N drafts).
    """
    from apis.register_signals import franchise_batch_cache

    outcomes: list[DraftOutcome] = []
    with franchise_batch_cache(topics, channel_id=channel_id):
        for i, topic in enumerate(topics, 1):
            logger.info("Batch draft %d/%d: %s", i, len(topics), topic)
            existing = unreviewed_draft(channel_id, topic)
            if existing is not None:
                folder, meta = existing
                outcomes.append(
                    DraftOutcome(
                        topic=topic,
                        ok=True,
                        reused=True,
                        title=str(meta.get("title") or ""),
                        variant=str(meta.get("variant") or ""),
                        run_id=meta.get("run_id"),
                        path=folder,
                    )
                )
                continue
            try:
                outcomes.append(generate_draft(topic, channel_id, key_facts=key_facts))
            except Exception as exc:
                logger.warning("Draft failed for %r: %s", topic, exc)
                outcomes.append(DraftOutcome(topic=topic, error=str(exc)))
    try:
        from core.pipeline import finalize_run_observability

        finalize_run_observability()
    except Exception as exc:
        logger.debug("finalize_run_observability skipped: %s", exc)
    try:
        from core.events import emit_event

        emit_event(
            "batch_completed",
            {
                "channel_id": channel_id,
                "requested": len(topics),
                "saved": sum(1 for o in outcomes if o.ok),
                "drafts": [
                    {"topic": o.topic, "ok": o.ok, "title": o.title, "path": o.path}
                    for o in outcomes
                ],
            },
        )
    except Exception as exc:
        logger.debug("batch_completed event not emitted: %s", exc)
    return outcomes


def render_summary(outcomes: list[DraftOutcome]) -> str:
    lines = ["", "Batch drafts", "=" * 40]
    for o in outcomes:
        if o.reused:
            lines.append(f"  KEEP {o.title or o.topic} - draft already waiting for review")
            lines.append(f"       {o.path}")
        elif o.ok:
            hook = f"hook {o.hook_score}" if o.hook_score is not None else "hook n/a"
            auth = o.authenticity_verdict or "n/a"
            flags = f", {len(o.ungrounded)} ungrounded" if o.ungrounded else ""
            if o.unsupported_claims:
                flags += f", {o.unsupported_claims} unsupported claim(s)"
            if o.fact_conflicts:
                flags += f", {o.fact_conflicts} fact conflict(s)"
            arm = f", A/B {o.experiment_arm}" if o.experiment_arm else ""
            lines.append(f"  OK   {o.title or o.variant}")
            lines.append(f"       {hook} ({o.hook_verdict}), authenticity {auth}{flags}{arm}")
            lines.append(f"       {o.path}  [{o.seconds:.0f}s]")
        else:
            lines.append(f"  FAIL {o.topic} — {o.error}")
    made = sum(1 for o in outcomes if o.ok)
    lines.append(f"  {made}/{len(outcomes)} drafts saved")
    if made:
        lines.append("  Review them: py -m scripts.ops batch-review")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="N ideas -> N draft scripts, unattended")
    parser.add_argument("topics", nargs="*", help="Topics (default: best bets)")
    parser.add_argument("--channel", default="tapin", help="Channel id (default: tapin)")
    parser.add_argument("--file", default=None, help="File with one topic per line")
    parser.add_argument(
        "--count", type=int, default=3, help="How many best-bet topics when none given"
    )
    parser.add_argument(
        "--facts-file",
        default="",
        help="Operator key facts (paste-block file) applied to every draft in the batch",
    )
    args = parser.parse_args(argv)

    from core.run_mode import CostModeBlocked, apply_and_guard

    try:
        apply_and_guard()
    except CostModeBlocked as exc:
        print(f"  {exc}")
        return 2

    from core.operator_facts import load_key_facts

    key_facts = load_key_facts(args.facts_file)
    topics = collect_topics(args.channel, args.topics, args.file, args.count)
    if not topics:
        print("No topics to draft (give topics, --file, or record analytics for best bets).")
        return 1
    outcomes = run_batch(args.channel, topics, key_facts=key_facts or None)
    print(render_summary(outcomes))
    return 0 if any(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
