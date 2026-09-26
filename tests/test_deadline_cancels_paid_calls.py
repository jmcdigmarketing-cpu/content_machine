"""#820: a dropped signal's thread was abandoned, not cancelled.

#811's `shutdown(wait=False)` returns at the deadline but the worker keeps running until
its provider answers, so a 114 s straggler still spends its API call and its Apify
credit; the budget bought the operator's time, not money. Two gaps the map exposed:
signals still *queued* behind `DISCOVERY_MAX_WORKERS` started after the drop (no
`cancel_futures`), and nothing between `_fetch_one` and `apify_client.run_actor` knew a
deadline had passed.

The late `set_cache` write from a free straggler is deliberate and kept - only the paid
call is refused. No network: `requests.post` is a mock that records whether it was hit.
"""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from apis.signal_contract import STATUS_OK, make_signal

_SLOW_SLEEP = 1.5


def _fast(_topic):
    return make_signal(connected=True, active=True, score=50, confidence=0.9)


def _paid_after_sleep(_topic):
    """A signal that, like the Apify-backed ones, calls run_actor after some work."""
    from apis.apify_client import run_actor

    time.sleep(_SLOW_SLEEP)
    items = run_actor("acme/actor", {"q": "x"}, purpose="main")
    return make_signal(connected=True, active=items is not None, score=99, confidence=0.9)


class _Case(unittest.TestCase):
    def _build(self, sources, **env):
        from apis.register_signals import build_registry

        with (
            patch("apis.register_signals._active_signal_sources", return_value=sources),
            patch("apis.register_signals.start_youtube_warmup_background"),
            patch("apis.register_signals.get_cached", return_value=None),
            patch("apis.register_signals.set_cache"),
            patch("apis.register_signals._two_stage_web", return_value=False),
            patch("apis.register_signals._fanout_enabled", return_value=False),
            patch("core.discovery_headroom.emit_headroom"),
            patch("apis.apify_client.get_cached", return_value=None),
            patch("apis.apify_client._sync_persistent"),
            patch("apis.apify_client.requests.post") as post,
            patch.dict(
                os.environ,
                {"APIFY_CONTENT_MACHINE_KEY": "k", "FREE_MODE_STRICT": "", **env},
                clear=False,
            ),
        ):
            post.return_value.status_code = 200
            post.return_value.json.return_value = [{"ok": 1}]
            results = build_registry("a topic")
            # Let the straggler reach its paid call before we assert on it.
            time.sleep(_SLOW_SLEEP + 0.5)
            return results, post


class TestPaidCallsStopAtTheDeadline(_Case):
    def test_a_straggler_does_not_post_to_apify_after_the_drop(self) -> None:
        results, post = self._build(
            (("fast", _fast), ("paid", _paid_after_sleep)), DISCOVERY_DEADLINE_S="0.3"
        )
        self.assertEqual(results["fast"]["status"], STATUS_OK)
        self.assertFalse(post.called, "the dropped signal still spent an Apify run")

    def test_a_signal_inside_the_budget_still_posts(self) -> None:
        _results, post = self._build((("paid", _paid_after_sleep),), DISCOVERY_DEADLINE_S="10")
        self.assertTrue(post.called)

    def test_no_deadline_means_no_cancellation(self) -> None:
        _results, post = self._build((("paid", _paid_after_sleep),))
        self.assertTrue(post.called)

    def test_the_refusal_is_counted_and_named(self) -> None:
        from apis import apify_client

        results, _post = self._build(
            (("fast", _fast), ("paid", _paid_after_sleep)), DISCOVERY_DEADLINE_S="0.3"
        )
        self.assertGreaterEqual(int(apify_client._state.get("cancelled_after_deadline") or 0), 1)
        self.assertIn("deadline", results["paid"]["status_detail"])


class TestQueuedSignalsAreCancelledToo(unittest.TestCase):
    def test_shutdown_cancels_queued_futures(self) -> None:
        # With one worker, the second signal is still queued at the deadline; it must
        # never start (cancel_futures), not merely be abandoned.
        from apis.register_signals import _fetch_all

        started: list[str] = []

        def _first(_t):
            started.append("first")
            time.sleep(0.6)
            return _fast(_t)

        def _second(_t):
            started.append("second")
            return _fast(_t)

        with (
            patch("apis.register_signals.get_cached", return_value=None),
            patch("apis.register_signals.set_cache"),
            patch.dict(os.environ, {"DISCOVERY_DEADLINE_S": "0.2"}, clear=False),
        ):
            _fetch_all((("first", _first), ("second", _second)), "t", {}, workers=1)
            time.sleep(0.9)
        self.assertEqual(started, ["first"], "a queued signal started after the deadline")


if __name__ == "__main__":
    unittest.main()
