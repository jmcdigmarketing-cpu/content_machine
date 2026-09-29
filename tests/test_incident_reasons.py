"""#908: an incident says why the signal failed, not only that it did.

The operator's `ops reliability` (2026-09-27) listed `youtube` and `youtube_comments` as
`unavailable` ten times each, and nothing could say why: `core/run_trace._slim_signals`
kept status / connected / active / score and dropped `status_detail`, so the ledger saw
the word "unavailable" and nothing else. That word covers three different things - a
timeout (`signal_contract.classify_exception`), a signal dropped at the discovery
deadline (`register_signals._fetch_all`) and a signal that never connected. The trace now
keeps the detail, the ledger counts the reasons, and a trace written before this change
says so instead of guessing.
"""

from __future__ import annotations

import unittest


def _trace(at: float, status: str, detail: str | None, *, name: str = "youtube") -> dict:
    sig: dict = {"status": status, "connected": status != "unavailable", "active": False}
    if detail is not None:
        sig["status_detail"] = detail
    return {"at": at, "signals": {name: sig}}


class SlimTests(unittest.TestCase):
    def test_the_trace_keeps_the_detail(self):
        from core.run_trace import _slim_signals

        slim = _slim_signals(
            {"youtube": {"status": "unavailable", "status_detail": "The read operation timed out"}}
        )
        self.assertEqual(slim["youtube"]["status_detail"], "The read operation timed out")

    def test_a_long_detail_is_trimmed(self):
        from core.run_trace import _slim_signals

        slim = _slim_signals({"x": {"status": "error", "status_detail": "e" * 500}})
        self.assertEqual(len(slim["x"]["status_detail"]), 120)


class LedgerTests(unittest.TestCase):
    TRACES = (
        _trace(1.0, "unavailable", "missed the 25s discovery deadline"),
        _trace(2.0, "unavailable", "missed the 25s discovery deadline"),
        _trace(3.0, "unavailable", "HTTPSConnectionPool: Read timed out. (read timeout=10)"),
        _trace(4.0, "unavailable", ""),
        _trace(5.0, "unavailable", None),  # written before #908
    )

    def test_unavailable_is_split_by_reason(self):
        from core.incident_ledger import rank_incidents

        row = rank_incidents(list(self.TRACES), now=5.0)[0]
        self.assertEqual(row.count, 5)
        self.assertEqual(
            row.reasons,
            {"deadline": 2, "timeout": 1, "not connected": 1, "before #908": 1},
        )

    def test_the_render_names_the_reasons(self):
        from core.incident_ledger import rank_incidents, render

        text = render(rank_incidents(list(self.TRACES), now=5.0))
        self.assertIn("deadline 2", text)
        self.assertIn("timeout 1", text)
        self.assertIn("before #908 1", text)

    def test_other_statuses_keep_their_detail(self):
        from core.incident_ledger import rank_incidents

        row = rank_incidents([_trace(1.0, "upstream_error", "schema drift: missing `x`")])[0]
        self.assertEqual(row.last_detail, "schema drift: missing `x`")
        self.assertEqual(row.reasons, {"schema drift": 1})

    def test_the_ledger_file_carries_them(self):
        import json
        import os
        import tempfile

        from core.incident_ledger import persist, rank_incidents

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "incidents.json")
            persist(rank_incidents(list(self.TRACES), now=5.0), path=path)
            with open(path, encoding="utf-8") as f:
                row = json.load(f)["incidents"][0]
        self.assertEqual(row["reasons"]["deadline"], 2)


class ReasonTests(unittest.TestCase):
    def test_reason_of(self):
        from core.incident_ledger import reason_of

        cases = {
            ("unavailable", "missed the 25s discovery deadline"): "deadline",
            ("unavailable", "The read operation timed out"): "timeout",
            ("unavailable", ""): "not connected",
            ("unavailable", None): "before #908",
            ("quota_exceeded", "quotaExceeded"): "quota",
            ("rate_limited", "429 Too Many Requests"): "rate limit",
            ("upstream_error", "schema drift: missing `x`"): "schema drift",
            ("upstream_error", "Server error (503)"): "server error",
            ("error", "KeyError: 'items'"): "other",
            ("unavailable", "Connection reset by peer"): "other",
            ("no_key", "Set RAWG_API_KEY in .env"): "no key",
            ("error", "read 1500 bytes"): "other",
        }
        for (status, detail), want in cases.items():
            with self.subTest(status=status, detail=detail):
                self.assertEqual(reason_of(status, detail), want)


if __name__ == "__main__":
    unittest.main()
