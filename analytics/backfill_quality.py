"""Backfill content_runs.quality_json for historical runs (#823).

Three waves added measurements that have never produced a single data point,
because no run has been generated since they landed. Measured on `tapin`
(2026-09-20, 87 runs): `hedge_density` 0 rows (#800, wave 26), `grade_score` /
`grade_components` 0 (#808, wave 29), `style_recurrence_*` 0 (#803, wave 29).
`script_preview` is on all 87 rows, so every script-derived field is
recomputable offline and the archive can carry them today rather than in
months.

`angle_spread` / `angle_scores` (#807) are deliberately NOT here: the backlog
records that traces never stored the five variants, so there is nothing to
recompute from. Those need new runs.

    py -m scripts.ops backfill-quality --channel tapin           # dry run
    py -m scripts.ops backfill-quality --channel tapin --apply

**As-of window.** `build_quality` calls `evaluate_authenticity`, which compares
a script against the 12 most recent runs *as of now*. Scoring run 12 against
runs that did not exist when it was written would poison exactly the archive
#808 exists to protect, so each run is compared only against runs with a lower
id, passed down through `build_quality(recent=)`. Early runs get a thin or
empty baseline; that is the truthful answer for them, not a defect.

**Carry forward what this does not own.** `analytics/backfill_features.py`
records the hazard first-hand: a `--force` rebuild silently destroyed the cost
ledger until it copied unknown keys across. Here the keys `build_quality` never
produces are the post-render thumbnail score and anything a previous wave
merged in, so existing keys win unless this module actually recomputed them.

Dry run by default. It writes to the operator's real archive.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("analytics.backfill_quality")

# Keys `build_quality` owns and may legitimately overwrite. Anything else on an
# existing row is carried forward untouched.
_OWNED_PREFIXES = (
    "hook_",
    "authenticity_",
    "style_recurrence_",
    "grade_",
    "ungrounded_",
    "numeric_outliers",
    "hedge_density",
    "word_count",
    "min_words",
    "max_words",
    "quality_version",
)

_RECENT_WINDOW = 12


def _as_of_window(rows: list[Any], run_id: int, *, window: int = _RECENT_WINDOW) -> list[str]:
    """The scripts that existed before `run_id`, newest first.

    Mirrors `authenticity._recent_scripts`' ordering and cap, but bounded by id
    rather than by "now" — the whole point of the as-of rule.
    """
    earlier = [r for r in rows if r.id < run_id and (r.script_preview or "").strip()]
    earlier.sort(key=lambda r: r.id, reverse=True)
    return [r.script_preview for r in earlier[:window]]


def _owned(key: str) -> bool:
    return any(key.startswith(prefix) for prefix in _OWNED_PREFIXES)


def backfill_channel(
    channel_id: str, *, apply: bool = False, force: bool = False
) -> dict[str, int]:
    """Recompute script-derived quality for runs missing it. Never raises per-run."""
    from core.run_quality import build_quality
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    rows = sorted(repo.list_for_channel(channel_id), key=lambda r: r.id)
    tally = {"runs": len(rows), "would_update": 0, "updated": 0, "skipped": 0, "failed": 0}

    for run in rows:
        script = (run.script_preview or "").strip()
        if not script:
            tally["skipped"] += 1
            continue
        try:
            existing = json.loads(run.quality_json or "{}")
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, TypeError):
            existing = {}
        if existing.get("grade_score") is not None and not force:
            tally["skipped"] += 1
            continue

        try:
            features = json.loads(run.features_json or "{}")
            if not isinstance(features, dict):
                features = {}
        except (json.JSONDecodeError, TypeError):
            features = {}

        try:
            rebuilt = build_quality(
                script=script,
                channel_id=channel_id,
                features=features,
                exclude_run_id=run.id,
                composite_score=float(run.composite_score or 0.0),
                # The as-of rule: only what existed before this run.
                recent=_as_of_window(rows, run.id),
            )
        except Exception as exc:
            logger.debug("backfill skipped run %s: %s", run.id, exc)
            tally["failed"] += 1
            continue

        merged = dict(existing)
        for key, value in rebuilt.items():
            # An existing value the rebuilder does not own stays put: the
            # thumbnail score arrives post-render and cannot be recomputed here.
            if key in merged and not _owned(key):
                continue
            merged[key] = value
        # Re-stamp the grade against the merged dict so a carried-forward
        # thumbnail is inside the snapshot, exactly as `merge_quality` does.
        try:
            from core.run_quality import snapshot_grade

            merged.update(snapshot_grade(merged, float(run.composite_score or 0.0)))
        except Exception as exc:
            logger.debug("backfill grade re-stamp skipped for run %s: %s", run.id, exc)
        # #808's recorded grade means "the number this run's own rubric
        # produced", which is what lets calibration report drift against
        # today's code. A backfilled grade was produced by today's code by
        # definition, so it must not be counted as evidence the rubric held.
        merged["grade_backfilled"] = True

        tally["would_update"] += 1
        if apply:
            repo.update(run.id, {"quality_json": json.dumps(merged)})
            tally["updated"] += 1

    return tally


def render(tally: dict[str, int], channel_id: str, *, apply: bool) -> str:
    verb = "Updated" if apply else "Would update"
    count = tally["updated"] if apply else tally["would_update"]
    lines = [
        f"Quality backfill - {channel_id}",
        f"  {tally['runs']} run(s); {verb} {count}; "
        f"skipped {tally['skipped']}; failed {tally['failed']}",
    ]
    if not apply:
        lines.append("  Dry run - nothing written. Re-run with --apply.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill content_runs.quality_json (#823)")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--apply", action="store_true", help="Write (default is a dry run)")
    parser.add_argument(
        "--force", action="store_true", help="Recompute rows that already have a grade"
    )
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    tally = backfill_channel(channel_id, apply=bool(args.apply), force=bool(args.force))
    print(render(tally, channel_id, apply=bool(args.apply)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
