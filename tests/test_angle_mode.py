"""#1092: the operator changes the mode on the angle screen, and the angles follow.

`core/angle_intent.py`'s docstring has said since run 73 that the operator "is shown the result
on the angle screen, and they can override it". On 6b5f648 the screen printed the mode and had
no key to change it: an idea the cue list misread ("Bolts bounce back week 5" reads neutral)
could only be retyped. "M = change mode" now picks the mode, writes the angles again from the
signals already fetched (no new discovery), and records the choice as the operator's - the
labelled data #1089 (stance beyond the cue words) and #1021 (angle-pick learning) need.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

IDEA = "Bolts bounce back week 5"


class KeyTests(unittest.TestCase):
    def test_every_mode_has_a_key(self):
        from core.angle_intent import ALL_INTENTS, MODE_KEYS, mode_for_key, mode_menu_lines

        self.assertEqual({intent for intent, _label in MODE_KEYS.values()}, set(ALL_INTENTS))
        self.assertEqual(mode_for_key("h"), "hope")
        self.assertEqual(mode_for_key("N"), "default")
        self.assertEqual(mode_for_key("plan"), "plan")
        self.assertEqual(mode_for_key(""), "")
        self.assertEqual(mode_for_key("z"), "")
        self.assertEqual(len(mode_menu_lines()), len(MODE_KEYS))


def _discovery():
    from core.pipeline import DiscoveryResult

    return DiscoveryResult(
        input_topic=IDEA,
        base_signals={"espn": {"active": True, "data": {"lines": ["LA 0-4"]}}},
        evaluated=[("What the Chargers' week 5 matchup turns on", 50.0, {})],
        channel_id="tapin",
        meta={"angles_dropped": [{"angle": "old", "reason": "x"}], "kept": 1},
    )


class RegenerateTests(unittest.TestCase):
    def test_the_angles_are_written_again_in_the_chosen_mode_without_discovery(self):
        from core import pipeline
        from core.angle_intent import operator_intent

        seen: dict = {}

        def fake_variants(topic, **kwargs):
            seen.update(kwargs, topic=topic)
            return ["Herbert's deep ball is back", "Two starters return for week 5"]

        old = _discovery()
        with (
            patch.object(pipeline, "generate_variants", side_effect=fake_variants),
            patch.object(pipeline, "build_registry", side_effect=AssertionError("discovery")),
            patch.dict("os.environ", {"ANGLE_LLM_JUDGE": "false"}),
        ):
            new = pipeline.regenerate_angles(old, operator_intent("hope"))
        self.assertEqual(seen["intent"], "hope")
        self.assertEqual(seen["topic"], IDEA)
        self.assertEqual([v for v, *_ in new.evaluated], ["Herbert's deep ball is back",
                                                          "Two starters return for week 5"])  # fmt: skip
        self.assertIs(new.base_signals, old.base_signals)
        self.assertEqual(new.meta["angle_mode"], "hope")
        self.assertNotIn("angles_dropped", new.meta)  # the old list's drops are not this one's
        self.assertEqual(new.meta["kept"], 1)
        self.assertEqual(set(new.angle_scores), {v for v, *_ in new.evaluated})

    def test_a_chosen_neutral_stays_neutral(self):
        """A topic with a hope cue, set to neutral by the operator, gets no hope STANCE line."""
        from apis import topic_variants

        prompts: list[str] = []
        with patch.object(
            topic_variants, "complete", side_effect=lambda p, **_k: prompts.append(p) or "a\nb\nc"
        ):
            topic_variants.generate_variants(
                "Chargers Hopeium going into week 5", channel_id="tapin", intent="default"
            )
        self.assertNotIn("reasons for HOPE", prompts[0])
        self.assertIn("neutral analysis", prompts[0])


class ScreenTests(unittest.TestCase):
    def _change(self, key, regen=None):
        import main
        from core.angle_intent import read_intent

        discovery = _discovery()
        read = read_intent(IDEA)
        with (
            patch.object(main, "ask_choice", return_value=key),
            patch("core.pipeline.regenerate_angles", side_effect=regen or (lambda d, r: "new")),
            redirect_stdout(io.StringIO()) as out,
        ):
            got, chosen = main._change_angle_mode(discovery, read)
        return discovery, got, chosen, out.getvalue()

    def test_h_picks_hope_and_rewrites_the_angles(self):
        _old, got, chosen, out = self._change("h")
        self.assertEqual(got, "new")
        self.assertEqual((chosen.intent, chosen.source), ("hope", "operator"))
        self.assertIn("h) hope", out)

    def test_enter_keeps_everything(self):
        old, got, chosen, _out = self._change("")
        self.assertIs(got, old)
        self.assertEqual(chosen.source, "default")

    def test_a_failed_rewrite_keeps_the_angles_and_the_mode(self):
        def boom(_d, _r):
            raise RuntimeError("model down")

        old, got, chosen, out = self._change("t", regen=boom)
        self.assertIs(got, old)
        self.assertEqual(chosen.intent, "take")
        self.assertIn("follows your mode", out)


if __name__ == "__main__":
    unittest.main()
