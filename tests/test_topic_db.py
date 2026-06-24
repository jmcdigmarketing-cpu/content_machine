"""Tests for the Topic Winners + Graveyard view (core/topic_db)."""

import unittest
from unittest.mock import patch

from core import topic_db
from core.topic_db import TopicRecord


def _rec(topic, rate, measured=1, domain="ufc", runs=1, status="rendered"):
    return TopicRecord(
        topic=topic,
        domain=domain,
        runs=runs,
        measured=measured,
        avg_engaged_rate=rate,
        best_engaged_rate=rate,
        last_status=status,
    )


_RECORDS = [
    _rec("kape vs horiguchi", 0.30, measured=3),  # winner
    _rec("marvel rivals meta", 0.12, measured=4),  # mid
    _rec("random cod take", 0.02, measured=2),  # flop
    _rec("dead nba ramble", 0.01, measured=1),  # flop
    _rec("never measured idea", None, measured=0),  # no data
]


class TestWinners(unittest.TestCase):
    def test_ranks_by_engagement_and_excludes_unmeasured(self):
        with patch.object(topic_db, "_topic_records", return_value=_RECORDS):
            w = topic_db.winners("tapin", n=3)
        self.assertEqual(
            [r.topic for r in w], ["kape vs horiguchi", "marvel rivals meta", "random cod take"]
        )
        self.assertTrue(all(r.avg_engaged_rate is not None for r in w))

    def test_min_measured_filters_thin_topics(self):
        with patch.object(topic_db, "_topic_records", return_value=_RECORDS):
            w = topic_db.winners("tapin", min_measured=3)
        self.assertEqual({r.topic for r in w}, {"kape vs horiguchi", "marvel rivals meta"})


class TestGraveyard(unittest.TestCase):
    def test_flags_below_floor_only(self):
        with patch.dict("os.environ", {"GRAVEYARD_RATE_FLOOR": "0.04"}, clear=False):
            with patch.object(topic_db, "_topic_records", return_value=_RECORDS):
                g = topic_db.graveyard("tapin")
        topics = [r.topic for r in g]
        self.assertIn("random cod take", topics)
        self.assertIn("dead nba ramble", topics)
        self.assertNotIn("marvel rivals meta", topics)  # 12% is above the floor
        # Worst first.
        self.assertEqual(g[0].topic, "dead nba ramble")

    def test_graveyard_topics_avoid_set(self):
        with patch.dict("os.environ", {"GRAVEYARD_AVOID": "true"}, clear=False):
            with patch.object(topic_db, "_topic_records", return_value=_RECORDS):
                avoid = topic_db.graveyard_topics("tapin")
        self.assertIn("random cod take", avoid)
        self.assertNotIn("kape vs horiguchi", avoid)

    def test_avoid_disabled_returns_empty(self):
        with patch.dict("os.environ", {"GRAVEYARD_AVOID": "false"}, clear=False):
            with patch.object(topic_db, "_topic_records", return_value=_RECORDS):
                self.assertEqual(topic_db.graveyard_topics("tapin"), set())


class TestDisplay(unittest.TestCase):
    def test_display_handles_empty(self):
        lines: list[str] = []
        topic_db.display_winners([], print_fn=lines.append)
        topic_db.display_graveyard([], print_fn=lines.append)
        self.assertTrue(any("no engagement data" in line for line in lines))
        self.assertTrue(any("nothing below the floor" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
