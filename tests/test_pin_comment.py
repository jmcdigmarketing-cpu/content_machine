"""#105 opt-in pin of a clean answer to the top youtube_comments question."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from apis.youtube_comments_signal import _is_clean


class TestPinTopComment(unittest.TestCase):
    def test_opt_in_required(self):
        from youtube.pin_comment import maybe_pin_top_answer

        service = MagicMock()
        with patch.dict(os.environ, {"YOUTUBE_PIN_COMMENT": ""}, clear=False):
            os.environ.pop("YOUTUBE_PIN_COMMENT", None)
            result = maybe_pin_top_answer(
                service,
                video_id="vid1",
                topic="GTA 6 leak",
                questions=["When does GTA 6 actually release on PlayStation?"],
            )
        self.assertEqual(result.status, "skipped")
        service.commentThreads.assert_not_called()

    def test_profanity_filter_stays_in_front(self):
        from youtube.pin_comment import maybe_pin_top_answer

        dirty = "When the fuck does GTA 6 drop?"
        self.assertFalse(_is_clean(dirty))
        service = MagicMock()
        with patch.dict(os.environ, {"YOUTUBE_PIN_COMMENT": "true"}, clear=False):
            result = maybe_pin_top_answer(
                service,
                video_id="vid1",
                topic="GTA 6 leak",
                questions=[dirty],
            )
        self.assertEqual(result.status, "skipped")
        service.commentThreads.assert_not_called()

    def test_posts_channel_answer_for_clean_question(self):
        from youtube.pin_comment import maybe_pin_top_answer

        service = MagicMock()
        service.commentThreads.return_value.insert.return_value.execute.return_value = {
            "id": "thread1"
        }
        question = "When does GTA 6 actually release on PlayStation?"
        monday = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "YOUTUBE_PIN_COMMENT": "true",
                "PIN_COMMENT_FILE": os.path.join(tmp, "pins.json"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = maybe_pin_top_answer(
                    service,
                    video_id="vid1",
                    topic="GTA 6 leak",
                    questions=[question],
                    channel_id="tapin",
                    now=monday,
                )
        self.assertEqual(result.status, "scheduled")
        service.commentThreads.assert_not_called()
        self.assertIn("T", result.detail or "")


if __name__ == "__main__":
    unittest.main()
