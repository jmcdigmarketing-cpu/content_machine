"""Wave 96 (#1218-#1220): what the morning counts, and the lines it prints.

- Every command printed python-dotenv's "could not parse statement starting at line 34" and "36".
  Line 34 of the operator's `.env` is blank; the lines that are not NAME=value are 35, 36 and 39
  (`ops doctor` named them right, #1193). On 2026-10-15 Claude's page told the operator 34 and 36.
- 2026-10-16: 8 of 21 waiting drafts were past their window and the morning said "1 past their
  window" - the window was checked after claims, labels and titles. Answering "n" to "still
  current?" left the draft for later, and it was back the next morning. Run 137, "Cleveland
  Cavaliers at Orlando Magic", had the 7-day window of an evergreen video.
- `ops health` data quality: "signal 'anime' not-ok in the last 4 runs" - runs 136, 137, 146 and
  147, all games before #1170 kept anime off games. The newer runs did not run it, so the streak
  never closed.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

# ---- #1218: dotenv's line numbers are not printed ----------------------------------------------

ENV = "CM_T1218_A=1\nCM_T1218_B=2\n\nClient secret pasted here\nand its second line\n"
ENV += "CM_T1218_C=3\n\nTOKENWITHNOEQUALSSIGN0123456789\nCM_T1218_D=4\n"


class DotenvTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, ".env")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(ENV)

    def _load(self):
        from config.settings import load_env_file

        with patch.dict(os.environ, {}), self.assertLogs(level="WARNING") as logs:
            load_env_file(self.path)
            self.assertEqual(os.environ.get("CM_T1218_D"), "4")
        return [record.getMessage() for record in logs.records]

    def test_the_line_before_a_bad_one_is_never_named(self):
        messages = self._load()
        self.assertFalse(any("could not parse" in m for m in messages), messages)

    def test_the_bad_lines_are_named_once_by_number(self):
        messages = [m for m in self._load() if "not NAME=value" in m]
        self.assertEqual(len(messages), 1)
        self.assertIn("lines 4, 5, 8", messages[0])

    def test_a_clean_file_says_nothing(self):
        from config.settings import load_env_file

        with open(self.path, "w", encoding="utf-8") as f:
            f.write("CM_T1218_E=5\n")
        with patch.dict(os.environ, {}):
            logger = logging.getLogger("config.settings")
            with patch.object(logger, "warning") as warn:
                load_env_file(self.path)
        warn.assert_not_called()


# ---- #1219: a draft past its window says so first, and "no" sets it aside -------------------------


def _meta(**extra):
    base = {
        "run_id": 143,
        "channel_id": "tapin",
        "topic": "Chargers Hopeium going into week 5",
        "title": "Chargers Hopeium: Harbaugh's Pep Talk, McConkey's Return",
        "created_at": (datetime.now() - timedelta(days=2.8)).isoformat(timespec="seconds"),
        "authenticity_verdict": "ok",
        "claim_verification": {
            "unsupported": [{"claim": "The Chargers signed Jake Browning, a former Bengals QB."}],
            "claims": [],
        },
    }
    base.update(extra)
    return base


class WindowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name

    def _draft(self, meta):
        from core.batch_review import PendingDraft

        folder = os.path.join(self.root, str(meta["run_id"]))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
            f.write("# Draft\n\n## Script\n\nThe Chargers are 0-4. Here is the path back.\n")
        return PendingDraft(folder=folder, meta=meta, script="The Chargers are 0-4.")

    def test_run143_says_it_is_past_its_window(self):
        from core.batch_review import unattended_block_reason

        reason = unattended_block_reason(self._draft(_meta()))
        self.assertIn("past its window", reason)

    def test_a_started_game_says_so_before_its_title(self):
        from core.batch_review import unattended_block_reason

        meta = _meta(
            run_id=146,
            topic="Seattle Seahawks at Denver Broncos",
            created_at=datetime.now().isoformat(timespec="seconds"),
            claim_verification={"unsupported": [], "claims": []},
            title_warnings=["title claim not backed by the facts"],
            event_at="2026-10-16T00:15:00+00:00",
        )
        reason = unattended_block_reason(self._draft(meta), now=datetime(2026, 10, 16, 16, 0))
        self.assertTrue(reason.startswith("its game has started"), reason)

    def test_a_fresh_draft_still_names_its_claim(self):
        from core.batch_review import unattended_block_reason

        meta = _meta(created_at=datetime.now().isoformat(timespec="seconds"))
        self.assertEqual(unattended_block_reason(self._draft(meta)), "a claim is not supported")

    def test_the_count_says_how_many_are_past(self):
        from core.batch_review import drafts_line

        self._draft(_meta())
        self._draft(_meta(run_id=144))
        with (
            patch("core.batch_review.unattended_limit", return_value=2),
            patch("core.batch_review.shelf_pause", return_value=""),
        ):
            line = drafts_line("tapin", root=self.root)
        self.assertIn("2 past their window", line)

    def test_no_to_still_current_sets_it_aside(self):
        from core.batch_review import review_drafts

        self._draft(_meta(claim_verification={"unsupported": [], "claims": []}))
        answers = iter(["n"])
        printed: list[str] = []
        review_drafts(
            "tapin",
            root=self.root,
            ask=lambda _prompt: next(answers),
            print_fn=lambda *a, **_k: printed.append(" ".join(str(x) for x in a)),
        )
        with open(os.path.join(self.root, "143", "meta.json"), encoding="utf-8") as f:
            review = json.load(f).get("review") or {}
        self.assertEqual(review.get("decision"), "expired")
        self.assertEqual(review.get("by"), "operator")

    def test_a_fixture_is_news(self):
        from core.batch_review import freshness_window_days

        meta = {
            "topic": "Cleveland Cavaliers at Orlando Magic",
            "title": "Cleveland Cavaliers' Roster Moves Changed Their Season Outlook",
        }
        self.assertEqual(freshness_window_days(meta), 2.0)

    def test_an_evergreen_idea_keeps_its_week(self):
        from core.batch_review import freshness_window_days

        meta = {"topic": "12 Biggest GTA 6 Questions", "title": "GTA 6's Narrative Gaps"}
        self.assertEqual(freshness_window_days(meta), 7.0)


# ---- #1220: a signal's failure streak ends when it stops running -----------------------------------


def _trace(run_id, **signals):
    return {"run_id": run_id, "signals": {k: {"status": v} for k, v in signals.items()}}


class StreakTests(unittest.TestCase):
    def test_anime_off_games_is_no_longer_flagged(self):
        from core.data_quality import _signal_checks

        traces = [  # newest first, as `list_traces` gives them
            _trace(156, news="ok"),
            _trace(155, news="ok"),
            _trace(154, news="ok"),
            _trace(147, anime="unavailable", news="ok"),
            _trace(146, anime="unavailable", news="ok"),
            _trace(137, anime="unavailable", news="ok"),
            _trace(136, anime="unavailable", news="ok"),
        ]
        checks = _signal_checks(traces)
        self.assertNotIn("anime", checks["streaks"])
        self.assertNotIn("anime", checks["high_failure"])

    def test_a_signal_failing_now_is_still_flagged(self):
        from core.data_quality import _signal_checks, warnings

        traces = [_trace(r, odds="error", news="ok") for r in (156, 155, 154)]
        checks = _signal_checks(traces)
        self.assertEqual(checks["streaks"].get("odds"), 3)
        lines = warnings({"signals": checks, "joins": {}})
        self.assertIn("newest run 156", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
