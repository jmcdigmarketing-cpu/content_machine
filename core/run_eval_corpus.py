"""Prompt-eval corpus runner seam (system_prompts_leaks → adversarial fixtures).

The system_prompts_leaks archive is a reference corpus, not a dependency. Drop chosen
prompt/adversarial-case files into `prompts/eval_corpus/` and this runner replays each as
a case against the claim verifier / prompt-eval rubric, logging pass/fail — a cheap way to
regression-test guardrails when the verifier or script prompts change.

Baseline: loads and lists the corpus (fail-open to an empty list when the dir is absent).
The verifier-scoring pass runs only when `EVAL_CORPUS_LLM=true`, so `unittest`/CI never
spends an LLM call. CLI: `py -m core.run_eval_corpus`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("core.run_eval_corpus")

_CORPUS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "eval_corpus"
_EXTS = (".md", ".txt")


def load_cases() -> list[tuple[str, str]]:
    """Return `(name, text)` for each corpus file. `[]` when the dir is absent."""
    if not _CORPUS_DIR.is_dir():
        return []
    cases: list[tuple[str, str]] = []
    for path in sorted(_CORPUS_DIR.iterdir()):
        if path.suffix.lower() not in _EXTS or path.stem.lower() == "readme":
            continue
        try:
            cases.append((path.stem, path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.debug("Corpus case %s unreadable: %s", path.stem, exc)
            continue
    return cases


def run_corpus() -> list[dict[str, Any]]:
    """Replay the corpus. Fail-open: `[]` when empty; never raises.

    With `EVAL_CORPUS_LLM=true`, each case is scored via `core.prompt_evals`; otherwise it
    reports the loaded case (a lint-only pass) so CI stays free of LLM calls.
    """
    cases = load_cases()
    if not cases:
        return []
    use_llm = (os.getenv("EVAL_CORPUS_LLM", "") or "").strip().lower() in ("1", "true", "yes")
    report: list[dict[str, Any]] = []
    for name, text in cases:
        row: dict[str, Any] = {"case": name, "chars": len(text), "scored": False}
        if use_llm:
            try:
                from core.prompt_evals import score_script

                row["result"] = score_script(text, key_facts=[], length_choice="standard")
                row["scored"] = True
            except Exception as exc:
                logger.info("eval case %s scoring skipped: %s", name, exc)
        report.append(row)
    return report


def main(argv: list[str] | None = None) -> int:
    rows = run_corpus()
    if not rows:
        print("No eval corpus found (add files under prompts/eval_corpus/).")
        return 0
    for row in rows:
        print(f"- {row['case']} ({row['chars']} chars) scored={row['scored']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
