"""Backfill editorial angle scores from the archive's own variant texts (#836).

`#819` asks whether the angle score predicts engagement, and wave 32 started
persisting it - which left the question waiting on new runs. But every run row
already stores its angle texts in `variants_json` (`[text, composite]` pairs) and the
chosen one in `selected_topic`, so the score can be recomputed offline with
`angle_ranker.rank_angles(..., llm_judge=False)` (deterministic, no network).

Approximate by construction: the live pipeline seeds the ranker with the operator's
typed brief as well as the topic and may blend in a cheap-model judge; neither was
persisted. So every value this writes is stamped `angle_backfilled`, and calibration
says how many of its n are approximations.

    py -m scripts.ops backfill-angles --channel tapin           # dry run
    py -m scripts.ops backfill-angles --channel tapin --apply
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("analytics.backfill_angles")


def _load(raw: Any) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _variant_texts(raw: Any) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    texts: list[str] = []
    for item in data if isinstance(data, list) else []:
        text = item[0] if isinstance(item, list | tuple) and item else item
        if isinstance(text, str) and text.strip() and text not in texts:
            texts.append(text)
    return texts


def backfill_channel(
    channel_id: str, *, apply: bool = False, force: bool = False
) -> dict[str, int]:
    """Score each run's stored angles offline. Never raises per run."""
    from core.angle_ranker import rank_angles
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    rows = sorted(repo.list_for_channel(channel_id), key=lambda r: r.id)
    tally = {"runs": len(rows), "would_update": 0, "updated": 0, "skipped": 0, "failed": 0}

    for run in rows:
        texts = _variant_texts(getattr(run, "variants_json", "[]"))
        selected = (getattr(run, "selected_topic", "") or "").strip()
        if len(texts) < 2 or selected not in texts:
            tally["skipped"] += 1
            continue
        quality = _load(run.quality_json)
        features = _load(run.features_json)
        if quality.get("angle_score") is not None and not force:
            tally["skipped"] += 1
            continue
        try:
            scores = rank_angles(texts, seed_topic=run.input_topic or selected, llm_judge=False)
        except Exception as exc:
            logger.debug("angle backfill skipped run %s: %s", run.id, exc)
            tally["failed"] += 1
            continue
        chosen = scores.get(selected)
        if not isinstance(chosen, int | float):
            tally["skipped"] += 1
            continue
        features["angle_scores"] = {k: float(v) for k, v in scores.items()}
        features["angle_score"] = float(chosen)
        quality["angle_score"] = float(chosen)
        quality["angle_backfilled"] = True

        tally["would_update"] += 1
        if apply:
            repo.update(
                run.id,
                {"features_json": json.dumps(features), "quality_json": json.dumps(quality)},
            )
            tally["updated"] += 1
    return tally


def render(tally: dict[str, int], channel_id: str, *, apply: bool) -> str:
    verb = "Updated" if apply else "Would update"
    count = tally["updated"] if apply else tally["would_update"]
    lines = [
        f"Angle-score backfill - {channel_id}",
        f"  {tally['runs']} run(s); {verb} {count}; "
        f"skipped {tally['skipped']}; failed {tally['failed']}",
        "  Values are approximate (no operator brief, no LLM judge) and stamped angle_backfilled.",
    ]
    if not apply:
        lines.append("  Dry run - nothing written. Re-run with --apply.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill angle scores from variants_json (#836)")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--apply", action="store_true", help="Write (default is a dry run)")
    parser.add_argument(
        "--force", action="store_true", help="Recompute rows that already carry an angle score"
    )
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    tally = backfill_channel(channel_id, apply=bool(args.apply), force=bool(args.force))
    print(render(tally, channel_id, apply=bool(args.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
