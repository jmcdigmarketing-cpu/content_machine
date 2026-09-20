"""Tests for regenerate-then-warn fact grounding (core/content_engine)."""

import unittest
from unittest.mock import patch

from core import content_engine as ce

# Facts mention only the Giannis -> Heat trade.
_FACTS = "Giannis Antetokounmpo was traded to the Miami Heat."
# Script blends a supported trade with an invented Butler -> Celtics storyline.
_ORIGINAL = (
    "Giannis Antetokounmpo joined the Miami Heat in a blockbuster move. "
    "Meanwhile Jimmy Butler went to the Boston Celtics to chase a title."
)
_TOPIC = "NBA trades"


def _flags(script: str) -> list[str]:
    from core.fact_grounding import find_ungrounded_entities

    return find_ungrounded_entities(script, _FACTS)


class TestRegroundScript(unittest.TestCase):
    def test_accepts_cleaner_rewrite(self):
        clean = (
            "Giannis Antetokounmpo joined the Miami Heat in a blockbuster move. "
            "Another contender also reshaped its roster to chase a title this offseason."
        )
        self.assertTrue(_flags(_ORIGINAL))  # original is dirty
        self.assertFalse(_flags(clean))  # rewrite is clean
        with patch.object(ce, "_call_content_llm", return_value={"script": clean}):
            with patch.dict("os.environ", {"GROUNDING_REGEN_ENABLED": "true"}, clear=False):
                script, remaining = ce._maybe_reground_script(
                    _ORIGINAL, _FACTS, _TOPIC, _flags(_ORIGINAL)
                )
        self.assertEqual(script, clean)
        self.assertEqual(remaining, [])

    def test_rejects_rewrite_that_does_not_reduce(self):
        worse = (
            "LeBron James joined the Los Angeles Lakers and Kevin Durant moved on as well "
            "while several other stars changed teams during a chaotic week of deals."
        )
        with patch.object(ce, "_call_content_llm", return_value={"script": worse}):
            script, remaining = ce._maybe_reground_script(
                _ORIGINAL, _FACTS, _TOPIC, _flags(_ORIGINAL)
            )
        self.assertEqual(script, _ORIGINAL)  # kept original

    def test_rejects_gutted_rewrite(self):
        gutted = "Trades happened today."  # 0 flags but far too short
        with patch.object(ce, "_call_content_llm", return_value={"script": gutted}):
            script, remaining = ce._maybe_reground_script(
                _ORIGINAL, _FACTS, _TOPIC, _flags(_ORIGINAL)
            )
        self.assertEqual(script, _ORIGINAL)

    def test_disabled_is_noop(self):
        with patch.dict("os.environ", {"GROUNDING_REGEN_ENABLED": "false"}, clear=False):
            with patch.object(ce, "_call_content_llm") as mock_llm:
                script, remaining = ce._maybe_reground_script(
                    _ORIGINAL, _FACTS, _TOPIC, _flags(_ORIGINAL)
                )
                mock_llm.assert_not_called()
        self.assertEqual(script, _ORIGINAL)

    def test_no_flags_is_noop(self):
        with patch.object(ce, "_call_content_llm") as mock_llm:
            script, remaining = ce._maybe_reground_script(_ORIGINAL, _FACTS, _TOPIC, [])
            mock_llm.assert_not_called()
        self.assertEqual(script, _ORIGINAL)
        self.assertEqual(remaining, [])


class TestRegroundMergeWhenDisabled(unittest.TestCase):
    """#813: a disabled reground pass must not double-count the held-back flags.

    `_regroundable` deliberately holds negative-fact hits back from the rewrite.
    Wave 26 seeded the "what survived" box with the *whole* ungrounded list, so
    when the pass never ran the merge returned `held + (held + targets)` and
    every held-back hit was counted twice against the grounding grade.
    """

    def test_disabled_reground_does_not_duplicate_held_flags(self):
        import os

        from core.content_engine import generate_content_package

        script = (
            "Giannis Antetokounmpo joined the Miami Heat in a blockbuster move that "
            "reshaped the conference overnight. Jimmy Butler went to the Boston Celtics "
            "to chase one more title before the window shuts on this roster for good. "
            "The Heat now build around a new core and the East runs through Miami again."
        )
        payload = {
            "script": script,
            "title": "Heat trade",
            "description": "desc",
            "tags": ["nba"],
        }
        with (
            patch.dict("os.environ", {"GROUNDING_REGEN_ENABLED": "false"}, clear=False),
            patch.object(ce, "enrich_facts", return_value=_FACTS),
            patch.object(ce, "_call_content_llm", return_value=payload),
            patch.object(ce, "find_ungrounded_entities", return_value=["Jimmy Butler"]),
            patch("core.negative_facts.apply_negative_facts", return_value=["Giannis retired"]),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="Heat trade"),
        ):
            self.assertFalse(ce._reground_enabled(), os.getenv("GROUNDING_REGEN_ENABLED"))
            result = generate_content_package(
                _TOPIC,
                {},
                (40, 80),
                "2026-09-20",
                channel_id="tapin",
                length_choice="1",
            )

        flags = result.get("ungrounded_entities") or []
        self.assertEqual(len(flags), len(set(flags)), flags)
        self.assertEqual(sorted(flags), sorted(["Jimmy Butler", "negative-fact: Giannis retired"]))


if __name__ == "__main__":
    unittest.main()
