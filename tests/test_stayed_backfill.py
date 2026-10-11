"""Wave 77 (#1124): the stayed share for videos synced before it existed.

Measured 2026-10-10: 5 of 43 TapIn videos carried `stayed_share`. The sync has asked YouTube
for engaged views since #951 (2026-10-04) but only revisits young videos, so the 38 whose
numbers were stored before then were never asked. The hook learner, the intro test and the
growth report all read "who stayed" from five videos.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _row(row_id, metrics, video_id="vid"):
    return SimpleNamespace(
        id=row_id,
        youtube_video_id=f"{video_id}{row_id}" if video_id else "",
        metrics_json=json.dumps(metrics) if metrics is not None else None,
    )


OLD = {"views": 200, "period_start": "2026-07-01", "period_end": "2026-07-18", "likes": 3}


class NeedsStayedTests(unittest.TestCase):
    def _needs(self, row):
        from analytics.packaging import needs_stayed

        return needs_stayed(row)

    def test_views_for_a_period_and_no_engaged_views(self):
        self.assertTrue(self._needs(_row(1, OLD)))

    def test_a_video_that_has_the_number_is_not_asked_again(self):
        self.assertFalse(self._needs(_row(1, dict(OLD, engaged_views=50))))
        self.assertFalse(self._needs(_row(1, dict(OLD, engaged_views=0))))

    def test_no_views_or_no_period_is_left_alone(self):
        self.assertFalse(self._needs(_row(1, dict(OLD, views=0))))
        self.assertFalse(self._needs(_row(1, {"views": 200})))
        self.assertFalse(self._needs(_row(1, None)))

    def test_a_seeded_row_or_one_with_no_video_is_left_alone(self):
        from storage.repositories.publish_log import SEED_SOURCE

        self.assertFalse(self._needs(_row(1, dict(OLD, source=SEED_SOURCE))))
        self.assertFalse(self._needs(_row(1, OLD, video_id="")))


class BackfillStayedTests(unittest.TestCase):
    def _run(self, rows, apply, fetch=None, sign_in=""):
        from analytics import packaging

        updates: list[tuple[int, dict]] = []
        repo = SimpleNamespace(
            list_uploaded_for_channel=lambda channel: rows,
            update=lambda row_id, data: updates.append((row_id, data)),
        )
        fetch = fetch or (lambda *a, **k: 50)
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch("analytics.youtube_metrics.fetch_engaged_views", side_effect=fetch) as asked,
            patch("youtube.oauth.sign_in_problem", return_value=sign_in),
        ):
            tally = packaging.backfill_stayed("tapin", apply, False)
        return tally, updates, asked

    def test_a_dry_run_counts_and_asks_nothing(self):
        rows = [_row(1, OLD), _row(2, dict(OLD, engaged_views=9)), _row(3, OLD)]
        tally, updates, asked = self._run(rows, apply=False)
        self.assertEqual(tally, {"runs": 3, "stale": 2, "would_update": 2, "updated": 0})
        self.assertEqual(updates, [])
        asked.assert_not_called()

    def test_apply_asks_for_the_period_the_stored_views_cover(self):
        tally, updates, asked = self._run([_row(7, OLD)], apply=True)
        self.assertEqual(tally["updated"], 1)
        asked.assert_called_once_with(
            "vid7", channel_id="tapin", start="2026-07-01", end="2026-07-18"
        )
        ((row_id, data),) = updates
        stored = json.loads(data["metrics_json"])
        self.assertEqual(row_id, 7)
        self.assertEqual(stored["engaged_views"], 50)
        self.assertEqual(stored["stayed_share"], 0.25)
        self.assertEqual(stored["likes"], 3)  # nothing else is touched

    def test_more_engaged_than_views_is_capped_at_one(self):
        _tally, updates, _asked = self._run([_row(7, OLD)], apply=True, fetch=lambda *a, **k: 260)
        self.assertEqual(json.loads(updates[0][1]["metrics_json"])["stayed_share"], 1.0)

    def test_a_refused_answer_is_skipped_and_the_rest_still_asked(self):
        answers = iter([None, 40])
        tally, updates, asked = self._run(
            [_row(1, OLD), _row(2, OLD)], apply=True, fetch=lambda *a, **k: next(answers)
        )
        self.assertEqual(asked.call_count, 2)
        self.assertEqual([u[0] for u in updates], [2])
        self.assertEqual(tally["updated"], 1)

    def test_a_dead_sign_in_stops_after_the_first_refusal(self):
        tally, updates, asked = self._run(
            [_row(1, OLD), _row(2, OLD)],
            apply=True,
            fetch=lambda *a, **k: None,
            sign_in="sign in again",
        )
        self.assertEqual(asked.call_count, 1)
        self.assertEqual(updates, [])
        self.assertEqual(tally["updated"], 0)


class RegistryTests(unittest.TestCase):
    def test_ops_backfill_knows_it(self):
        from analytics import backfills

        entry = backfills.get_backfill("stayed")
        self.assertIn("stayed", entry.fills)
        with patch("analytics.packaging.backfill_stayed", return_value={"updated": 4}) as run:
            self.assertEqual(entry.run("tapin", True, False), {"updated": 4})
        run.assert_called_once_with("tapin", True, False)

    def test_with_analytics_off_nothing_is_asked(self):
        from analytics import youtube_metrics

        with patch.dict("os.environ", {"YOUTUBE_ANALYTICS_SYNC": ""}):
            self.assertIsNone(
                youtube_metrics.fetch_engaged_views(
                    "vid", channel_id="tapin", start="2026-07-01", end="2026-07-18"
                )
            )

    def test_the_figures_reader_uses_what_the_backfill_stores(self):
        from analytics.packaging import packaging_figures

        figures = packaging_figures(dict(OLD, engaged_views=50, stayed_share=0.25))
        self.assertEqual(figures.get("stayed"), 0.25)


if __name__ == "__main__":
    unittest.main()
