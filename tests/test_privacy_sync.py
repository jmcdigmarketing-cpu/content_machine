"""Wave 79 (#1128, #1126): a video's privacy is read back from YouTube.

Measured 2026-10-10: the publish log said 32 public, 5 unlisted, 6 private. YouTube said all 43
were public. A scheduled upload goes up private and turns public at its slot, a held one is made
public in Studio, and nothing asked again - so the line counting "finished, not public" videos
counted five that were live. The operator's answer to a question about three of them was "all 3
were published".
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _row(row_id, video_id, privacy, run_id=None):
    return SimpleNamespace(
        id=row_id,
        youtube_video_id=video_id,
        privacy_status=privacy,
        content_run_id=run_id if run_id is not None else row_id,
        metrics_json="{}",
    )


def _service(statuses):
    service = MagicMock()

    def _list(part, id, maxResults):
        call = MagicMock()
        call.execute.return_value = {
            "items": [
                {"id": vid, "status": {"privacyStatus": statuses[vid]}}
                for vid in id.split(",")
                if vid in statuses
            ]
        }
        return call

    service.videos.return_value.list.side_effect = _list
    return service


class DriftTests(unittest.TestCase):
    def test_a_video_made_public_since_upload_is_a_change(self):
        from analytics.privacy_sync import drift

        got = drift(
            {"a": "unlisted", "b": "public", "c": "private"},
            {"a": "public", "b": "public", "c": "public"},
        )
        self.assertEqual(got, {"a": ["unlisted", "public"], "c": ["private", "public"]})

    def test_a_video_youtube_no_longer_returns_is_gone(self):
        from analytics.privacy_sync import GONE, drift

        self.assertEqual(drift({"a": "public"}, {}), {"a": ["public", GONE]})

    def test_an_empty_answer_is_not_a_change(self):
        from analytics.privacy_sync import drift

        self.assertEqual(drift({"a": "public"}, {"a": ""}), {})
        self.assertEqual(drift({"a": "Public"}, {"a": "public"}), {})


class SyncTests(unittest.TestCase):
    def _sync(self, rows, statuses, *, apply=True, runs=None):
        from analytics import privacy_sync

        updates: list[tuple[int, dict]] = []
        run_updates: list[tuple[int, dict]] = []
        log = SimpleNamespace(
            list_uploaded_for_channel=lambda channel: rows,
            update=lambda row_id, data: updates.append((row_id, data)),
        )
        runs = runs or {}
        run_repo = SimpleNamespace(
            get=lambda rid: runs.get(rid),
            update=lambda rid, data: run_updates.append((rid, data)),
        )
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch("apis.youtube_quota.record_usage") as spent,
        ):
            report = privacy_sync.sync_privacy("tapin", service=_service(statuses), apply=apply)
        return report, updates, run_updates, spent

    def test_the_record_is_corrected_to_what_youtube_says(self):
        rows = [
            _row(1, "a", "unlisted", 92),
            _row(2, "b", "public", 93),
            _row(3, "c", "private", 55),
        ]
        report, updates, _runs, spent = self._sync(
            rows, {"a": "public", "b": "public", "c": "public"}
        )
        self.assertEqual(report["checked"], 3)
        self.assertEqual(
            updates, [(1, {"privacy_status": "public"}), (3, {"privacy_status": "public"})]
        )
        self.assertEqual([c["run_id"] for c in report["changed"]], [92, 55])
        spent.assert_called_once_with(units=1)

    def test_a_dry_run_reports_and_writes_nothing(self):
        rows = [_row(1, "a", "unlisted")]
        report, updates, run_updates, _spent = self._sync(
            rows, {"a": "public"}, apply=False, runs={1: SimpleNamespace(status="scheduled")}
        )
        self.assertEqual(len(report["changed"]), 1)
        self.assertEqual(report["runs_published"], [1])
        self.assertEqual(updates, [])
        self.assertEqual(run_updates, [])

    def test_a_video_gone_from_youtube_is_reported_and_left_alone(self):
        rows = [_row(1, "a", "public"), _row(2, "b", "public")]
        report, updates, _runs, _spent = self._sync(rows, {"a": "public"})
        self.assertEqual([g["video_id"] for g in report["gone"]], ["b"])
        self.assertEqual(updates, [])

    def test_a_run_still_scheduled_follows_its_public_video(self):
        rows = [_row(1, "a", "private", 7), _row(2, "b", "public", 8), _row(3, "c", "unlisted", 9)]
        runs = {
            7: SimpleNamespace(status="scheduled"),
            8: SimpleNamespace(status="published"),
            9: SimpleNamespace(status="scheduled"),
        }
        report, _updates, run_updates, _spent = self._sync(
            rows, {"a": "public", "b": "public", "c": "unlisted"}, runs=runs
        )
        self.assertEqual(run_updates, [(7, {"status": "published"})])
        self.assertEqual(report["runs_published"], [7])

    def test_a_seeded_row_is_not_asked_about(self):
        from storage.repositories.publish_log import SEED_ID_PREFIX

        rows = [_row(1, f"{SEED_ID_PREFIX}x", "public"), _row(2, "", "public")]
        report, _updates, _runs, spent = self._sync(rows, {})
        self.assertEqual(report["checked"], 0)
        spent.assert_not_called()

    def test_a_failed_read_changes_nothing(self):
        from analytics import privacy_sync

        service = MagicMock()
        service.videos.return_value.list.return_value.execute.side_effect = RuntimeError("quota")
        log = SimpleNamespace(
            list_uploaded_for_channel=lambda channel: [_row(1, "a", "unlisted")],
            update=lambda *a: self.fail("nothing may be written"),
        )
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch("apis.youtube_quota.record_usage"),
        ):
            report = privacy_sync.sync_privacy("tapin", service=service)
        self.assertEqual(report["error"], "YouTube did not answer")
        self.assertEqual(
            privacy_sync.sync_lines(report), ["Privacy: not checked (YouTube did not answer)"]
        )


class LineTests(unittest.TestCase):
    def test_the_sync_says_what_it_corrected(self):
        from analytics.privacy_sync import sync_lines

        lines = sync_lines(
            {
                "changed": [
                    {"run_id": 92, "video_id": "a", "was": "unlisted", "now": "public"},
                    {"run_id": 55, "video_id": "c", "was": "private", "now": "public"},
                ],
                "gone": [{"run_id": 12, "video_id": "z", "was": "public", "now": "gone"}],
                "runs_published": [7, 8],
            }
        )
        self.assertIn("2 video(s) are public on YouTube and the record said otherwise", lines[0])
        self.assertIn("run 92, run 55", lines[0])
        self.assertIn("1 video(s) are no longer on YouTube (run 12)", lines[1])
        self.assertIn('2 run(s) were still "scheduled" - now published', lines[2])

    def test_a_record_that_matches_prints_nothing(self):
        from analytics.privacy_sync import sync_lines

        self.assertEqual(
            sync_lines({"checked": 43, "changed": [], "gone": [], "runs_published": []}), []
        )

    def test_the_metrics_sync_calls_it(self):
        from pathlib import Path

        text = (
            Path(__file__)
            .resolve()
            .parent.parent.joinpath("analytics", "sync_metrics.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn("privacy_sync.sync_privacy(channel_id)", text)


if __name__ == "__main__":
    unittest.main()
