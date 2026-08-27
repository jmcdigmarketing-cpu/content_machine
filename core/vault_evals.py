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
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.vault_evals")

EVALS_DIR = os.path.join(DATA_DIR, "vault_evals")
EVALS_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "vault_evals.json"
)


def load_cases() -> list[dict[str, Any]]:
    """Frozen labelled cases. [] when the config is missing or unreadable (fail-open)."""
    try:
        with open(EVALS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("vault eval config unreadable (%s) — no cases", exc)
        return []
    cases = data.get("cases")
    return [c for c in cases if isinstance(c, dict)] if isinstance(cases, list) else []


def decide(case: dict[str, Any]) -> bool:
    """Does the CURRENT code attach this bullet? True = attaches (uncertain counts).

    Runs the real `load_fact_records` against a temp vault built from the case, so the
    eval scores the shipped decision path rather than a reimplementation of it.
    """
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from core.obsidian_facts import load_fact_records

    stem = str(case.get("note_stem") or "note")
    heading = str(case.get("note_headings") or "")
    bullet = str(case.get("bullet") or "")
    topic = str(case.get("topic") or "")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "vault" / "tapin"
        root.mkdir(parents=True)
        (root / f"{stem}.md").write_text(
            f"---\nchannel: tapin\ntags: [facts]\n---\n\n# {heading}\n- {bullet}\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault")}):
            records = load_fact_records(topic, "tapin", require_distinctive=True)
    return any(bullet[:60] in r.claim for r in records)


def score(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Precision / recall of the current decision path over the labelled cases."""
    cases = cases if cases is not None else load_cases()
    tp = fp = tn = fn = 0
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected = bool(case.get("expected"))
        try:
            got = decide(case)
        except Exception as exc:
            logger.warning("vault eval case %s failed: %s", case.get("id"), exc)
            continue
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
        rows.append({"id": case.get("id"), "expected": expected, "got": got, "verdict": verdict})

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cases": len(rows),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 3) if precision is not None else None,
        "recall": round(recall, 3) if recall is not None else None,
        "rows": rows,
    }


def render(result: dict[str, Any]) -> str:
    """ASCII-safe report (cp1252 consoles — candidate 250)."""
    lines = [
        f"Vault relevance evals - {result.get('cases', 0)} labelled case(s)",
        "",
        f"  precision : {result.get('precision')}   (of what it attached, how much belonged)",
        f"  recall    : {result.get('recall')}   (of what belonged, how much it attached)",
        f"  leaked    : {result.get('false_positive', 0)} off-topic attached",
        f"  missed    : {result.get('false_negative', 0)} on-topic dropped",
        "",
    ]
    for row in result.get("rows") or []:
        mark = "  " if row.get("verdict") == "ok" else "! "
        lines.append(
            f"  {mark}{row.get('id')}: expected={row.get('expected')} got={row.get('got')}"
        )
    return "\n".join(lines)


def save(result: dict[str, Any]) -> str:
    """Persist one run. Never overwrites an earlier one — a lost baseline is the
    whole point of the harness gone, and two runs inside the same second is exactly
    what happens when someone scores before and after a one-line change."""
    os.makedirs(EVALS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(EVALS_DIR, f"{stamp}.json")
    suffix = 1
    while os.path.exists(path):
        path = os.path.join(EVALS_DIR, f"{stamp}-{suffix}.json")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vault subject-relevance evals")
    parser.add_argument("--compare", action="store_true", help="diff the last two runs")
    args = parser.parse_args(argv)
    if args.compare:
        print(compare_latest())
        return 0
    result = score()
    print(render(result))
    print(f"\nSaved: {save(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
