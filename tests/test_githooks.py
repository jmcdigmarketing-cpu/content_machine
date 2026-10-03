"""The commit-msg hook must actually be able to run.

`.githooks/commit-msg` enforces the AGENTS.md provenance policy: `Co-authored-by:`
trailers are encouraged (the 2026-08-28 reversal — two agents share one git author,
so the trailer is the per-commit record of who wrote a change), and
"Generated with ..." is refused as marketing rather than provenance.

A hook without the executable bit is skipped silently by git (it prints a hint to
stderr and commits anyway), so the file was shipped non-executable and enforced
nothing on a fresh clone. That is the docs/audit_2026-09.md §3 shape: a check that
reports success while not checking. Hence a test, not a fixed permission alone.
Verified end-to-end in-container on 2026-09-25: exit 1 on a "Generated with"
message, warn-and-pass on a trailer-less one.

No network. #930: NTFS has no exec bits, so on Windows the mode check reads the mode git
recorded (`git ls-files -s`, one subprocess) instead of the file's - the thing that
decides whether a fresh clone can run the hook.
"""

from __future__ import annotations

import os
import stat
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

HOOKS = Path(__file__).resolve().parent.parent / ".githooks"


class TestGitHooks(unittest.TestCase):
    def test_every_hook_is_executable(self):
        hooks = sorted(p for p in HOOKS.iterdir() if p.is_file())
        self.assertTrue(hooks, "no hooks found — did .githooks move?")
        not_executable = [p.name for p in hooks if not os.access(p, os.X_OK)]
        self.assertEqual(
            not_executable,
            [],
            "git skips a non-executable hook silently: chmod +x, and commit the mode bit",
        )

    def test_hooks_are_committed_with_the_executable_mode_bit(self):
        # os.access passes on a fresh checkout only if git recorded mode 100755.
        self.assertEqual(_not_executable(), [])

    def test_on_windows_the_recorded_mode_is_what_counts(self):
        with patch("tests.test_githooks.os.name", "nt"):
            self.assertEqual(_not_executable(), [])
            listing = (
                "100644 abc 0\t.githooks/commit-msg\n100755 def 0\t.githooks/prepare-commit-msg\n"
            )
            with patch("tests.test_githooks.subprocess.run") as run:
                run.return_value.stdout = listing
                self.assertEqual(_not_executable(), ["commit-msg"])

    def test_commit_msg_hook_still_enforces_the_provenance_policy(self):
        body = (HOOKS / "commit-msg").read_text(encoding="utf-8")
        # Still refuses marketing attribution...
        self.assertIn("generated with", body.lower())
        # ...and still speaks to the trailer policy (encourage, since 2026-08-28).
        self.assertIn("co-authored-by:", body.lower())
        self.assertNotIn("trailer is not allowed", body.lower())


def _not_executable() -> list[str]:
    """Hooks a fresh clone could not run: by file mode, or on Windows by git's recorded mode."""
    if os.name == "nt":
        out = subprocess.run(
            ["git", "ls-files", "-s", ".githooks"],
            cwd=HOOKS.parent,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return sorted(
            line.split("\t", 1)[1].rsplit("/", 1)[-1]
            for line in out.splitlines()
            if "\t" in line and not line.startswith("100755")
        )
    return [
        p.name
        for p in sorted(HOOKS.iterdir())
        if p.is_file() and not (p.stat().st_mode & stat.S_IXUSR)
    ]


if __name__ == "__main__":
    unittest.main()
