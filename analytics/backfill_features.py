"""Backfill content_runs.features_json for historical runs.

Reconstructs the engagement-independent features (domain, angle, title_structure,
hook, format, word_count) from each run's stored title/script/timings so the weekly
report works on existing history immediately. Brief-derived fields (controversy,
sentiment, title_direction, suggested_hook) and key-facts are left blank — they
weren't recorded pre-feature-store and cannot be reconstructed.

    py -m analytics.backfill_features --channel tapin
    py -m analytics.backfill_features --channel tapin --force   # recompute all
"""

from __future__ import annotations

import argparse
import json

from config.channels import resolve_channel_id


def _length_choice_from_timings(timings_json: str) -> str:
    try:
        return str((json.loads(timings_json or "{}")).get("length_preset") or "2")
    except (json.JSONDecodeError, TypeError):
        return "2"


def backfill_channel(channel_id: str, *, force: bool = False) -> int:
    """Write reconstructed features for runs missing them. Returns count updated."""
    from core.run_features import build_features
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    runs = repo.list_for_channel(channel_id)
    updated = 0
    for run in runs:
        try:
            existing = json.loads(run.features_json or "{}")
        except (json.JSONDecodeError, TypeError):
            existing = {}
        if existing and not force:
            continue

        topic = run.selected_topic or run.input_topic or ""
        features = build_features(
            topic=topic,
            channel_id=channel_id,
            content_package={
                "title": run.title,
                "script": run.script_preview,
            },
            research_brief=None,
            length_choice=_length_choice_from_timings(run.timings_json),
            key_facts=None,
            fact_source="backfilled",
        )
        # `build_features` does not produce `cost` (the pipeline adds it separately), so
        # a --force rebuild would silently destroy the cost ledger for every run it
        # touched. Carry forward anything build_features doesn't own.
        for key, value in existing.items():
            if key not in features:
                features[key] = value

        repo.update(run.id, {"features_json": json.dumps(features)})
        updated += 1
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill content_runs.features_json")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--force", action="store_true", help="Recompute even if present")
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    n = backfill_channel(channel_id, force=args.force)
    print(f"Backfilled features for {n} run(s) on {channel_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
