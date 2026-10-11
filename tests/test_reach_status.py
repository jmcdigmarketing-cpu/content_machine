"""#1058: why the click-through numbers never arrived, said out loud.

Measured 2026-10-10: `data/reach_tapin.json` did not exist and 0 of 43 videos carried
impressions or click-through. The filed items (#1049, #1058) call that data "stored, unused";
none was ever stored. The cause is outside the code - the YouTube Reporting API is not enabled
in the Google Cloud project (HTTP 403) - and the one line that says so is printed in the
middle of `ops sync-metrics`. With no token scope the sync said nothing at all.

The sync now records what happened, and `ops doctor` shows it.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class _ReachCase(unittest.TestCase):
    def setUp(self):
        from analytics import reach_report

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        template = os.path.join(self.tmp.name, "reach_{channel}.json")
        patcher = patch.object(reach_report, "REACH_TEMPLATE", template)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _sync(self, service):
        from analytics import reach_report

        with patch("youtube.oauth.get_youtube_reporting_service", return_value=service):
            return reach_report.sync_reach("tapin")


class SyncRecordsWhatHappenedTests(_ReachCase):
    def test_no_reporting_service_is_recorded_for_the_doctor(self):
        from analytics import reach_report

        self.assertEqual(self._sync(None), "")
        self.assertEqual(reach_report.load("tapin")["last_status"], "no_service")
        ok, line = reach_report.status("tapin")
        self.assertFalse(ok)
        self.assertIn("oauth_setup", line)

    def test_a_disabled_api_is_recorded(self):
        from analytics import reach_report

        service = MagicMock()
        service.jobs.return_value.list.return_value.execute.side_effect = RuntimeError(
            "YouTube Reporting API has not been used in project 1 before or it is disabled"
        )
        line = self._sync(service)
        self.assertIn("enable the YouTube Reporting API", line)
        self.assertEqual(reach_report.load("tapin")["last_status"], "api_disabled")

    def test_a_new_job_with_no_report_yet_is_waiting(self):
        from analytics import reach_report

        service = MagicMock()
        service.jobs.return_value.list.return_value.execute.return_value = {"jobs": []}
        service.jobs.return_value.create.return_value.execute.return_value = {"id": "job1"}
        with patch.object(reach_report, "_reports", return_value=[]):
            self._sync(service)
        data = reach_report.load("tapin")
        self.assertEqual(data["last_status"], "waiting")
        self.assertEqual(data["job_id"], "job1")

    def test_videos_with_numbers_is_ok(self):
        from analytics import reach_report

        reach_report._save(
            "tapin", {"job_id": "job1", "videos": {"v1": {"2026-10-01": [10, 0.05]}}}
        )
        with (
            patch.object(reach_report, "download_new", return_value=1),
            patch.object(reach_report, "merge_into_metrics", return_value=1),
        ):
            self._sync(MagicMock())
        self.assertEqual(reach_report.load("tapin")["last_status"], "ok")


class StatusLineTests(_ReachCase):
    def _line(self, data):
        from analytics import reach_report

        if data is not None:
            reach_report._save("tapin", data)
        return reach_report.status("tapin")

    def test_never_synced(self):
        ok, line = self._line(None)
        self.assertFalse(ok)
        self.assertIn("never synced", line)

    def test_the_disabled_api_names_the_fix(self):
        ok, line = self._line({"last_status": "api_disabled", "checked": "2026-10-10"})
        self.assertFalse(ok)
        self.assertIn("enable the YouTube Reporting API", line)
        self.assertIn("2026-10-10", line)

    def test_waiting_says_since_when(self):
        ok, line = self._line(
            {
                "last_status": "waiting",
                "job_id": "j",
                "job_created": "2026-10-10",
                "checked": "2026-10-11",
            }
        )
        self.assertTrue(ok)
        self.assertIn("2026-10-10", line)

    def test_ok_counts_the_videos(self):
        ok, line = self._line(
            {"last_status": "ok", "checked": "2026-10-12", "videos": {"a": {}, "b": {}}}
        )
        self.assertTrue(ok)
        self.assertIn("2 video", line)

    def test_the_doctor_has_the_row(self):
        from pathlib import Path

        text = (
            Path(__file__)
            .resolve()
            .parent.parent.joinpath("core", "ops_doctor.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn('add("reach"', text)


if __name__ == "__main__":
    unittest.main()
