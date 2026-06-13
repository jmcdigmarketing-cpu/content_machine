import os
import unittest
from unittest.mock import MagicMock, patch

from publishing.repurpose import enqueue_repurpose_jobs


class TestRepurposeSmoke(unittest.TestCase):
    @patch("publishing.repurpose.enqueue_publish_job")
    def test_enqueues_youtube_job(self, mock_enqueue):
        mock_enqueue.return_value = MagicMock(id=42)

        with patch.dict(os.environ, {"REPURPOSE_PUBLISH_ENABLED": "true"}, clear=False):
            result = enqueue_repurpose_jobs(
                channel_id="tapin",
                content_run_id=7,
                file_path="output/video/x.mp4",
                title="Title",
                description="Desc",
                tags=["gaming"],
            )

        self.assertEqual(result.platforms, ["youtube"])
        mock_enqueue.assert_called_once()
        call = mock_enqueue.call_args.kwargs
        self.assertEqual(call["platform"], "youtube")
        self.assertEqual(call["content_run_id"], 7)

    @patch("publishing.repurpose.enqueue_publish_job")
    def test_skips_deferred_tiktok_in_publishers_list(self, mock_enqueue):
        mock_enqueue.return_value = MagicMock(id=1)

        with (
            patch(
                "publishing.repurpose.listed_publish_platforms",
                return_value=("youtube", "tiktok", "instagram"),
            ),
            patch("publishing.repurpose._repurpose_enabled", return_value=True),
        ):
            result = enqueue_repurpose_jobs(
                channel_id="tapin",
                content_run_id=3,
                file_path="a.mp4",
                title="T",
                description="D",
            )

        self.assertIn("tiktok", result.skipped_platforms)
        self.assertIn("instagram", result.skipped_platforms)
        self.assertEqual(mock_enqueue.call_count, 1)


if __name__ == "__main__":
    unittest.main()
