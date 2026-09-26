"""#839: the commit-msg hook refuses a non-ASCII subject and warns on a non-ASCII body.

The ASCII rule for commit messages was written down but not enforced, which is how the
#838 arrow glyph reached `main`. Git hands the hook the raw editor file - `#` comment
lines and the `-v` scissors diff included - so those must not trip it.
Runs the real hook under `sh`; skipped where no POSIX shell exists.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".githooks" / "commit-msg"
SIGNED = "\n\nCo-Authored-By: Someone <x@example.com>\n"


@unittest.skipUnless(shutil.which("sh"), "needs a POSIX sh")
class CommitMsgAsciiTests(unittest.TestCase):
    def _run(self, text: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "COMMIT_EDITMSG"
            path.write_bytes(text.encode("utf-8"))
            return subprocess.run(
                ["sh", str(HOOK), str(path)], capture_output=True, text=True, check=False
            )

    def test_ascii_message_passes(self):
        self.assertEqual(self._run("Fix the queue -> slot mapping" + SIGNED).returncode, 0)

    def test_non_ascii_subject_is_rejected(self):
        proc = self._run("Fix the queue → slot mapping" + SIGNED)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ASCII", proc.stderr)

    def test_non_ascii_body_warns_but_passes(self):
        proc = self._run("Fix the queue" + "\n\nWas broken — now fixed." + SIGNED)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("ASCII", proc.stderr)

    def test_comment_lines_and_scissors_are_ignored(self):
        text = (
            "# Please enter the commit message — lines starting with '#' are ignored\n"
            "Fix the queue"
            + SIGNED
            + "# ------------------------ >8 ------------------------\n"
            + "diff --git a/x b/x\n+café\n"
        )
        proc = self._run(text)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ASCII", proc.stderr)


if __name__ == "__main__":
    unittest.main()
