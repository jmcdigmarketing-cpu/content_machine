"""Wave 119 (2026-10-21 evening): the next ten.

Measured first: overnight's first follow-up (run 179, the Pistons) said "Since then, Detroit
clinched the No. 1 seed" - last season's playoff page, which the claim check passed because the
source supports it - and only "hard to say" stood between it and an unattended render. The sign-in
lapses tonight, and "Yours today" listed it only while it was still in its Testing window.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

TITLE = "Detroit Pistons bench outplays Boston Celtics reserves in key stretch"


class FollowUpDateTests(unittest.TestCase):
    """#1536: the follow-up names the original's date, and is still made once per video."""

    def _topic(self, recent):
        from core import batch_generation

        published = datetime(2026, 10, 18, 15, 8, tzinfo=timezone.utc)
        rows = [{"run_id": 162, "title": TITLE[:60], "subs": 2, "published": published}]
        repo = SimpleNamespace(get=lambda rid: SimpleNamespace(title=TITLE))
        with (
            patch("analytics.growth._rows", return_value=rows),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.channel_context.recent_input_topics", return_value=recent),
            patch.object(batch_generation, "unreviewed_draft", return_value=None),
        ):
            return batch_generation.follow_up_topic("tapin", now=published + timedelta(days=3))

    def test_the_date_is_in_it(self):
        self.assertEqual(
            self._topic([]),
            f'Follow-up to "{TITLE}" (Oct 18): what has happened since Oct 18',
        )

    def test_once_even_in_the_old_words(self):
        self.assertEqual(self._topic([f'Follow-up to "{TITLE}": what has happened since']), "")


class FollowUpHoldTests(unittest.TestCase):
    """#1536 (the operator: hold for review): a follow-up that says "since" waits for a person."""

    def _reason(self, topic, script):
        from core import batch_review

        draft = batch_review.PendingDraft(
            folder="f", meta={"run_id": 179, "title": "Pistons", "topic": topic}, script=script
        )
        with (
            patch.object(batch_review, "dead_reason", return_value=""),
            patch.object(batch_review, "_blocking_claims", return_value=False),
            patch.object(batch_review, "authenticity_now", return_value=("ok", "")),
            patch.object(batch_review, "game_block_reason", return_value=""),
            patch.object(batch_review, "arc_counter_reason", return_value=""),
        ):
            return batch_review.unattended_block_reason(draft)

    def test_run_179_is_held(self):
        reason = self._reason(
            f'Follow-up to "{TITLE}": what has happened since',
            "23-0 run. Since then, Detroit clinched the No. 1 seed in the East.",
        )
        self.assertIn("follow-up", reason)
        self.assertIn("since", reason)

    def test_other_drafts_and_follow_ups_without_it_render(self):
        self.assertEqual(
            self._reason("Xbox Game Pass adds Final Fantasy 7", "Since launch, it sold well."), ""
        )
        self.assertEqual(
            self._reason(
                f'Follow-up to "{TITLE}" (Oct 18)', "The bench went 23-0. That is the story."
            ),
            "",
        )


