"""Which recorded run features move with the outcome (#357) - measured, never acted on.

`core/run_features.build_features` records a dozen features per run and nothing tested
one against engaged rate. For every top-level feature with a measured outcome:

- numeric and boolean -> Pearson r against engaged rate, with the n at which that r would
  clear p<0.05 (`grade_calibration.n_for_significance`);
- categorical (a string with a handful of repeated levels) -> the mean engaged rate and
  n per level.

Free text (titles, hooks), ids, lists and nested records are not features here. Under
five measured runs a feature says "collecting". Report-only: no weight, gate or default
changes from it - #739's rule is measure, then decide, and n here is small.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

_MIN_RUNS = 5
_MAX_LEVELS = 8
# Recorded for provenance or display, not as a property of the video.
_NOT_FEATURES = frozenset(
    {"title", "hook_text", "suggested_hook", "title_direction", "feature_version", "menu_path"}
)


@dataclass
class FeatureImportance:
    name: str
    kind: str  # numeric | categorical
    n: int
    r: float | None = None
    n_needed: int | None = None
    levels: dict[str, tuple[float, int]] = field(default_factory=dict)


def _rows(channel_id: str) -> list[tuple[dict[str, Any], float]]:
    from core.engagement_predictor import run_engagement_map
    from storage.repositories.content_runs import get_content_run_repository

    outcomes = run_engagement_map(channel_id)
    rows: list[tuple[dict[str, Any], float]] = []
    for run in get_content_run_repository().list_for_channel(channel_id):
        rate = outcomes.get(int(run.id))
        if rate is None:
            continue
        try:
            features = json.loads(run.features_json or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(features, dict):
            rows.append((features, float(rate)))
    return rows


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    return None


def feature_importance(channel_id: str) -> list[FeatureImportance]:
    """Every feature with enough rows, strongest first (numeric by |r|, then categorical)."""
    from core.grade_calibration import _pearson, n_for_significance

    rows = _rows(channel_id)
    names = sorted({k for features, _ in rows for k in features if k not in _NOT_FEATURES})
    numeric: list[FeatureImportance] = []
    categorical: list[FeatureImportance] = []
    for name in names:
        pairs = [(_numeric(f.get(name)), rate) for f, rate in rows if f.get(name) is not None]
        nums = [(x, y) for x, y in pairs if x is not None]
        if nums and len(nums) == len(pairs):
            r = _pearson([x for x, _ in nums], [y for _, y in nums]) if len(nums) >= 2 else None
            need = n_for_significance(r) if r is not None else None
            numeric.append(FeatureImportance(name, "numeric", len(nums), r, need))
            continue
        texts = [
            (str(f[name]), rate) for f, rate in rows if isinstance(f.get(name), str) and f[name]
        ]
        levels: dict[str, list[float]] = {}
        for text, rate in texts:
            levels.setdefault(text, []).append(rate)
        if not levels or len(levels) > _MAX_LEVELS or max(len(v) for v in levels.values()) < 2:
            continue  # free text or an id: every value distinct
        categorical.append(
            FeatureImportance(
                name,
                "categorical",
                len(texts),
                levels={k: (sum(v) / len(v), len(v)) for k, v in sorted(levels.items())},
            )
        )
    numeric.sort(key=lambda f: (-abs(f.r) if f.r is not None else 1.0, f.name))
    categorical.sort(key=lambda f: f.name)
    return numeric + categorical


def report_lines(channel_id: str) -> list[str]:
    """`ops feature-report`."""
    rows = _rows(channel_id)
    lines = [
        f"Feature report (#357) - {channel_id}: {len(rows)} measured run(s); report-only, "
        "nothing is tuned from it"
    ]
    if len(rows) < _MIN_RUNS:
        lines.append(f"  collecting - {len(rows)} measured run(s), a correlation needs {_MIN_RUNS}")
        return lines
    for feat in feature_importance(channel_id):
        if feat.n < _MIN_RUNS:
            lines.append(f"  {feat.name}: collecting (n={feat.n})")
        elif feat.kind == "numeric":
            if feat.r is None:
                lines.append(f"  {feat.name}: no variance (n={feat.n})")
                continue
            settle = (
                "significant at this n"
                if feat.n_needed is not None and feat.n_needed <= feat.n
                else f"not significant; n={feat.n_needed} would settle it"
                if feat.n_needed
                else "not significant"
            )
            lines.append(f"  {feat.name}: r={feat.r:+.2f} (n={feat.n}) - {settle}")
        else:
            parts = ", ".join(
                f"{level} {mean * 100:.1f}% (n={n})" for level, (mean, n) in feat.levels.items()
            )
            lines.append(f"  {feat.name}: {parts}")
    return lines
