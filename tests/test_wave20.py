"""Wave 20: the Piper long-form experiment failed its listen, plus chapter quality.

Operator verdict 2026-09-17 after run 79: Piper long-form is "clearly worse" - it goes back to
ElevenLabs and Piper survives only as the 1-in-6 Shorts mix. A long video is 1-2 a month; the
3-5/week target is Shorts. Spend warns weekly and blocks nothing. Each test here failed on
unmodified b4e06fe unless its docstring says it guards existing behaviour.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


# --- #775 long-form voice ------------------------------------------------------------


class TestLongFormVoiceIsPaidAgain(unittest.TestCase):
    def test_extended_keeps_the_configured_provider(self):
        from core.tts import long_form_provider

        with patch.dict(os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": ""}):
            self.assertEqual(long_form_provider("elevenlabs", "4"), "elevenlabs")
            self.assertEqual(long_form_provider("elevenlabs", "3"), "elevenlabs")
            self.assertEqual(long_form_provider("elevenlabs", "2"), "elevenlabs")

    def test_the_operator_can_still_opt_in(self):
        from core.tts import long_form_provider

        with patch.dict(os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": "piper"}):
            self.assertEqual(long_form_provider("elevenlabs", "4"), "piper")
            self.assertEqual(long_form_provider("elevenlabs", "2"), "elevenlabs")

    def test_extended_costs_money_again(self):
        from core.cost_meter import render_cost_lines

        with patch.dict(os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": ""}):
            self.assertGreater(render_cost_lines("x" * 5700, length_choice="4")["tts"], 1.0)

    def test_piper_mixes_into_one_short_in_six(self):
        from core.tts import _piper_mix_every

        with patch.dict(os.environ, {"TTS_PIPER_MIX_EVERY": ""}):
            self.assertEqual(_piper_mix_every(), 6)

    def test_env_example_records_the_verdict(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("TTS_PROVIDER_LONG", text)
        self.assertIn("TTS_PIPER_MIX_EVERY=6", text)


# --- #776 weekly spend warning -------------------------------------------------------


class TestWeeklySpendWarning(unittest.TestCase):
    def _traces(self, root: Path, rows: list[tuple[float, float]]) -> None:
        for i, (days_ago, total) in enumerate(rows, 1):
            (root / f"{i}.json").write_text(
                json.dumps(
                    {"run_id": i, "at": time.time() - days_ago * 86400, "cost": {"total": total}}
                ),
                encoding="utf-8",
            )

    def test_only_the_last_seven_days_count(self):
        from core import spend_week

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._traces(root, [(1.0, 2.0), (3.0, 1.5), (9.0, 40.0)])
            with patch.object(spend_week, "TRACES_DIR", str(root)):
                usd, runs = spend_week.weekly_spend()
        self.assertAlmostEqual(usd, 3.5, places=2)
        self.assertEqual(runs, 2)

    def test_the_line_names_the_overage_and_stays_quiet_under_it(self):
        from core import spend_week

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._traces(root, [(1.0, 4.0), (2.0, 2.4)])
            with (
                patch.object(spend_week, "TRACES_DIR", str(root)),
                patch.dict(os.environ, {"SPEND_WARN_WEEKLY_USD": "5"}),
            ):
                line = spend_week.spend_warning_line()
                self.assertIn("$6.40", line)
                self.assertIn("7 days", line)
                self.assertIn("2 run", line)
            with (
                patch.object(spend_week, "TRACES_DIR", str(root)),
                patch.dict(os.environ, {"SPEND_WARN_WEEKLY_USD": "50"}),
            ):
                self.assertEqual(spend_week.spend_warning_line(), "")

    def test_an_unreadable_trace_never_raises(self):
        from core import spend_week

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.json").write_text("{not json", encoding="utf-8")
            with patch.object(spend_week, "TRACES_DIR", str(root)):
                self.assertEqual(spend_week.weekly_spend(), (0.0, 0))

    def test_status_and_overnight_print_it(self):
        for name in ("core/status.py", "core/overnight.py"):
            with self.subTest(caller=name):
                self.assertIn("spend_warning_line(", (ROOT / name).read_text(encoding="utf-8"))
        self.assertIn("SPEND_WARN_WEEKLY_USD", (ROOT / ".env.example").read_text(encoding="utf-8"))


class TestRetireByRunId(unittest.TestCase):
    """The test renders (79-84) are days old, so the age filter could not reach them."""

    def test_named_runs_are_retired_whatever_their_age(self):
        from types import SimpleNamespace

        from scripts import ops

        runs = [
            SimpleNamespace(id=79, mp4_path=__file__, title="all angles", features_json="{}"),
            SimpleNamespace(id=80, mp4_path=__file__, title="short 1", features_json="{}"),
        ]
        merged: dict[int, dict] = {}
        args = SimpleNamespace(channel="tapin", days=0, apply=True, run_id=79)
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=runs),
            patch(
                "core.stale_renders.merge_features",
                side_effect=lambda run_id, updates: merged.setdefault(run_id, updates),
            ),
            patch("builtins.print"),
        ):
            ops.COMMANDS["retire-renders"][1](args)
        self.assertEqual(list(merged), [79])

    def test_without_run_id_the_age_filter_still_applies(self):
        from core import stale_renders

        with patch.object(stale_renders, "render_age_days", return_value=1.0):
            with patch("scripts.requeue_upload.list_recyclable", return_value=[object()]):
                self.assertEqual(stale_renders.find_stale_renders("tapin", days=30), [])


# --- #770 chapter openers ------------------------------------------------------------


class TestChapterOpenersStandAlone(unittest.TestCase):
    """Run 79's cuts 2, 4 and 5 opened on a back-reference."""

    SCRIPT = (
        "Rockstar isn't selling you GTA 6 Online. That's the whole economy in one sentence. "
        "So the real question isn't whether GTA 6 Online has microtransactions. "
        "The budget number is the part people keep skipping past. "
        "But let's get concrete about what that friction looks like. "
        "And it's not just about microtransactions anymore."
    )

    def _chapters(self):
        from core.angle_chapters import AngleChapter

        text = self.SCRIPT
        starts = [
            0,
            text.index("So the real question"),
            text.index("The budget number"),
            text.index("But let's get concrete"),
            text.index("And it's not just"),
        ]
        words = [len(text[:c].split()) for c in starts]
        return [
            AngleChapter(i, f"Chapter {i + 1}", f"angle {i + 1}", words[i], starts[i], "llm")
            for i in range(5)
        ]

    def test_a_leading_connective_is_trimmed(self):
        from core.angle_chapters import trim_chapter_openers

        script, chapters, notes = trim_chapter_openers(self.SCRIPT, self._chapters())
        self.assertIn("The real question isn't whether", script)
        self.assertIn("Let's get concrete", script)
        self.assertNotIn("So the real question", script)
        self.assertNotIn("But let's get concrete", script)
        self.assertEqual(len(notes), 3, notes)

    def test_every_chapter_still_starts_on_its_own_sentence(self):
        from core.angle_chapters import trim_chapter_openers

        script, chapters, _notes = trim_chapter_openers(self.SCRIPT, self._chapters())
        words = script.split()
        for chapter in chapters:
            with self.subTest(chapter=chapter.index):
                opener = " ".join(words[chapter.word_start : chapter.word_start + 4])
                self.assertTrue(opener[:1].isupper(), opener)
                self.assertNotIn(opener.split()[0].lower(), {"so", "but", "and", "now"})

    def test_a_connective_that_cannot_be_dropped_is_only_a_note(self):
        from core.angle_chapters import AngleChapter, trim_chapter_openers

        text = "Nothing much happened here. And then everything changed."
        chapters = [
            AngleChapter(0, "one", "a", 0, 0, "llm"),
            AngleChapter(1, "two", "b", 4, text.index("And then"), "llm"),
        ]
        script, _chapters, notes = trim_chapter_openers(text, chapters)
        self.assertEqual(script, text)
        self.assertTrue(notes)

    def test_the_pipeline_trims_before_tts(self):
        pipeline = (ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("trim_chapter_openers(", pipeline)


# --- #773 bounded keyword fallback ---------------------------------------------------


class TestKeywordFallbackKeepsItsShare(unittest.TestCase):
    """Run 78: chapters at words 0/208/775/835/946 of 1,007 - one of 567, two of ~60."""

    ANGLES = (
        "Monetization breaks player trust",
        "Psychological spending traps",
        "Players abandon over paytowin fears",
        "Pricing mirrors criticized tactics",
        "Revenue depends on endless bait",
    )

    def _script(self) -> str:
        """Every later angle's vocabulary sits in the last fifth, which is what pulled run
        78's chapters into 775/835/946 of 1,007 words."""
        filler = "Rockstar keeps the monetization conversation about trust going here"
        sentences = [f"{filler} in line {i}." for i in range(48)]
        sentences += [
            "Psychological spending traps shape every storefront decision now.",
            "Players abandon the mode over paytowin fears they keep repeating.",
            "Pricing mirrors the criticized tactics from the last decade exactly.",
            "Revenue depends on endless bait dressed as seasonal content drops.",
            "That is the whole economy in one sentence for the audience.",
        ]
        return " ".join(sentences)

    def test_no_chapter_is_under_half_or_over_double_its_share(self):
        from core.angle_chapters import _keyword_chapter_starts

        script = self._script()
        angles = list(self.ANGLES)
        starts = _keyword_chapter_starts(script, angles)
        total = len(script.split())
        bounds = [len(script[:c].split()) for c in starts] + [total]
        spans = [bounds[i + 1] - bounds[i] for i in range(len(angles))]
        share = total / len(angles)
        for i, span in enumerate(spans):
            with self.subTest(chapter=i):
                self.assertGreater(span, share * 0.4, spans)
                self.assertLess(span, share * 2.0, spans)


# --- #774 the full script survives the run -------------------------------------------


class TestFullScriptIsKept(unittest.TestCase):
    SCRIPT = "Sentence one. " * 400  # past the 2,000-char script_preview cap

    def test_write_and_read_back(self):
        from core import run_trace

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(run_trace, "TRACES_DIR", tmp):
                run_trace.write_full_script(78, self.SCRIPT)
                self.assertEqual(run_trace.full_script(78), self.SCRIPT.strip())
                self.assertIsNone(run_trace.full_script(999))

    def test_a_missing_directory_never_raises(self):
        from core import run_trace

        with patch.object(
            run_trace, "TRACES_DIR", os.path.join(tempfile.gettempdir(), "no_such_9f")
        ):
            self.assertIsNone(run_trace.full_script(1))

    def test_the_trace_writer_and_readers_use_it(self):
        trace = (ROOT / "core" / "run_trace.py").read_text(encoding="utf-8")
        self.assertIn("write_full_script(", trace)
        for name in ("core/chapter_shorts.py", "core/batch_review.py"):
            with self.subTest(reader=name):
                self.assertIn("full_script(", (ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
