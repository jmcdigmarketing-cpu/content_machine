"""Wave 118 (2026-10-20 evening): the next ten.

Measured first: today's overnight made 3 drafts and rendered none - two held only by "1 sentence
hard to say", whose read-aloud rewrite threw away correct splits; run 176's draft read "... the
way a name does. 24 at Etihad Arena", because the stock-phrase pass split at "Oct."; and the
Tonight line said "renders up to 2" while the shelf pause (3 finished videos waiting) held them.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TonightPausedTests(unittest.TestCase):
    """#1534 (wave 117's slip): the Tonight line reads the shelf pause."""

    PAUSE = "3 finished videos are waiting (overnight stops at 3) - py -m scripts.ops shelf --channel tapin"

    def test_the_paused_text(self):
        from core.nightly_task import tonight_text

        self.assertEqual(
            tonight_text(3, 2, (5, 0), paused=self.PAUSE),
            "Tonight at 5:00 AM (or when the PC is next on): drafts 3, no renders - 3 finished "
            "videos wait for you (ops shelf)",
        )

    def test_the_line_asks_the_shelf(self):
        from core import nightly_task

        with (
            patch.object(
                nightly_task, "_queried_times", return_value={"count": 3, "start": (5, 0)}
            ),
            patch("core.batch_review.pending_drafts", return_value=[]),
            patch("core.batch_review.overnight_render_limit", return_value=(2, "")),
            patch("core.batch_review.shelf_pause", return_value=self.PAUSE),
            patch("os.path.isdir", return_value=True),
        ):
            line = nightly_task.tonight_line("tapin")
        self.assertIn("no renders - 3 finished videos wait for you", line)


RUN_176 = (
    "Aldo's logic: an undefeated No. 1 contender who wins decisions doesn't sell the way a name "
    "does. UFC 333 is Saturday, Oct. 24 at Etihad Arena in Abu Dhabi. The odds are dead even."
)


class SentenceSplitTests(unittest.TestCase):
    """#1532: one splitter that does not break at "No." or "Oct." (run 176)."""

    def test_abbreviations_hold(self):
        from apis.topic_tokens import split_sentences

        self.assertEqual(
            split_sentences(RUN_176),
            [
                "Aldo's logic: an undefeated No. 1 contender who wins decisions doesn't sell the "
                "way a name does.",
                "UFC 333 is Saturday, Oct. 24 at Etihad Arena in Abu Dhabi.",
                "The odds are dead even.",
            ],
        )

    def test_the_passes_that_cut_use_it(self):
        from core.script_craft import hard_to_say, script_sentences

        self.assertEqual(len(script_sentences(RUN_176)), 3)
        self.assertFalse(any(s["sentence"].startswith("24") for s in hard_to_say(RUN_176)))

    def test_a_repeated_sentence_goes_whole(self):
        from core.authenticity import rewrite_repeated

        recent = [
            "Big fight. UFC 333 is Saturday, Oct. 24 at Etihad Arena in Abu Dhabi. Tune in."
        ] * 3
        out, verdict = rewrite_repeated(RUN_176, recent)
        self.assertTrue(verdict["rewritten"])
        self.assertNotIn("24 at Etihad", out)  # the whole sentence, never "... Oct." alone
        self.assertIn("No. 1 contender", out)

    def test_no_new_private_splitter(self):
        """The naive `(?<=[.!?])` split may fall, never rise (30 before wave 118)."""
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        count = sum(
            path.read_text(encoding="utf-8", errors="replace").count("(?<=[.!?])")
            for folder in ("core", "apis", "analytics", "publishing", "video", "scripts", "jobs")
            for path in (root / folder).rglob("*.py")
        )
        self.assertLessEqual(count, 27, "split with apis.topic_tokens.split_sentences instead")


