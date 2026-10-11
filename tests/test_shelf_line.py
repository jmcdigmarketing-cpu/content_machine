"""Wave 77 (#1122): finished videos that are not public, on the lines the operator reads.

Measured 2026-10-10: 129 TapIn runs had produced 32 public videos. 13 renders were never
uploaded, 5 uploads were still unlisted (two of them rendered past the grounding gate), and
the startup header, `ops status` and the weekly decisions said nothing about the unlisted ones
and did not tell a recent render from one months past its news date.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch


def _row(run_id, privacy="unlisted", video_id="vid"):
    return SimpleNamespace(
        id=run_id, content_run_id=run_id, privacy_status=privacy, youtube_video_id=video_id
    )


class ShelfCountTests(unittest.TestCase):
    def _shelf(self, renders, ages, rows, overrides=()):
        from core import stale_renders

        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=renders),
            patch.object(stale_renders, "render_age_days", side_effect=lambda run: ages[run.id]),
            patch("publishing.go_public.unlisted_holds", return_value=rows),
            patch("publishing.go_public.override_held", side_effect=lambda rid: rid in overrides),
        ):
            return stale_renders.shelf("tapin")

    def test_renders_split_by_age_and_holds_split_by_claim(self):
        renders = [SimpleNamespace(id=1), SimpleNamespace(id=114), SimpleNamespace(id=132)]
        got = self._shelf(
            renders, {1: 120.0, 114: 31.0, 132: 0.5}, [_row(92), _row(98), _row(119)], (92, 119)
        )
        self.assertEqual(got, {"renders": 3, "stale": 2, "unlisted": 3, "claim": 2})

    def test_a_render_with_no_file_age_is_not_called_stale(self):
        got = self._shelf([SimpleNamespace(id=5)], {5: None}, [])
        self.assertEqual(got, {"renders": 1, "stale": 0, "unlisted": 0, "claim": 0})

    def test_unlisted_holds_reads_only_unlisted_rows_with_a_video(self):
        from publishing import go_public

        rows = [_row(1, "public"), _row(2), _row(3, video_id=""), _row(4, "private"), _row(5)]
        repo = SimpleNamespace(list_uploaded_for_channel=lambda channel: rows)
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            self.assertEqual([r.id for r in go_public.unlisted_holds("tapin")], [5, 2])


class ShelfLineTests(unittest.TestCase):
    def test_each_kind_names_the_command_that_moves_it(self):
        from core.stale_renders import shelf_lines

        lines = shelf_lines("tapin", {"renders": 13, "stale": 11, "unlisted": 5, "claim": 2})
        self.assertEqual(len(lines), 2)
        self.assertIn("Unlisted, not public: 5 video(s)", lines[0])
        self.assertIn("3 ready - py -m scripts.ops go-public --channel tapin", lines[0])
        self.assertIn("2 held for a claim - py -m scripts.ops verify-claim", lines[0])
        self.assertIn("Rendered, not on YouTube: 13 video(s)", lines[1])
        self.assertIn("2 recent - py -m scripts.requeue_upload --channel tapin", lines[1])
        self.assertIn("11 older than 30 days - py -m scripts.ops retire-renders", lines[1])

    def test_nothing_on_the_shelf_prints_nothing(self):
        from core.stale_renders import shelf_lines, shelf_short

        empty = {"renders": 0, "stale": 0, "unlisted": 0, "claim": 0}
        self.assertEqual(shelf_lines("tapin", empty), [])
        self.assertEqual(shelf_short(empty), "")

    def test_only_fresh_renders_offer_no_retire_command(self):
        from core.stale_renders import shelf_lines

        (line,) = shelf_lines("tapin", {"renders": 1, "stale": 0, "unlisted": 0, "claim": 0})
        self.assertNotIn("retire-renders", line)


class WhereItIsShownTests(unittest.TestCase):
    COUNTS: ClassVar[dict[str, int]] = {"renders": 13, "stale": 11, "unlisted": 5, "claim": 2}

    def test_the_startup_header_counts_them(self):
        from core import status

        with (
            patch.object(status, "_hdr_name", return_value="TapIn"),
            patch.object(status, "_hdr_sign_in", return_value="sign-in ok"),
            patch.object(status, "_hdr_spent", return_value=""),
            patch.object(status, "_hdr_uploads", return_value=""),
            patch.object(status, "_hdr_queue", return_value=""),
            patch.object(status, "_hdr_last", return_value=""),
            patch("core.stale_renders.shelf", return_value=self.COUNTS),
        ):
            self.assertEqual(
                status.header_line("tapin"), "TapIn · sign-in ok · 18 finished, not public"
            )

    def test_the_header_says_nothing_when_all_of_it_is_public(self):
        from core import status

        with (
            patch.object(status, "_hdr_name", return_value="TapIn"),
            patch.object(status, "_hdr_sign_in", return_value=""),
            patch.object(status, "_hdr_spent", return_value=""),
            patch.object(status, "_hdr_uploads", return_value=""),
            patch.object(status, "_hdr_queue", return_value=""),
            patch.object(status, "_hdr_last", return_value=""),
            patch("core.stale_renders.shelf", return_value={}),
        ):
            self.assertEqual(status.header_line("tapin"), "TapIn")

    def test_ops_status_lists_the_unlisted_ones(self):
        from core.status import build_status_lines

        with patch("core.stale_renders.shelf", return_value=self.COUNTS):
            text = "\n".join(build_status_lines("tapin"))
        self.assertIn("Unlisted, not public: 5 video(s)", text)
        self.assertIn("Rendered, not on YouTube: 13 video(s)", text)

    def test_the_weekly_decisions_open_with_it(self):
        from analytics.weekly_report import operator_digest, shelf_decision

        report = {
            "ready": True,
            "channel_id": "tapin",
            "next_actions": ["Make more ranking videos."],
            "shelf": self.COUNTS,
        }
        first = shelf_decision(report)
        self.assertIn("18 finished video(s) are not public", first)
        self.assertIn("5 unlisted, 13 never uploaded", first)
        digest = operator_digest(report)
        self.assertLess(digest.index("18 finished"), digest.index("1. Make more ranking"))

    def test_the_weekly_decisions_skip_it_when_the_shelf_is_empty(self):
        from analytics.weekly_report import operator_digest, shelf_decision

        report = {"ready": True, "channel_id": "tapin", "next_actions": ["Do X."], "shelf": {}}
        self.assertEqual(shelf_decision(report), "")
        self.assertNotIn("not public", operator_digest(report))


if __name__ == "__main__":
    unittest.main()
