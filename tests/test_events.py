"""Tests for core/events.py — outbound webhook events (requests mocked)."""

import unittest
from unittest.mock import patch

from core import events


class TestEmitEvent(unittest.TestCase):
    def test_disabled_without_url(self):
        with patch.dict("os.environ", {"EVENT_WEBHOOK_URL": ""}):
            self.assertFalse(events.events_enabled())
            self.assertFalse(events.emit_event("run_completed", {"x": 1}, wait=True))

    def test_delivers_envelope_synchronously(self):
        with (
            patch.dict("os.environ", {"EVENT_WEBHOOK_URL": "http://localhost:5678/hook"}),
            patch("requests.post") as post,
        ):
            sent = events.emit_event("video_published", {"video_id": "abc"}, wait=True)
        self.assertTrue(sent)
        post.assert_called_once()
        url = post.call_args.args[0]
        envelope = post.call_args.kwargs["json"]
        self.assertEqual(url, "http://localhost:5678/hook")
        self.assertEqual(envelope["event"], "video_published")
        self.assertEqual(envelope["payload"], {"video_id": "abc"})
        self.assertIn("at", envelope)

    def test_event_filter(self):
        env = {
            "EVENT_WEBHOOK_URL": "http://localhost:5678/hook",
            "EVENT_WEBHOOK_EVENTS": "video_published",
        }
        with patch.dict("os.environ", env), patch("requests.post") as post:
            self.assertFalse(events.emit_event("run_completed", {}, wait=True))
            self.assertTrue(events.emit_event("video_published", {}, wait=True))
        post.assert_called_once()

    def test_delivery_failure_never_raises(self):
        with (
            patch.dict("os.environ", {"EVENT_WEBHOOK_URL": "http://localhost:5678/hook"}),
            patch("requests.post", side_effect=OSError("connection refused")),
        ):
            # Attempted (True) but swallowed — the pipeline must never notice.
            self.assertTrue(events.emit_event("run_completed", {}, wait=True))

    def test_timeout_env_parsed(self):
        with patch.dict("os.environ", {"EVENT_WEBHOOK_TIMEOUT": "2.5"}):
            self.assertEqual(events._timeout(), 2.5)
        with patch.dict("os.environ", {"EVENT_WEBHOOK_TIMEOUT": "junk"}):
            self.assertEqual(events._timeout(), 5.0)

    def test_background_thread_delivery(self):
        import threading

        done = threading.Event()
        with (
            patch.dict("os.environ", {"EVENT_WEBHOOK_URL": "http://localhost:5678/hook"}),
            patch("requests.post", side_effect=lambda *a, **k: done.set()) as post,
        ):
            self.assertTrue(events.emit_event("batch_completed", {"n": 2}))
            self.assertTrue(done.wait(timeout=5), "background delivery never ran")
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
