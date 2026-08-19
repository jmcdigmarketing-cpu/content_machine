"""Post-render cost must reach the ledger, not just the operator's screen.

Both operator render paths finalize the run *before* rendering: `main.py` calls
`run_pipeline(proceed_video=False)` then renders separately, and `auto_generate` does
the same. The stored cost therefore kept `tts: 0.0` on every rendered run, while
`core/unit_economics` computes contribution margin from `features_json.cost.total` —
so margin was overstated by roughly the entire TTS line, the largest cost of a render.
Live check on 2026-08-14: 38 rendered runs totalling $0.75 stored versus $11.77 real.

`main.py` did recompute the correct number, but only into a local dict for display.
These tests pin that the value is persisted and that the display reads it back.
"""

import json
import unittest
from typing import ClassVar
from unittest.mock import MagicMock, patch

from core import cost_meter


class TestRenderCostLines(unittest.TestCase):
    def test_prices_from_the_creator_plan_rate(self):
        # ElevenLabs Creator: $22 / 100k chars -> $0.22 per 1k.
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            lines = cost_meter.render_cost_lines("x" * 1000)
        self.assertAlmostEqual(lines["tts"], 0.22, places=4)

    def test_real_script_length(self):
        # Run 64: 1135 chars -> ~$0.25, versus a stored total of $0.0328.
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            self.assertAlmostEqual(cost_meter.render_cost_lines("x" * 1135)["tts"], 0.2497, 3)

    def test_local_provider_is_free(self):
        for provider in ("piper", "kokoro", "xtts"):
            with patch.dict("os.environ", {"TTS_PROVIDER": provider}, clear=False):
                self.assertEqual(cost_meter.render_cost_lines("x" * 5000)["tts"], 0.0)

    def test_empty_script_costs_nothing(self):
        self.assertEqual(cost_meter.render_cost_lines("")["tts"], 0.0)

    def test_rate_is_env_tunable(self):
        with patch.dict(
            "os.environ",
            {"TTS_PROVIDER": "elevenlabs", "COST_TTS_PER_1K_CHARS": "0.10"},
            clear=False,
        ):
            self.assertAlmostEqual(cost_meter.render_cost_lines("x" * 1000)["tts"], 0.10, places=4)


