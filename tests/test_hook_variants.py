"""#987: hook variants - several openings, the one that should hold viewers kept.

The opt-in hook rewrite (`HOOK_REGEN_ENABLED`) asked for one replacement first sentence and kept
it if it scored higher. Now it asks for `HOOK_VARIANTS` (default 3) in one cheap call, ranks them
with `analytics.hook_learning.rank_openers` - the scorer's score, plus the channel's learned
trait gaps once #985 is ready - and keeps the best only when it beats the current opener on that
same score, still passes, and adds no name or number the script does not already have (an
opener that invents "2 times in 3 years" is not a better hook, it is a new claim). Every variant
and its score is kept on the pass's ledger row, so later learning sees what was tried.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

# The second sentence carries the facts without restating any opener below word for word (the
# first version of this script did, and was exactly the live-check defect).
SCRIPT = "So today we talk about the Heat. They went 11 and 1, 11 of 12 games, and Bam looks new."


class RankTests(unittest.TestCase):
    def test_scorer_only_before_learning(self):
        from analytics.hook_learning import rank_openers

        ranked = rank_openers(["So today we talk about the Heat.",
                               "The Heat won 11 of 12 preseason games."], {})  # fmt: skip
        self.assertEqual(ranked[0][0], "The Heat won 11 of 12 preseason games.")
        self.assertGreater(ranked[0][1], ranked[1][1])

    def test_learned_gaps_move_the_order(self):
        from analytics.hook_learning import rank_openers

        guidance = {"prefer": [{"trait": "a name", "gap": 0.30}],
                    "avoid": [{"trait": "a number", "gap": -0.30}]}  # fmt: skip
        ranked = rank_openers(["The Heat won 11 of 12 preseason games.",
                               "Bam Adebayo is not the same player anymore."], guidance)  # fmt: skip
        self.assertEqual(ranked[0][0], "Bam Adebayo is not the same player anymore.")


class PassTests(unittest.TestCase):
    def _run(self, openers, script=SCRIPT, guidance=None):
        from core import content_engine

        calls = []

        def fake_llm(system, user, **kw):
            calls.append(system)
            return {"openers": openers}

        with (
            patch.dict("os.environ", {"HOOK_REGEN_ENABLED": "true", "HOOK_VARIANTS": "3"}),
            patch.object(content_engine, "_call_content_llm", side_effect=fake_llm),
            patch("analytics.hook_learning.regen_guidance", return_value=guidance or {}),
        ):
            out, extra = content_engine._hook_variants(script, channel_id="tapin")
        return out, extra, calls

    def test_the_best_grounded_variant_wins(self):
        out, extra, calls = self._run([
            "The Heat won 11 of 12 preseason games.",
            "Bam looks new and the Heat won 11 of 12.",
            "Here is a fun one about the Heat.",
        ])  # fmt: skip
        self.assertEqual(len(calls), 1)
        self.assertIn("3", calls[0])  # asked for three
        self.assertTrue(out.startswith("The Heat won 11 of 12 preseason games."))
        self.assertTrue(out.endswith("Bam looks new."))
        self.assertEqual(len(extra["variants"]), 3)
        self.assertEqual(extra["picked"], "The Heat won 11 of 12 preseason games.")

    def test_a_variant_that_invents_a_number_is_refused(self):
        out, extra, _calls = self._run(["The Heat won 14 straight games this October."])
        self.assertEqual(out, SCRIPT)
        self.assertEqual(extra["picked"], "")
        self.assertIn("new specifics", extra["variants"][0]["refused"])

    def test_a_variant_that_repeats_a_later_sentence_is_refused(self):
        # Live check, 2026-10-06: the kept opener restated the script's next sentence word for
        # word ("The Heat won 11 of 12 preseason games. The Heat won 11 of 12 ...").
        script = "So today we look at the Heat. The Heat won 11 of 12 preseason games."
        out, extra, _calls = self._run(
            ["The Heat won 11 of 12 preseason games.", "Bam Adebayo looks like a new player."],
            script=script,
        )
        self.assertNotIn("games. The Heat won 11 of 12", out)
        refused = [v for v in extra["variants"] if v.get("refused")]
        self.assertTrue(any("repeats" in v["refused"] for v in refused), extra)

    def test_nothing_better_keeps_the_script(self):
        script = "The Heat won 11 of 12 preseason games. Bam looks new."
        out, _extra, _calls = self._run(["Here is a thing about the Heat."], script=script)
        self.assertEqual(out, script)

    def test_the_pass_records_its_variants(self):
        import inspect

        from core import content_engine

        source = inspect.getsource(content_engine.generate_content_package)
        self.assertIn("_hook_variants(", source)


if __name__ == "__main__":
    unittest.main()
