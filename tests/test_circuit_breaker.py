"""Unit tests for the session signal circuit breaker in apis/register_signals.py."""

import time
import unittest
from unittest.mock import patch

from apis import register_signals as rs
from apis.signal_contract import (
    STATUS_AUTH,
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    STATUS_RATE_LIMIT,
    make_signal,
)


class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        rs.reset_session_breaker()

    def tearDown(self):
        rs.reset_session_breaker()

    def _record(self, name, status):
        rs._record_signal_health(name, make_signal(connected=False, active=False, status=status))

    def test_quota_trips_breaker(self):
        self._record("youtube_competitors", STATUS_QUOTA)
        self.assertIn("youtube_competitors", rs._disabled_signals())

    def test_auth_trips_breaker(self):
        self._record("twitter", STATUS_AUTH)
        self.assertIn("twitter", rs._disabled_signals())

    def test_no_key_trips_breaker(self):
        self._record("finnhub", STATUS_NO_KEY)
        self.assertIn("finnhub", rs._disabled_signals())

    def test_ok_and_inactive_do_not_trip(self):
        self._record("youtube", STATUS_OK)
        self._record("reddit", STATUS_INACTIVE)
        self.assertEqual(rs._disabled_signals(), set())

    def test_rate_limit_does_not_trip_permanently_by_default(self):
        # With the cooldown disabled, a 429 must not touch the session breaker.
        with patch.dict("os.environ", {"SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS": "0"}):
            self._record("twitter", STATUS_RATE_LIMIT)
        self.assertNotIn("twitter", rs._disabled_signals())

    def test_rate_limit_trips_when_env_enabled(self):
        with patch.dict("os.environ", {"SIGNAL_BREAKER_INCLUDE_RATE_LIMIT": "true"}):
            self._record("twitter", STATUS_RATE_LIMIT)
            self.assertIn("twitter", rs._disabled_signals())
        # Permanent trip, not a cooldown: survives cooldown expiry semantics.
        self.assertEqual(rs.signal_cooldowns(), {})

    def test_disabled_signal_excluded_from_active_sources(self):
        self._record("rawg", STATUS_QUOTA)
        sources = rs._active_signal_sources("Marvel Rivals new season meta")
        names = {n for n, _ in sources}
        self.assertNotIn("rawg", names)

    def test_breaker_disabled_via_env(self):
        with patch.dict("os.environ", {"SIGNAL_CIRCUIT_BREAKER": "false"}):
            self._record("youtube_competitors", STATUS_QUOTA)
            # When disabled, nothing is recorded and nothing is reported disabled.
            self.assertEqual(rs._disabled_signals(), set())

    def test_reset_clears_disabled(self):
        self._record("twitter", STATUS_AUTH)
        self.assertIn("twitter", rs._disabled_signals())
        rs.reset_session_breaker()
        self.assertEqual(rs._disabled_signals(), set())


class TestRateLimitCooldown(unittest.TestCase):
    """Timed disabled-until-T cooldown for transient 429s."""

    def setUp(self):
        rs.reset_session_breaker()

    def tearDown(self):
        rs.reset_session_breaker()

    def _record(self, name, status):
        rs._record_signal_health(name, make_signal(connected=False, active=False, status=status))

    def test_rate_limit_starts_cooldown(self):
        self._record("youtube_competitors", STATUS_RATE_LIMIT)
        self.assertIn("youtube_competitors", rs._disabled_signals())
        cooldowns = rs.signal_cooldowns()
        self.assertIn("youtube_competitors", cooldowns)
        # Until-timestamp is in the future (default 900s window).
        self.assertGreater(cooldowns["youtube_competitors"], time.time())

    def test_cooldown_expires_and_signal_recovers(self):
        self._record("reddit", STATUS_RATE_LIMIT)
        with rs._BREAKER_LOCK:
            rs._COOLDOWN_UNTIL["reddit"] = time.time() - 1  # force expiry
        self.assertNotIn("reddit", rs._disabled_signals())
        self.assertEqual(rs.signal_cooldowns(), {})

    def test_hard_statuses_do_not_start_cooldown(self):
        self._record("twitter", STATUS_QUOTA)
        self.assertEqual(rs.signal_cooldowns(), {})
        self.assertIn("twitter", rs._disabled_signals())  # permanent trip instead

    def test_cooldown_disabled_via_env(self):
        with patch.dict("os.environ", {"SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS": "0"}):
            self._record("reddit", STATUS_RATE_LIMIT)
        self.assertEqual(rs.signal_cooldowns(), {})
        self.assertNotIn("reddit", rs._disabled_signals())

    def test_cooling_signal_excluded_from_active_sources(self):
        self._record("rawg", STATUS_RATE_LIMIT)
        sources = rs._active_signal_sources("Marvel Rivals new season meta")
        names = {n for n, _ in sources}
        self.assertNotIn("rawg", names)

    def test_reset_clears_cooldowns(self):
        self._record("reddit", STATUS_RATE_LIMIT)
        self.assertNotEqual(rs.signal_cooldowns(), {})
        rs.reset_session_breaker()
        self.assertEqual(rs.signal_cooldowns(), {})

    def test_repeat_rate_limit_does_not_shorten_cooldown(self):
        self._record("reddit", STATUS_RATE_LIMIT)
        first = rs.signal_cooldowns()["reddit"]
        with patch.dict("os.environ", {"SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS": "1"}):
            self._record("reddit", STATUS_RATE_LIMIT)
        self.assertGreaterEqual(rs.signal_cooldowns()["reddit"], first)


if __name__ == "__main__":
    unittest.main()
