"""Pillar 5 (Agent layer) tests — Channel Health Agent, weekly analyst agent,
overnight operator. All storage/LLM/vault mocked; no real DB, network, or vault."""

import json
import unittest
from unittest.mock import MagicMock, patch

from core import analyst_agent, channel_health, overnight


def _run(run_id, auth=85):
    r = MagicMock()
    r.id = run_id
    r.quality_json = json.dumps({"hook_score": 70, "authenticity_score": auth})
    return r


class TestChannelHealth(unittest.TestCase):
    def test_healthy_channel_reads_green(self):
        econ = MagicMock(videos=[1, 2, 3], total_cost=0.12, total_margin=None)  # $0.04/video
        rates = {i: 0.35 for i in range(1, 9)}
        runs = [_run(i, auth=85) for i in range(1, 6)]
        with (
            patch("core.engagement_predictor.run_engagement_map", return_value=rates),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=MagicMock(list_for_channel=MagicMock(return_value=runs)),
            ),
            patch("core.reliability.gather", return_value={"apify": {}, "llm": {}, "signals": {}}),
            patch("core.unit_economics.channel_economics", return_value=econ),
            patch("core.data_quality.warnings", return_value=[]),
            patch(
                "core.cadence.cadence_status",
                return_value=MagicMock(total=2, cap=5, window_days=7),
            ),
        ):
            report = channel_health.build_health("tapin")
        self.assertEqual(report.overall, "green")
        self.assertEqual(
            {s.name for s in report.subs},
            {"engagement", "cadence", "authenticity", "reliability", "cost", "data quality"},
        )

    def test_declining_engagement_and_breaker_go_red(self):
        econ = MagicMock(videos=[1], total_cost=0.5, total_margin=-0.3)  # negative margin -> red
        # engagement declining: early high, recent low
        rates = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.1, 6: 0.1, 7: 0.1, 8: 0.1}
        runs = [_run(i, auth=40) for i in range(1, 6)]  # low authenticity -> red
        with (
            patch("core.engagement_predictor.run_engagement_map", return_value=rates),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=MagicMock(list_for_channel=MagicMock(return_value=runs)),
            ),
            patch(
                "core.reliability.gather",
                return_value={
                    "apify": {"disabled": True},
                    "llm": {"disabled_providers": {"deepseek": "x"}},
                    "signals": {},
                },
            ),
            patch("core.unit_economics.channel_economics", return_value=econ),
            patch("core.data_quality.warnings", return_value=["a", "b", "c"]),
            patch(
                "core.cadence.cadence_status",
                return_value=MagicMock(total=6, cap=5, window_days=7),  # over cap
            ),
        ):
            report = channel_health.build_health("tapin")
        self.assertEqual(report.overall, "red")
        by = {s.name: s.status for s in report.subs}
        self.assertEqual(by["engagement"], "red")
        self.assertEqual(by["authenticity"], "red")
        self.assertEqual(by["cadence"], "red")
        self.assertEqual(by["cost"], "red")

    def test_thin_data_never_green(self):
        econ = MagicMock(videos=[], total_cost=0.0, total_margin=None)
        with (
            patch("core.engagement_predictor.run_engagement_map", return_value={}),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=MagicMock(list_for_channel=MagicMock(return_value=[])),
            ),
            patch("core.reliability.gather", return_value={"apify": {}, "llm": {}, "signals": {}}),
            patch("core.unit_economics.channel_economics", return_value=econ),
            patch("core.data_quality.warnings", return_value=[]),
            patch(
                "core.cadence.cadence_status",
                return_value=MagicMock(total=0, cap=5, window_days=7),
            ),
        ):
            report = channel_health.build_health("tapin")
        self.assertEqual(report.overall, "yellow")  # collecting, not green

    def test_sub_failure_is_fail_open(self):
        with (
            patch(
                "core.engagement_predictor.run_engagement_map",
                side_effect=RuntimeError("db"),
            ),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                side_effect=RuntimeError("db"),
            ),
            patch("core.reliability.gather", side_effect=RuntimeError("x")),
            patch("core.unit_economics.channel_economics", side_effect=RuntimeError("x")),
            patch("core.data_quality.warnings", side_effect=RuntimeError("x")),
            patch("core.cadence.cadence_status", side_effect=RuntimeError("x")),
        ):
            report = channel_health.build_health("tapin")
        # Never raises; every sub degrades to yellow n/a.
        self.assertTrue(all(s.status == "yellow" for s in report.subs))
        self.assertEqual(report.overall, "yellow")
        # cp1252-safe render.
        channel_health.render_health(report).encode("cp1252")


