"""#811: discovery blocks on its slowest signal.

Signals already run concurrently, but `build_registry` waits for the last
future to land - median 58.7 s and max 114.6 s across the recorded runs, set by
one straggler while everything else finished in seconds.

The fix is a wall-clock budget, following wave 27's `RESEARCH_BRIEF_DEADLINE_S`
pattern. Two things this must not break:

- a dropped signal still returns a `make_signal()`-shaped dict (several tests
  key off that shape), reusing `STATUS_UNAVAILABLE` - the status
  `classify_exception` already gives a timeout, and deliberately one that does
  *not* trip the session breaker, so the signal is simply retried next run;
- the dropped names go in `DiscoveryResult.meta`, never `timings` (#813: the
  intelligence report sums that dict and prints every key as seconds).
"""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from apis.signal_contract import STATUS_OK, STATUS_UNAVAILABLE, make_signal

_SLOW_SLEEP = 3.0


def _fast(_topic):
    return make_signal(connected=True, active=True, score=50, confidence=0.9)


def _slow(_topic):
    time.sleep(_SLOW_SLEEP)
    return make_signal(connected=True, active=True, score=99, confidence=0.9)


class _RegistryCase(unittest.TestCase):
    """Isolates the signal cache — no test may write the real signal_cache.json."""

    def _build(self, topic="a topic", **env):
        from apis.register_signals import build_registry

        sources = (("fast", _fast), ("slow", _slow))
        with (
            patch("apis.register_signals._active_signal_sources", return_value=sources),
            patch("apis.register_signals.start_youtube_warmup_background"),
            patch("apis.register_signals.get_cached", return_value=None),
            patch("apis.register_signals.set_cache"),
            patch("apis.register_signals._two_stage_web", return_value=False),
            patch("apis.register_signals._fanout_enabled", return_value=False),
            patch("core.discovery_headroom.emit_headroom"),
            patch.dict(os.environ, env, clear=False),
        ):
            started = time.perf_counter()
            results = build_registry(topic)
            return results, time.perf_counter() - started


class TestDiscoveryDeadline(_RegistryCase):
    def test_a_straggler_does_not_hold_the_run(self) -> None:
        results, elapsed = self._build(DISCOVERY_DEADLINE_S="0.3")
        self.assertLess(elapsed, _SLOW_SLEEP - 1.0, f"waited {elapsed:.1f}s for the straggler")
        self.assertEqual(results["fast"]["status"], STATUS_OK)

    def test_the_dropped_signal_keeps_the_contract_shape(self) -> None:
        results, _ = self._build(DISCOVERY_DEADLINE_S="0.3")
        dropped = results["slow"]
        for key in ("connected", "active", "score", "confidence", "data", "status"):
            self.assertIn(key, dropped)
        self.assertEqual(dropped["status"], STATUS_UNAVAILABLE)
        self.assertFalse(dropped["active"])
        self.assertIn("deadline", (dropped["status_detail"] or "").lower())

    def test_which_signals_were_dropped_is_recorded(self) -> None:
        results, _ = self._build(DISCOVERY_DEADLINE_S="0.3")
        meta = results.get("_deadline") or {}
        self.assertEqual(meta.get("dropped"), ["slow"])
        self.assertAlmostEqual(float(meta.get("budget_s")), 0.3, places=3)

    def test_the_deadline_is_off_by_default(self) -> None:
        """Unset means the previous behaviour exactly — wait for everything."""
        results, elapsed = self._build(DISCOVERY_DEADLINE_S="")
        self.assertGreaterEqual(elapsed, _SLOW_SLEEP - 0.5)
        self.assertEqual(results["slow"]["status"], STATUS_OK)
        self.assertNotIn("_deadline", results)

    def test_nothing_is_dropped_when_everything_beats_the_budget(self) -> None:
        results, _ = self._build(DISCOVERY_DEADLINE_S="30")
        self.assertEqual(results["slow"]["status"], STATUS_OK)
        self.assertNotIn("_deadline", results)


class TestTheDropReachesTheRunRecord(_RegistryCase):
    """A reading nothing carries forward is not a reading."""

    def test_run_discovery_lifts_the_drop_into_meta(self) -> None:
        from core.pipeline import run_discovery

        sources = (("fast", _fast), ("slow", _slow))
        with (
            patch("apis.register_signals._active_signal_sources", return_value=sources),
            patch("apis.register_signals.start_youtube_warmup_background"),
            patch("apis.register_signals.get_cached", return_value=None),
            patch("apis.register_signals.set_cache"),
            patch("apis.register_signals._two_stage_web", return_value=False),
            patch("apis.register_signals._fanout_enabled", return_value=False),
            patch("core.discovery_headroom.emit_headroom"),
            patch("core.pipeline.generate_variants", return_value=["a variant"]),
            patch("core.pipeline.collect_scored_variants", return_value=([], {}, {})),
            patch("core.pipeline._store_discovery_cache"),
            patch("core.pipeline._load_discovery_cache", return_value=None),
            patch.dict(os.environ, {"DISCOVERY_DEADLINE_S": "0.3"}, clear=False),
        ):
            result = run_discovery("a topic", channel_id="tapin")

        self.assertEqual(result.meta.get("discovery_dropped"), "slow")
        # #813: a string in `timings` is a TypeError in the intelligence report.
        self.assertNotIn("discovery_dropped", result.timings)
        sum(result.timings.values())
        # The registry the rest of the run reads stays signals only.
        self.assertNotIn("_deadline", result.base_signals)


class TestDroppedNamesStayOutOfTimings(unittest.TestCase):
    """#813 again: a string in `timings` crashes the intelligence report."""

    def test_meta_carries_the_drop_not_timings(self) -> None:
        from core.pipeline import DiscoveryResult

        result = DiscoveryResult(
            input_topic="t",
            base_signals={},
            evaluated=[],
            timings={"discovery": 1.0},
            meta={"discovery_dropped": "slow"},
        )
        # Exactly the sum the intelligence report performs.
        self.assertEqual(sum(result.timings.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
