"""mypy as a ratchet: the error count may fall, never rise (#833, master_plan M3.2).

CI ran mypy with `continue-on-error` — a baseline nobody enforced, so it grew (~94 in
June, 135 by 2026-09-26). This turns the number into a check without a blocking
rewrite: `mypy_baseline.txt` holds the last accepted count; a run that reports MORE
errors fails; one that reports fewer prints the new number so the baseline can be
lowered in the same commit. Same directory list as `.github/workflows/ci.yml`.

    py scripts/mypy_ratchet.py            # exit 1 if errors > baseline
    py scripts/mypy_ratchet.py --update   # write the current count as the baseline
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "mypy_baseline.txt"
# Keep in step with the `typecheck` job in .github/workflows/ci.yml.
TARGETS = ("analytics", "apis", "core", "config", "storage", "desktop")

_SUMMARY = re.compile(r"Found (\d+) errors? in \d+ files?|^Success: no issues found", re.M)


def parse_error_count(mypy_output: str) -> int:
    """The N in mypy's summary line; 0 for a clean run. Raises when there is no summary."""
    m = _SUMMARY.search(mypy_output)
    if m is None:
        raise ValueError("no mypy summary line found in output")
    return int(m.group(1)) if m.group(1) is not None else 0


def read_baseline(path: Path = BASELINE) -> int:
    return int(path.read_text(encoding="utf-8").strip())


def verdict(current: int, baseline: int) -> tuple[int, str]:
    """(exit code, one line). Rising is a failure; falling is an invitation to lower."""
    if current > baseline:
        return (
            1,
            f"mypy: {current} errors > baseline {baseline} — fix the new ones or justify raising the baseline",
        )
    if current < baseline:
        return (
            0,
            f"mypy: {current} errors < baseline {baseline} — lower the baseline: py scripts/mypy_ratchet.py --update",
        )
    return 0, f"mypy: {current} errors == baseline {baseline}"


def run_mypy() -> str:
    # --no-incremental: a stale .mypy_cache reported 24 fewer errors than a fresh run on
    # the same tree (2026-09-26). CI has no cache, so the ratchet must count the way CI does.
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", *TARGETS],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    output = run_mypy()
    current = parse_error_count(output)
    if "--update" in args:
        BASELINE.write_text(f"{current}\n", encoding="utf-8")
        print(f"mypy baseline set to {current}")
        return 0
    if not BASELINE.exists():
        print(
            f"mypy: no baseline file at {BASELINE}; run with --update to create it", file=sys.stderr
        )
        return 1
    code, line = verdict(current, read_baseline())
    print(line)
    if code:
        # Show the errors so the failing CI log is actionable without a re-run.
        print(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
