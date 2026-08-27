"""Vault subject-relevance eval set (candidate 329 P1).

Whether a vault bullet is *about the same subject* as the topic has been argued three
times and measured zero times, so each change has traded a false positive for a false
negative with no way to tell whether it helped. This makes it a number.

Same shape as [prompt_evals](prompt_evals.py), for the same reason: frozen labelled
cases in `config/vault_evals.json`, a deterministic rubric (no LLM judge, so a re-run on
unchanged code is reproducible), results written to `data/vault_evals/<timestamp>.json`,
and `compare` diffing the two most recent runs.

    py -m scripts.ops vault-eval              # score the CURRENT decision path
    py -m scripts.ops vault-eval --compare    # diff the last two runs

**Baseline first.** Score today's behaviour before changing it, or the replacement
cannot be shown to be better — the rule this repo asks of every gate, applied to the
gate itself.

The cases carry the run's fact **corpus**, not just the angle, because the corpus is the
disambiguator: measured on run 71, the off-topic "Wolverine Rage" bullet scores *higher*
than the on-topic "Rockstar Games" one against the angle (0.286 vs 0.154) and lower
against the corpus (0.143 vs 0.309). The angle is the ambiguous thing.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import replace
from itertools import pairwise, product
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.vault_evals")

EVALS_DIR = os.path.join(DATA_DIR, "vault_evals")
EVALS_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "vault_evals.json"
)


def _load_config() -> dict[str, Any]:
    try:
        with open(EVALS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("vault eval config unreadable (%s) — eval is invalid", exc)
        return {}


def load_cases() -> list[dict[str, Any]]:
    """Frozen labelled cases. [] when the config is missing or unreadable (fail-open)."""
    data = _load_config()
    cases = data.get("cases")
    return [c for c in cases if isinstance(c, dict)] if isinstance(cases, list) else []


def _case_records(
    case: dict[str, Any],
    *,
    mode: str | None = None,
    policy: str = "operator",
):
    """Run the production loader over one isolated fixture case."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from core.obsidian_facts import load_fact_records

    stem = str(case.get("note_stem") or "note").replace("/", "-").replace("\\", "-")
    heading = str(case.get("note_headings") or "")
    bullet = str(case.get("bullet") or "")
    topic = str(case.get("topic") or "")
    corpus = str(case.get("corpus") or "")
    channel_id = str(case.get("channel_id") or "tapin")
    tier = str(case.get("tier") or "vault")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "vault" / channel_id
        root.mkdir(parents=True)
        (root / f"{stem}.md").write_text(
            f"---\nchannel: {channel_id}\ntags: [facts]\ntier: {tier}\n"
            f"---\n\n# {heading}\n- {bullet}\n",
            encoding="utf-8",
        )
        env = {"OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault")}
        if mode:
            env["VAULT_RELEVANCE_MODE"] = mode
        with patch.dict(os.environ, env, clear=False):
            return load_fact_records(
                topic,
                channel_id,
                require_distinctive=True,
                corpus=corpus,
                relevance_policy=policy,
                limit=50,
            )


def evaluate_case(
    case: dict[str, Any],
    *,
    mode: str | None = None,
    policy: str = "operator",
) -> dict[str, Any]:
    """Detailed verdict from the real loader; uncertain counts as attached."""
    bullet = str(case.get("bullet") or "")
    records = _case_records(case, mode=mode, policy=policy)
    record = next((r for r in records if bullet[:60] in r.claim), None)
    if record is None:
        return {
            "got": False,
            "band": "reject",
            "score": None,
            "breakdown": {},
        }
    band = getattr(record, "relevance_band", "") or (
        "uncertain" if getattr(record, "uncertain", False) else "confident"
    )
    return {
        "got": True,
        "band": band,
        "score": getattr(record, "relevance_score", None),
        "breakdown": dict(getattr(record, "relevance_breakdown", {}) or {}),
    }


def decide(
    case: dict[str, Any],
    *,
    mode: str | None = None,
    policy: str = "operator",
) -> bool:
    """Does the selected production mode attach this bullet?"""
    return bool(evaluate_case(case, mode=mode, policy=policy)["got"])


