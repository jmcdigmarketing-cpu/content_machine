"""Incident ledger — fixture traces, temp persist path (never data/incidents.json)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from core.incident_ledger import persist, rank_incidents, render


class TestIncidentLedger(unittest.TestCase):
    def test_ranks_by_count_and_recency(self):
        now = 1_000_000.0
        traces = [
            {
                "at": now,
                "signals": {
                    "tiktok_trends": {"status": "unavailable"},
                    "news": {"status": "ok"},
                },
            },
            {
                "at": now - 3600,
                "signals": {"tiktok_trends": {"status": "unavailable"}},
            },
            {
                "at": now - 10 * 86400,
                "signals": {"rawg": {"status": "no_key"}},
            },
        ]
        ranked = rank_incidents(traces, now=now)
        self.assertEqual(ranked[0].name, "tiktok_trends")
        self.assertEqual(ranked[0].count, 2)
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_inactive_is_not_an_incident(self):
        traces = [{"at": 1.0, "signals": {"twitter": {"status": "inactive"}}}]
        self.assertEqual(rank_incidents(traces, now=1.0), [])

    def test_llm_error_counts(self):
        traces = [
            {
                "at": 50.0,
                "signals": {},
                "llm_calls": [{"provider": "openrouter", "error": "402"}],
            }
        ]
        ranked = rank_incidents(traces, now=50.0)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].kind, "llm")

    def test_persist_uses_caller_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "incidents.json")
            ranked = rank_incidents(
                [{"at": 1.0, "signals": {"news": {"status": "error"}}}],
                now=1.0,
            )
            self.assertEqual(persist(ranked, path=path), path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["incidents"][0]["name"], "news")

    def test_render_ascii(self):
        blob = render(rank_incidents([], now=1.0))
        self.assertIn("none", blob.lower())

    def test_ops_command_registered(self):
        from scripts import ops

        self.assertIn("incidents", ops.COMMANDS)


if __name__ == "__main__":
    unittest.main()
