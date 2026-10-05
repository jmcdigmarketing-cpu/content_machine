"""#958: a metrics refresh keeps what other writers stored.

`merge_metric_snapshots` rebuilt each video's metrics from the fresh 28-day fetch. The
lifetime views (#940) and the reach numbers (#951) survived only because their writers ran
after the refresh in the same sync; a sync that failed before them, or any later writer
(the first-day verdict, #49), lost its key on the next refresh. The stored metrics are now
the base and the fresh fetch overwrites only the keys it returned.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

PUBLISHED = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


class MergeTests(unittest.TestCase):
    def _merge(self, existing, fresh, *, days=10):
        from analytics.youtube_metrics import merge_metric_snapshots

        return merge_metric_snapshots(
            existing, fresh, published_at=PUBLISHED, now=PUBLISHED + timedelta(days=days)
        )

    def test_keys_the_fetch_did_not_return_are_kept(self):
        existing = {"views": 100, "lifetime_views": 5400, "lifetime_views_at": "2026-10-01",
                    "reach": {"impressions": 9000, "ctr": 0.041}}  # fmt: skip
        got = self._merge(existing, {"views": 300, "engaged_rate": 0.5})
        self.assertEqual(got["lifetime_views"], 5400)
        self.assertEqual(got["reach"], {"impressions": 9000, "ctr": 0.041})

    def test_the_fresh_fetch_wins_every_key_it_returned(self):
        got = self._merge({"views": 100, "engaged_rate": 0.3}, {"views": 300, "engaged_rate": 0.5})
        self.assertEqual((got["views"], got["engaged_rate"]), (300, 0.5))

    def test_snapshots_stay_frozen(self):
        first = self._merge({}, {"views": 100, "engaged_rate": 0.4}, days=0)
        later = self._merge(dict(first, lifetime_views=50), {"views": 900}, days=7)
        self.assertEqual(later["snapshots"]["24h"]["views"], 100)
        self.assertEqual(later["snapshots"]["7d"]["views"], 900)
        self.assertEqual(later["lifetime_views"], 50)

    def test_an_unreadable_existing_blob_is_ignored(self):
        got = self._merge("not a dict", {"views": 3})  # type: ignore[arg-type]
        self.assertEqual(got["views"], 3)


if __name__ == "__main__":
    unittest.main()
