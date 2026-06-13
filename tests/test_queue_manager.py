import unittest
from unittest.mock import MagicMock, patch

from youtube.upload import _result_from_existing_log


class TestQueueManager(unittest.TestCase):
    def test_cancelled_log_allows_reupload(self):
        existing = MagicMock()
        existing.status = "cancelled"
        existing.youtube_video_id = "abc"
        existing.id = 1
        self.assertIsNone(_result_from_existing_log(existing))


if __name__ == "__main__":
    unittest.main()
