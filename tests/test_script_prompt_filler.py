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

    def test_framing_rule_treats_facts_as_evidence(self):
        # The FRAMING block is what stops the model reciting facts as a list.
        system_prompt, _ = _build("2")
        self.assertIn("FRAMING", system_prompt)
        lowered = system_prompt.lower()
        self.assertIn("evidence", lowered)  # facts are evidence, not the point
        self.assertIn("attributed", lowered)  # speculation must be attributed, not asserted

    def test_explainer_prompt_does_not_order_a_take(self):
        """#660. An explainer seed must not get TAKE A SIDE or a hot-take close."""
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic="how does the offside rule actually work",
            signals={},
            min_words=150,
            max_words=300,
            today="2026-06-22",
            channel_id="tapin",
            script_brief="Be clear.",
            seo_block="",
            signal_facts="No structured facts available.",
            signal_summary="",
            brief_block="",
            length_choice="2",
            key_facts=None,
        )
        blob = f"{system}\n{user}"
        self.assertNotIn("TAKE A SIDE", blob)
        self.assertNotIn("Build to a strong closing line", blob)
        self.assertIn("explainer", blob.lower())

    def test_default_topic_still_orders_a_take(self):
        system, user = _build("2")
        blob = f"{system}\n{user}"
        self.assertIn("TAKE A SIDE", blob)


if __name__ == "__main__":
    unittest.main()
