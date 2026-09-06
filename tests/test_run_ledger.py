"""Pillar 1 (Run Ledger) tests — quality persistence, run traces, viewers,
data-quality monitor, unit economics. All storage mocked or temp-dir'd."""

import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import data_quality, run_quality, run_trace, unit_economics
from core.run_ledger import render_dossier, render_traces

SCRIPT = (
    "Nobody saw this $2 billion collapse coming. The company lost everything in "
    "three weeks and the fallout is still spreading. Here is what actually "
    "happened and why it matters for everyone watching the sector."
)


def _mock_repo(runs=None):
    repo = MagicMock()
    repo.list_for_channel.return_value = runs or []
    repo.get.return_value = None
    return repo


class TestBuildQuality(unittest.TestCase):
    def test_scores_present_for_real_script(self):
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=_mock_repo(),
        ):
            q = run_quality.build_quality(
                script=SCRIPT,
                channel_id="tapin",
                features={"key_facts_count": 2, "ungrounded_entities": ["FooCorp"]},
            )
        self.assertIn("hook_score", q)
        self.assertIn("authenticity_score", q)
        self.assertEqual(q["ungrounded_count"], 1)
        self.assertEqual(q["trade_warning_count"], 0)
        self.assertEqual(q["tier_warning_count"], 0)
        self.assertEqual(q["fact_conflict_count"], 0)
        self.assertNotIn("claim_support_rate", q)  # verifier did not run
        self.assertEqual(q["quality_version"], run_quality.QUALITY_VERSION)

    def test_empty_script_returns_version_only(self):
        """Read the constant rather than pinning the literal: the version is
        meant to move when the schema does (v3 added the #645 length keys), and
        a hardcoded copy just reports the bump as a failure."""
        q = run_quality.build_quality(script="  ", channel_id="tapin")
        self.assertEqual(q["quality_version"], run_quality.QUALITY_VERSION)
        self.assertEqual(q["grade_version"], "v3")
        self.assertEqual(set(q), {"quality_version", "grade_version"})

    def test_pillar3_features_persist_into_quality(self):
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=_mock_repo(),
        ):
            q = run_quality.build_quality(
                script=SCRIPT,
                channel_id="tapin",
                features={
                    "tier_warnings": ["w1", "w2"],
                    "fact_conflicts": ["c1"],
                    "claim_verification": {
                        "total": 4,
                        "supported": 3,
                        "support_rate": 0.75,
                        "unsupported": ["bad claim"],
                    },
                },
            )
        self.assertEqual(q["tier_warning_count"], 2)
        self.assertEqual(q["fact_conflict_count"], 1)
        self.assertEqual(q["claim_support_rate"], 0.75)
        self.assertEqual(q["unsupported_claim_count"], 1)

    def test_none_support_rate_is_not_persisted(self):
        # Guard: a verifier that ran but returned a non-numeric support_rate must
        # not leave a non-numeric quality_json key for the calibration averages.
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=_mock_repo(),
        ):
            q = run_quality.build_quality(
                script=SCRIPT,
                channel_id="tapin",
                features={
                    "claim_verification": {
                        "total": 2,
                        "supported": 2,
                        "support_rate": None,
                        "unsupported": [],
                    },
                },
            )
        self.assertNotIn("claim_support_rate", q)
        self.assertEqual(q["unsupported_claim_count"], 0)  # count still recorded


class TestQualityPersistence(unittest.TestCase):
    def test_persist_writes_quality_json(self):
        repo = _mock_repo()
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            run_quality.persist_quality(7, {"hook_score": 55})
        run_id, data = repo.update.call_args[0]
        self.assertEqual(run_id, 7)
        self.assertEqual(json.loads(data["quality_json"])["hook_score"], 55)

    def test_persist_noop_without_run_id(self):
        repo = _mock_repo()
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            run_quality.persist_quality(None, {"hook_score": 55})
        repo.update.assert_not_called()

    def test_merge_preserves_existing_keys(self):
        repo = _mock_repo()
        record = MagicMock()
        record.quality_json = json.dumps({"hook_score": 60})
        repo.get.return_value = record
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            run_quality.merge_quality(3, {"thumbnail_overall": 71.0})
        _, data = repo.update.call_args[0]
        merged = json.loads(data["quality_json"])
        self.assertEqual(merged["hook_score"], 60)
        self.assertEqual(merged["thumbnail_overall"], 71.0)

    def test_load_quality_fail_open(self):
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            side_effect=RuntimeError("db down"),
        ):
            self.assertEqual(run_quality.load_quality(1), {})


class TraceCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(run_trace, "TRACES_DIR", self._tmp.name)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _write(self, run_id, **overrides):
        base = {
            "run_id": run_id,
            "channel_id": "tapin",
            "input_topic": "t",
            "selected_topic": "variant",
            "status": "drafted",
            "timings": {"signals_and_variants": 4.0, "content_package": 9.0},
            "signals": {"youtube": {"status": "ok", "active": True, "score": 5}},
            "features": {"cost": {"total": 0.02}},
            "quality": {"hook_score": 70, "authenticity_score": 80},
        }
        base.update(overrides)
        return run_trace.write_run_trace(**base)


