"""Repair `content_runs.features_json.cost` for runs that rendered before the fix.

Both operator render paths finalized a run *before* rendering it, so the stored cost
kept `tts: 0.0` forever even though the video was synthesized, rendered and published.
`core/unit_economics.py` computes contribution margin from `features_json.cost.total`,
so every historical margin is overstated — `ops economics` reported 20 uploads at
$0.32 total when TTS alone was worth roughly $5 of that.

`core/pipeline.run_media_only` now persists the render lines going forward; this repairs
what is already on disk so the two eras are comparable.

    py -m analytics.backfill_cost --channel tapin --dry-run
    py -m analytics.backfill_cost --channel tapin

Only touches runs that actually rendered (`rendered`/`scheduled`/`published`) and whose
cost has no TTS line, so it is idempotent and never rewrites a draft. Merges into the
`cost` block alone — the rest of `features_json` is left untouched.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from config.channels import resolve_channel_id

# A run only incurs TTS once it renders.
RENDERED_STATUSES = frozenset({"rendered", "scheduled", "published", "uploaded"})

# `script_preview` is truncated at 2000 chars by core/run_recorder.py, so a preview at
# exactly the cap tells us nothing about the real length; estimate from word_count then.
_PREVIEW_CAP = 2000
# Measured on run 64: 191 words / 1135 chars.
_CHARS_PER_WORD = 5.9


def _load(raw: str | None) -> dict[str, Any]:
    try:
        loaded = json.loads(raw or "{}")
        return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def script_chars(run: Any, features: dict[str, Any]) -> tuple[int, bool]:
    """(character count, was_estimated) for a historical run."""
    preview = getattr(run, "script_preview", "") or ""
    if 0 < len(preview) < _PREVIEW_CAP:
        return len(preview), False  # full script survived in the preview

    words = features.get("word_count")
    try:
        words = int(words or 0)
    except (TypeError, ValueError):
        words = 0
    if words > 0:
        return int(words * _CHARS_PER_WORD), True
    return len(preview), bool(preview)


def plan_channel(channel_id: str, *, force: bool = False) -> list[dict[str, Any]]:
    """Rows needing repair, with before/after costs. Read-only."""
    from core.cost_meter import merge_render_cost
    from storage.repositories.content_runs import get_content_run_repository

    rows: list[dict[str, Any]] = []
    for run in get_content_run_repository().list_for_channel(channel_id):
        if str(run.status or "") not in RENDERED_STATUSES:
            continue
        features = _load(getattr(run, "features_json", ""))
        cost = features.get("cost") or {}
        if cost.get("tts") and not force:
            continue  # already repaired

        chars, estimated = script_chars(run, features)
        if chars <= 0:
            continue  # nothing to price from

        updated = merge_render_cost(cost, "x" * chars)
        rows.append(
            {
                "run_id": run.id,
                "title": (run.title or run.selected_topic or "")[:48],
                "status": run.status,
                "chars": chars,
                "estimated": estimated,
                # Runs that predate cost metering have no llm/apify/web_search lines at
                # all. Adding TTS makes them far more accurate but still not complete,
                # so the total is flagged rather than presented as fully loaded.
                "partial": not cost,
                "before": float(cost.get("total") or 0.0),
                "after": updated["total"],
                "cost": updated,
                "features": features,
            }
        )
    return rows


def apply_rows(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Write the repaired cost. Returns (rows updated, traces updated)."""
    from core.run_features import merge_features
    from core.run_trace import update_trace

    applied = 0
    traces = 0
    for row in rows:
        payload: dict[str, Any] = {"cost": row["cost"]}
        if row["estimated"]:
            # An estimate must be labelled as one.
            payload["cost_estimated"] = True
        if row["partial"]:
            payload["cost_partial"] = True
        merge_features(row["run_id"], payload)
        applied += 1
        # The trace carries the same pre-render lie ("drafted", pre-render cost), and
        # it is what `ops traces` reads. Fix both or the two views disagree.
        if update_trace(row["run_id"], {"status": "rendered", "cost": row["cost"]}):
            traces += 1
    return applied, traces


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill missing TTS cost on rendered runs")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--dry-run", action="store_true", help="Show changes, write nothing")
    parser.add_argument("--force", action="store_true", help="Recompute even if tts is present")
    args = parser.parse_args(argv)

    channel_id = resolve_channel_id(args.channel)
    rows = plan_channel(channel_id, force=args.force)
    if not rows:
        print(f"No rendered runs need a cost backfill on {channel_id}.")
        return 0

    print(f"\n  {'run':>5}  {'status':10} {'chars':>6}  {'before':>8}  {'after':>8}  title")
    print("  " + "-" * 74)
    for row in rows:
        flag = "~" if row["estimated"] else " "
        flag += "p" if row["partial"] else " "
        print(
            f"  {row['run_id']:>5}  {row['status']:10} {row['chars']:>6}{flag}"
            f" ${row['before']:>7.4f}  ${row['after']:>7.4f}  {row['title']}"
        )
    before = sum(r["before"] for r in rows)
    after = sum(r["after"] for r in rows)
    n_partial = sum(1 for r in rows if r["partial"])
    print("  " + "-" * 74)
    print(f"  {len(rows)} run(s): ${before:.4f} -> ${after:.4f}  (+${after - before:.4f})")
    print("  ~ = chars estimated from word_count (script_preview was truncated at 2000)")
    if n_partial:
        print(
            f"  p = {n_partial} run(s) predate cost metering: TTS added, but they still "
            "have no llm/apify/web_search lines (flagged cost_partial)"
        )

    if args.dry_run:
        print("\n  Dry run — nothing written. Re-run without --dry-run to apply.\n")
        return 0

    applied, traces = apply_rows(rows)
    print(f"\n  Updated {applied} run(s) on {channel_id} ({traces} trace file(s) corrected).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
