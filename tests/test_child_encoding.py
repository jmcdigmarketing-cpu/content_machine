"""Wave 79 (#1135): a module `ops` starts writes UTF-8 whatever its stdout is.

Found 2026-10-11 running `ops sync-metrics` through a pipe: the child process's stdout was
cp1252 and the first video line's check mark raised UnicodeEncodeError, so the sync stopped
before storing anything. `ops` had fixed its own stdout (#767) and every module it starts with
`_run_module` was a new process without the fix - the same death under Task Scheduler.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from unittest.mock import patch


class ChildEnvTests(unittest.TestCase):
    def test_a_child_module_is_told_to_write_utf8(self):
        from scripts import ops

        with patch.object(ops.subprocess, "call", return_value=0) as call:
            self.assertEqual(ops._run_module("analytics.sync_metrics", "--channel", "tapin"), 0)
        env = call.call_args.kwargs["env"]
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8:replace")
        self.assertEqual(
            call.call_args.args[0][1:], ["-m", "analytics.sync_metrics", "--channel", "tapin"]
        )

    def test_the_rest_of_the_environment_is_passed_through(self):
        from scripts import ops

        with patch.dict("os.environ", {"CONTENT_CHANNEL_ID": "tapin"}):
            env = ops._child_env()
        self.assertEqual(env["CONTENT_CHANNEL_ID"], "tapin")

    def test_an_encoding_the_operator_set_is_kept(self):
        from scripts import ops

        with patch.dict("os.environ", {"PYTHONIOENCODING": "utf-16"}):
            self.assertEqual(ops._child_env()["PYTHONIOENCODING"], "utf-16")

    def test_a_check_mark_survives_a_cp1252_pipe(self):
        """The real failure, reproduced: a child printing a check mark into a pipe."""
        from scripts import ops

        code = "print('  \\u2713 video')"
        env = ops._child_env()
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, env=env, timeout=60, check=False
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("✓", proc.stdout.decode("utf-8"))

    def test_the_sync_fixes_its_own_stdout_when_run_directly(self):
        from pathlib import Path

        text = (
            Path(__file__)
            .resolve()
            .parent.parent.joinpath("analytics", "sync_metrics.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn("ensure_utf8_stdout()", text)


if __name__ == "__main__":
    unittest.main()
