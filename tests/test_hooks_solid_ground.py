"""#1018: hooks on solid ground.

The operator, 2026-10-08: "hooks have performed pretty poorly consistently how can we improve
that?". Run 124's first sentence - "Only one team in NFL history has made the playoffs after
starting 0-4" - was the script's one unsupported claim. Measured causes:

- the HOOK RULE asks for "a specific fact, number, or contradiction" and nothing checks that
  the fact is a fact; `find_ungrounded_superlatives` knew "the only" but not "only one team
  in NFL history" or "no team has ever";
- both repair passes were told "Keep the opening hook" - so a flagged hook was the one
  sentence they could not fix;
- stock openers recur ("Here's the part everyone's missing", "nobody wants to say out
  loud"); `style_recurrence` reported it and nothing acted;
- the hook rewrite (`HOOK_REGEN_ENABLED`) was off by default.

Now the hook pass runs by default, after the fact corpus is built; a hook that is unsupported,
a stock opener or a repeat of a recent opener is replaced by the best variant built from the
VERIFIED FACTS that has none of those problems; the repair passes may replace a flagged hook.
`score_hook` (a report-card component) is unchanged, so `GRADE_VERSION` stays.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

RUN_124_HOOK = "Only one team in NFL history has made the playoffs after starting 0-4."
FACTS = (
    "The Chargers are 0-4 for the first time since 2017.\n"
    "Herbert has thrown six interceptions, tied for second-most in the league.\n"
    "The defense ranks near the top 10 in EPA per play."
)
SCRIPT = (
    RUN_124_HOOK + " The Chargers need three things to change. Herbert has to protect the ball."
)


class SuperlativeTests(unittest.TestCase):
    def test_history_and_ever_claims(self):
        from core.script_craft import find_ungrounded_superlatives

        self.assertTrue(find_ungrounded_superlatives(RUN_124_HOOK, FACTS))
        self.assertTrue(find_ungrounded_superlatives("No team has ever come back from 0-4.", FACTS))
        self.assertFalse(find_ungrounded_superlatives("The Chargers are 0-4.", FACTS))


class StockOpenerTests(unittest.TestCase):
    def test_stock_openers(self):
        from core.hook_score import stock_opener

        for hook in ("Here's the part everyone's missing about the Chargers.",
                     "Nobody wants to say this out loud, but the Chargers are done.",
                     "Here's what nobody is talking about."):  # fmt: skip
            self.assertTrue(stock_opener(hook), hook)
        self.assertIsNone(stock_opener("The Chargers are 0-4 for the first time since 2017."))

    def test_regen_is_on_by_default(self):
        from core.hook_score import hook_regen_enabled

        env = {k: v for k, v in os.environ.items() if k != "HOOK_REGEN_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(hook_regen_enabled())
        with patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "false"}):
            self.assertFalse(hook_regen_enabled())


class HookProblemTests(unittest.TestCase):
    def test_run_124_hook_is_unsupported(self):
        from core.content_engine import _hook_problems

        self.assertTrue(_hook_problems(RUN_124_HOOK, FACTS))
        self.assertEqual(_hook_problems("The Chargers are 0-4 for the first time since 2017.",
                                        FACTS), [])  # fmt: skip

    def test_a_number_not_in_the_facts_is_a_problem(self):
        from core.content_engine import _hook_problems

        self.assertTrue(_hook_problems("The Chargers have lost 9 straight games.", FACTS))

    def test_a_repeat_of_a_recent_opener(self):
        from core.content_engine import _hook_problems

        recent = ["The Chargers are 0-4 for the first time since 2017 and it shows."]
        got = _hook_problems("The Chargers are 0-4 for the first time since 2017.", FACTS,
                             recent_openers=recent)  # fmt: skip
        self.assertTrue(any("recent" in p for p in got), got)


class VariantTests(unittest.TestCase):
    def _run(self, script, openers):
        from core import content_engine as ce

        prompts: list[str] = []

        def fake(system, user, **_kw):
            prompts.append(system + "\n" + user)
            return {"openers": openers}

        with (
            patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true", "HOOK_VARIANTS": "3"}),
            patch.object(ce, "_call_content_llm", side_effect=fake),
            patch.object(ce, "_recent_openers", return_value=[]),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
        ):
            out, extra = ce._hook_variants(script, channel_id="tapin", grounding_text=FACTS)
        return out, extra, prompts

    def test_an_unsupported_hook_is_replaced_from_the_facts(self):
        out, extra, prompts = self._run(SCRIPT, [
            "No team in history has ever recovered from this.",
            "The Chargers are 0-4 for the first time since 2017.",
        ])  # fmt: skip
        self.assertTrue(out.startswith("The Chargers are 0-4 for the first time since 2017."))
        self.assertTrue(extra["problems"])
        self.assertIn("VERIFIED FACTS", prompts[0])
        self.assertIn("since 2017", prompts[0])
        refused = [r for r in extra["variants"] if r.get("refused")]
        self.assertTrue(any("unsupported" in r["refused"] for r in refused), refused)

    def test_no_supported_variant_keeps_the_script(self):
        out, _extra, _prompts = self._run(SCRIPT, ["Only one team in NFL history did this."])
        self.assertEqual(out, SCRIPT)


class RepairPromptTests(unittest.TestCase):
    def test_reground_may_replace_a_flagged_hook(self):
        from core import content_engine as ce

        seen: list[str] = []

        def fake(system, user, **_kw):
            seen.append(system)
            return None

        with patch.object(ce, "_call_content_llm", side_effect=fake):
            ce._maybe_reground_script(SCRIPT, FACTS, "Chargers", ["only one team"])
        self.assertTrue(seen)
        self.assertNotIn("Keep the opening hook, the", seen[0])
        self.assertIn("unless the hook itself", seen[0])


if __name__ == "__main__":
    unittest.main()
