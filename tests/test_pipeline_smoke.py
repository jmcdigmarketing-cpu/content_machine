import unittest
from unittest.mock import MagicMock, patch

from core.pipeline import DiscoveryResult, run_pipeline


class TestPipelineSmoke(unittest.TestCase):
    # Ledger writes (quality/trace) are patched so the test never touches the
    # real DB or data/traces/ — see tests/CLAUDE.md.
    @patch("core.pipeline.write_run_trace")
    @patch("core.pipeline.persist_quality")
    @patch("core.pipeline.build_quality", return_value={})
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=99)
    @patch("core.pipeline.generate_content_package")
    @patch("core.pipeline.run_discovery")
    def test_run_pipeline_drafted_without_video(
        self, mock_discovery, mock_content, mock_record, mock_learn, _bq, _pq, mock_trace
    ):
        discovery = DiscoveryResult(
            input_topic="Marvel Rivals meta",
            base_signals={"youtube": {"connected": True, "active": True, "score": 50}},
            evaluated=[
                (
                    "Marvel Rivals meta dead",
                    72.0,
                    {"youtube": {"connected": True, "active": True, "score": 55}},
                )
            ],
            channel_id="tapin",
        )
        mock_discovery.return_value = discovery
        mock_content.return_value = {
            "title": "Test",
            "script": "Hook line.",
            "description": "Desc",
        }

        result = run_pipeline(
            "Marvel Rivals meta",
            discovery=discovery,
            proceed_video=False,
            channel_id="tapin",
        )

        self.assertTrue(result.aborted)
        self.assertEqual(result.abort_reason, "proceed_video=False")
        self.assertEqual(result.run_id, 99)
        self.assertEqual(result.title, "Test")
        mock_learn.assert_called_once()
        mock_trace.assert_called_once()  # ledger trace written for drafted runs too

    @patch("core.pipeline.write_run_trace")
    @patch("core.pipeline.persist_quality")
    @patch("core.pipeline.build_quality", return_value={})
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=7)
    @patch("core.pipeline.generate_content_package")
    @patch("core.pipeline.run_discovery")
    def test_fact_engine_outputs_flow_into_features(
        self, mock_discovery, mock_content, mock_record, mock_learn, _bq, _pq, _tr
    ):
        """Pillar 3: tier warnings, conflicts, and verifier output reach features."""
        discovery = DiscoveryResult(
            input_topic="UFC 350",
            base_signals={},
            evaluated=[("UFC 350 recap", 70.0, {})],
            channel_id="tapin",
        )
        mock_discovery.return_value = discovery
        verification = {"total": 3, "supported": 2, "unsupported": ["bad claim"]}
        mock_content.return_value = {
            "title": "T",
            "script": "S",
            "description": "D",
            "tier_warnings": ["tier warning"],
            "fact_conflicts": ["conflict"],
            "fact_conflicts_dropped": 1,
            "claim_verification": verification,
        }

        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            result = run_pipeline(
                "UFC 350",
                discovery=discovery,
                proceed_video=False,
                channel_id="tapin",
            )

        self.assertEqual(result.features["tier_warnings"], ["tier warning"])
        self.assertEqual(result.features["fact_conflicts"], ["conflict"])
        self.assertEqual(result.features["fact_conflicts_dropped"], 1)
        self.assertEqual(result.features["claim_verification"], verification)


if __name__ == "__main__":
    unittest.main()
