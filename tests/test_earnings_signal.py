"""Earnings-calendar signal (Pillar 6, U9) — make_signal shape, fail-open, gating.

No network: `requests` is mocked. The signal must never raise and must always
return the make_signal() shape, and it must be registered + finance-domain-gated.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from apis import earnings_signal as es
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, STATUS_RATE_LIMIT

_SHAPE = {"connected", "active", "score", "confidence", "data", "status", "status_detail"}


def _resp(status_code=200, payload=None):
    r = mock.Mock()
    r.status_code = status_code
    r.text = ""
    r.json.return_value = payload if payload is not None else {}
    return r


class TestEarningsSignal(unittest.TestCase):
    def test_no_key_returns_no_key_shape(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            sig = es.get_earnings_signal("AAPL earnings")
            self.assertEqual(set(sig), _SHAPE)  # make_signal shape
            self.assertEqual(sig["status"], STATUS_NO_KEY)
            self.assertFalse(sig["active"])

    def test_no_ticker_is_inactive(self):
        with mock.patch.dict(os.environ, {"FINNHUB_API_KEY": "k"}, clear=True):
            with mock.patch.object(es, "requests") as req:
                sig = es.get_earnings_signal("what are the best dividend stocks")
                self.assertEqual(sig["status"], STATUS_INACTIVE)
                req.get.assert_not_called()  # no ticker -> no HTTP

    def test_upcoming_earnings_scores_active(self):
        soon = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        payload = {"earningsCalendar": [{"date": soon, "epsEstimate": 1.2}]}
        with mock.patch.dict(os.environ, {"FINNHUB_API_KEY": "k"}, clear=True):
            with mock.patch.object(es, "requests") as req:
                req.get.return_value = _resp(200, payload)
                sig = es.get_earnings_signal("AAPL earnings this week")
                self.assertEqual(set(sig), _SHAPE)
                self.assertEqual(sig["status"], STATUS_OK)
                self.assertTrue(sig["active"])
                self.assertGreater(sig["score"], 0)
                self.assertEqual(sig["data"]["symbol"], "AAPL")
                self.assertEqual(sig["data"]["days_until"], 3)

    def test_no_upcoming_is_inactive(self):
        with mock.patch.dict(os.environ, {"FINNHUB_API_KEY": "k"}, clear=True):
            with mock.patch.object(es, "requests") as req:
                req.get.return_value = _resp(200, {"earningsCalendar": []})
                sig = es.get_earnings_signal("TSLA earnings")
                self.assertEqual(sig["status"], STATUS_INACTIVE)

    def test_http_429_classified_not_raised(self):
        with mock.patch.dict(os.environ, {"FINNHUB_API_KEY": "k"}, clear=True):
            with mock.patch.object(es, "requests") as req:
                req.get.return_value = _resp(429)
                sig = es.get_earnings_signal("NVDA earnings")
                self.assertEqual(sig["status"], STATUS_RATE_LIMIT)

    def test_exception_never_raises(self):
        with mock.patch.dict(os.environ, {"FINNHUB_API_KEY": "k"}, clear=True):
            with mock.patch.object(es, "requests") as req:
                req.get.side_effect = RuntimeError("boom")
                sig = es.get_earnings_signal("MSFT earnings")  # must not raise
                self.assertEqual(set(sig), _SHAPE)
                self.assertFalse(sig["connected"])


class TestRegistrationAndGating(unittest.TestCase):
    def test_registered(self):
        from apis.signals_bootstrap import get_signal_registry

        self.assertIn("earnings", get_signal_registry().get_registered_signals())

    def test_finance_domain_gated(self):
        from apis import register_signals as rs

        self.assertIn("earnings", rs._DOMAIN_SIGNALS["finance"])
        # Gated OUT for a non-finance (gaming) topic.
        with mock.patch.dict(os.environ, {"DOMAIN_SIGNAL_GATING": "true"}, clear=True):
            with mock.patch("apis.topic_scorer.infer_domain", return_value="gaming"):
                self.assertIn("earnings", rs._gated_signal_names("some game topic"))


if __name__ == "__main__":
    unittest.main()
