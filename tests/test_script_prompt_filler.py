"""Regression: the script prompt must not coach (or emit) stock filler phrases.

The "But here's the thing" crutch showed up in every live script because the
retention rule literally told the model to write a "but here's the thing" moment.
"""

import unittest


def _build(length_choice):
    from core.content_engine import _build_prompts

    return _build_prompts(
        topic="Test topic",
        signals={},
        min_words=150,
        max_words=300,
        today="2026-06-22",
        channel_id="tapin",
        script_brief="Be punchy.",
        seo_block="",
        signal_facts="No structured facts available.",
        signal_summary="",
        brief_block="",
        length_choice=length_choice,
        key_facts=None,
    )


class TestScriptPromptFiller(unittest.TestCase):
    def test_retention_rule_does_not_coach_the_crutch_phrase(self):
        # Medium length triggers the retention/pivot rule.
        system_prompt, _ = _build("2")
        self.assertIn("RETENTION RULE", system_prompt)
        # Inspect only the retention rule itself (up to the next rule block), not
        # the later banned-phrase list which legitimately names the crutch.
        start = system_prompt.index("RETENTION RULE")
        end = system_prompt.index("OPERATOR KEY FACTS RULE", start)
        rule_region = system_prompt[start:end]
        self.assertNotIn("but here's the thing", rule_region.lower())

    def test_stock_filler_phrases_are_banned(self):
        system_prompt, _ = _build("2")
        lowered = system_prompt.lower()
        self.assertIn("but here's the thing", lowered)  # named in the banned list
        self.assertIn("banned", lowered)


if __name__ == "__main__":
    unittest.main()
