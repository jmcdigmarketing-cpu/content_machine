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


if __name__ == "__main__":
    unittest.main()
