"""The commit-msg hook must actually be able to run.

`.githooks/commit-msg` rejects AI co-author trailers. AGENTS.md is explicit that the
hook exists because a written rule was not enough on its own — `e4d2242` landed a
trailer the commit after the rule was added.

A hook without the executable bit is skipped silently by git (it prints a hint to
stderr and commits anyway), so the file was shipped non-executable and enforced
nothing on a fresh clone. That is the docs/audit_2026-09.md §3 shape: a check that
reports success while not checking. Hence a test, not a fixed permission alone.

No network, no subprocess.
"""

from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path

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
        bad = [
            p.name
            for p in sorted(HOOKS.iterdir())
            if p.is_file() and not (p.stat().st_mode & stat.S_IXUSR)
        ]
        self.assertEqual(bad, [])

    def test_commit_msg_hook_still_guards_ai_attribution(self):
        body = (HOOKS / "commit-msg").read_text(encoding="utf-8")
        self.assertIn("co-authored-by:", body.lower())
        self.assertIn("generated with", body.lower())


if __name__ == "__main__":
    unittest.main()
