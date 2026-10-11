"""Wave 75: three defects the wave 74 checks turned up.

- #1115: run 133 asked for five angles and kept one chapter. The file was renamed (#1102) but
  `features.all_angles` stayed true, so the pre-publish checklist asked a single-angle video
  for a chapter list and the Shorts split read it as long-form.
- #1116: run 132's title spells "Illia Topuria"; every YouTube suggestion spells it "ilia".
- #1117: a run trace carries `run_id` and no title, description, script or file path. `ops
  desc-fold` read `trace["description"]` and always answered "No description on the last run";
  `ops publish-dry-run` printed "Dry-run title".
"""

from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


class OneChapterIsNotAllAnglesTests(unittest.TestCase):
    def test_two_or_more_kept_chapters_is_an_all_angles_video(self):
        from core.angle_chapters import is_all_angles

        self.assertTrue(is_all_angles(5))
        self.assertTrue(is_all_angles(2))

    def test_one_kept_chapter_is_a_single_angle_video(self):
        from core.angle_chapters import is_all_angles

        self.assertFalse(is_all_angles(1))
        self.assertFalse(is_all_angles(0))

    def test_the_pipeline_stores_what_was_kept(self):
        """The line that wrote `True` whatever was kept now asks the helper."""
        from pathlib import Path

        text = (
            Path(__file__)
            .resolve()
            .parent.parent.joinpath("core", "pipeline.py")
            .read_text(encoding="utf-8")
        )
        self.assertNotIn('result.features["all_angles"] = True', text)
        self.assertIn('result.features["all_angles"] = is_all_angles(len(chapters))', text)


SUGGESTIONS = [
    "ilia topuria",
    "ilia topuria vs justin gaethje",
    "ilia topuria highlights",
    "ilia topuria walkout",
]


class SubjectSpellingTests(unittest.TestCase):
    def _check(self, title, suggestions=SUGGESTIONS):
        from core.title_generator import suggest_check

        return suggest_check(title, "UFC Illia Islam", fetch=lambda phrase: suggestions)

    def test_a_one_letter_difference_is_reported(self):
        got = self._check("Can Illia Topuria adapt before UFC's next title cycle?")
        self.assertEqual(got["spelling"], {"typed": "illia", "searched": "ilia"})

    def test_the_line_says_how_people_spell_it(self):
        from core.title_generator import suggest_line

        line = suggest_line(self._check("Can Illia Topuria adapt before UFC's next title cycle?"))
        self.assertIn('"ilia"', line)
        self.assertIn('"illia"', line.lower())

    def test_a_matching_spelling_reports_nothing(self):
        got = self._check("Can Ilia Topuria adapt before the next title cycle?")
        self.assertNotIn("spelling", got)

    def test_a_different_word_is_not_a_spelling(self):
        got = self._check(
            "Can Illia Topuria adapt?", ["islam makhachev", "islam makhachev highlights"]
        )
        self.assertNotIn("spelling", got)

    def test_one_stray_suggestion_is_not_enough(self):
        got = self._check(
            "Can Illia Topuria adapt?",
            ["illia topuria", "illia topuria next fight", "ilia topuria", "illia topuria wife"],
        )
        self.assertNotIn("spelling", got)


RUN = SimpleNamespace(
    title="Can the Chargers still make the Super Bowl?",
    description="First line.\n\nSecond block that sits below the fold.",
    script_preview="The Chargers are 0-4.",
    mp4_path="output/chargers.mp4",
    tags_json='["chargers", "nfl"]',
    features_json='{"domain": "nfl"}',
)


class TraceRunTests(unittest.TestCase):
    def _trace_run(self, trace, run=RUN):
        from core import review_booth

        repo = SimpleNamespace(get=lambda rid: run)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            return review_booth.trace_run(trace)

    def test_the_runs_copy_fills_what_the_trace_lacks(self):
        got = self._trace_run({"run_id": 131, "selected_topic": "chargers", "cost": {"total": 1}})
        self.assertEqual(got["title"], RUN.title)
        self.assertEqual(got["description"], RUN.description)
        self.assertEqual(got["script"], RUN.script_preview)
        self.assertEqual(got["mp4_path"], RUN.mp4_path)
        self.assertEqual(got["tags"], ["chargers", "nfl"])
        self.assertEqual(got["features"], {"domain": "nfl"})
        self.assertEqual(got["cost"], {"total": 1})

    def test_what_the_trace_has_wins(self):
        got = self._trace_run({"run_id": 131, "title": "From the trace"})
        self.assertEqual(got["title"], "From the trace")

    def test_no_run_is_the_trace_unchanged(self):
        self.assertEqual(self._trace_run({"status": "drafted"}), {"status": "drafted"})
        self.assertEqual(self._trace_run({"run_id": 131}, run=None), {"run_id": 131})
        self.assertEqual(self._trace_run(None), {})

    def test_desc_fold_reads_the_last_runs_description(self):
        from core import review_booth
        from scripts.ops import COMMANDS

        repo = SimpleNamespace(get=lambda rid: RUN)
        with (
            patch.object(review_booth, "last_trace", return_value={"run_id": 131}),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = COMMANDS["desc-fold"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn("First line.", buf.getvalue())

    def test_the_dry_run_uses_the_runs_title(self):
        from core import review_booth
        from publishing import prepublish
        from scripts.ops import COMMANDS

        repo = SimpleNamespace(get=lambda rid: RUN)
        with (
            patch.object(review_booth, "last_trace", return_value={"run_id": 131}),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch.object(prepublish, "checklist", return_value=[]),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                COMMANDS["publish-dry-run"][1](Namespace(channel="tapin"))
        self.assertIn(RUN.title, buf.getvalue())
        self.assertNotIn("Dry-run title", buf.getvalue())


class KeptOneAngleIsShownTests(unittest.TestCase):
    def test_the_checklist_says_one_of_five_was_kept(self):
        from publishing import prepublish
        from publishing.base import PublishRequest

        run = SimpleNamespace(
            description="", features_json='{"all_angles": false, "angles_asked": 5}'
        )
        request = PublishRequest(file_path="x.mp4", title="T", description="Body.")
        with (
            patch.object(prepublish, "_disclosure_line", return_value=""),
            patch.object(prepublish, "_run", return_value=run),
        ):
            checks = {
                c.name: c
                for c in prepublish.checklist(request, channel_id="tapin", content_run_id=133)
            }
        self.assertTrue(checks["chapters"].ok)
        self.assertIn("one of 5 angles kept", checks["chapters"].detail)

    def test_the_review_screen_shows_the_read_aloud_count(self):
        from core.ui import display_fact_engine_report

        printed: list[str] = []
        display_fact_engine_report(
            {"read_aloud": {"flagged": 3, "rewritten": 1, "why": ["names", "numbers"]}},
            print_fn=printed.append,
        )
        text = "\n".join(printed)
        self.assertIn("3 sentence(s) hard to say", text)
        self.assertIn("1 rewritten", text)


if __name__ == "__main__":
    unittest.main()
