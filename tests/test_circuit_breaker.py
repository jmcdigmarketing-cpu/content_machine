"""Unit tests for the session signal circuit breaker in apis/register_signals.py."""

import os
import tempfile
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
from core import quota_governor, quota_state


class _IsolatedStateCase(unittest.TestCase):
    """Redirect data/quota_state.json to a temp file — hard trips now persist,
    and tests must never poison the real cross-run state."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp.name, "q.json")
        )
        self._state_patch.start()
        rs.reset_session_breaker()

    def tearDown(self):
        rs.reset_session_breaker()
        self._state_patch.stop()
        self._tmp.cleanup()

    def _record(self, name, status):
        rs._record_signal_health(name, make_signal(connected=False, active=False, status=status))


class TestCircuitBreaker(_IsolatedStateCase):
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


class TestRateLimitCooldown(_IsolatedStateCase):
    """Timed disabled-until-T cooldown for transient 429s."""

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


class TestBreakerPersistence(_IsolatedStateCase):
    """Hard trips persist across runs via core/quota_governor.py."""

    def _simulate_fresh_process(self):
        # Clear session state WITHOUT reset_session_breaker (which also wipes
        # the persisted store) — the next _disabled_signals() re-reads it.
        with rs._BREAKER_LOCK:
            rs._SESSION_DISABLED.clear()
            rs._COOLDOWN_UNTIL.clear()
            rs._PERSISTED_DISABLED = set()
            rs._PERSISTED_SYNCED = False

    def test_hard_trip_survives_a_fresh_process(self):
        self._record("youtube_competitors", STATUS_QUOTA)
        self._simulate_fresh_process()
        self.assertIn("youtube_competitors", rs._disabled_signals())
        reasons = quota_governor.persisted_disabled_signals()
        self.assertIn("quota_exceeded", reasons["youtube_competitors"])

    def test_rate_limit_cooldown_is_not_persisted(self):
        self._record("twitter", STATUS_RATE_LIMIT)
        self.assertEqual(quota_governor.persisted_disabled_signals(), {})
        self._simulate_fresh_process()
        self.assertNotIn("twitter", rs._disabled_signals())

    def test_persistence_disabled_via_env(self):
        with patch.dict("os.environ", {"SIGNAL_BREAKER_PERSIST": "false"}):
            self._record("finnhub", STATUS_NO_KEY)
            self.assertEqual(quota_governor.persisted_disabled_signals(), {})
        self._simulate_fresh_process()
        self.assertNotIn("finnhub", rs._disabled_signals())

    def test_key_change_clears_persisted_record(self):
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "old-key"}):
            self._record("finnhub", STATUS_AUTH)
            self.assertIn("finnhub", quota_governor.persisted_disabled_signals())
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "rotated-key"}):
            self.assertEqual(quota_governor.persisted_disabled_signals(), {})
            self._simulate_fresh_process()
            self.assertNotIn("finnhub", rs._disabled_signals())

    def test_reset_session_breaker_clears_persisted(self):
        self._record("twitter", STATUS_AUTH)
        rs.reset_session_breaker()
        self.assertEqual(quota_governor.persisted_disabled_signals(), {})
        self.assertEqual(rs._disabled_signals(), set())

    def test_persisted_signal_excluded_from_active_sources(self):
        self._record("rawg", STATUS_QUOTA)
        self._simulate_fresh_process()
        names = {n for n, _ in rs._active_signal_sources("Marvel Rivals new season meta")}
        self.assertNotIn("rawg", names)


class TestEmpty200Quarantine(_IsolatedStateCase):
    """#394: three Tapology-class empty-200s session-disable; quota_state untouched.

    ``STATUS_INACTIVE`` is healthy no-match (Wikipedia has no page; Tapology is
    not an MMA topic). Only connected+empty with no skip-detail counts.
    """

    def _empty_200(self, name, *, detail="No Tapology event match"):
        rs._record_signal_health(
            name,
            make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail=detail,
            ),
        )

    def test_one_inactive_does_not_trip(self):
        self._empty_200("tapology")
        self.assertNotIn("tapology", rs._disabled_signals())

    def test_three_inactives_disable_the_fourth_without_persisting(self):
        for _ in range(3):
            self._empty_200("tapology")
        self.assertIn("tapology", rs._disabled_signals())
        self.assertEqual(quota_governor.persisted_disabled_signals(), {})
        state_path = quota_state.QUOTA_STATE_FILE
        if os.path.isfile(state_path):
            with open(state_path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertNotIn("tapology", body)

    def test_ok_resets_the_empty_streak(self):
        self._empty_200("tapology")
        self._empty_200("tapology")
        self._record("tapology", STATUS_OK)
        self._empty_200("tapology")
        self.assertNotIn("tapology", rs._disabled_signals())

    def test_wikipedia_empty_is_not_tapology_down(self):
        """A topic with no Wikipedia page is an answer, not a dead scraper."""
        for _ in range(3):
            self._empty_200("wikipedia", detail="no page for this topic")
        self.assertNotIn("wikipedia", rs._disabled_signals())
        self.assertNotIn("tapology", rs._disabled_signals())

    def test_domain_skip_does_not_quarantine_tapology(self):
        for _ in range(3):
            self._empty_200("tapology", detail="Not an MMA/UFC topic")
        self.assertNotIn("tapology", rs._disabled_signals())

    def test_a_lookup_signal_with_no_detail_is_not_quarantined(self):
        """rawg/odds/sports return connected+INACTIVE and NO status_detail when the
        topic is outside their domain (apis/rawg_api.py:166, odds_api.py:61,
        sports_data_api.py:76). A batch over three non-game topics must not cost
        the next GTA topic its RAWG data."""
        for name in ("rawg", "odds", "sports"):
            with self.subTest(signal=name):
                for _ in range(3):
                    self._empty_200(name, detail="")
                self.assertNotIn(name, rs._disabled_signals())

    def test_the_scraper_class_signal_still_quarantines_with_no_detail(self):
        for _ in range(3):
            self._empty_200("tapology", detail="")
        self.assertIn("tapology", rs._disabled_signals())


if __name__ == "__main__":
    unittest.main()
