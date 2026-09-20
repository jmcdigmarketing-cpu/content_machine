"""#799: which rewrite pass changed the script must be on the report card.

Five `_maybe_*` passes can rewrite a finished script and nothing recorded which
fired, what it changed, or what it cost. Run 74 lost words to one of them and it
took a live investigation to see it. The ledger is the prerequisite for every
other script change in wave 26.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core import content_engine as ce
from core.llm_router import _record_usage, reset_usage
from core.run_quality import build_quality
from core.video_grade import grade_from_parts, render_grade

_FACTS = "Giannis Antetokounmpo was traded to the Miami Heat."
_TOPIC = "NBA trades"
_RECAP = (
    "Giannis Antetokounmpo was traded to the Miami Heat. The deal was announced on Monday. "
    "Miami sent multiple players and picks to complete the move."
)
_WITH_TAKE = _RECAP + " Here's why it matters: this instantly makes Miami the team to beat."


def _record_paid_script_call() -> None:
    _record_usage("openai", "gpt-4o-mini", "premium", 800, 200, stage="script")


def _row(ledger: list[dict], name: str) -> dict:
    matches = [r for r in ledger if r.get("name") == name]
    assert matches, f"no row named {name} in {ledger!r}"
    return matches[0]


class TestScriptPassLedger(unittest.TestCase):
    def setUp(self) -> None:
        reset_usage()

    def tearDown(self) -> None:
        reset_usage()

    def test_adopted_insight_pass_records_word_delta_and_cost(self) -> None:
        """The wrapper calls the real helper. Mock the LLM, not the ledger."""
        ledger: list[dict] = []

        def fake_llm(*_a, **_k):
            _record_paid_script_call()
            return {"script": _WITH_TAKE}

        with (
            patch.object(ce, "_call_content_llm", side_effect=fake_llm),
            patch.dict("os.environ", {"INSIGHT_INJECTION_ENABLED": "true"}, clear=False),
        ):
            out = ce.run_script_pass(
                ledger,
                "inject_insight",
                _RECAP,
                lambda s: ce._maybe_inject_insight(s, _FACTS, _TOPIC),
            )
        self.assertEqual(out, _WITH_TAKE)
        row = _row(ledger, "inject_insight")
        self.assertTrue(row["adopted"])
        self.assertTrue(row["llm_called"])
        self.assertGreater(row["word_delta"], 0)
        self.assertGreater(row["cost_usd"], 0)
        self.assertEqual(row.get("skip_reason") or "", "")

    def test_disabled_hook_is_recorded_as_disabled_not_as_a_run(self) -> None:
        ledger: list[dict] = []
        env = {k: v for k, v in os.environ.items() if k != "HOOK_REGEN_ENABLED"}
        with patch.dict("os.environ", env, clear=True):
            os.environ.pop("HOOK_REGEN_ENABLED", None)
            from core.hook_score import hook_regen_enabled

            self.assertFalse(hook_regen_enabled())
            out = ce.run_script_pass(
                ledger,
                "improve_hook",
                _RECAP,
                ce._maybe_improve_hook,
                disabled=not hook_regen_enabled(),
            )
        self.assertEqual(out, _RECAP)
        row = _row(ledger, "improve_hook")
        self.assertEqual(row["skip_reason"], "disabled")
        self.assertFalse(row["llm_called"])
        self.assertFalse(row["adopted"])
        self.assertEqual(row["word_delta"], 0)
        self.assertEqual(row["cost_usd"], 0)

    def test_rejected_candidate_is_llm_called_not_adopted(self) -> None:
        ledger: list[dict] = []
        no_take = _RECAP + " The trade was finalized after league approval."

        def fake_llm(*_a, **_k):
            _record_paid_script_call()
            return {"script": no_take}

        with (
            patch.object(ce, "_call_content_llm", side_effect=fake_llm),
            patch.dict("os.environ", {"INSIGHT_INJECTION_ENABLED": "true"}, clear=False),
        ):
            out = ce.run_script_pass(
                ledger,
                "inject_insight",
                _RECAP,
                lambda s: ce._maybe_inject_insight(s, _FACTS, _TOPIC),
            )
        self.assertEqual(out, _RECAP)
        row = _row(ledger, "inject_insight")
        self.assertTrue(row["llm_called"])
        self.assertFalse(row["adopted"])
        self.assertEqual(row["skip_reason"], "rejected")
        self.assertEqual(row["word_delta"], 0)

    def test_reground_adopt_persists_pre_and_post_unsupported_counts(self) -> None:
        from core.fact_grounding import find_ungrounded_entities

        original = (
            "Giannis Antetokounmpo joined the Miami Heat in a blockbuster move. "
            "Meanwhile Jimmy Butler went to the Boston Celtics to chase a title."
        )
        clean = (
            "Giannis Antetokounmpo joined the Miami Heat in a blockbuster move. "
            "Another contender also reshaped its roster to chase a title this offseason."
        )
        flags = find_ungrounded_entities(original, _FACTS)
        self.assertTrue(flags)
        ledger: list[dict] = []

        def fake_llm(*_a, **_k):
            _record_paid_script_call()
            return {"script": clean}

        def _run(script: str):
            new, remaining = ce._maybe_reground_script(script, _FACTS, _TOPIC, flags)
            return new, {
                "pre_reground_ungrounded": len(flags),
                "post_reground_ungrounded": len(remaining),
            }

        with (
            patch.object(ce, "_call_content_llm", side_effect=fake_llm),
            patch.dict("os.environ", {"GROUNDING_REGEN_ENABLED": "true"}, clear=False),
        ):
            out = ce.run_script_pass(ledger, "reground", original, _run)
        self.assertEqual(out, clean)
        row = _row(ledger, "reground")
        self.assertTrue(row["adopted"])
        self.assertGreater(row["pre_reground_ungrounded"], row["post_reground_ungrounded"])
        self.assertEqual(row["post_reground_ungrounded"], 0)


class TestScriptPassesReachTheCard(unittest.TestCase):
    """Guard: if the copy into quality is dropped, the report card goes silent."""

    def test_quality_and_report_card_show_an_adopted_pass(self) -> None:
        features = {
            "script_passes": [
                {
                    "name": "inject_insight",
                    "adopted": True,
                    "llm_called": True,
                    "skip_reason": "",
                    "word_delta": 12,
                    "hook_delta": 0.0,
                    "cost_usd": 0.004,
                },
                {
                    "name": "rewrite_claims",
                    "adopted": True,
                    "llm_called": True,
                    "skip_reason": "",
                    "word_delta": -3,
                    "hook_delta": 0.0,
                    "cost_usd": 0.002,
                },
            ]
        }
        quality = build_quality(
            script="A grounded sentence about the topic. " * 20,
            channel_id="tapin",
            features=features,
        )
        self.assertEqual(quality["script_passes"][0]["word_delta"], 12)
        self.assertEqual(quality["script_passes"][1]["word_delta"], -3)
        card = render_grade(grade_from_parts(quality=quality))
        self.assertIn("passes:", card)
        self.assertIn("insight", card)
        self.assertIn("+12w", card)
        self.assertIn("claims", card)
        self.assertIn("-3w", card)

    def test_historical_quality_without_the_key_prints_no_passes_line(self) -> None:
        quality = {
            "hook_score": 80,
            "hook_verdict": "strong",
            "authenticity_score": 90,
            "authenticity_verdict": "ok",
            "ungrounded_count": 0,
            "trade_warning_count": 0,
        }
        card = render_grade(grade_from_parts(quality=quality))
        self.assertNotIn("passes:", card)

    def test_pipeline_copies_script_passes_from_the_package(self) -> None:
        from core.pipeline import copy_content_package_features

        features: dict = {}
        copy_content_package_features(
            {"script_passes": [{"name": "inject_insight", "adopted": True, "word_delta": 12}]},
            features,
        )
        self.assertEqual(features["script_passes"][0]["word_delta"], 12)


if __name__ == "__main__":
    unittest.main()
