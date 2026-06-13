import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from analytics.post_timing import next_optimal_post_time


class TestUploadQueueReservation(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"USE_LEARNED_POST_SLOTS": "false"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    @patch("analytics.upload_queue.get_reserved_publish_times")
    def test_second_video_skips_first_reserved_slot(self, mock_reserved):
        first = datetime(2026, 6, 7, 23, 0, tzinfo=timezone.utc)
        mock_reserved.return_value = [first]
        after = datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc)
        second = next_optimal_post_time("tapin", "UFC 250", after=after)
        self.assertGreater(second, first)


if __name__ == "__main__":
    unittest.main()
