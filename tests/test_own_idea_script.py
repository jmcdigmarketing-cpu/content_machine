"""Wave 85 (#1159-#1163): the script the operator's own idea gets.

Read again on 2026-10-13, an hour after waves 81-84 were pushed:

- `ops script-check --idea` passed `variant_index=0`, the first generated angle. Angle 1 in
  `main.py` is the operator's idea (index -1). Runs 140-142, reported as "your ideas", were
  written from generated angles: run 140's was "Herbert's deep-ball accuracy jumps to
  league-leading clip", which no fact backed, and the script was built on it.
- The grounding check reported "Court Mc" (McGee), "Vonta Smith" (DeVonta), "the Tik"
  (TikTok) and a sentence's first word ("Losing") as names the facts lack. Drafts 107 and 134
  waited for a person on that alone.
- An unbacked claim in the first sentence was never repaired: the cut skips the hook. 8 of the
  newest 40 runs carried one there.
- Run 141: the one cut available left 148 words against a 150 minimum, so nothing was cut.
- Since #374 a free small model wrote every script body, a local 8B one on 3 of 9 runs.
"""

from __future__ import annotations

import inspect
import json
import os
import unittest
from unittest.mock import patch

from tests.test_batch_generation import BatchCase, _discovery, _pipeline_result

IDEA = "Chargers Hopeium going into week 5"
WORDED = "Los Angeles Chargers Hopeium Going Into Week 5"

# ---- #1159: script-check --idea writes the idea the way angle 1 does ------------------------


