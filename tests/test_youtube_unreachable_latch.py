"""Run 74: one dead endpoint cost two signals and most of the discovery wall-clock.

    Youtube: OFF — The read operation timed out
    Youtube_comments: OFF — The read operation timed out
    Completed in 37.8s

`youtube` and `youtube_comments` both go through `apis/youtube_api`, and both sat
on the 15-second socket timeout before giving up — 30 of the run's 37.8 seconds,
for nothing. A read timeout is transient, so the session breaker (which trips on
hard statuses like quota and auth) never fired.

A process-level latch closes the gap without touching the breaker: once the Data
API has timed out, later calls in the same process fail immediately instead of
waiting out the timeout again. It is deliberately narrow — only a timeout arms
it, and `reset_api_unreachable()` clears it, because a latch that survives a
transient blip would silently disable a working signal for a whole session.
"""

from __future__ import annotations

import socket
import unittest

from apis import youtube_api


class _Case(unittest.TestCase):
    def setUp(self):
        youtube_api.reset_api_unreachable()
        self.addCleanup(youtube_api.reset_api_unreachable)


class TestTheLatchArmsOnlyOnATimeout(_Case):
    def test_clean_by_default(self):
        self.assertEqual(youtube_api.api_unreachable(), "")

    def test_a_socket_timeout_arms_it(self):
        youtube_api.note_api_failure(TimeoutError("The read operation timed out"))
        self.assertTrue(youtube_api.api_unreachable())

    def test_a_timeout_error_arms_it(self):
        youtube_api.note_api_failure(TimeoutError("timed out"))
        self.assertTrue(youtube_api.api_unreachable())

    def test_a_message_that_only_says_timed_out_arms_it(self):
        youtube_api.note_api_failure(OSError("The read operation timed out"))
        self.assertTrue(youtube_api.api_unreachable())

    def test_a_quota_error_does_not_arm_it(self):
        youtube_api.note_api_failure(RuntimeError("quotaExceeded"))
        self.assertEqual(youtube_api.api_unreachable(), "")

    def test_an_auth_error_does_not_arm_it(self):
        youtube_api.note_api_failure(RuntimeError("API key not valid"))
        self.assertEqual(youtube_api.api_unreachable(), "")


class TestTheLatchIsClearable(_Case):
    def test_reset_clears_it(self):
        youtube_api.note_api_failure(TimeoutError("timed out"))
        youtube_api.reset_api_unreachable()
        self.assertEqual(youtube_api.api_unreachable(), "")


class TestTheReasonIsCarriedNotInvented(_Case):
    def test_the_original_message_survives(self):
        youtube_api.note_api_failure(TimeoutError("The read operation timed out"))
        self.assertIn("timed out", youtube_api.api_unreachable().lower())


class TestTheTimeoutDefaultIsBounded(unittest.TestCase):
    def test_the_default_is_no_longer_fifteen_seconds(self):
        # Two signals x 15s was 30s of a 37.8s discovery.
        self.assertLessEqual(youtube_api.api_timeout(), 8.0)

    def test_it_is_still_long_enough_to_be_a_real_attempt(self):
        self.assertGreaterEqual(youtube_api.api_timeout(), 3.0)


class TestTheSharedCallPathHonoursTheLatch(_Case):
    """`_search_videos` is what both the youtube and youtube_comments signals use."""

    def test_a_timeout_on_the_first_call_arms_the_latch(self):
        class _Boom:
            def search(self):
                raise TimeoutError("The read operation timed out")

        with self.assertRaises(socket.timeout):
            youtube_api._search_videos(_Boom(), "gta 6")
        self.assertTrue(youtube_api.api_unreachable())

    def test_the_second_signal_fails_fast_instead_of_waiting(self):
        called = []

        class _Counting:
            def search(self):
                called.append(1)
                raise AssertionError("must not reach the network")

        youtube_api.note_api_failure(TimeoutError("The read operation timed out"))
        with self.assertRaises(TimeoutError):
            youtube_api._search_videos(_Counting(), "gta 6")
        self.assertEqual(called, [])

    def test_a_quota_error_leaves_later_calls_alone(self):
        class _Quota:
            def search(self):
                raise RuntimeError("quotaExceeded")

        with self.assertRaises(RuntimeError):
            youtube_api._search_videos(_Quota(), "gta 6")
        self.assertEqual(youtube_api.api_unreachable(), "")


if __name__ == "__main__":
    unittest.main()
