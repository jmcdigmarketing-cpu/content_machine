"""#598: the weekly report compares scheduled uploads with immediate ones.

Nothing split outcomes by how a video was published. Since #915 a scheduled upload keeps
`status="scheduled"` and counts once live, and an immediate one is `"uploaded"`, so the
split was already recorded - it only needed reading. `_load_rows` now marks each row
`upload_mode` (scheduled / immediate) and the report's existing winners/losers engine
breaks performance down by it, under the same three-per-group gate.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

NOW = datetime.now(timezone.utc)


def _log(run_id, status, rate):
    return SimpleNamespace(
        content_run_id=run_id, status=status, published_at=NOW - timedelta(days=run_id),
        metrics_json=f'{{"engaged_rate": {rate}}}',
    )  # fmt: skip


class UploadModeTests(unittest.TestCase):
    def _report(self, logs):
        from analytics import weekly_report as wr

        runs = [SimpleNamespace(id=log.content_run_id, features_json="{}") for log in logs]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_timed_outcomes=lambda c: logs),
            ),
        ):
            return wr._load_rows("tapin"), wr.build_report("tapin")

    def test_each_row_says_how_it_was_published(self):
        rows, _ = self._report([_log(1, "scheduled", 0.4), _log(2, "uploaded", 0.2)])
        modes = {r["run_id"]: r["features"]["upload_mode"] for r in rows}
        self.assertEqual(modes, {1: "scheduled", 2: "immediate"})

    def test_the_report_breaks_it_down(self):
        logs = [_log(i, "scheduled", 0.45) for i in (1, 2, 3)]
        logs += [_log(i, "uploaded", 0.15) for i in (4, 5, 6)]
        _, report = self._report(logs)
        groups = {g["value"]: g for g in report["dimensions"]["upload_mode"]}
        self.assertEqual((groups["scheduled"]["n"], groups["immediate"]["n"]), (3, 3))
        self.assertGreater(groups["scheduled"]["delta"], 0)
        self.assertTrue(any("scheduled uploads" in a for a in report["next_actions"]))

    def test_the_formatted_report_shows_it(self):
        from analytics import weekly_report as wr

        logs = [_log(i, "scheduled", 0.4) for i in (1, 2, 3)]
        logs += [_log(i, "uploaded", 0.2) for i in (4, 5, 6)]
        _, report = self._report(logs)
        self.assertIn("By upload_mode:", wr.format_report(report))


if __name__ == "__main__":
    unittest.main()
