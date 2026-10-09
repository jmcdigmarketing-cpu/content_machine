"""Replay frozen live-run defects (wave 36).

A fix's own test usually pins one run's strings beside the code it changed, so a later
change elsewhere can undo it and stay green: #745 replaced the grounding stopwords and
"Why Jason Duval" was a name again; an SRT force_style burned run 77's karaoke captions
at a tenth of their size. And a fix reaches one module but not its siblings - run 98's
question-word fix held in 1 of 7 tokenizers.

`tests/regression_corpus.json` keeps each defect as one pure call plus what must stay
true. CI replays all of them; `ops regressions --file <path>` lists the old fixes that
guard a file before you change it.

Expectations (all given must hold): equals, contains, not_contains, includes_all,
excludes_any, truthy, falsy. Optional per case: `kwargs`, `env`, `pluck` (a key read
from each item of a list result), `select` (a key read from a dict result) and
`patch_raise` (targets patched to raise, so a case never reaches a network).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "regression_corpus.json"


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    data = json.loads((path or CORPUS).read_text(encoding="utf-8"))
    return list(data.get("cases") or [])


def resolve(call: str):
    module, _, name = call.partition(":")
    return getattr(importlib.import_module(module), name)


def module_file(call: str) -> str:
    module = call.partition(":")[0]
    return module.replace(".", "/") + ".py"


def _members(got: Any) -> Any:
    if isinstance(got, set | frozenset):
        return sorted(got, key=str)
    if isinstance(got, tuple):
        return list(got)
    return got


def _check(expect: dict[str, Any], got: Any) -> bool:
    got = _members(got)
    for kind, want in expect.items():
        if kind == "equals":
            ok = got == want
        elif kind == "contains":
            ok = want in got
        elif kind == "not_contains":
            ok = want not in got
        elif kind == "includes_all":
            ok = all(w in got for w in want)
        elif kind == "excludes_any":
            ok = not any(w in got for w in want)
        elif kind == "truthy":
            ok = bool(got)
        elif kind == "falsy":
            ok = not got
        else:
            return False
        if not ok:
            return False
    return True


def run_case(case: dict[str, Any]) -> tuple[bool, Any]:
    """(held, what the call returned). A raising call is a failed case, never a crash."""
    try:
        fn = resolve(case["call"])
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, dict(case.get("env") or {})))
            for target in case.get("patch_raise") or []:
                stack.enter_context(patch(target, side_effect=RuntimeError("regression corpus")))
            got = fn(*(case.get("args") or []), **(case.get("kwargs") or {}))
        if case.get("select") is not None:  # 0 is an index, not "no select"
            got = got[case["select"]]
        if case.get("pluck"):
            got = [item.get(case["pluck"]) for item in got]
    except Exception as exc:
        return False, f"raised {type(exc).__name__}: {exc}"
    return _check(dict(case.get("expect") or {}), got), _members(got)


def cases_for_file(path: str) -> list[dict[str, Any]]:
    """The cases whose function lives in `path` (repo-relative)."""
    want = Path(path).as_posix().lstrip("./")
    return [c for c in load_cases() if module_file(c["call"]) == want]


def render(results: list[tuple[dict[str, Any], bool, Any]]) -> str:
    held = sum(1 for _c, ok, _g in results if ok)
    lines = [f"Regression corpus: {held} of {len(results)} held"]
    for case, ok, got in results:
        mark = "ok  " if ok else "FAIL"
        lines.append(f"  {mark} #{case['item']:<4} {case['id']}  ({case['call']})")
        if not ok:
            lines.append(f"         got {got!r}")
            lines.append(f"         why: {case['why']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay frozen live-run defects")
    parser.add_argument("--file", default="", help="only the cases guarding this file")
    args = parser.parse_args(argv)
    cases = cases_for_file(args.file) if args.file else load_cases()
    if args.file and not cases:
        print(f"No regression case guards {args.file} yet.")
        return 0
    results = []
    for case in cases:
        ok, got = run_case(case)
        results.append((case, ok, got))
    print(render(results))
    return 0 if all(ok for _c, ok, _g in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