class TestRunTrace(TraceCase):
    def test_write_read_roundtrip(self):
        path = self._write(11)
        self.assertIsNotNone(path)
        trace = run_trace.read_trace(11)
        self.assertEqual(trace["run_id"], 11)
        self.assertEqual(trace["quality"]["hook_score"], 70)
        self.assertEqual(trace["signals"]["youtube"]["status"], "ok")
        self.assertEqual(trace["cost"], {"total": 0.02})

    def test_no_run_id_is_noop(self):
        self.assertIsNone(self._write(None))

    def test_list_traces_newest_first_and_channel_filter(self):
        self._write(1)
        self._write(2)
        self._write(3, channel_id="moneywise")
        traces = run_trace.list_traces(limit=10)
        self.assertEqual([t["run_id"] for t in traces], [3, 2, 1])
        tapin_only = run_trace.list_traces(limit=10, channel_id="tapin")
        self.assertEqual([t["run_id"] for t in tapin_only], [2, 1])

    def test_write_stores_composite_score(self):
        self._write(21, composite_score=77.5)
        trace = run_trace.read_trace(21)
        self.assertEqual(trace["composite_score"], 77.5)

    def test_menu_path_and_intent_are_persisted_when_given(self):
        """#665. Traces could not say which menu option or intent produced a run."""
        self._write(31, menu_path="5", angle_intent="explainer")
        trace = run_trace.read_trace(31)
        self.assertEqual(trace["menu_path"], "5")
        self.assertEqual(trace["angle_intent"], "explainer")

    def test_omitted_menu_path_is_absent_not_invented(self):
        self._write(32)
        trace = run_trace.read_trace(32)
        self.assertNotIn("menu_path", trace)
        self.assertNotIn("angle_intent", trace)


class TestFinalizePersistsMenuPath(unittest.TestCase):
    def test_finalize_forwards_menu_path_and_intent(self):
        from core import pipeline

        captured: dict = {}

        def _capture(**kwargs):
            captured.update(kwargs)
            return "/tmp/trace.json"

        with (
            patch.object(pipeline, "record_content_run", return_value=88),
            patch.object(pipeline, "write_run_trace", side_effect=_capture),
            patch.object(pipeline, "build_quality", return_value={}),
            patch.object(pipeline, "persist_quality"),
            patch.object(pipeline, "write_run_dossier"),
            patch.object(pipeline, "record_learning_outcome"),
        ):
            pipeline._finalize_run(
                channel_id="tapin",
                input_topic="t",
                discovery=pipeline.DiscoveryResult(
                    input_topic="t", base_signals={}, evaluated=[], timings={}
                ),
                result=pipeline.PipelineResult(
                    topic="t",
                    score=0.0,
                    signals={},
                    script="s",
                    menu_path="5",
                    angle_intent="explainer",
                ),
            )
        self.assertEqual(captured["menu_path"], "5")
        self.assertEqual(captured["angle_intent"], "explainer")

    def test_finalize_omits_path_when_unset(self):
        from core import pipeline

        captured: dict = {}

        def _capture(**kwargs):
            captured.update(kwargs)
            return None

        with (
            patch.object(pipeline, "record_content_run", return_value=89),
            patch.object(pipeline, "write_run_trace", side_effect=_capture),
            patch.object(pipeline, "build_quality", return_value={}),
            patch.object(pipeline, "persist_quality"),
            patch.object(pipeline, "write_run_dossier"),
            patch.object(pipeline, "record_learning_outcome"),
        ):
            pipeline._finalize_run(
                channel_id="tapin",
                input_topic="t",
                discovery=pipeline.DiscoveryResult(
                    input_topic="t", base_signals={}, evaluated=[], timings={}
                ),
                result=pipeline.PipelineResult(topic="t", score=0.0, signals={}, script="s"),
            )
        self.assertIsNone(captured.get("menu_path"))
        self.assertIsNone(captured.get("angle_intent"))


class TestViewers(TraceCase):
    def test_render_traces_lists_runs(self):
        self._write(5, status="rendered")
        out = render_traces(limit=5)
        self.assertIn("#5", out)
        self.assertIn("rendered", out)
        self.assertIn("hook  70", out)

    def test_render_traces_empty(self):
        self.assertIn("No run traces yet", render_traces(limit=5))

    def test_render_dossier_joins_run_row(self):
        record = MagicMock()
        record.channel_id = "tapin"
        record.status = "rendered"
        record.selected_topic = "Marvel Rivals meta"
        record.input_topic = "Marvel Rivals"
        record.title = "The Meta Broke"
        record.composite_score = 82.0
        record.abort_reason = ""
        record.features_json = json.dumps(
            {"domain": "gaming", "cost": {"total": 0.05, "llm": 0.01}}
        )
        record.quality_json = json.dumps({"hook_score": 66, "hook_verdict": "solid"})
        record.timings_json = json.dumps({"content_package": 7.5})
        repo = _mock_repo()
        repo.get.return_value = record
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            out = render_dossier(9)
        self.assertIn("Run dossier - #9", out)
        self.assertIn("hook 66/100 (solid)", out)
        self.assertIn("$0.050", out)
        self.assertIn("(not uploaded)", out)
        # cp1252 regression: ops (no forced UTF-8 stdout) must be able to print it.
        out.encode("cp1252")

    def test_render_dossier_missing_run(self):
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=_mock_repo(),
        ):
            self.assertIn("No content run #42", render_dossier(42))


