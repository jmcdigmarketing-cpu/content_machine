"""signal_facts earnings ratchet — structured keys, not a JSON dump."""

from __future__ import annotations

import json
import unittest

from core.signal_facts import format_signal_facts


def _ok(data: dict) -> dict:
    return {"earnings": {"connected": True, "active": True, "data": data}}


class TestSignalFactsEarnings(unittest.TestCase):
    def test_earnings_keys_are_rendered(self):
        out = format_signal_facts(
            _ok({"symbol": "AAPL", "date": "2026-08-28", "days_until": 8, "eps_estimate": 1.2})
        )
        self.assertIn("AAPL", out)
        self.assertIn("2026-08-28", out)
        self.assertIn("in 8d", out)
        self.assertIn("1.2", out)
        self.assertNotIn("{", out)

    def test_json_dump_path_is_not_used(self):
        data = {"symbol": "MSFT", "date": "2026-09-01", "days_until": 12, "eps_estimate": 2.5}
        out = format_signal_facts(_ok(data))
        self.assertNotIn(json.dumps(data)[:40], out)

    def test_inactive_earnings_omitted(self):
        out = format_signal_facts(
            {"earnings": {"connected": True, "active": False, "data": {"symbol": "AAPL"}}}
        )
        self.assertNotIn("AAPL", out)


if __name__ == "__main__":
    unittest.main()