def score(
    cases: list[dict[str, Any]] | None = None,
    *,
    mode: str | None = None,
    policy: str = "operator",
) -> dict[str, Any]:
    """Precision/recall plus confidence-band coverage for one production mode."""
    cases = cases if cases is not None else load_cases()
    tp = fp = tn = fn = 0
    errors = 0
    confident = uncertain = rejected = 0
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected = bool(case.get("expected"))
        try:
            if mode is None:
                # Preserve the small metric-math seam used by unit tests and old callers.
                got = decide(case)
                detail = {"got": got, "band": "confident" if got else "reject"}
            else:
                detail = evaluate_case(case, mode=mode, policy=policy)
                got = bool(detail["got"])
        except Exception as exc:
            logger.warning("vault eval case %s failed: %s", case.get("id"), exc)
            errors += 1
            continue
        band = str(detail.get("band") or ("confident" if got else "reject"))
        if band == "confident":
            confident += 1
        elif band == "uncertain":
            uncertain += 1
        else:
            rejected += 1
        if expected and got:
            tp += 1
            verdict = "ok"
        elif expected and not got:
            fn += 1
            verdict = "MISSED"
        elif not expected and got:
            fp += 1
            verdict = "LEAKED"
        else:
            tn += 1
            verdict = "ok"
        rows.append(
            {
                "id": case.get("id"),
                "source": case.get("source"),
                "split": case.get("split") or "calibration",
                "expected": expected,
                "got": got,
                "band": band,
                "score": detail.get("score"),
                "breakdown": detail.get("breakdown") or {},
                "verdict": verdict,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    attempted = len(cases)
    completed = len(rows)
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rubric_version": str(_load_config().get("rubric_version") or "v1"),
        "mode": mode or "current",
        "policy": policy,
        "valid": bool(attempted and completed == attempted and errors == 0),
        "attempted": attempted,
        "cases": completed,
        "errors": errors,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 3) if precision is not None else None,
        "recall": round(recall, 3) if recall is not None else None,
        "confident": confident,
        "uncertain": uncertain,
        "rejected": rejected,
        "abstention_rate": round(uncertain / completed, 3) if completed else None,
        "rows": rows,
    }


