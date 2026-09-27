"""Every derived field that history can be re-filled with, in one registry (#870).

Four verbs grew one at a time - `backfill-features`, `backfill-cost`, `backfill-quality`,
`backfill-angles` - each with its own rule for "this row is stale" and its own default:
two wrote unless told not to, two only wrote with `--apply`. A rubric change could leave
history half re-stamped. Each entry here names what it fills, the version it stamps and
its stale rule; `ops backfill` lists how far behind each is, and recomputes only the
stale rows, as a dry run unless `--apply`.

Order is the dependency order: quality reads features, and cost reads the rendered
status features record.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.backfills")


@dataclass(frozen=True)
class Backfill:
    name: str
    fills: str
    version: Callable[[], str]
    stale: Callable[[Any], bool]
    run: Callable[[str, bool, bool], dict[str, int]]  # (channel, apply, force) -> tally


def _load(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _rows(channel_id: str) -> list[Any]:
    from storage.repositories.content_runs import get_content_run_repository

    return sorted(
        get_content_run_repository().list_for_channel(channel_id) or [], key=lambda r: r.id
    )


def _tally(runs: int, stale: int, would: int, updated: int) -> dict[str, int]:
    return {"runs": runs, "stale": stale, "would_update": would, "updated": updated}


# ---- features: missing only. A rebuild from `script_preview` has no research brief, so
# it would overwrite real fields with blanks; a newer FEATURE_VERSION is not a reason.


def _features_version() -> str:
    from core.run_features import FEATURE_VERSION

    return FEATURE_VERSION


def _features_stale(run: Any) -> bool:
    return not _load(getattr(run, "features_json", ""))


def _features_run(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    from analytics.backfill_features import backfill_channel

    rows = _rows(channel_id)
    stale = sum(1 for r in rows if _features_stale(r))
    count = backfill_channel(channel_id, force=force, apply=apply)
    return _tally(len(rows), stale, count, count if apply else 0)


# ---- cost: a rendered run with no TTS line (renders finalized before the TTS cost).


def _cost_stale(run: Any) -> bool:
    from analytics.backfill_cost import RENDERED_STATUSES

    if str(getattr(run, "status", "") or "") not in RENDERED_STATUSES:
        return False
    cost = _load(getattr(run, "features_json", "")).get("cost") or {}
    return not (isinstance(cost, dict) and cost.get("tts"))


def _cost_run(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    from analytics.backfill_cost import apply_rows, plan_channel

    planned = plan_channel(channel_id, force=force)
    updated = apply_rows(planned)[0] if apply and planned else 0
    rows = _rows(channel_id)
    return _tally(len(rows), sum(1 for r in rows if _cost_stale(r)), len(planned), updated)


# ---- quality: behind the current quality or grade version, or never graded.


def _quality_version() -> str:
    from core.run_quality import QUALITY_VERSION
    from core.video_grade import GRADE_VERSION

    return f"{QUALITY_VERSION}/{GRADE_VERSION}"


def _quality_stale(run: Any) -> bool:
    from core.run_quality import QUALITY_VERSION
    from core.video_grade import GRADE_VERSION

    if not (getattr(run, "script_preview", "") or "").strip():
        return False
    quality = _load(getattr(run, "quality_json", ""))
    return (
        quality.get("grade_score") is None
        or quality.get("quality_version") != QUALITY_VERSION
        or quality.get("grade_version") != GRADE_VERSION
    )


def _quality_run(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    from analytics.backfill_quality import backfill_channel

    rows = _rows(channel_id)
    stale_ids = {r.id for r in rows if _quality_stale(r)}
    tally = backfill_channel(
        channel_id, apply=apply, force=force, run_ids=None if force else stale_ids
    )
    return _tally(len(rows), len(stale_ids), tally["would_update"], tally["updated"])


# ---- angles: a run with two or more stored angles and no angle score.


def _angles_stale(run: Any) -> bool:
    from analytics.backfill_angles import _variant_texts

    texts = _variant_texts(getattr(run, "variants_json", "[]"))
    selected = (getattr(run, "selected_topic", "") or "").strip()
    if len(texts) < 2 or selected not in texts:
        return False
    return _load(getattr(run, "quality_json", "")).get("angle_score") is None


def _angles_run(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    from analytics.backfill_angles import backfill_channel

    rows = _rows(channel_id)
    tally = backfill_channel(channel_id, apply=apply, force=force)
    return _tally(
        len(rows), sum(1 for r in rows if _angles_stale(r)), tally["would_update"], tally["updated"]
    )


REGISTRY: tuple[Backfill, ...] = (
    Backfill(
        "features",
        "run features for rows that have none",
        _features_version,
        _features_stale,
        _features_run,
    ),
    Backfill("cost", "the TTS line on rendered runs' cost", lambda: "v1", _cost_stale, _cost_run),
    Backfill(
        "quality",
        "grade, hook, hedge and style fields",
        _quality_version,
        _quality_stale,
        _quality_run,
    ),
    Backfill(
        "angles", "offline angle scores (approximate)", lambda: "v1", _angles_stale, _angles_run
    ),
)


def get_backfill(name: str) -> Backfill:
    for entry in REGISTRY:
        if entry.name == name:
            return entry
    raise KeyError(name)


def stale_counts(channel_id: str) -> dict[str, tuple[int, int]]:
    """{name: (stale rows, all rows)} - read-only."""
    rows = _rows(channel_id)
    return {entry.name: (sum(1 for r in rows if entry.stale(r)), len(rows)) for entry in REGISTRY}


def run_backfills(
    channel_id: str, names: list[str], *, apply: bool = False, force: bool = False
) -> dict[str, dict[str, int]]:
    """Run the named backfills ("all" = every one) in registry order."""
    wanted = {n.strip().lower() for n in names if n.strip()}
    out: dict[str, dict[str, int]] = {}
    for entry in REGISTRY:
        if "all" in wanted or entry.name in wanted:
            out[entry.name] = entry.run(channel_id, apply, force)
    return out
