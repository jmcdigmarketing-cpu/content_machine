"""Reliability time series + YouTube units under a governor scope (O12 remainder).

`ops reliability` shows the current state; it cannot show *direction*, which is what
catches slow degradation — creeping LLM spend, YouTube units drifting toward the cap,
feeds dying one at a time. Every failure found this session began as a gradual change
nobody could see because yesterday's numbers were never kept.

Isolated per tests/CLAUDE.md: the history file is patched to a temp path so the real
`data/reliability_history.json` is never written.
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from core import reliability_history as rh


def _snapshot(**over):
    data = {
        "llm": {"spend_today": 0.0123, "dead_models": {"a": "x", "b": "y"}},
        "youtube": {"used": 3958, "limit": 10000, "remaining": 6042},
        "cache": {"hit_rate": 0.42},
        "signals": {"disabled": ["igdb"], "persisted": {"reddit": "retired"}},
        "apify": {"exhausted": False},
    }
    data.update(over)
    return data


class _IsolatedHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "reliability_history.json")
        self.patcher = patch("config.paths.RELIABILITY_HISTORY_FILE", self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestSummarize(_IsolatedHistory):
    def test_pulls_the_trendable_numbers(self):
        row = rh.summarize(_snapshot())
        self.assertEqual(row["llm_spend_usd"], 0.0123)
        self.assertEqual(row["youtube_units"], 3958)
        self.assertEqual(row["llm_dead_models"], 2)
        self.assertEqual(row["cache_hit_rate"], 0.42)

    def test_signals_disabled_counts_session_and_persisted(self):
        self.assertEqual(rh.summarize(_snapshot())["signals_disabled"], 2)

    def test_stamped_with_today(self):
        self.assertEqual(rh.summarize(_snapshot())["date"], date.today().isoformat())

    def test_empty_snapshot_does_not_raise(self):
        row = rh.summarize({})
        self.assertEqual(row["llm_spend_usd"], 0.0)
        self.assertEqual(row["youtube_units"], 0)


class TestRecord(_IsolatedHistory):
    def test_record_then_read_back(self):
        rh.record(_snapshot())
        rows = rh.history()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["youtube_units"], 3958)

    def test_same_day_upserts_rather_than_appends(self):
        rh.record(_snapshot())
        rh.record(_snapshot(youtube={"used": 5000, "limit": 10000}))
        rows = rh.history()
        self.assertEqual(len(rows), 1, "one row per day")
        self.assertEqual(rows[0]["youtube_units"], 5000, "latest value wins")

    def test_history_is_capped(self):
        rows = [{"date": f"2026-01-{d:02d}", "youtube_units": d} for d in range(1, 29)]
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)
        with patch.dict(os.environ, {"RELIABILITY_HISTORY_DAYS": "7"}, clear=False):
            rh.record(_snapshot())
            self.assertLessEqual(len(rh.history(days=999)), 7)

    def test_corrupt_file_does_not_raise(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(rh.history(), [])
        self.assertTrue(rh.record(_snapshot()))

    def test_rows_stay_date_sorted(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump([{"date": "2026-09-01"}, {"date": "2026-01-01"}], fh)
        rh.record(_snapshot())
        dates = [r["date"] for r in rh.history(days=999)]
        self.assertEqual(dates, sorted(dates))


class TestRender(_IsolatedHistory):
    def _seed(self, n=5):
        rows = [
            {
                "date": f"2026-08-{d:02d}",
                "llm_spend_usd": 0.01 * d,
                "youtube_units": 1000 * d,
                "signals_disabled": d,
                "feeds_dead": 0,
                "cache_hit_rate": 0.5,
            }
            for d in range(1, n + 1)
        ]
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def test_empty_history_explains_itself(self):
        self.assertIn("No history yet", rh.render())

    def test_rising_series_reads_as_up(self):
        self._seed()
        out = rh.render()
        self.assertIn("LLM spend", out)
        self.assertIn("up", out)

    def test_render_is_cp1252_safe(self):
        # `py -m scripts.ops reliability` prints this on a cp1252 console.
        self._seed()
        rh.render().encode("cp1252")

    def test_sparkline_shape(self):
        self.assertEqual(len(rh._spark([1, 2, 3, 4])), 4)
        self.assertEqual(rh._spark([]), "")
        self.assertEqual(rh._spark([5, 5, 5]), "---", "flat series has no fake movement")


class TestGovernorYouTubeScope(unittest.TestCase):
    """O12: YouTube units reported through the governor, not a second store read."""

    def test_snapshot_includes_youtube(self):
        from core.quota_governor import snapshot

        self.assertIn("youtube", snapshot())

    def test_youtube_usage_shape(self):
        from core.quota_governor import youtube_usage

        usage = youtube_usage()
        for field in ("used", "limit", "remaining", "pct", "day"):
            self.assertIn(field, usage)

    def test_pct_is_derived(self):
        from core import quota_governor

        with patch(
            "apis.youtube_quota.get_usage_summary",
            return_value={"used": 2500, "limit": 10000, "remaining": 7500, "day": "2026-08-14"},
        ):
            self.assertEqual(quota_governor.youtube_usage()["pct"], 25.0)

    def test_fails_open_when_tracker_unreadable(self):
        from core import quota_governor

        with patch("apis.youtube_quota.get_usage_summary", side_effect=OSError("gone")):
            self.assertEqual(quota_governor.youtube_usage()["used"], 0)

    def test_zero_limit_does_not_divide_by_zero(self):
        from core import quota_governor

        with patch(
            "apis.youtube_quota.get_usage_summary",
            return_value={"used": 5, "limit": 0, "remaining": 0, "day": "d"},
        ):
            self.assertEqual(quota_governor.youtube_usage()["pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