class OwnIdeaDraftTests(BatchCase):
    def _draft(self, **over):
        from core import batch_generation as bg

        with (
            patch("core.pipeline.run_discovery", return_value=_discovery(topic=IDEA)) as rd,
            patch("core.pipeline.run_pipeline", return_value=_pipeline_result()) as rp,
            patch("apis.topic_variants.idea_angle", return_value=WORDED),
            patch("core.experiments.next_arm", side_effect=AssertionError("no lever here")),
        ):
            out = bg.generate_draft(IDEA, "tapin", own_idea=True, **over)
        return out, rd, rp

    def test_angle_one_is_the_idea_not_a_generated_angle(self):
        out, _rd, rp = self._draft()
        kwargs = rp.call_args.kwargs
        self.assertEqual(kwargs["variant_index"], -1)
        self.assertTrue(kwargs["own_idea"])
        self.assertEqual(kwargs["own_topic"], WORDED)
        self.assertEqual(kwargs["creative_brief"], IDEA)
        self.assertEqual(out.variant, WORDED)
        self.assertTrue(out.ok)

    def test_discovery_reads_the_idea_as_the_brief(self):
        _out, rd, _rp = self._draft()
        self.assertEqual(rd.call_args.kwargs.get("brief"), IDEA)

    def test_the_draft_is_kept_where_batch_review_reads(self):
        from core.batch_review import pending_drafts

        out, _rd, _rp = self._draft()
        with open(os.path.join(out.path, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.assertTrue(meta["own_idea"])
        self.assertEqual(meta["variant"], WORDED)
        self.assertEqual(out.script, "Hook line!\nBody line.")
        self.assertEqual([d.run_id for d in pending_drafts("tapin")], [42])

    def test_a_batch_draft_still_takes_the_best_generated_angle(self):
        from core import batch_generation as bg

        with (
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", return_value=_pipeline_result()) as rp,
        ):
            out = bg.generate_draft("UFC 320", "tapin")
        self.assertEqual(rp.call_args.kwargs["variant_index"], 1)
        self.assertFalse(rp.call_args.kwargs.get("own_idea", False))
        self.assertEqual(out.variant, "Angle two (best)")


class ScriptCheckIdeaTests(unittest.TestCase):
    def _lines(self, outcome):
        from core.runs import script_report

        with patch("core.batch_generation.generate_draft", return_value=outcome) as gd:
            return script_report.draft_lines("tapin", IDEA), gd

    def test_the_command_goes_through_the_own_idea_draft(self):
        from core.batch_generation import DraftOutcome

        outcome = DraftOutcome(
            topic=IDEA,
            ok=True,
            title="Chargers Hopeium: Week 5",
            variant=WORDED,
            run_id=143,
            path="output/tapin/drafts/x",
            script="Herbert's line is healthy. The defense ranks fourth.",
            script_clean={"ok": True, "why": [], "points": {}, "cut": []},
        )
        lines, gd = self._lines(outcome)
        self.assertEqual(gd.call_args.args[:2], (IDEA, "tapin"))
        self.assertTrue(gd.call_args.kwargs["own_idea"])
        text = "\n".join(lines)
        self.assertIn(f"Angle 1: {WORDED}", text)
        self.assertIn("Herbert's line is healthy.", text)
        self.assertIn("Script check: clean", text)
        self.assertIn("py -m scripts.ops batch-review --channel tapin", text)

    def test_a_draft_that_was_not_written_says_why(self):
        from core.batch_generation import DraftOutcome

        lines, _gd = self._lines(DraftOutcome(topic=IDEA, error="pipeline produced no script"))
        self.assertIn("No draft", lines[0])
        self.assertIn("pipeline produced no script", lines[0])

    def test_the_review_screen_says_it_is_your_idea(self):
        from core import batch_review

        self.assertIn('meta.get("own_idea")', inspect.getsource(batch_review._show))


# ---- #1160: a name with a capital inside it; a sentence's first word ------------------------


class NameTests(unittest.TestCase):
    def _names(self, text):
        from core.facts.grounding import extract_entities

        return extract_entities(text)

    def _missing(self, script, facts):
        from core.facts.grounding import find_ungrounded_entities

        return find_ungrounded_entities(script, facts)

    def test_run107_mcgee_is_one_name(self):
        names = self._names("Court McGee defies retirement talk ahead of his fight at UFC 332.")
        self.assertIn("Court McGee", names)
        self.assertNotIn("Court Mc", names)
        self.assertEqual(
            self._missing(
                "Court McGee defies retirement talk ahead of UFC 332.",
                "Court McGee explains why retirement is the last thing on his mind at UFC 332",
            ),
            [],
        )

    def test_run134_devonta_is_one_name(self):
        names = self._names("DeVonta Smith was traded by the Eagles before the Jaguars game.")
        self.assertIn("DeVonta Smith", names)
        self.assertNotIn("Vonta Smith", names)
        self.assertEqual(
            self._missing(
                "DeVonta Smith was traded by the Eagles in the offseason.",
                "The Eagles traded DeVonta Smith in the offseason.",
            ),
            [],
        )

    def test_run102_tiktok_is_one_word(self):
        names = self._names("The TikTok ban reshaped the NBA playoffs conversation.")
        self.assertFalse([n for n in names if n.lower().endswith("tik")], names)

    def test_run140_a_sentences_first_word_is_not_a_name(self):
        self.assertEqual(
            self._missing(
                "Losing a starting tackle to injured reserve hurts in the playoffs.",
                "The Chargers lost Rashawn Slater to injured reserve.",
            ),
            [],
        )
        for script in (
            "Adding a veteran quarterback is insurance for the playoffs.",
            "Make no mistake, the playoffs are slipping away.",
            "Expect the roster to change before the playoffs.",
            "Guess who leads the playoffs race.",
            "Tweaks to the roster came before the playoffs.",
            "Sounds like the playoffs are gone.",
        ):
            self.assertEqual(self._missing(script, "The roster is thin."), [], script)

    def test_a_name_that_opens_a_sentence_once_is_still_checked(self):
        """The frozen verdicts hold: "LeBron was traded" opens a sentence and is a name. So is
        a surname that happens to end like a participle."""
        facts = "The Lakers made a trade in the offseason."
        self.assertIn("LeBron", self._missing("LeBron was traded to the Lakers.", facts))
        self.assertIn("Manning", self._missing("Manning threw two picks in the playoffs.", facts))

    def test_a_name_that_opens_a_sentence_and_recurs_is_still_checked(self):
        script = "Zolanski arrived on Monday. The Chargers love Zolanski for the playoffs."
        self.assertIn("Zolanski", self._missing(script, "The Chargers made a trade."))

    def test_a_name_inside_a_sentence_is_still_checked(self):
        script = "The Chargers traded for Zolanski before the playoffs."
        self.assertIn("Zolanski", self._missing(script, "The Chargers made a trade."))

    def test_a_made_up_name_with_an_inner_capital_is_still_checked(self):
        script = "Court McFakename headlines the UFC card."
        self.assertIn("Court McFakename", self._missing(script, "Court McGee fights at UFC 332."))


# ---- #1161: an unbacked claim in the first sentence ------------------------------------------

RUN140 = (
    "Herbert leads the league in deep-ball accuracy, and the Chargers are 0-5. That "
    "contradiction is the entire Hopeium case. Adding a veteran QB is insurance that keeps "
    "Herbert fresh for the throws that matter."
)
FACTS = "- Los Angeles Chargers: 0-5; next: Denver Broncos\n- Chargers lose Rashawn Slater to IR"


class HookClaimTests(unittest.TestCase):
    def test_run140_the_claim_is_in_the_first_sentence(self):
        from core.script_craft import hook_claims

        claims = [
            "Herbert leads the league in deep-ball accuracy.",
            "The Chargers are adding a veteran QB.",
        ]
        self.assertEqual(hook_claims(RUN140, claims), [claims[0]])

    def test_a_sound_first_sentence_has_none(self):
        from core.script_craft import hook_claims

        self.assertEqual(hook_claims(RUN140, ["The Chargers are adding a veteran QB."]), [])
        self.assertEqual(hook_claims(RUN140, []), [])

    def test_the_rebuild_is_told_what_not_to_state(self):
        from core import content_engine as ce

        seen = {}

        def fake(system, user, **kwargs):
            seen["system"] = system
            return {"openers": []}

        claim = "Herbert leads the league in deep-ball accuracy."
        with (
            patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true"}),
            patch.object(ce, "_call_content_llm", side_effect=fake),
        ):
            _script, extra = ce._hook_variants(RUN140, grounding_text=FACTS, unbacked=[claim])
        self.assertIn("states what the facts do not", seen["system"])
        self.assertIn(claim, seen["system"])
        self.assertIn("VERIFIED FACTS", seen["system"])
        self.assertTrue(any(claim in problem for problem in extra["problems"]))

    def test_the_engine_runs_the_repair_and_checks_it(self):
        from core import content_engine as ce

        source = inspect.getsource(ce.generate_content_package)
        self.assertIn('"repair_hook"', source)
        self.assertIn("hook_claims(", source)
        at = source.index('"repair_hook"')
        self.assertLess(source.index('"cut_unsupported"'), at)


# ---- #1162: a cut within 15% of the minimum ---------------------------------------------------


def _script(words_after_cut):
    filler = " ".join(f"Point {i} about the line holds up well." for i in range(60))
    kept = " ".join(filler.split()[: words_after_cut - 6]) + "."
    return f"The Chargers are 0-5 this year. {kept} He has 40 knockouts in the UFC."


CLAIM = ["Topuria has 40 knockouts in the UFC."]


class ShortCutTests(unittest.TestCase):
    def test_run141_two_words_under_is_still_cut(self):
        from core.script_craft import cut_unsupported

        script = _script(148)
        new, cut = cut_unsupported(script, CLAIM, min_words=150)
        self.assertEqual(cut, ["He has 40 knockouts in the UFC."])
        self.assertLess(len(new.split()), 150)

    def test_a_cut_past_fifteen_percent_is_not_made(self):
        from core.script_craft import cut_unsupported

        script = _script(120)
        self.assertEqual(cut_unsupported(script, CLAIM, min_words=150), (script, []))

    def test_the_other_cuts_keep_the_strict_minimum(self):
        from core.script_craft import drop_sentences

        script = _script(148)
        doomed = ["He has 40 knockouts in the UFC."]
        self.assertEqual(drop_sentences(script, doomed, min_words=150), (script, []))

    def test_the_check_says_how_short_and_stays_clean(self):
        from core.script_craft import script_check, script_check_line

        check = script_check(script="The line held. The defense ranks fourth.", short_by=2)
        self.assertTrue(check["ok"])
        self.assertEqual(check["short_by"], 2)
        self.assertIn("2 words under its minimum", script_check_line(check))
        self.assertNotIn("short_by", script_check(script="The line held."))

    def test_the_engine_measures_it_on_the_finished_script(self):
        from core import content_engine as ce

        self.assertIn("short_by=", inspect.getsource(ce.generate_content_package))


# ---- #1163: the better model writes the body --------------------------------------------------


class BodyTierTests(unittest.TestCase):
    def _tier(self, value=None):
        from core.content_engine import _script_body_tier

        env = {k: v for k, v in os.environ.items() if k != "SCRIPT_BODY_TIER"}
        if value is not None:
            env["SCRIPT_BODY_TIER"] = value
        with patch.dict(os.environ, env, clear=True):
            return _script_body_tier()

    def test_one_model_writes_the_whole_script_by_default(self):
        """Operator, 2026-10-13: "the better model". #374 had made the body a free-tier call."""
        self.assertEqual(self._tier(), "premium")
        self.assertEqual(self._tier("nonsense"), "premium")

    def test_the_split_is_still_one_setting_away(self):
        self.assertEqual(self._tier("cheap"), "cheap")
        self.assertEqual(self._tier("extract"), "extract")


if __name__ == "__main__":
    unittest.main()


class ClaimSentenceTests(unittest.TestCase):
    """Found on the corrected proof drafts (runs 143-145): two claims were flagged and their
    sentences were not found, so neither the cut nor the hook repair could act."""

    RUN145 = (
        "Wemby's +200 for MVP - SGA says he's the best alive. Sports Illustrated has the Spurs "
        "winning the Finals over the Cavaliers."
    )
    RUN144 = (
        "Second, end the Quentin Johnston experiment. Third, use Jake Browning. They signed the "
        "former Bengals QB, and he's leverage they have. The margin is one game at a time."
    )

    def test_run145_a_possessive_does_not_hide_the_sentence(self):
        from core.script_craft import claim_sentences, hook_claims

        claim = "Wemby has +200 odds for MVP."
        self.assertEqual(
            claim_sentences(self.RUN145, [claim]),
            ["Wemby's +200 for MVP - SGA says he's the best alive."],
        )
        self.assertEqual(hook_claims(self.RUN145, [claim]), [claim])

    def test_run144_a_claim_told_across_two_sentences_takes_both(self):
        from core.script_craft import claim_sentences

        claim = "The Chargers signed Jake Browning, the former Bengals QB."
        self.assertEqual(
            claim_sentences(self.RUN144, [claim]),
            [
                "Third, use Jake Browning.",
                "They signed the former Bengals QB, and he's leverage they have.",
            ],
        )

    def test_a_shared_name_is_not_the_claim(self):
        from core.script_craft import claim_sentences

        self.assertEqual(claim_sentences(self.RUN145, ["The Spurs traded for a new center."]), [])
        self.assertEqual(claim_sentences(self.RUN144, ["Jake Browning threw four picks."]), [])
