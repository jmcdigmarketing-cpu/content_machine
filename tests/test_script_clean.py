"""Wave 81 (#1139 #1141 #1142 #1143 #1138): the script that comes out, checked as a whole.

Operator, 2026-10-11: a clean script keeps "my idea and stance rules", has "nothing
unsupported" and uses "my typed thoughts, closely"; an unsupported sentence is "cut, and tell
me which". Measured that day: 13 of 31 waiting drafts were blocked by an unsupported claim (9
by one sentence); the stance was read on a script's first and last line only (2 of 45 stored
scripts knock it mid-script: run 107 "denial", run 118 "doomed"); run 116's draft was titled
"Contrarian: Spain's World Cup win ...".
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

SCRIPT = (
    "The Chargers are 0-4 and the schedule turns in week five.\n\n"
    "Justin Herbert has thrown for 1,100 yards behind a line missing two starters. "
    "The demo is said to be live on PS5 and Switch 2. "
    "Both tackles return from injury this week.\n\n"
    "Their next three opponents are a combined 3-9. That is the opening."
)
CLAIM = "The demo is live on PS5 and Switch 2."


class CutUnsupportedTests(unittest.TestCase):
    def test_the_sentence_carrying_the_claim_is_cut_and_named(self):
        from core.script_craft import cut_unsupported

        new, cut = cut_unsupported(SCRIPT, [CLAIM], min_words=20)
        self.assertEqual(cut, ["The demo is said to be live on PS5 and Switch 2."])
        self.assertNotIn("Switch 2", new)
        self.assertIn("1,100 yards behind a line missing two starters. Both tackles return", new)
        self.assertEqual(new.count("\n\n"), 2)  # the paragraphs survive

    def test_the_hook_is_never_cut(self):
        from core.script_craft import cut_unsupported

        new, cut = cut_unsupported(
            SCRIPT, ["The Chargers are 0-4 and the schedule turns in week five."], min_words=20
        )
        self.assertEqual((new, cut), (SCRIPT, []))

    def test_more_than_two_sentences_is_a_script_to_look_at(self):
        from core.script_craft import cut_unsupported

        claims = [
            "Justin Herbert has thrown for 1,100 yards behind a line missing two starters.",
            CLAIM,
            "Both tackles return from injury this week.",
        ]
        self.assertEqual(cut_unsupported(SCRIPT, claims, min_words=20), (SCRIPT, []))

    def test_a_cut_that_guts_the_script_is_refused(self):
        from core.script_craft import cut_unsupported

        self.assertEqual(cut_unsupported(SCRIPT, [CLAIM], min_words=60), (SCRIPT, []))

    def test_a_claim_no_sentence_carries_changes_nothing(self):
        from core.script_craft import cut_unsupported

        self.assertEqual(
            cut_unsupported(SCRIPT, ["Aaron Rodgers retired."], min_words=20), (SCRIPT, [])
        )

    def test_the_switch_turns_it_off(self):
        from core.script_craft import cut_unsupported_enabled

        with patch.dict("os.environ", {"CUT_UNSUPPORTED": "false"}):
            self.assertFalse(cut_unsupported_enabled())
        with patch.dict("os.environ", {"CUT_UNSUPPORTED": ""}):
            self.assertTrue(cut_unsupported_enabled())


class StanceTests(unittest.TestCase):
    HOPE = (
        "The Chargers can still turn this around.\n\n"
        "Fans are in denial about the offensive line. "
        "Herbert gets both tackles back this week.\n\n"
        "The next three opponents are a combined 3-9."
    )

    def test_a_sentence_past_the_opener_that_knocks_the_stance_is_found(self):
        from core.angle_intent import ANGLE_HOPE
        from core.script_craft import stance_slips

        slips = stance_slips(self.HOPE, ANGLE_HOPE, "Chargers Hopeium going into week 5")
        self.assertEqual([s for s, _why in slips], ["Fans are in denial about the offensive line."])

    def test_it_is_cut_from_the_finished_script(self):
        from core.angle_intent import ANGLE_HOPE
        from core.script_craft import hold_stance

        new, cut = hold_stance(
            self.HOPE, ANGLE_HOPE, "Chargers Hopeium going into week 5", min_words=10
        )
        self.assertEqual(cut, ["Fans are in denial about the offensive line."])
        self.assertNotIn("denial", new)

    def test_a_word_the_idea_itself_uses_is_not_a_slip(self):
        from core.angle_intent import ANGLE_HOPE
        from core.script_craft import stance_slips

        self.assertEqual(stance_slips(self.HOPE, ANGLE_HOPE, "why Chargers fans are in denial"), [])

    def test_no_intent_reads_nothing(self):
        from core.script_craft import hold_stance, stance_slips

        self.assertEqual(stance_slips(self.HOPE, "", "x"), [])
        self.assertEqual(hold_stance(self.HOPE, "", "x", min_words=10), (self.HOPE, []))


THOUGHTS = (
    "How the 0-4 Chargers can turn it around this year\n"
    "the offensive line gets both tackles back\n"
    "the next three opponents have losing records; Herbert is still top ten in passing yards"
)


class TypedThoughtsTests(unittest.TestCase):
    def test_typed_thoughts_become_points(self):
        from core.script_craft import thought_points

        points = thought_points(THOUGHTS)
        self.assertEqual(len(points), 4)
        self.assertIn("the offensive line gets both tackles back", points)
        self.assertIn("Herbert is still top ten in passing yards", points)

    def test_a_one_line_idea_has_no_points(self):
        from core.script_craft import thought_points

        self.assertEqual(thought_points("How the 0-4 Chargers can turn it around this year"), [])
        self.assertEqual(thought_points(""), [])

    def test_a_point_the_script_does_not_carry_is_missing(self):
        from core.script_craft import points_used, thought_points

        script = (
            "The Chargers are 0-4 and can still turn it around this year. The offensive line "
            "gets both tackles back. The next three opponents all have losing records."
        )
        used, missing = points_used(script, thought_points(THOUGHTS))
        self.assertEqual(missing, ["Herbert is still top ten in passing yards"])
        self.assertEqual(len(used), 3)

    def test_the_idea_check_fails_a_script_missing_a_point_without_a_paid_check(self):
        from core import content_engine

        script = "The Chargers are 0-4 and can still turn it around this year. " * 4
        calls: list[str] = []

        def _llm(system, user, **kwargs):
            calls.append(system)
            return {"script": script}  # the rewrite brings nothing new

        with patch.object(content_engine, "_call_content_llm", side_effect=_llm):
            out, extra = content_engine._keep_to_idea(script, THOUGHTS, min_words=10, max_words=400)
        self.assertEqual(out, script)
        self.assertFalse(extra["answers_idea"])
        self.assertIn("the creator's own points are missing", extra["missing_before"])
        self.assertEqual(len(calls), 1)  # the rewrite only - the miss was found for free
        self.assertIn("Rewrite", calls[0])


class ScriptCheckTests(unittest.TestCase):
    def test_a_clean_script_says_so(self):
        from core.script_craft import script_check, script_check_line

        check = script_check(
            script="The Chargers are 0-4. Both tackles return this week.",
            title="Can the Chargers still turn it around?",
            idea="How the 0-4 Chargers can turn it around this year",
        )
        self.assertTrue(check["ok"])
        self.assertEqual(script_check_line(check), "Script check: clean")

    def test_each_thing_wrong_is_named(self):
        from core.angle_intent import ANGLE_HOPE
        from core.script_craft import script_check, script_check_line

        check = script_check(
            script=StanceTests.HOPE,
            title="Contrarian: the Chargers are fine",
            idea="Chargers Hopeium going into week 5",
            thoughts=THOUGHTS,
            intent=ANGLE_HOPE,
            unsupported=["Fans are in denial."],
            cut=["A sentence that was cut."],
        )
        self.assertFalse(check["ok"])
        text = " | ".join(check["why"])
        self.assertIn("1 claim(s) the facts do not support", text)
        self.assertIn("knocks the stance", text)
        self.assertIn("points missing", text)
        self.assertIn('the title starts with a label ("Contrarian:")', text)
        line = script_check_line(check)
        self.assertTrue(line.startswith("Script check: 4 to look at - "))
        self.assertIn('cut 1 sentence(s): "A sentence that was cut."', line)

    def test_used_points_are_counted_on_the_line(self):
        from core.script_craft import script_check, script_check_line

        script = (
            "The 0-4 Chargers can turn it around this year. The offensive line gets both "
            "tackles back. The next three opponents have losing records. Herbert is still top "
            "ten in passing yards."
        )
        check = script_check(script=script, thoughts=THOUGHTS, idea=THOUGHTS)
        self.assertEqual(check["points"], {"total": 4, "used": 4, "missing": []})
        self.assertEqual(script_check_line(check), "Script check: clean - your points: 4 of 4 used")

    def test_no_check_is_no_line(self):
        from core.script_craft import script_check_line

        self.assertEqual(script_check_line(None), "")
        self.assertEqual(script_check_line({}), "")

    def test_the_review_screen_prints_it(self):
        from core.ui import display_fact_engine_report

        printed: list[str] = []
        display_fact_engine_report(
            {"script_clean": {"ok": False, "why": ["1 claim(s) the facts do not support"]}},
            print_fn=lambda *a: printed.append(" ".join(map(str, a))),
        )
        self.assertIn(
            "Script check: 1 to look at - 1 claim(s) the facts do not support", "\n".join(printed)
        )

    def test_the_engine_stores_it_and_the_pipeline_keeps_it(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        engine = root.joinpath("core", "content_engine.py").read_text(encoding="utf-8")
        pipeline = root.joinpath("core", "pipeline.py").read_text(encoding="utf-8")
        self.assertIn('"script_clean": script_clean,', engine)
        self.assertIn('"cut_unsupported", script, _run_cut', engine)
        self.assertIn('"hold_stance", script, _run_hold', engine)
        self.assertIn('result.features["script_clean"] = dict(content["script_clean"])', pipeline)


class OvernightRequiresCleanTests(unittest.TestCase):
    def _reason(self, **over):
        from core.batch_review import pending_drafts, unattended_block_reason

        meta = {
            "run_id": 1, "channel_id": "tapin", "topic": "Topic", "title": "Title",
            "hook_verdict": "strong", "authenticity_verdict": "ok", "claim_verification": {},
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }  # fmt: skip
        meta.update(over)
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "draft_0001")
            os.makedirs(folder)
            with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump(meta, fh)
            with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as fh:
                fh.write("# Draft\n\n## Script\n\nA script.\n")
            (draft,) = pending_drafts("tapin", root=tmp)
            return unattended_block_reason(draft)

    def test_a_draft_whose_script_check_failed_waits(self):
        why = self._reason(script_clean={"ok": False, "why": ["a sentence knocks the stance"]})
        self.assertEqual(why, "script check: a sentence knocks the stance")

    def test_a_clean_or_unchecked_draft_is_not_held_by_it(self):
        self.assertEqual(self._reason(script_clean={"ok": True, "why": []}), "")
        self.assertEqual(self._reason(), "")


class TitleLabelTests(unittest.TestCase):
    def test_the_label_is_stripped_where_the_title_is_written(self):
        from core.title_generator import strip_label, title_label

        self.assertEqual(
            strip_label("Contrarian: Spain's World Cup win exposes overreliance on Rodri"),
            "Spain's World Cup win exposes overreliance on Rodri",
        )
        self.assertEqual(strip_label("Hot take: the Jets are doomed"), "The Jets are doomed")
        self.assertEqual(title_label("Contrarian: X"), "Contrarian:")

    def test_a_colon_that_is_not_a_label_stays(self):
        from core.title_generator import strip_label, title_label

        for title in (
            "UFC 320: what it means for the division",
            "Analysis paralysis at QB",
            "Take Two delays GTA 6",
        ):
            self.assertEqual(strip_label(title), title)
            self.assertEqual(title_label(title), "")

    def test_the_engine_strips_it(self):
        from pathlib import Path

        text = (
            Path(__file__)
            .resolve()
            .parent.parent.joinpath("core", "content_engine.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn("title = strip_label(title)", text)


if __name__ == "__main__":
    unittest.main()


class DirectiveTests(unittest.TestCase):
    def test_an_experiments_instruction_is_not_the_operators_points(self):
        from core import experiment_levers
        from core.script_craft import thought_points

        lever = next((lv for lv in experiment_levers.levers() if experiment_levers.arms(lv)), None)
        self.assertIsNotNone(lever)
        text = next(
            experiment_levers.directive(lever, arm)
            for arm in experiment_levers.arms(lever)
            if experiment_levers.directive(lever, arm)
        )
        self.assertTrue(experiment_levers.is_directive(text))
        self.assertTrue(experiment_levers.is_directive("  " + text.replace(" ", "  ") + " "))
        self.assertEqual(thought_points(text), [])

    def test_typed_thoughts_are_not_a_directive(self):
        from core.experiment_levers import is_directive

        self.assertFalse(is_directive("Herbert has no line; the schedule eases in week five"))
        self.assertFalse(is_directive(""))


def _recorded(run_id, *, script="", title="A plain title", idea="Chargers week five", **features):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=run_id,
        features_json=json.dumps(features),
        script_preview=script,
        title=title,
        input_topic=idea,
        selected_topic=idea,
    )


class ScriptReportTests(unittest.TestCase):
    """`ops script-check` (#1143): the check over what is on record, and over one new draft."""

    def test_a_stored_check_is_used_as_it_is(self):
        from core.runs.script_report import check_run

        stored = {"ok": False, "why": ["1 claim(s) the facts do not support"]}
        self.assertEqual(check_run(_recorded(7, script="x", script_clean=stored)), stored)

    def test_an_older_run_is_checked_from_what_it_kept(self):
        from core.runs.script_report import check_run

        with patch("core.run_trace.full_script", return_value=SCRIPT):
            check = check_run(_recorded(8, title="Contrarian: the Chargers are fine"))
        self.assertFalse(check["ok"])
        self.assertIn("label", " ".join(check["why"]))

    def test_a_run_without_a_script_has_no_check(self):
        from core.runs.script_report import check_run

        with patch("core.run_trace.full_script", return_value=""):
            self.assertIsNone(check_run(_recorded(9)))

    def test_the_report_counts_the_clean_and_names_the_rest(self):
        from types import SimpleNamespace

        from core.runs import script_report

        runs = [
            _recorded(3, script="x", script_clean={"ok": True, "why": []}),
            _recorded(
                4, script="x", script_clean={"ok": False, "why": ["2 sentence(s) hard to say"]}
            ),
            _recorded(
                5,
                script="x",
                script_clean={"ok": False, "why": ["1 claim(s) the facts do not support"]},
            ),
            _recorded(
                6,
                script="x",
                script_clean={"ok": False, "why": ["3 claim(s) the facts do not support"]},
            ),
        ]
        repo = SimpleNamespace(list_for_channel=lambda channel: runs)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            lines = script_report.recorded_lines("tapin", limit=30)
        self.assertIn("newest 4 scripts: 1 clean", lines[0])
        self.assertIn("  2  a claim the facts do not support", "\n".join(lines))
        self.assertIn("run 6:", "\n".join(lines))  # the newest fault is named first

    def test_a_new_draft_prints_its_script_and_its_check(self):
        from types import SimpleNamespace

        from core.runs import script_report

        result = SimpleNamespace(
            script=SCRIPT,
            title="The Chargers' schedule turns",
            run_id=140,
            features={"script_clean": {"ok": True, "why": [], "points": {}, "cut": []}},
        )
        with patch.object(script_report, "_own_idea_draft", return_value=result):
            text = "\n".join(script_report.draft_lines("tapin", "Chargers hope in week five"))
        self.assertIn("Idea:  Chargers hope in week five", text)
        self.assertIn("Their next three opponents are a combined 3-9.", text)
        self.assertIn("Script check: clean", text)
        self.assertIn("run 140, no render", text)

    def test_no_draft_says_why(self):
        from core.runs import script_report

        with patch.object(script_report, "_own_idea_draft", return_value=None):
            lines = script_report.draft_lines("tapin", "an idea")
        self.assertIn("no angles came back", lines[0])
        with patch.object(script_report, "_own_idea_draft", side_effect=RuntimeError("no model")):
            lines = script_report.draft_lines("tapin", "an idea")
        self.assertIn("RuntimeError: no model", lines[0])

    def test_the_command_reads_the_record_unless_given_an_idea(self):
        import io
        from contextlib import redirect_stdout

        from scripts.ops import COMMANDS, build_parser

        args = build_parser().parse_args(["script-check", "--channel", "tapin"])
        with (
            patch("core.runs.script_report.recorded_lines", return_value=["recorded"]) as rec,
            patch("core.runs.script_report.draft_lines", return_value=["drafted"]) as draft,
            redirect_stdout(io.StringIO()) as out,
        ):
            COMMANDS["script-check"][1](args)
            args.topic = "Chargers hope in week five"
            COMMANDS["script-check"][1](args)
        rec.assert_called_once()
        draft.assert_called_once_with("tapin", "Chargers hope in week five")
        self.assertEqual(out.getvalue().split(), ["recorded", "drafted"])