class TestMergeRenderCost(unittest.TestCase):
    STORED: ClassVar[dict[str, float]] = {
        "llm": 0.0048,
        "tts": 0.0,
        "apify": 0.02,
        "web_search": 0.008,
        "total": 0.0328,
    }

    def test_preserves_session_metered_lines(self):
        # llm/apify/web_search are already correct; only the render lines were missing.
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            merged = cost_meter.merge_render_cost(self.STORED, "x" * 1135)
        self.assertEqual(merged["llm"], 0.0048)
        self.assertEqual(merged["apify"], 0.02)
        self.assertEqual(merged["web_search"], 0.008)

    def test_total_is_recomputed_not_carried(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            merged = cost_meter.merge_render_cost(self.STORED, "x" * 1135)
        self.assertAlmostEqual(merged["total"], 0.2825, places=3)
        self.assertGreater(merged["total"], self.STORED["total"])

    def test_is_idempotent(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            once = cost_meter.merge_render_cost(self.STORED, "x" * 1135)
            twice = cost_meter.merge_render_cost(once, "x" * 1135)
        self.assertEqual(once, twice)

    def test_handles_missing_and_junk_input(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            self.assertIn("total", cost_meter.merge_render_cost(None, "x" * 100))
            merged = cost_meter.merge_render_cost({"llm": "not-a-number"}, "x" * 100)
        self.assertNotIn("llm", merged)  # unparseable lines are dropped, not crashed on

    def test_estimate_run_cost_still_agrees(self):
        # The extracted helper must not change the pre-existing full estimate.
        with patch.dict("os.environ", {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            full = cost_meter.estimate_run_cost(script="x" * 1135, signals={}, rendered=True)
            lines = cost_meter.render_cost_lines("x" * 1135)
        self.assertEqual(full["tts"], lines["tts"])

    def test_unrendered_estimate_has_no_tts(self):
        self.assertEqual(
            cost_meter.estimate_run_cost(script="x" * 1135, signals={}, rendered=False)["tts"], 0.0
        )


class TestMergeFeatures(unittest.TestCase):
    def _repo(self, features):
        record = MagicMock()
        record.features_json = json.dumps(features)
        repo = MagicMock()
        repo.get.return_value = record
        return repo

    def test_merges_without_clobbering_other_keys(self):
        from core.run_features import merge_features

        repo = self._repo({"domain": "gaming", "word_count": 191, "cost": {"tts": 0.0}})
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            merge_features(7, {"cost": {"tts": 0.25, "total": 0.28}})
        written = json.loads(repo.update.call_args[0][1]["features_json"])
        self.assertEqual(written["domain"], "gaming")
        self.assertEqual(written["word_count"], 191)
        self.assertEqual(written["cost"]["tts"], 0.25)

    def test_no_run_id_is_a_noop(self):
        from core.run_features import merge_features

        repo = self._repo({})
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            merge_features(None, {"cost": {}})
            merge_features(7, {})
        repo.update.assert_not_called()

    def test_db_failure_never_raises(self):
        from core.run_features import merge_features

        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            side_effect=OSError("db down"),
        ):
            merge_features(7, {"cost": {"tts": 0.25}})  # must not raise


class TestUpdateTrace(unittest.TestCase):
    def test_patches_status_and_cost(self):
        from core import run_trace

        existing = {"run_id": 64, "status": "drafted", "cost": {"total": 0.03}}
        written = {}
        with (
            patch.object(run_trace, "read_trace", return_value=dict(existing)),
            patch("builtins.open", MagicMock()),
            patch.object(run_trace.json, "dump", side_effect=lambda d, f, **k: written.update(d)),
        ):
            ok = run_trace.update_trace(64, {"status": "rendered", "cost": {"total": 0.28}})
        self.assertTrue(ok)
        self.assertEqual(written["status"], "rendered")
        self.assertEqual(written["cost"]["total"], 0.28)
        self.assertEqual(written["run_id"], 64)  # untouched keys survive

    def test_missing_trace_returns_false(self):
        from core.run_trace import update_trace

        with patch("core.run_trace.read_trace", return_value=None):
            self.assertFalse(update_trace(999, {"status": "rendered"}))

    def test_no_run_id_or_empty_patch(self):
        from core.run_trace import update_trace

        self.assertFalse(update_trace(None, {"status": "rendered"}))
        self.assertFalse(update_trace(1, {}))


class TestRunMediaOnlyPersists(unittest.TestCase):
    """The actual fix: `run_media_only` is the single choke point both flows share.

    `main.py` and `scripts/auto_generate.py` each call `run_pipeline(proceed_video=False)`
    and then render separately, so fixing it here fixes both at once.
    """

    SCRIPT = "x" * 1135

    def _render(self, *, run_id=64, stored_cost=None):
        from core import pipeline

        stored = {"word_count": 191, "cost": stored_cost} if stored_cost else {"word_count": 191}
        with (
            patch.dict(
                "os.environ",
                {
                    "TTS_PROVIDER": "elevenlabs",
                    "THUMBNAIL_MODE": "off",
                    "CONTENT_RENDER_PROGRESS": "0",
                },
                clear=False,
            ),
            patch.object(
                pipeline, "media_paths_for_topic", return_value=("a.mp3", "v.mp4", "out/v.mp4")
            ),
            patch.object(pipeline, "generate_audio"),
            patch.object(pipeline, "render_vertical_video", return_value=("v", "bg")),
            patch.object(pipeline, "update_content_run_media"),
            patch.object(pipeline, "record_render_assets"),
            patch("core.run_features.load_features", return_value=stored),
            patch("core.run_features.merge_features") as merge,
            patch("core.run_trace.update_trace") as trace,
        ):
            pipeline.run_media_only("topic", self.SCRIPT, channel_id="tapin", content_run_id=run_id)
        return merge, trace

    def test_cost_is_persisted_with_the_tts_line(self):
        merge, _ = self._render(
            stored_cost={"llm": 0.0048, "apify": 0.02, "web_search": 0.008, "total": 0.0328}
        )
        merge.assert_called_once()
        cost = merge.call_args[0][1]["cost"]
        self.assertAlmostEqual(cost["tts"], 0.2497, places=3)
        self.assertAlmostEqual(cost["total"], 0.2825, places=3)
        self.assertEqual(cost["llm"], 0.0048, "session-metered lines preserved")

    def test_trace_marked_rendered(self):
        _, trace = self._render()
        trace.assert_called_once()
        self.assertEqual(trace.call_args[0][1]["status"], "rendered")

    def test_no_run_id_skips_persistence(self):
        merge, trace = self._render(run_id=None)
        merge.assert_not_called()
        trace.assert_not_called()

    def test_bookkeeping_failure_never_fails_a_finished_render(self):
        from core import pipeline

        with (
            patch.dict(
                "os.environ",
                {"THUMBNAIL_MODE": "off", "CONTENT_RENDER_PROGRESS": "0"},
                clear=False,
            ),
            patch.object(
                pipeline, "media_paths_for_topic", return_value=("a.mp3", "v.mp4", "out/v.mp4")
            ),
            patch.object(pipeline, "generate_audio"),
            patch.object(pipeline, "render_vertical_video", return_value=("v", "bg")),
            patch.object(pipeline, "update_content_run_media"),
            patch.object(pipeline, "record_render_assets"),
            patch("core.run_features.load_features", side_effect=OSError("db down")),
        ):
            mp3, mp4, _ = pipeline.run_media_only(
                "topic", self.SCRIPT, channel_id="tapin", content_run_id=64
            )
        self.assertEqual(mp4, "out/v.mp4")  # render result still returned


class TestBackfillFeaturesPreservesCost(unittest.TestCase):
    """`--force` rebuilt features_json wholesale, and build_features has no cost block."""

    def test_force_rebuild_keeps_the_cost_ledger(self):
        from analytics.backfill_features import backfill_channel

        run = MagicMock()
        run.id = 42
        run.features_json = json.dumps(
            {"domain": "gaming", "cost": {"tts": 0.25, "total": 0.28}, "cost_estimated": True}
        )
        run.selected_topic = "Some topic"
        run.input_topic = "Some topic"
        run.title = "T"
        run.script_preview = "word " * 100
        run.timings_json = "{}"
        repo = MagicMock()
        repo.list_for_channel.return_value = [run]

        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            backfill_channel("tapin", force=True)

        written = json.loads(repo.update.call_args[0][1]["features_json"])
        self.assertEqual(written["cost"]["total"], 0.28, "cost must survive a forced rebuild")
        self.assertTrue(written["cost_estimated"])
        self.assertIn("word_count", written, "rebuilt features still present")


if __name__ == "__main__":
    unittest.main()
