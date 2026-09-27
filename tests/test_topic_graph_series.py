"""#879: a continuation best bet keeps the series it continues.

Run 99's best bet was "UFC week 2". Week 1's topic had no "week N", so
`next_arc_topic` fell back to the franchise label and threw the series away - it was
Dana White's Contender Series, and the vague seed pulled UFC-wide vault facts.
"""

from __future__ import annotations

import unittest


class NextArcTopicTests(unittest.TestCase):
    def test_a_topic_without_a_week_keeps_its_series_name(self):
        from core.topic_graph import next_arc_topic

        topic = next_arc_topic("UFC Contender Series: 5 contracts handed out", 1, "ufc")
        self.assertIn("Contender Series", topic)
        self.assertIn("week 2", topic)
        self.assertNotEqual(topic, "UFC week 2")

    def test_a_lower_case_topic_keeps_its_words(self):
        from core.topic_graph import next_arc_topic

        topic = next_arc_topic("ufc contender series recap", 1, "ufc")
        self.assertIn("contender series", topic.lower())
        self.assertTrue(topic.endswith("week 2"))

    def test_the_week_path_is_unchanged(self):
        from core.topic_graph import next_arc_topic

        self.assertEqual(next_arc_topic("GTA 6 leak week 1", 1, "gta"), "GTA 6 leak week 2")

    def test_an_empty_topic_still_gives_the_label(self):
        from core.topic_graph import next_arc_topic

        self.assertEqual(next_arc_topic("", 1, "ufc"), "UFC week 2")

    def test_the_rationale_names_the_series(self):
        import json
        import os
        import tempfile
        from unittest.mock import patch

        from core import topic_graph

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "graph.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "channels": {
                            "tapin": {
                                "arcs": {
                                    "ufc": {
                                        "ordinal": 1,
                                        "last_topic": "UFC Contender Series: 5 contracts",
                                        "updated_at": "2026-09-26T00:00:00+00:00",
                                    }
                                }
                            }
                        }
                    },
                    f,
                )
            with patch.object(topic_graph, "_path", return_value=path):
                bet = topic_graph.follow_up_seed("tapin")
        self.assertIsNotNone(bet)
        self.assertIn("Contender Series", bet.rationale)
        self.assertIn("Contender Series", bet.topic)


if __name__ == "__main__":
    unittest.main()
