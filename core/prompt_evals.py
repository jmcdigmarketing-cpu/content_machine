"""Prompt-evolution eval set (Pillar 2) — frozen rubric + golden topics.

Prompt changes were previously vibed: edit `content_engine`, eyeball one
script, ship. This harness makes them measurable — a fixed set of golden
topics with frozen key facts (`config/prompt_evals.json`) is generated with
the *current* prompts, scored against a frozen heuristic rubric, and saved to
`data/prompt_evals/<timestamp>.json` tagged with the prompt version.
`compare` diffs the two most recent eval runs per metric.

    py -m core.prompt_evals run --channel tapin      (costs a few LLM calls)
    py -m core.prompt_evals compare

Rubric (all heuristic, no LLM-judge — deterministic given a script):
hook score, authenticity score, ungrounded-specifics count vs the frozen
facts, word-count fit vs the length preset, filler-phrase count.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.prompt_evals")

EVALS_DIR = os.path.join(DATA_DIR, "prompt_evals")
EVALS_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompt_evals.json"
)

# Frozen filler list (rubric v1) — mirrors the script prompt's ban-list. Do not
# extend casually: a rubric change invalidates cross-run comparison.
_FILLER_PHRASES = (
    "but here's the thing",
    "let's dive in",
    "without further ado",
    "at the end of the day",
    "buckle up",
    "game-changer",
)


def _load_config() -> dict[str, Any]:
    try:
        with open(EVALS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("prompt_evals config unreadable: %s", exc)
        return {}


def score_script(script: str, *, key_facts: list[str], length_choice: str) -> dict[str, Any]:
    """Frozen rubric v1 — heuristic, deterministic per script."""
    out: dict[str, Any] = {"rubric_version": "v1"}
    try:
        from core.hook_score import score_script_hook

        out["hook_score"] = score_script_hook(script).score
    except Exception:
        out["hook_score"] = None
    try:
        from core.fact_grounding import find_ungrounded_entities

        out["ungrounded_count"] = len(find_ungrounded_entities(script, "\n".join(key_facts)))
    except Exception:
        out["ungrounded_count"] = None
    try:
        from core.script_length import count_spoken_words, word_range

        lo, hi = word_range(length_choice)
        words = count_spoken_words(script)
        out["word_count"] = words
        out["length_fit"] = bool(lo <= words <= hi)
    except Exception:
        out["length_fit"] = None
    lower = script.lower()
    out["filler_count"] = sum(lower.count(p) for p in _FILLER_PHRASES)
    return out


def _generate(
    topic: str, key_facts: list[str], length_choice: str, channel_id: str
) -> tuple[str, str]:
    """Generate a script for a golden topic with the live prompts (no signals)."""
    from datetime import datetime

    from core.content_engine import generate_content_package
    from core.script_length import word_range

    package = generate_content_package(
        topic=topic,
        signals={},
        word_range=word_range(length_choice),
        today=datetime.now().strftime("%Y-%m-%d"),
        channel_id=channel_id,
        research_brief=None,
        length_choice=length_choice,
        key_facts=list(key_facts),
    )
    return str(package.get("script") or ""), str(package.get("prompt_version") or "")


def run_evals(channel_id: str | None = None) -> dict[str, Any]:
    """Generate + score every golden topic; persist and return the result."""
    config = _load_config()
    channels = config.get("channels") or {}
    targets = {channel_id: channels.get(channel_id, [])} if channel_id else channels

    results: list[dict[str, Any]] = []
    prompt_version = ""
    for channel, cases in targets.items():
        for case in cases or []:
            topic = str(case.get("topic") or "")
            facts = [str(f) for f in case.get("key_facts") or []]
            length_choice = str(case.get("length_choice") or "2")
            if not topic:
                continue
            try:
                script, prompt_version = _generate(topic, facts, length_choice, channel)
            except Exception as exc:
                logger.warning("eval generation failed for '%s': %s", topic, exc)
                results.append({"id": case.get("id"), "channel": channel, "error": str(exc)[:200]})
                continue
            scores = score_script(script, key_facts=facts, length_choice=length_choice)
            results.append(
                {
                    "id": case.get("id"),
                    "channel": channel,
                    "topic": topic,
                    "scores": scores,
                    "script_preview": script[:400],
                }
            )

    payload = {
        "at": time.time(),
        "prompt_version": prompt_version,
        "rubric_version": str(config.get("rubric_version") or "v1"),
        "results": results,
    }
    try:
        os.makedirs(EVALS_DIR, exist_ok=True)
        path = os.path.join(EVALS_DIR, f"{int(time.time())}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        payload["path"] = path
    except Exception as exc:
        logger.warning("eval save failed: %s", exc)
    return payload


def _load_eval_files(limit: int = 2) -> list[dict[str, Any]]:
    try:
        names = sorted((n for n in os.listdir(EVALS_DIR) if n.endswith(".json")), reverse=True)
    except Exception:
        return []
    out = []
    for name in names[:limit]:
        try:
            with open(os.path.join(EVALS_DIR, name), encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            continue
    return out


_METRICS = ("hook_score", "ungrounded_count", "filler_count")


def compare_latest() -> str:
    """Diff the two most recent eval runs per golden topic and metric."""
    evals = _load_eval_files(2)
    if len(evals) < 2:
        return "Need two eval runs to compare - run `py -m core.prompt_evals run` twice."
    new, old = evals[0], evals[1]
    lines = [
        f"Prompt evals: {old.get('prompt_version', '?')} -> {new.get('prompt_version', '?')}",
        "=" * 64,
    ]
    old_by_id = {r.get("id"): r for r in old.get("results", [])}
    for result in new.get("results", []):
        case_id = result.get("id")
        before = old_by_id.get(case_id)
        lines.append(f"  {case_id}:")
        if result.get("error"):
            lines.append(f"    generation error: {result['error']}")
            continue
        new_scores = result.get("scores") or {}
        old_scores = (before or {}).get("scores") or {}
        for metric in _METRICS:
            n_val, o_val = new_scores.get(metric), old_scores.get(metric)
            if n_val is None:
                continue
            if o_val is None:
                lines.append(f"    {metric:<18} {n_val} (no baseline)")
            else:
                delta = n_val - o_val
                mark = "=" if delta == 0 else ("+" if delta > 0 else "")
                lines.append(f"    {metric:<18} {o_val} -> {n_val} ({mark}{delta})")
        if new_scores.get("length_fit") is not None:
            lines.append(f"    {'length_fit':<18} {new_scores['length_fit']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prompt-evolution eval harness")
    parser.add_argument("action", choices=["run", "compare"])
    parser.add_argument("--channel", default=None, help="Limit run to one channel")
    args = parser.parse_args(argv)
    if args.action == "run":
        payload = run_evals(args.channel)
        ok = [r for r in payload["results"] if not r.get("error")]
        print(
            f"Evaluated {len(ok)}/{len(payload['results'])} golden topics "
            f"(prompt {payload.get('prompt_version', '?')})"
        )
        for r in ok:
            s = r["scores"]
            print(
                f"  {r['id']:<20} hook {s.get('hook_score')} · "
                f"ungrounded {s.get('ungrounded_count')} · filler {s.get('filler_count')} · "
                f"length_fit {s.get('length_fit')}"
            )
        if payload.get("path"):
            print(f"Saved: {payload['path']}")
        return 0
    print(compare_latest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
