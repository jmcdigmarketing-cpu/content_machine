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


if __name__ == "__main__":
    unittest.main()
