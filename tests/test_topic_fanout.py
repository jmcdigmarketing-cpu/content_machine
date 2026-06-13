import unittest

from apis.topic_fanout import parse_subtopics, primary_search_query


class TestTopicFanout(unittest.TestCase):
    def test_parse_multi_game_topic(self):
        topic = "State of Gaming 2026. Marvel Rivals, terraria, cod, subnautica 2, and more"
        parts = parse_subtopics(topic)
        self.assertGreaterEqual(len(parts), 3)
        self.assertTrue(any("marvel" in p.lower() for p in parts))
        self.assertIn("terraria", [p.lower() for p in parts])

    def test_single_topic_no_fanout(self):
        self.assertEqual(parse_subtopics("Marvel Rivals only"), [])

    def test_primary_search_query(self):
        topic = "State of Gaming 2026. Marvel Rivals, terraria"
        self.assertEqual(primary_search_query(topic), "Marvel Rivals")


if __name__ == "__main__":
    unittest.main()
