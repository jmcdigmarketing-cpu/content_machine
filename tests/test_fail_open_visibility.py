"""Fail-open must be fail-*visible* (decisions §24).

The project's dominant idiom is "never raise, degrade instead". That is correct, and it
is also how sources spent a month reporting "nothing found" instead of "I am broken"
(decisions §18). The 2026-08 audit counted 93 handlers that swallowed with a bare `pass`.

`S110`/`S112` in ruff now stop new ones appearing. These tests cover the half a linter
can't check: that the handlers guarding a *guarantee* speak at WARNING (visible at the
default `CONTENT_LOG_LEVEL`), that they say something useful, and — just as important —
that a healthy call stays silent, because a warning that always fires teaches the
operator to ignore warnings.

State file isolated per tests/CLAUDE.md.
"""

import logging
import os
import tempfile
import unittest
from unittest.mock import patch

from core import quota_governor as qg
from core import quota_state


class _IsolatedGovernor(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp.name, "q.json")
        )
        self._state_patch.start()

    def tearDown(self):
        self._state_patch.stop()
        self._tmp.cleanup()


class TestLostGuaranteesWarn(_IsolatedGovernor):
    """A swallow that costs the system a guarantee has to be visible by default."""

    LOGGER = "content_machine.core.quota_governor"

    def test_unpersisted_llm_spend_warns(self):
        # The daily-budget downgrade reads this ledger; a lost write makes it under-count
        # spend and quietly stop guarding, which is the expensive silent failure.
        with (
            patch.object(quota_state, "increment_value", side_effect=OSError("disk full")),
            self.assertLogs(self.LOGGER, level=logging.WARNING) as caught,
        ):
            qg.llm_add_spend(0.0431)
        message = "\n".join(caught.output)
        self.assertIn("0.0431", message)  # how much was lost
        self.assertIn("disk full", message)  # why

    def test_failed_signal_clear_warns(self):
        # The record survives, so a paid signal the operator just fixed stays disabled.
        with (
            patch.object(quota_state, "clear_exhausted", side_effect=OSError("locked")),
            self.assertLogs(self.LOGGER, level=logging.WARNING) as caught,
        ):
            qg.clear_signal("reddit")
        self.assertIn("reddit", "\n".join(caught.output))

    def test_failed_apify_clear_warns(self):
        with (
            patch.object(quota_state, "clear_exhausted", side_effect=OSError("locked")),
            self.assertLogs(self.LOGGER, level=logging.WARNING),
        ):
            qg.apify_clear("content_machine")

    def test_missing_run_trace_warns(self):
        # No trace means `ops traces`, `ops dossier` and data_quality's per-signal
        # failure rates are all blind for that run, with nothing else to notice it.
        from core import pipeline

        # record_content_run is stubbed too: unpatched it writes a real row to the live
        # DB (tests/CLAUDE.md), which is how this test first reported run 67 for run 77.
        with (
            patch.object(pipeline, "record_content_run", return_value=77),
            patch.object(pipeline, "write_run_trace", side_effect=OSError("no space")),
            patch.object(pipeline, "build_quality", return_value={}),
            patch.object(pipeline, "persist_quality"),
            patch.object(pipeline, "write_run_dossier"),
            patch.object(pipeline, "record_learning_outcome"),
            self.assertLogs("content_machine.pipeline", level=logging.WARNING) as caught,
        ):
            pipeline._finalize_run(
                channel_id="tapin",
                input_topic="t",
                discovery=pipeline.DiscoveryResult(
                    input_topic="t", base_signals={}, evaluated=[], timings={}
                ),
                result=pipeline.PipelineResult(
                    topic="t", score=0.0, signals={}, run_id=77, script="s"
                ),
            )
        self.assertIn("77", "\n".join(caught.output))


class TestHealthyRunsStaySilent(_IsolatedGovernor):
    """A warning that fires on a good run trains the operator to ignore warnings."""

    def test_successful_spend_write_is_quiet(self):
        with self.assertNoLogs("content_machine.core.quota_governor", level=logging.WARNING):
            qg.llm_add_spend(0.01)

    def test_successful_clear_is_quiet(self):
        qg.disable_signal("finnhub", "no_key")
        with self.assertNoLogs("content_machine.core.quota_governor", level=logging.WARNING):
            qg.clear_signal("finnhub")

    def test_best_effort_misses_stay_at_debug(self):
        # Enrichment that fails is not a lost guarantee — it must not reach WARNING.
        from core import creator_coach

        with (
            patch(
                "analytics.post_timing.get_recommended_time", side_effect=RuntimeError("no data")
            ),
            self.assertNoLogs("content_machine.core.creator_coach", level=logging.WARNING),
        ):
            creator_coach.build_coach("tapin")


if __name__ == "__main__":
    unittest.main()
