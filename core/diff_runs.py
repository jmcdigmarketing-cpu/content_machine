"""#443 join two run dossier/quality dicts."""

from __future__ import annotations

from typing import Any


def _cost_total(features: dict[str, Any]) -> str:
    cost = features.get("cost") or {}
    if isinstance(cost, dict) and cost.get("total") is not None:
        return f"${float(cost['total']):.2f}"
    return "n/a"


def _q(block: dict[str, Any], key: str) -> Any:
    return (block.get("quality") or {}).get(key)


def diff_quality_features(a: dict[str, Any], b: dict[str, Any]) -> str:
    lines = [
        "diff-runs",
        f"  grade      : {a.get('grade', 'n/a'):<8} vs {b.get('grade', 'n/a')}",
        f"  cost       : {_cost_total(a.get('features') or {}):<8} vs {_cost_total(b.get('features') or {})}",
        f"  ungrounded : {_q(a, 'ungrounded_count')} vs {_q(b, 'ungrounded_count')}",
        f"  disputed   : {_q(a, 'disputed')} vs {_q(b, 'disputed')}",
        f"  hook       : {_q(a, 'hook_score')} vs {_q(b, 'hook_score')}",
    ]
    pre_a = str(_q(a, "script_pre_rewrite") or "").strip()
    pre_b = str(_q(b, "script_pre_rewrite") or "").strip()
    if pre_a or pre_b:
        lines.append("  script-diff: present" if (pre_a or pre_b) else "  script-diff: none")
    return "\n".join(lines)


def diff_run_ids(run_a: int, run_b: int) -> str:
    from core.video_grade import grade_from_record
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    rec_a = repo.get(int(run_a))
    rec_b = repo.get(int(run_b))

    def _pack(rec: Any) -> dict[str, Any]:
        import json

        if rec is None:
            return {"quality": {}, "features": {}, "grade": "n/a"}
        try:
            quality = json.loads(getattr(rec, "quality_json", None) or "{}")
        except Exception:
            quality = {}
        try:
            features = json.loads(getattr(rec, "features_json", None) or "{}")
        except Exception:
            features = {}
        graded = grade_from_record(rec)
        return {
            "quality": quality if isinstance(quality, dict) else {},
            "features": features if isinstance(features, dict) else {},
            "grade": graded.letter if graded else "n/a",
        }

    return diff_quality_features(_pack(rec_a), _pack(rec_b))