class TestDataQuality(TraceCase):
    def test_streak_and_failure_warnings(self):
        # newest 3 traces: 'news' failing every time -> streak warning
        for rid in (1, 2, 3):
            self._write(rid, signals={"news": {"status": "upstream_error"}})
        data = data_quality.gather()
        self.assertEqual(data["signals"]["streaks"].get("news"), 3)
        warns = data_quality.warnings(data)
        self.assertTrue(any("news" in w for w in warns))

    def test_healthy_signals_no_warnings(self):
        for rid in (1, 2, 3):
            self._write(rid)  # youtube ok
        data = data_quality.gather()
        self.assertEqual(data["signals"]["streaks"], {})
        self.assertEqual(data["signals"]["high_failure"], {})

    def test_inactive_is_not_a_failure(self):
        for rid in (1, 2, 3):
            self._write(rid, signals={"rawg": {"status": "inactive"}})
        self.assertEqual(data_quality.gather()["signals"]["streaks"], {})

    def test_join_checks_flag_missing_quality(self):
        run = MagicMock()
        run.status = "rendered"
        run.quality_json = "{}"
        run.features_json = json.dumps({"domain": "gaming"})
        repo = _mock_repo([run])
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            joins = data_quality.gather("tapin")["joins"]
        self.assertEqual(joins["missing_quality"], 1)
        self.assertEqual(joins["missing_features"], 0)


class TestUnitEconomics(unittest.TestCase):
    def _publish_row(self, run_id, metrics):
        row = MagicMock()
        row.id = run_id
        row.content_run_id = run_id
        row.youtube_video_id = f"vid{run_id}"
        row.detail = f"Video {run_id}"
        row.metrics_json = json.dumps(metrics)
        return row

    def _content_run(self, run_id, total_cost):
        run = MagicMock()
        run.id = run_id
        run.features_json = json.dumps({"cost": {"total": total_cost}})
        return run

    def test_margin_join(self):
        content_repo = _mock_repo([self._content_run(1, 0.40), self._content_run(2, 0.50)])
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = [
            self._publish_row(1, {"views": 100, "estimated_revenue_usd": 1.25}),
            self._publish_row(2, {"views": 50}),  # no revenue data
        ]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=content_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            econ = unit_economics.channel_economics("tapin")
        self.assertEqual(len(econ.videos), 2)
        by_run = {v.run_id: v for v in econ.videos}
        self.assertAlmostEqual(by_run[1].margin_usd, 0.85)
        self.assertIsNone(by_run[2].margin_usd)
        self.assertAlmostEqual(econ.total_cost, 0.90)
        self.assertAlmostEqual(econ.total_revenue, 1.25)
        self.assertAlmostEqual(econ.total_margin, 0.85)  # only revenue-covered videos

    def test_summary_lines_without_revenue(self):
        content_repo = _mock_repo([self._content_run(1, 0.40)])
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = [self._publish_row(1, {"views": 10})]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=content_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            econ = unit_economics.channel_economics("tapin")
        lines = unit_economics.summary_lines(econ)
        self.assertTrue(any("no data yet" in line for line in lines))


class TestEstimatedRevenueFetch(unittest.TestCase):
    def _service(self, rows=None, error=None):
        service = MagicMock()
        query = service.reports.return_value.query
        if error:
            query.return_value.execute.side_effect = error
        else:
            query.return_value.execute.return_value = {"rows": rows or []}
        return service

    def test_parses_revenue_row(self):
        from analytics.youtube_metrics import _fetch_estimated_revenue

        service = self._service(rows=[[1.2345]])
        self.assertEqual(
            _fetch_estimated_revenue("vid", service, "2026-06-01", "2026-06-28"), 1.2345
        )

    def test_missing_scope_reads_none(self):
        from analytics.youtube_metrics import _fetch_estimated_revenue

        service = self._service(error=RuntimeError("insufficient scope"))
        self.assertIsNone(_fetch_estimated_revenue("vid", service, "2026-06-01", "2026-06-28"))

    def test_no_rows_reads_none(self):
        from analytics.youtube_metrics import _fetch_estimated_revenue

        service = self._service(rows=[])
        self.assertIsNone(_fetch_estimated_revenue("vid", service, "2026-06-01", "2026-06-28"))


if __name__ == "__main__":
    unittest.main()
