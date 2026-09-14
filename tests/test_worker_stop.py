"""Ctrl+C on `py -m jobs.worker --loop 30` printed a KeyboardInterrupt traceback (run 78)."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


class TestWorkerStopsCleanly(unittest.TestCase):
    def test_ctrl_c_in_the_poll_loop_exits_without_a_traceback(self):
        from jobs import worker

        out = io.StringIO()
        with (
            patch("sys.argv", ["worker", "--loop", "30"]),
            patch.object(worker, "process_one", return_value=False),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch.object(worker.time, "sleep", side_effect=KeyboardInterrupt),
            redirect_stdout(out),
        ):
            worker.main()
        self.assertIn("Worker stopped", out.getvalue())


if __name__ == "__main__":
    unittest.main()
