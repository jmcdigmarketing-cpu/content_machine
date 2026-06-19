"""Unit tests for domain-aware signal gating in apis/register_signals.py."""

import unittest
from unittest.mock import patch

from apis import register_signals as rs


class TestGatedSignalNames(unittest.TestCase):
    def test_ufc_topic_gates_gaming_signals(self):
        gated = rs._gated_signal_names("UFC 311 Topuria title defense")
        # Gaming signals must be skipped on a UFC/sports topic
        self.assertIn("rawg", gated)
        self.assertIn("steam", gated)
        self.assertIn("igdb", gated)
        # Sports signals must NOT be gated on a UFC topic
        self.assertNotIn("ufc_context", gated)
        self.assertNotIn("tapology", gated)

    def test_gaming_topic_gates_sports_signals(self):
        gated = rs._gated_signal_names("Marvel Rivals new season meta")
        # Sports/UFC signals must be skipped on a gaming topic
        self.assertIn("tapology", gated)
        self.assertIn("ufc_context", gated)
        self.assertIn("odds", gated)
        # Gaming signals must NOT be gated on a gaming topic
        self.assertNotIn("rawg", gated)
        self.assertNotIn("steam", gated)

    def test_finance_topic_gates_gaming_and_sports(self):
        gated = rs._gated_signal_names("Apple earnings beat estimates 2026")
        self.assertIn("rawg", gated)
        self.assertIn("tapology", gated)
        self.assertNotIn("fred", gated)
        self.assertNotIn("sec_edgar", gated)

    def test_universal_signals_never_gated(self):
        for topic in ("UFC 311 Topuria", "Marvel Rivals meta", "Tesla earnings"):
            gated = rs._gated_signal_names(topic)
            for universal in ("youtube", "trends", "news", "wikipedia", "reddit", "twitter"):
                self.assertNotIn(universal, gated)

    def test_neutral_topic_gates_nothing(self):
        # A topic with no domain keywords should fail open (run everything).
        gated = rs._gated_signal_names("some random ambiguous phrase")
        self.assertEqual(gated, set())

    def test_disabled_via_env_gates_nothing(self):
        with patch.dict("os.environ", {"DOMAIN_SIGNAL_GATING": "false"}):
            gated = rs._gated_signal_names("UFC 311 Topuria title defense")
            self.assertEqual(gated, set())


class TestActiveSignalSources(unittest.TestCase):
    def test_active_sources_excludes_gated(self):
        sources = rs._active_signal_sources("UFC 311 Topuria title defense")
        names = {n for n, _ in sources}
        self.assertNotIn("rawg", names)
        self.assertNotIn("steam", names)
        self.assertIn("youtube", names)
        self.assertIn("ufc_context", names)

    def test_no_topic_returns_all_non_skipped(self):
        # Empty topic = no gating applied (back-compat with old signature).
        sources = rs._active_signal_sources()
        names = {n for n, _ in sources}
        self.assertIn("rawg", names)
        self.assertIn("ufc_context", names)


if __name__ == "__main__":
    unittest.main()
