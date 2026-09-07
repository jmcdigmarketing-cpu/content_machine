"""#350. Frozen grounding verdicts — a gate change that loosens them fails CI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.fact_grounding import find_ungrounded_entities

CORPUS_PATH = Path(__file__).resolve().parent.parent / "config" / "grounding_corpus.json"


def load_grounding_corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        return []
    return [c for c in cases if isinstance(c, dict)]


def evaluate_case(case: dict[str, Any]) -> list[str]:
    script = str(case.get("script") or "")
    facts = str(case.get("facts") or "")
    return find_ungrounded_entities(script, facts)


def main(argv: list[str] | None = None) -> int:
    failed = 0
    for case in load_grounding_corpus():
        got = evaluate_case(case)
        expect = list(case.get("expect_ungrounded") or [])
        cid = case.get("id")
        if got != expect:
            failed += 1
            print(f"FAIL {cid}: got {got!r} expected {expect!r}")
        else:
            print(f"ok   {cid}")
    print(f"{len(load_grounding_corpus())} cases, {failed} fail(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