class YoursAfterTheLapseTests(unittest.TestCase):
    """#1537: once the sign-in has lapsed, "Yours today" says to sign in again."""

    def test_the_lapse_is_named(self):
        from core import status_summary

        with (
            patch(
                "youtube.oauth.sign_in_status",
                return_value="YouTube sign-in for tapin has expired or been revoked",
            ),
            patch(
                "youtube.oauth.sign_in_expiry",
                return_value=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
            patch("core.stale_renders.shelf_rows", return_value=[]),
            patch("os.path.isdir", return_value=False),
        ):
            items = status_summary.yours_items("tapin")
        self.assertEqual(len(items), 1)
        self.assertTrue(
            items[0].startswith(
                "sign in again - uploads wait: py -m youtube.oauth_setup --channel tapin"
            )
        )


class CrashLogTests(unittest.TestCase):
    """#1466 and #1463: a run that never finished keeps its log; the week counts them."""

    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = os.path.join(self.tmp.name, "overnight-last.log")
        self.crashes = os.path.join(self.tmp.name, "crashes")
        with open(self.log, "w", encoding="utf-8") as handle:
            handle.write("\n".join(f"line {i}" for i in range(300)))

    def _keep(self, started, finished, now):
        from core import nightly_task

        with (
            patch.object(nightly_task, "_recorded_start", return_value=started),
            patch.object(nightly_task, "_recorded_finish", return_value=finished),
        ):
            return nightly_task.keep_crash_log(now=now, log_path=self.log, crash_dir=self.crashes)

    def test_an_unfinished_run_keeps_its_last_200_lines(self):
        import os

        started = datetime.now() - timedelta(hours=4)
        os.utime(self.log, None)
        kept = self._keep(started, None, datetime.now())
        self.assertTrue(kept.endswith(f"overnight-{started:%Y%m%d-%H%M}.log"))
        with open(kept, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual((len(lines), lines[0], lines[-1]), (200, "line 100", "line 299"))
        self.assertEqual(self._keep(started, None, datetime.now()), "")  # once

    def test_a_finished_or_running_run_keeps_nothing(self):
        started = datetime.now() - timedelta(hours=4)
        self.assertEqual(self._keep(started, started + timedelta(minutes=8), datetime.now()), "")
        self.assertEqual(
            self._keep(datetime.now() - timedelta(minutes=30), None, datetime.now()), ""
        )

    def test_the_week_counts_them(self):
        import os

        from core.nightly_task import crash_count

        os.makedirs(self.crashes)
        now = datetime(2026, 10, 21, 20, 0)
        for name in (
            "overnight-20261020-0500.log",
            "overnight-20261016-0500.log",
            "overnight-20261010-0500.log",
        ):
            open(os.path.join(self.crashes, name), "w").close()
        self.assertEqual(crash_count(now=now, crash_dir=self.crashes), 2)


class DropOffTests(unittest.TestCase):
    """#1494: each video's drop-off second - where it fell under half its viewers."""

    def test_the_second(self):
        from core.retention import drop_off_position, drop_off_text

        curve = [(0.0, 1.1), (0.2, 0.8), (0.4, 0.55), (0.5, 0.45), (0.8, 0.3)]
        self.assertEqual(drop_off_position(curve), 0.5)
        self.assertEqual(drop_off_text(0.5, 42.0), "half gone at 0:21 of 0:42")
        self.assertEqual(drop_off_text(0.5, None), "half gone at 50%")
        self.assertIsNone(drop_off_position([(0.0, 1.0), (0.5, 0.9), (1.0, 0.6)]))


class SecondReadTests(unittest.TestCase):
    """#1341: a cheap second read of an overnight render's title and first sentence."""

    def test_a_no_holds_and_a_yes_passes(self):
        from core.batch_review import second_read

        bad = second_read(
            "Pistons win",
            "The bench went 23-0 and",
            call=lambda s, u: {"ok": False, "why": "cut off"},
        )
        self.assertEqual(bad, "cut off")
        self.assertEqual(
            second_read("Pistons win", "Detroit won.", call=lambda s, u: {"ok": True}), ""
        )
        self.assertEqual(
            second_read("t", "s", call=lambda s, u: (_ for _ in ()).throw(RuntimeError("x"))), ""
        )

    def test_the_render_waits_on_a_no(self):
        from core import batch_review

        draft = SimpleNamespace(run_id=175, title="T", script="S.", meta={})
        with (
            patch.object(batch_review, "unattended_candidates", return_value=([draft], [])),
            patch.object(batch_review, "shelf_max", return_value=0),
            patch.object(
                batch_review,
                "second_read",
                return_value="the title says more than the first sentence",
            ),
        ):
            out = batch_review.render_unattended(
                "tapin", 1, render=lambda d, q: (_ for _ in ()).throw(AssertionError("rendered"))
            )
        self.assertEqual(out["rendered"], [])
        self.assertIn(
            (175, "second read: the title says more than the first sentence"), out["waiting"]
        )


class YouTypedTests(unittest.TestCase):
    """#1343 and #1342: your idea beside what it wrote, with the share of your words it kept."""

    def test_the_lines(self):
        from core.batch_review import typed_lines

        lines = typed_lines(
            "Pereira should fight Ankalaev again in March",
            "Pereira wants Ankalaev again. March is the date he named. Everything else is noise.",
        )
        self.assertEqual(lines[0], "    you typed: Pereira should fight Ankalaev again in March")
        self.assertEqual(
            lines[1], "    it wrote:  Pereira wants Ankalaev again. March is the date he named."
        )
        self.assertIn("4 of your 5 words", lines[2])


if __name__ == "__main__":
    unittest.main()