def score_modes(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Evaluate legacy and scored paths over the exact same frozen cases."""
    cases = cases if cases is not None else load_cases()
    config = _load_config()
    from core.vault_relevance import load_relevance_config

    scorer = load_relevance_config()
    modes = {
        name: score(cases, mode=name)
        for name in (
            "legacy",
            "scored",
        )
    }
    splits: dict[str, dict[str, Any]] = {}
    for split_name in ("calibration", "holdout"):
        subset = [case for case in cases if (case.get("split") or "calibration") == split_name]
        splits[split_name] = {name: score(subset, mode=name) for name in ("legacy", "scored")}
    gate = _p3_gate(cases, modes, splits)
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rubric_version": str(config.get("rubric_version") or "v1"),
        "scorer_version": scorer.scorer_version,
        "valid": all(result.get("valid") for result in modes.values()),
        "modes": modes,
        "splits": splits,
        "p3_gate": gate,
    }


def _p3_gate(
    cases: list[dict[str, Any]],
    modes: dict[str, dict[str, Any]],
    splits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Measured default-flip gate; no single-story calibration can pass it."""
    holdout_cases = [case for case in cases if case.get("split") == "holdout"]
    holdout_sources = {
        str(case.get("source") or "")
        for case in holdout_cases
        if str(case.get("source") or "").startswith("live-run ")
    }
    labels = {bool(case.get("expected")) for case in holdout_cases}
    scored_holdout = (splits.get("holdout") or {}).get("scored") or {}
    legacy_rows = {row.get("id"): row for row in (modes.get("legacy") or {}).get("rows") or []}
    scored_rows = {row.get("id"): row for row in (modes.get("scored") or {}).get("rows") or []}
    regressions = [
        case_id
        for case_id, old in legacy_rows.items()
        if old.get("verdict") == "ok" and (scored_rows.get(case_id) or {}).get("verdict") != "ok"
    ]
    checks = {
        "all_cases_completed": bool(
            modes.get("legacy", {}).get("valid") and modes.get("scored", {}).get("valid")
        ),
        "multi_run_holdout": len(holdout_sources) >= 2,
        "both_holdout_labels": labels == {False, True},
        "precision_beats_baseline": (
            isinstance(scored_holdout.get("precision"), int | float)
            and scored_holdout["precision"] > 0.667
        ),
        "recall_beats_baseline": (
            isinstance(scored_holdout.get("recall"), int | float)
            and scored_holdout["recall"] > 0.667
        ),
        "no_legacy_regressions": not regressions,
    }
    return {
        "passed": all(checks.values()),
        "baseline_precision": 0.667,
        "baseline_recall": 0.667,
        "holdout_cases": len(holdout_cases),
        "holdout_sources": sorted(holdout_sources),
        "regressions": regressions,
        "checks": checks,
    }


def render(result: dict[str, Any]) -> str:
    """ASCII-safe report (cp1252 consoles — candidate 250)."""
    if isinstance(result.get("modes"), dict):
        lines = [
            f"Vault relevance evals - rubric {result.get('rubric_version', '?')} "
            f"/ scorer {result.get('scorer_version', '?')}",
            "",
        ]
        for name in ("legacy", "scored"):
            mode_result = (result.get("modes") or {}).get(name) or {}
            state = "valid" if mode_result.get("valid") else "INVALID"
            lines.append(
                f"  {name:8} precision={mode_result.get('precision')} "
                f"recall={mode_result.get('recall')} "
                f"uncertain={mode_result.get('uncertain', 0)} [{state}]"
            )
        gate = result.get("p3_gate") or {}
        holdout = ((result.get("splits") or {}).get("holdout") or {}).get("scored") or {}
        gate_state = "passed" if gate.get("passed") else "failed"
        lines.append(
            f"  holdout  precision={holdout.get('precision')} "
            f"recall={holdout.get('recall')} "
            f"p3 {gate_state} ({gate.get('holdout_cases', 0)} cases)"
        )
        return "\n".join(lines)

    state = "" if result.get("valid", True) else " [INVALID]"
    lines = [
        f"Vault relevance evals - {result.get('cases', 0)}/"
        f"{result.get('attempted', result.get('cases', 0))} labelled case(s){state}",
        "",
        f"  precision : {result.get('precision')}   (of what it attached, how much belonged)",
        f"  recall    : {result.get('recall')}   (of what belonged, how much it attached)",
        f"  leaked    : {result.get('false_positive', 0)} off-topic attached",
        f"  missed    : {result.get('false_negative', 0)} on-topic dropped",
        f"  bands     : {result.get('confident', 0)} confident / "
        f"{result.get('uncertain', 0)} uncertain / {result.get('rejected', 0)} rejected",
        f"  errors    : {result.get('errors', 0)}",
        "",
    ]
    for row in result.get("rows") or []:
        mark = "  " if row.get("verdict") == "ok" else "! "
        lines.append(
            f"  {mark}{row.get('id')}: expected={row.get('expected')} got={row.get('got')}"
        )
    return "\n".join(lines)


def save(result: dict[str, Any], *, output_dir: str | None = None) -> str:
    """Persist one run. Never overwrites an earlier one — a lost baseline is the
    whole point of the harness gone, and two runs inside the same second is exactly
    what happens when someone scores before and after a one-line change."""
    target_dir = output_dir or EVALS_DIR
    os.makedirs(target_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(target_dir, f"{stamp}.json")
    suffix = 1
    while os.path.exists(path):
        path = os.path.join(target_dir, f"{stamp}-{suffix}.json")
        suffix += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return path


def _recent(limit: int = 2) -> list[dict[str, Any]]:
    try:
        names = sorted(os.listdir(EVALS_DIR), reverse=True)[:limit]
    except OSError:
        return []
    out = []
    for name in names:
        try:
            with open(os.path.join(EVALS_DIR, name), encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception as exc:
            logger.debug("vault eval %s unreadable: %s", name, exc)
    return out


def compare_latest() -> str:
    runs = _recent(2)
    if len(runs) < 2:
        return "Need two vault-eval runs to compare (run `ops vault-eval` twice)."
    new, old = runs[0], runs[1]
    old_rubric = old.get("rubric_version")
    new_rubric = new.get("rubric_version")
    if old_rubric and new_rubric and old_rubric != new_rubric:
        return (
            "Incompatible vault-eval rubrics: "
            f"{old_rubric} -> {new_rubric}; compare within one rubric version."
        )
    lines = [f"Vault relevance: {old.get('timestamp')} -> {new.get('timestamp')}", ""]
    for key in ("precision", "recall", "false_positive", "false_negative"):
        a, b = old.get(key), new.get(key)
        if isinstance(a, int | float) and isinstance(b, int | float):
            delta = b - a
            arrow = "same" if abs(delta) < 1e-9 else ("up" if delta > 0 else "down")
            lines.append(f"  {key:16} {a} -> {b}  ({arrow})")
        else:
            lines.append(f"  {key:16} {a} -> {b}")
    return "\n".join(lines)


def _binary_metrics(labels: list[bool], scores: list[float], threshold: float) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for expected, value in zip(labels, scores, strict=True):
        got = value >= threshold
        if expected and got:
            tp += 1
        elif expected:
            fn += 1
        elif got:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(labels) if labels else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
    }


def tune(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Recommend bounded weights/thresholds; never writes shipped config.

    Whole-run holdouts are excluded from tuning. The search is intentionally small
    and deterministic, with tier fixed as a low tie-breaker. P3 judges the resulting
    recommendation on holdout cases rather than this calibration score.
    """
    from core.vault_relevance import load_relevance_config, score_vault_fact

    all_cases = cases if cases is not None else load_cases()
    calibration = [case for case in all_cases if case.get("split") != "holdout"]
    if not calibration:
        calibration = list(all_cases)
    labels = [bool(case.get("expected")) for case in calibration]
    if not labels or set(labels) != {False, True}:
        return {
            "valid": False,
            "reason": "calibration set must contain both labels",
            "cases": len(labels),
        }

    base = load_relevance_config()
    best: tuple[tuple[float, ...], dict[str, Any]] | None = None
    ranges = (
        (0.2, 0.3, 0.4),
        (0.1, 0.2, 0.3),
        (0.15, 0.25, 0.35),
        (0.1, 0.2, 0.3),
        (0.05, 0.15, 0.25),
    )
    names = (
        "bullet_entity",
        "note_entity",
        "bullet_cosine",
        "note_cosine",
        "anchor",
    )
    for values in product(*ranges):
        raw = dict(zip(names, values, strict=True))
        raw["tier"] = 0.03
        total = sum(raw.values())
        weights = {key: value / total for key, value in raw.items()}
        candidate_config = replace(base, weights=weights)
        scores = [
            score_vault_fact(
                topic=str(case.get("topic") or ""),
                corpus=str(case.get("corpus") or ""),
                bullet=str(case.get("bullet") or ""),
                note_context=(f"{case.get('note_stem') or ''} {case.get('note_headings') or ''}"),
                tier=str(case.get("tier") or "vault"),
                config=candidate_config,
            ).score
            for case in calibration
        ]
        ordered = sorted(set(scores))
        thresholds = {0.0, 1.0, *ordered}
        thresholds.update((left + right) / 2 for left, right in pairwise(ordered))
        for threshold in thresholds:
            metrics = _binary_metrics(labels, scores, threshold)
            objective = (
                min(metrics["precision"], metrics["recall"]),
                metrics["f1"],
                metrics["accuracy"],
                threshold,
            )
            if best is None or objective > best[0]:
                best = (
                    objective,
                    {
                        "weights": {key: round(value, 6) for key, value in weights.items()},
                        "uncertain_threshold": round(threshold, 4),
                        "scores": scores,
                        "metrics": metrics,
                    },
                )

    assert best is not None
    recommendation = best[1]
    attach_threshold = float(recommendation["uncertain_threshold"])
    scores = list(recommendation.pop("scores"))
    confidence_candidates = sorted({value for value in scores if value >= attach_threshold})
    confident_threshold = attach_threshold
    best_confident: tuple[float, int, float] | None = None
    for threshold in confidence_candidates:
        metrics = _binary_metrics(labels, scores, threshold)
        predicted = sum(value >= threshold for value in scores)
        objective = (metrics["precision"], predicted, threshold)
        if best_confident is None or objective > best_confident:
            best_confident = objective
            confident_threshold = threshold

    return {
        "valid": True,
        "scorer_version": base.scorer_version,
        "calibration_cases": len(calibration),
        **recommendation,
        "confident_threshold": round(max(attach_threshold, confident_threshold), 4),
        "writes_config": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vault subject-relevance evals")
    parser.add_argument("--compare", action="store_true", help="diff the last two runs")
    parser.add_argument(
        "--mode",
        choices=("legacy", "shadow", "scored", "both"),
        default="both",
        help="decision path to evaluate (default: legacy and scored together)",
    )
    parser.add_argument("--tune", action="store_true", help="print an advisory calibration")
    parser.add_argument("--no-save", action="store_true", help="do not write data/vault_evals")
    parser.add_argument("--output-dir", default="", help="override eval result directory")
    args = parser.parse_args(argv)
    if args.compare:
        print(compare_latest())
        return 0
    if args.tune:
        recommendation = tune()
        print(json.dumps(recommendation, indent=2))
        return 0 if recommendation.get("valid") else 1
    result = score_modes() if args.mode == "both" else score(mode=args.mode)
    print(render(result))
    if not args.no_save:
        print(f"\nSaved: {save(result, output_dir=args.output_dir or None)}")
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
