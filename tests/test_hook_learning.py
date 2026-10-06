"""#985: the hook learns from the stayed share.

The hook scorer (`core/hook_score`) rates a script's opening line on fixed traits - a number, a
name, brevity, a contradiction, stakes, no question - and nothing ever checked those traits
against what viewers did. The sync now keeps, per Short, the share of starts not swiped away
(`stayed`, #951). `analytics/hook_learning` joins each uploaded video's stayed share to its run's
opening line and reports:

- the correlation of the hook score with stayed, and the n that would settle it (#824's
  `n_for_significance`);
- per trait, the median stayed share of openers with it against without it (3+ each side);
- the three openers that held viewers best.

Below `HOOK_LEARN_MIN` (10) measured videos it says "collecting". Once ready, the opt-in hook
rewrite (`HOOK_REGEN_ENABLED`) quotes the openers that held best, says which trait held more
viewers on this channel, and also rewrites an opener carrying a trait that measured worse -
even when its score passed. `ops growth` prints the line.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

# (opening line, stayed share). Numbers held better here; questions held worse.
HOOKS = [
    ("Conor McGregor lost 3 straight fights.", 0.74),
    ("The Heat won 11 of 12 preseason games.", 0.71),
    ("Silksong sold 2 million copies in a day.", 0.69),
    ("Arsenal paid 105 million for one midfielder.", 0.66),
    ("Bam Adebayo finally has a jumper.", 0.58),
    ("Manchester City look tired this season.", 0.55),
    ("Is this the end of the Lakers dynasty?", 0.44),
    ("Did Jon Jones just retire for good?", 0.41),
    ("Can the Celtics really repeat?", 0.40),
    ("Who wins the Ballon d'Or this year?", 0.38),
]


def _rows(hooks=HOOKS):
    uploads, runs = [], {}
    for i, (hook, stayed) in enumerate(hooks):
        uploads.append(SimpleNamespace(
            id=i, content_run_id=500 + i, youtube_video_id=f"v{i}", detail=f"Video {i}",
            published_at="2026-09-20T18:00:00+00:00",
            metrics_json=json.dumps({"views": 900, "stayed_share": stayed})))  # fmt: skip
        runs[500 + i] = SimpleNamespace(id=500 + i, script=f"{hook} Then the rest of it.",
                                        quality_json="{}")  # fmt: skip
    return uploads, runs


def _patched(hooks=HOOKS):
    uploads, runs = _rows(hooks)
    pub = SimpleNamespace(list_uploaded_for_channel=lambda c: uploads)
    run_repo = SimpleNamespace(get=lambda rid: runs.get(rid))
    return (
        patch("analytics.hook_learning._publish_repo", return_value=pub),
        patch("analytics.hook_learning._run_repo", return_value=run_repo),
    )


def _learn(hooks=HOOKS):
    from analytics.hook_learning import learn

    a, b = _patched(hooks)
    with a, b:
        return learn("tapin")


class LearnTests(unittest.TestCase):
    def test_numbers_held_and_questions_did_not(self):
        got = _learn()
        self.assertEqual(got["n"], 10)
        self.assertTrue(got["ready"])
        traits = {t["trait"]: t for t in got["traits"]}
        self.assertGreater(traits["a number"]["gap"], 0.1)
        self.assertLess(traits["a question"]["gap"], -0.1)
        self.assertIsNotNone(got["r"])
        self.assertGreater(got["r"], 0)

    def test_the_best_three_openers(self):
        best = _learn()["best_hooks"]
        self.assertEqual(len(best), 3)
        self.assertEqual(best[0][0], "Conor McGregor lost 3 straight fights.")

    def test_collecting_below_the_minimum(self):
        from analytics.hook_learning import render_line

        a, b = _patched(HOOKS[:4])
        with a, b:
            line = render_line("tapin")
        self.assertIn("collecting", line)
        self.assertIn("4 of 10", line)

    def test_the_line_names_the_traits(self):
        from analytics.hook_learning import render_line

        a, b = _patched()
        with a, b:
            line = render_line("tapin")
        self.assertIn("a number", line)
        self.assertIn("a question", line)
        self.assertIn("10 videos", line)

    def test_a_video_without_stayed_or_script_is_skipped(self):
        uploads, runs = _rows()
        uploads[0].metrics_json = json.dumps({"views": 10})
        runs[501].script = ""
        pub = SimpleNamespace(list_uploaded_for_channel=lambda c: uploads)
        with (
            patch("analytics.hook_learning._publish_repo", return_value=pub),
            patch("analytics.hook_learning._run_repo",
                  return_value=SimpleNamespace(get=lambda rid: runs.get(rid))),
        ):  # fmt: skip
            from analytics.hook_learning import learn

            self.assertEqual(learn("tapin")["n"], 8)


class RewriteTests(unittest.TestCase):
    def test_the_rewrite_prompt_carries_what_held(self):
        from core import content_engine

        seen = {}

        def fake_llm(system, user, **kw):
            seen["system"] = system
            # #987: the old fake's "2 times in 3 years" invented numbers and is now refused.
            return {"openers": ["Jon Jones walked away for good and nobody stopped him."]}

        a, b = _patched()
        with (
            a, b,
            patch.dict("os.environ", {"HOOK_REGEN_ENABLED": "true"}),
            patch.object(content_engine, "_call_content_llm", side_effect=fake_llm),
        ):  # fmt: skip
            # The score passes, but it opens on a question - the trait that held worst here.
            out = content_engine._maybe_improve_hook(
                "Did Jon Jones really retire for good? The rest of it.", channel_id="tapin"
            )
        self.assertIn("Conor McGregor lost 3 straight fights.", seen.get("system", ""))
        self.assertIn("a number", seen["system"])
        self.assertTrue(out.startswith("Jon Jones walked away for good"))

    def test_nothing_learned_ranks_by_the_scorer_alone(self):
        # #987 changed this: with the rewrite switched on, variants are asked for every run;
        # with nothing learned yet they compete on the hook scorer alone, and a variant that
        # does not beat the current opener is not kept.
        from core import content_engine

        a, b = _patched(HOOKS[:4])
        with (
            a, b,
            patch.dict("os.environ", {"HOOK_REGEN_ENABLED": "true"}),
            patch.object(content_engine, "_call_content_llm",
                         return_value={"openers": ["Here is something about Jon Jones."]}) as llm,
        ):  # fmt: skip
            script = "Jon Jones won 27 fights and lost once. The rest of it."
            self.assertEqual(content_engine._maybe_improve_hook(script, channel_id="tapin"),
                             script)  # fmt: skip
        system = llm.call_args[0][0]
        self.assertNotIn("held viewers best", system)


class GrowthTests(unittest.TestCase):
    def test_ops_growth_prints_the_hook_line(self):
        from analytics import growth

        with (
            patch("analytics.growth.report", return_value={"n": 6, "median_views": 500,
                  "best": {"title": "a", "views": 900}, "worst": {"title": "b", "views": 100},
                  "per_week": 3.0, "paid_share": 0.0}),
            patch("analytics.hook_learning.render_line", return_value="Hook vs stayed: X"),
        ):  # fmt: skip
            text = growth.render("tapin")
        self.assertIn("Hook vs stayed: X", text)


if __name__ == "__main__":
    unittest.main()
