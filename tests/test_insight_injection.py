"""Tests for original-insight injection (Phase O) in core/content_engine."""

import unittest
from unittest.mock import patch

from core import authenticity
from core import content_engine as ce

_FACTS = "Giannis Antetokounmpo was traded to the Miami Heat."
_TOPIC = "NBA trades"
# A neutral recap — no opinion/prediction markers.
_RECAP = (
    "Giannis Antetokounmpo was traded to the Miami Heat. The deal was announced on Monday. "
    "Miami sent multiple players and picks to complete the move."
)


class TestHasInsight(unittest.TestCase):
    def test_detects_a_take(self):
        self.assertTrue(authenticity.has_insight("Here's why this changes the East."))
        self.assertTrue(authenticity.has_insight("My prediction: they win the title."))

    def test_neutral_recap_has_no_take(self):
        self.assertFalse(authenticity.has_insight(_RECAP))


class TestInjectInsight(unittest.TestCase):
    def test_injects_when_recap_has_no_take(self):
        with_take = _RECAP + " Here's why it matters: this instantly makes Miami the team to beat."
        self.assertFalse(authenticity.has_insight(_RECAP))
        self.assertTrue(authenticity.has_insight(with_take))
        with patch.object(ce, "_call_content_llm", return_value={"script": with_take}):
            with patch.dict("os.environ", {"INSIGHT_INJECTION_ENABLED": "true"}, clear=False):
                out = ce._maybe_inject_insight(_RECAP, _FACTS, _TOPIC)
        self.assertEqual(out, with_take)

    def test_noop_when_script_already_has_take(self):
        already = _RECAP + " My prediction: Miami makes the Finals."
        with patch.object(ce, "_call_content_llm") as mock_llm:
            out = ce._maybe_inject_insight(already, _FACTS, _TOPIC)
            mock_llm.assert_not_called()
        self.assertEqual(out, already)

    def test_rejects_rewrite_that_still_has_no_take(self):
        no_take = _RECAP + " The trade was finalized after league approval."
        with patch.object(ce, "_call_content_llm", return_value={"script": no_take}):
            out = ce._maybe_inject_insight(_RECAP, _FACTS, _TOPIC)
        self.assertEqual(out, _RECAP)  # kept original — injection didn't add a take

    def test_rejects_gutted_rewrite(self):
        gutted = "Here's why it matters."  # has a marker but far too short
        with patch.object(ce, "_call_content_llm", return_value={"script": gutted}):
            out = ce._maybe_inject_insight(_RECAP, _FACTS, _TOPIC)
        self.assertEqual(out, _RECAP)

    def test_disabled_is_noop(self):
        with patch.dict("os.environ", {"INSIGHT_INJECTION_ENABLED": "false"}, clear=False):
            with patch.object(ce, "_call_content_llm") as mock_llm:
                out = ce._maybe_inject_insight(_RECAP, _FACTS, _TOPIC)
                mock_llm.assert_not_called()
        self.assertEqual(out, _RECAP)


if __name__ == "__main__":
    unittest.main()
