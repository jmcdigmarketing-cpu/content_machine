"""#1093: the idea's stance is kept to the last pass - the Long close, the hook, the idea check,
the title.

Planned 2026-10-10, measured on 6b5f648. Wave 68 put the stance in the angle, script and title
prompts. Four later passes never saw it: the user prompt told every Long script to end on a
"closing take" whatever the intent; the hook rewrite asked for "a contradiction" with no stance
line and no check; `_keep_to_idea` asked whether the script answers the idea, not whether it
keeps its stance; and the title carried the stance line but nothing checked what came back.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

IDEA = "Chargers Hopeium going into week 5"


def _blob(topic, brief=""):
    from core.content_engine import _build_prompts

    system, user = _build_prompts(
        topic=topic, signals={}, min_words=400, max_words=700, today="2026-10-10",
        channel_id="tapin", script_brief="", seo_block="", signal_facts="",
        signal_summary="", brief_block="", length_choice="3", key_facts=None,
        seed_topic=topic, creative_brief=brief,
    )  # fmt: skip
    return system + "\n" + user


class LongCloseTests(unittest.TestCase):
    def test_only_a_take_closes_on_a_take(self):
        self.assertNotIn("closing take", _blob("Chargers week 5", IDEA))
        self.assertNotIn("closing take", _blob("Chargers week 5"))
        self.assertIn("closing take", _blob("Chargers hot take: fire the coach"))


SCRIPT = "Herbert threw for 300 yards. The Chargers are 0-4. Week 5 is Miami at home."


class HookTests(unittest.TestCase):
    def test_an_opener_that_knocks_the_hope_is_refused(self):
        from core import content_engine as ce

        knock = "Herbert's 300 yards mask the Chargers' flaws."
        sound = "Herbert threw for 300 yards in a loss."
        prompts: list[str] = []

        def fake_llm(system, _user, **_kw):
            prompts.append(system)
            return {"openers": [knock, sound]}

        with (
            patch("core.hook_score.hook_regen_enabled", return_value=True),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
            patch(
                "analytics.hook_learning.rank_openers",
                side_effect=lambda openers, _g: [(o, 10.0 - i) for i, o in enumerate(openers)],
            ),
            patch.object(ce, "_call_content_llm", side_effect=fake_llm),
            patch.object(ce, "_hook_problems", return_value=[]),
        ):
            out, extra = ce._hook_variants(SCRIPT, intent="hope", idea=IDEA)
        self.assertIn("STANCE", prompts[0])
        refused = {row["opener"]: row.get("refused", "") for row in extra["variants"]}
        self.assertIn("stance", refused[knock])
        self.assertNotEqual(extra["picked"], knock)
        self.assertFalse(out.startswith(knock))


class IdeaCheckTests(unittest.TestCase):
    def test_a_closing_line_that_mocks_the_hope_fails_without_a_call(self):
        from core import content_engine as ce

        mocking = SCRIPT + " Chargers fans are in denial."
        fixed = SCRIPT + " Herbert's arm is the reason to believe."
        calls: list[str] = []

        def fake_llm(system, _user, **_kw):
            calls.append(system)
            if system.startswith("Rewrite"):
                return {"script": fixed}
            return {"answers": True, "missing": ""}

        with patch.object(ce, "_call_content_llm", side_effect=fake_llm):
            out, extra = ce._keep_to_idea(mocking, IDEA, min_words=5, max_words=200, intent="hope")
        self.assertTrue(calls[0].startswith("Rewrite"), calls[0][:80])
        self.assertIn("keeps its stance", calls[0])
        self.assertIn("denial", extra["missing_before"])
        self.assertEqual(out, fixed)

    def test_the_paid_check_asks_about_the_stance(self):
        from core import content_engine as ce

        calls: list[str] = []

        def fake_llm(system, _user, **_kw):
            calls.append(system)
            return {"answers": True}

        with patch.object(ce, "_call_content_llm", side_effect=fake_llm):
            ce._keep_to_idea(SCRIPT, IDEA, min_words=5, max_words=200, intent="hope")
        self.assertIn("keeps its stance", calls[0])
        self.assertIn("hope", calls[0])


class TitleTests(unittest.TestCase):
    def test_a_title_that_knocks_the_hope_is_asked_for_again(self):
        from core import title_generator

        replies = iter(["Chargers Hopeium Is Fan Denial Going Into Week 5",
                        "Chargers Hopeium: 3 Reasons To Believe Going Into Week 5"])  # fmt: skip
        with patch.object(title_generator, "complete", side_effect=lambda *_a, **_k: next(replies)):
            title = title_generator.generate_title(
                script=SCRIPT, topic="Chargers Hopeium week 5", seed_topic=IDEA,
                channel_id="tapin", brief=IDEA,
            )  # fmt: skip
        self.assertNotIn("Denial", title)
        self.assertIn("Reasons", title)

    def test_the_title_argues_a_stated_take(self):
        from core import title_generator

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return "Herbert Is Elite: The Numbers Through Week 4"

        with patch.object(title_generator, "complete", side_effect=fake):
            title_generator.generate_title(
                script=SCRIPT, topic="Herbert is elite", channel_id="tapin",
                brief="Chargers hot take: Herbert is elite",
            )  # fmt: skip
        self.assertIn("own take", prompts[0])


if __name__ == "__main__":
    unittest.main()
