"""Decision 82 (the operator, 2026-10-27): every change is in the race to monetization or to big
views for little money. Each open backlog item names its lane - views, subscribers, hours, money,
cost, or a defect that breaks publishing - or is parked (`- [-]`), neither open nor done."""

from __future__ import annotations

import unittest
from unittest.mock import patch

LINES = [
    "- [ ] 1597. **A marquee list that learns** *(2026-10-27)* `[S]` · lane: views",
    "- [ ] 1598. **Organic subscribers measured** *(2026-10-27)* `[S]` · lane: subscribers",
    "- [ ] 1599. **An hours ledger** *(2026-10-27)* `[M]` · lane: hours",
    "- [ ] 1600. **No lane named** *(2026-10-27)* `[S]`",
    "- [-] 1290. **Something parked** `[S]` *(parked 2026-10-27, decision 82: moves no number)*",
    "- [x] 1584. **Done already** `[S]`",
]


class ParkedTests(unittest.TestCase):
    def test_a_parked_item_is_neither_open_nor_done(self):
        from core import roadmap_index

        with patch.object(
            roadmap_index, "_lines", side_effect=lambda name: LINES if name == "backlog.md" else []
        ):
            data = roadmap_index.counts()
        self.assertEqual(data["open_total"], 4)
        self.assertEqual(data["done_total"], 1)
        self.assertEqual(data["parked_total"], 1)

    def test_lanes_and_the_ones_without(self):
        from core.roadmap_index import lane_counts

        lanes, unlaned = lane_counts(LINES)
        self.assertEqual(lanes, {"hours": 1, "subscribers": 1, "views": 1})
        self.assertEqual(unlaned, [1600])

    def test_the_report_says_both(self):
        from core import roadmap_index

        with patch.object(
            roadmap_index, "_lines", side_effect=lambda name: LINES if name == "backlog.md" else []
        ):
            text = roadmap_index.render()
        self.assertIn("parked 1", text)
        self.assertIn("by lane", text)
        self.assertIn("views 1", text)
        self.assertIn("#1600", text)


class GateTests(unittest.TestCase):
    """The gate itself, on the real backlog: an open numbered item without a lane fails CI."""

    def test_every_open_numbered_item_names_its_lane(self):
        from core.roadmap_index import _lines, lane_counts

        _lanes, unlaned = lane_counts(_lines("backlog.md"))
        self.assertEqual(unlaned, [], "name a lane (decision 82) or park it with `- [-]`")


if __name__ == "__main__":
    unittest.main()