class ReadAloudSplitTests(unittest.TestCase):
    """#1531: a rewrite that splits a sentence keeps it - a name may move to the front."""

    OLD = "Volkanovski, 28-4 with 13 knockouts, against Evloev, 19-0 with three KOs and four submissions."
    NEW = "Volkanovski is 28-4 with 13 knockouts. Evloev is 19-0, with three KOs and four submissions."

    def test_names_kept_where_they_move(self):
        from core.script_craft import _names_kept

        self.assertTrue(_names_kept(self.OLD, self.NEW))
        self.assertFalse(_names_kept(self.OLD, self.NEW.replace("Evloev", "He")))
        self.assertFalse(_names_kept(self.OLD, self.NEW + " Holloway watches."))

    def test_the_pass_keeps_the_split(self):
        import os

        from core.script_craft import read_aloud_pass

        script = f"The card is set. {self.OLD} Pick one."
        with patch.dict(os.environ, {"READ_ALOUD_REWRITE": "true"}):
            out, report = read_aloud_pass(
                script, lambda s, u: {"rewrites": [{"old": self.OLD, "new": self.NEW}]}
            )
        self.assertEqual(report["rewritten"], 1)
        self.assertIn("Evloev is 19-0", out)


class HardToSayWarnTests(unittest.TestCase):
    """#1535 (the operator: warn only): "hard to say" alone does not hold an overnight render."""

    def _reason(self, why):
        from core import batch_review

        draft = batch_review.PendingDraft(
            folder="f",
            meta={
                "run_id": 175,
                "title": "Xbox Game Pass",
                "script_clean": {"ok": False, "why": why},
            },
            script="A clean sentence.",
        )
        with (
            patch.object(batch_review, "dead_reason", return_value=""),
            patch.object(batch_review, "_blocking_claims", return_value=False),
            patch.object(batch_review, "authenticity_now", return_value=("ok", "")),
            patch.object(batch_review, "game_block_reason", return_value=""),
            patch.object(batch_review, "arc_counter_reason", return_value=""),
        ):
            return batch_review.unattended_block_reason(draft)

    def test_alone_it_renders(self):
        self.assertEqual(self._reason(["1 sentence(s) hard to say"]), "")

    def test_with_another_reason_it_waits(self):
        self.assertEqual(
            self._reason(["1 sentence(s) hard to say", "1 thing said twice"]),
            "script check: 1 thing said twice",
        )


class DeadlineDayTests(unittest.TestCase):
    """#1533: the decide-first deadline names its day - "8:30 PM EDT" read as tonight."""

    def test_the_day_is_there(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace

        from core import batch_review

        kickoff = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)  # Sat 1 PM EDT
        draft = SimpleNamespace(
            decision="", meta={"event_at": kickoff.isoformat()}, title="UFC 333 Preview", run_id=176
        )
        slots = [datetime(2026, 10, 24, 2, 0, tzinfo=timezone.utc)]  # Fri 10 PM EDT
        with (
            patch.object(batch_review, "pending_drafts", return_value=[draft]),
            patch("core.spaced_queue._taken_slots", return_value=set()),
            patch("core.spaced_queue.free_slots", return_value=slots),
        ):
            line = batch_review.deadline_line(
                "tapin", now=datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc)
            )
        self.assertIn("review it by Fri Oct 23 8:30 PM EDT for its 10:00 PM EDT slot", line)


class YoursTodayTests(unittest.TestCase):
    """#1407: what is yours today, in one line - and "Nothing by hand today" only when true."""

    def test_the_words(self):
        from core.status_summary import yours_text

        self.assertEqual(yours_text([]), "Nothing by hand today")
        self.assertEqual(yours_text(["a", "b"]), "Yours today: a; b")

    def test_the_items(self):
        from datetime import datetime, timedelta, timezone
        from types import SimpleNamespace

        from core import status_summary

        soon = datetime.now(timezone.utc) + timedelta(hours=20)
        rows = [{"run_id": n, "state": "unlisted on YouTube"} for n in (168, 170)] + [
            {"run_id": 171, "state": "rendered, never uploaded"}
        ]
        drafts = [SimpleNamespace(decision="") for _ in range(3)]
        deadline = (
            "Decide first: UFC 333 Preview - kicks off Sat Oct 24 1:00 PM EDT; review it by Fri Oct "
            "23 8:30 PM EDT for its 10:00 PM EDT slot"
        )
        with (
            patch("youtube.oauth.sign_in_status", return_value=""),  # wave 119: signed in
            patch("youtube.oauth.sign_in_expiry", return_value=soon),
            patch("youtube.oauth.sign_in_mode", return_value="testing"),
            patch("core.stale_renders.shelf_rows", return_value=rows),
            patch("core.batch_review.shelf_pause", return_value="3 finished videos are waiting"),
            patch("core.batch_review.shelf_max", return_value=3),
            patch("core.batch_review.pending_drafts", return_value=drafts),
            patch("core.batch_review.deadline_line", return_value=deadline),
            patch("os.path.isdir", return_value=True),
        ):
            items = status_summary.yours_items("tapin")
        self.assertEqual(len(items), 3)
        self.assertTrue(items[0].startswith("publish the Google app before "))
        self.assertEqual(
            items[1],
            "decide 3 finished videos (ops shelf) - overnight renders nothing until fewer than 3 wait",
        )
        self.assertEqual(
            items[2],
            "review 3 drafts (ops batch-review) - UFC 333 Preview by Fri Oct 23 8:30 PM EDT",
        )


