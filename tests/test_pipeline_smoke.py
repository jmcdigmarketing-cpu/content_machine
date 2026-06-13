import unittest
from unittest.mock import MagicMock, patch

from core.pipeline import DiscoveryResult, run_pipeline


class TestPipelineSmoke(unittest.TestCase):
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=99)
    @patch("core.pipeline.generate_content_package")
    @patch("core.pipeline.run_discovery")
    def test_run_pipeline_drafted_without_video(
        self, mock_discovery, mock_content, mock_record, mock_learn
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


if __name__ == "__main__":
    unittest.main()