class TestAnalystAgent(unittest.TestCase):
    def test_uses_llm_when_available(self):
        with (
            patch("core.analyst_agent._gather_context", return_value="## Weekly\ndata"),
            patch("core.llm_router.complete", return_value="  Headline. Do X.  ") as mock_llm,
            patch("core.vault_dossiers.write_report_note", return_value=None),
            patch("core.events.emit_event", return_value=True) as mock_evt,
        ):
            out = analyst_agent.run_analyst("tapin")
        self.assertEqual(out, "Headline. Do X.")
        self.assertEqual(mock_llm.call_args.kwargs["tier"], "premium")
        self.assertEqual(mock_evt.call_args[0][0], "analyst_briefing")

    def test_falls_back_to_rules_on_llm_error(self):
        report = {"ready": True}
        with (
            patch("core.analyst_agent._gather_context", return_value="ctx"),
            patch("core.llm_router.complete", side_effect=RuntimeError("no key")),
            patch("analytics.weekly_report.build_report", return_value=report),
            patch(
                "analytics.weekly_report.build_next_actions",
                return_value=["Lead with the fraud angle", "Retire recaps"],
            ),
            patch("core.vault_dossiers.write_report_note", return_value=None),
            patch("core.events.emit_event", return_value=True),
        ):
            out = analyst_agent.build_analyst_brief("tapin")
        self.assertIn("rules fallback", out)
        self.assertIn("fraud angle", out)

    def test_empty_context_uses_fallback(self):
        with (
            patch("core.analyst_agent._gather_context", return_value=""),
            patch("analytics.weekly_report.build_report", return_value={"ready": False}),
            patch("core.llm_router.complete") as mock_llm,
        ):
            out = analyst_agent.build_analyst_brief("tapin")
        mock_llm.assert_not_called()  # no context -> no spend
        self.assertIn("Not enough measured history", out)


class TestOvernight(unittest.TestCase):
    def _mk_outcome(self, ok, run_id):
        o = MagicMock()
        o.ok = ok
        o.run_id = run_id
        o.title = f"T{run_id}"
        return o

    def test_chains_batch_dossiers_health_and_event(self):
        outcomes = [
            self._mk_outcome(True, 10),
            self._mk_outcome(True, 11),
            self._mk_outcome(False, None),
        ]
        with (
            patch("core.batch_generation.collect_topics", return_value=["a", "b", "c"]),
            patch("core.batch_generation.run_batch", return_value=outcomes) as mock_batch,
            patch("core.vault_dossiers.write_run_dossier", return_value="path") as mock_doss,
            patch("core.channel_health.build_health", return_value=MagicMock()),
            patch("core.channel_health.health_line", return_value="Health: GREEN"),
            patch("core.events.emit_event", return_value=True) as mock_evt,
        ):
            result = overnight.run_overnight("tapin", count=3)
        mock_batch.assert_called_once_with("tapin", ["a", "b", "c"])
        self.assertEqual(result.drafted, 2)
        self.assertEqual(result.dossiers, 2)  # only the two ok+run_id outcomes
        self.assertEqual(mock_doss.call_count, 2)
        self.assertEqual(mock_evt.call_args[0][0], "overnight_completed")
        self.assertEqual(result.health_line, "Health: GREEN")

    def test_no_topics_is_noop(self):
        with (
            patch("core.batch_generation.collect_topics", return_value=[]),
            patch("core.batch_generation.run_batch") as mock_batch,
        ):
            result = overnight.run_overnight("tapin")
        mock_batch.assert_not_called()
        self.assertEqual(result.requested, 0)
        self.assertIn("Nothing done", overnight.render_overnight(result))


if __name__ == "__main__":
    unittest.main()
