"""#462: a log line emitted during a run carries that run's id.

Traces already store the run id. The log format did not, so the two could not
be joined. A line with no run bound stays as it was, and ` [WARNING] ` stays
so the log tail can still find warnings.
"""

from __future__ import annotations

import io
import logging
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core import logging as cm_logging


class RunLogTests(unittest.TestCase):
    def _fresh(self):
        root = logging.getLogger()
        app = logging.getLogger("content_machine")
        saved = (root.handlers[:], app.handlers[:], app.level, cm_logging._CONFIGURED)
        screen = io.StringIO()
        root.handlers[:] = []
        app.handlers[:] = []
        cm_logging._CONFIGURED = False
        return root, app, saved, screen

    def _restore(self, root, app, saved):
        for handler in list(app.handlers) + list(root.handlers):
            handler.close()
        root.handlers[:] = saved[0]
        app.handlers[:] = saved[1]
        app.setLevel(saved[2])
        cm_logging._CONFIGURED = saved[3]
        cm_logging.clear_run()

    def test_a_bound_run_is_on_the_line_and_an_unbound_line_is_unchanged(self):
        root, app, saved, screen = self._fresh()
        try:
            with (
                patch.dict(os_environ(), {"CONTENT_LOG_FILE": "", "CONTENT_LOG_LEVEL": "WARNING"}),
                patch("sys.stdout", screen),
            ):
                cm_logging.setup_logging()
                log = cm_logging.get_logger("run_log_test")
                log.warning("before any run")
                token = cm_logging.bind_run(71)
                log.warning("during the run")
                cm_logging.clear_run(token)
                log.warning("after the run")
            for handler in root.handlers:
                handler.flush()
        finally:
            self._restore(root, app, saved)
        text = screen.getvalue()
        before, during, after = [
            line for line in text.splitlines() if "the run" in line or "any run" in line
        ]
        self.assertNotIn("run=", before)
        self.assertIn("run=71", during)
        self.assertIn(" [WARNING] ", during)
        self.assertNotIn("run=", after)
        self.assertIn(" [WARNING] ", before)

    def test_a_worker_submitted_after_the_bind_keeps_the_run(self):
        root, app, saved, screen = self._fresh()
        try:
            with (
                patch.dict(os_environ(), {"CONTENT_LOG_FILE": "", "CONTENT_LOG_LEVEL": "WARNING"}),
                patch("sys.stdout", screen),
            ):
                cm_logging.setup_logging()
                log = cm_logging.get_logger("run_log_worker")

                def shout():
                    log.warning("from the worker")

                token = cm_logging.bind_run(88)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    cm_logging.submit_in_run(pool, shout).result()
                cm_logging.clear_run(token)
            for handler in root.handlers:
                handler.flush()
        finally:
            self._restore(root, app, saved)
        self.assertIn("run=88", screen.getvalue())
        self.assertIn("from the worker", screen.getvalue())


def os_environ():
    import os

    return os.environ
