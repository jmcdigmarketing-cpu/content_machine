"""#891: no "it's not just X - it's Y" (operator, 2026-09-27: "avoid the ai giveaway").

The script prompt banned one verbatim string ("This isn't just X - it's Y") and the
persona lint matched fixed phrases, so every variant the model wrote got through - run 78
opened a chapter with "And it's not just about microtransactions anymore." The detector
finds the pattern; a rewrite pass states the point directly and is kept only if it adds
no name or number; the prompt describes the pattern instead of one string.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

POSITIVE = [
    "It's not just about the money. It's about respect.",
    "This isn't only a trailer, it's actually a statement.",
    "And it's not just about microtransactions anymore.",
    "Not only did he win, but he did it in round one.",
    "This is more than just a patch.",
    "The fight is less about skill and more about cardio.",
    "It's not about the belt, it's about legacy.",
    "They don't just win, they finish people.",
    "It isn’t a delay. It’s actually a reboot.",
]
NEGATIVE = [
    "He isn't injured, he's suspended.",
    "The host city: Las Vegas.",
    "Not just anyone gets a title shot.",
    "The fight is on Saturday, and it's the main event.",
    "This is not a drill.",
    "It was not close. Topuria won every round.",
]


class DetectorTests(unittest.TestCase):
    def test_every_variant_is_found(self):
        from core.persona_lint import contrast_frames

        for text in POSITIVE:
            self.assertTrue(contrast_frames(text), text)

    def test_plain_statements_and_corrections_are_not(self):
        from core.persona_lint import contrast_frames

        for text in NEGATIVE:
            self.assertEqual(contrast_frames(text), [], text)

    def test_the_lint_reports_it(self):
        from core.persona_lint import lint_persona_script

        hits = lint_persona_script("GTA 6 is out. " + POSITIVE[0], channel_id="tapin")
        self.assertTrue(any("not just" in h.lower() or "contrast" in h.lower() for h in hits), hits)


SCRIPT = (
    "Rockstar moved GTA 6 to May 2026. It's not just about polish. It's about the online "
    "economy. Take-Two shares fell eight percent on the news."
)


class RewritePassTests(unittest.TestCase):
    def _run(self, payload, script=SCRIPT):
        from core import content_engine as ce

        with patch.object(ce, "_call_content_llm", return_value=payload) as call:
            out = ce._maybe_drop_contrast_frames(script, min_words=5, max_words=200)
        return out, call

    def test_a_clean_script_costs_no_call(self):
        out, call = self._run({}, script="Rockstar moved GTA 6 to May 2026. Shares fell.")
        call.assert_not_called()
        self.assertEqual(out, "Rockstar moved GTA 6 to May 2026. Shares fell.")

    def test_a_direct_rewrite_is_adopted(self):
        payload = {
            "rewrites": [
                {
                    "old": "It's not just about polish. It's about the online economy.",
                    "new": "The online economy is the real reason.",
                }
            ]
        }
        out, call = self._run(payload)
        call.assert_called_once()
        self.assertIn("The online economy is the real reason.", out)
        self.assertNotIn("not just", out)
        self.assertIn("Take-Two shares fell eight percent", out)

    def test_a_rewrite_that_adds_a_number_is_rejected(self):
        payload = {
            "rewrites": [
                {
                    "old": "It's not just about polish. It's about the online economy.",
                    "new": "The online economy earned 900 million dollars.",
                }
            ]
        }
        out, _ = self._run(payload)
        self.assertEqual(out, SCRIPT)

    def test_a_rewrite_that_keeps_the_frame_is_rejected(self):
        payload = {
            "rewrites": [
                {
                    "old": "It's not just about polish. It's about the online economy.",
                    "new": "It's not only polish, it's the online economy.",
                }
            ]
        }
        out, _ = self._run(payload)
        self.assertEqual(out, SCRIPT)

    def test_an_llm_failure_keeps_the_script(self):
        from core import content_engine as ce

        with patch.object(ce, "_call_content_llm", side_effect=RuntimeError("down")):
            self.assertEqual(
                ce._maybe_drop_contrast_frames(SCRIPT, min_words=5, max_words=200), SCRIPT
            )


class PromptTests(unittest.TestCase):
    def test_the_prompt_describes_the_pattern(self):
        import inspect

        from core import content_engine as ce

        src = inspect.getsource(ce)
        self.assertIn("not only X but Y", src)
        self.assertIn("more than just", src)


if __name__ == "__main__":
    unittest.main()