class ChapterFillTests(unittest.TestCase):
    """#1430 (the operator: gaming and evergreen only): chapter Shorts fill empty slots."""

    def _run(self, run_id, title, *, status="published", features=None):
        import json
        from types import SimpleNamespace

        return SimpleNamespace(
            id=run_id, title=title, status=status, features_json=json.dumps(features or {})
        )

    def test_the_candidates(self):
        from types import SimpleNamespace

        from core import chapter_shorts

        runs = [
            self._run(
                92,
                "GTA 6 Leaks, PC Rumors & Multiplayer Delay: All Angles",
                features={"all_angles": True},
            ),
            self._run(99, "UFC week 2: Gane stops Pereira", features={"all_angles": True}),
            self._run(
                80,
                "GTA 6 chapter",
                status="rendered",
                features={"short_source": "chapter_cut", "parent_run_id": 92, "chapter_index": 0},
            ),
        ]
        spans = [SimpleNamespace(fits_shorts=ok) for ok in (True, True, False)]
        with (
            patch.object(
                chapter_shorts,
                "get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            patch.object(chapter_shorts, "_record_spans", return_value=([], spans, "text")),
            patch(
                "apis.topic_scorer.infer_domain",
                side_effect=lambda t, c=None: "gaming" if "GTA" in t else "ufc",
            ),
        ):
            self.assertEqual(chapter_shorts.fill_candidates("tapin"), [(92, 1)])

    def _fill(self, *, scheduled=3, paused="", picks=((92, 1), (92, 3), (120, 0))):
        from core import chapter_shorts

        made = []

        def cut(parent, indices):
            made.append((parent, indices[0]))
            return [chapter_shorts.ChapterShort(indices[0], "t", 500 + len(made), "x.mp4")]

        queued = []
        with (
            patch.object(chapter_shorts, "scheduled_next_days", return_value=scheduled),
            patch("core.batch_review.shelf_pause", return_value=paused),
            patch.object(chapter_shorts, "fill_candidates", return_value=list(picks)),
        ):
            lines = chapter_shorts.fill_empty_slots(
                "tapin", cut=cut, queue=lambda rid, ch: queued.append(rid) or 9
            )
        return lines, made, queued

    def test_two_a_night_queued_unlisted(self):
        lines, made, queued = self._fill()
        self.assertEqual(made, [(92, 1), (92, 3)])
        self.assertEqual(queued, [501, 502])
        self.assertIn("queued unlisted", " ".join(lines))

    def test_held_by_the_shelf_or_a_full_week(self):
        lines, made, _queued = self._fill(
            paused="3 finished videos are waiting (overnight stops at 3)"
        )
        self.assertEqual(made, [])
        self.assertIn("none cut - 3 finished videos are waiting", lines[0])
        self.assertEqual(self._fill(scheduled=7), ([], [], []))

    def test_the_overnight_report_says_it(self):
        from core.overnight import OvernightResult, render_overnight

        result = OvernightResult(channel_id="tapin")
        result.chapter_lines = ["Chapter Shorts: 3 scheduled in the next 7 days - cutting 2"]
        self.assertIn("Chapter Shorts: 3 scheduled", render_overnight(result))


if __name__ == "__main__":
    unittest.main()
