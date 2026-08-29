"""Pillar 3 (Fact Engine) — pre-script contradiction detection: trade
direction, reversed results, champion claims, line filtering, display."""

import unittest
from unittest.mock import patch

from core.fact_conflicts import (
    conflict_filter_enabled,
    display_fact_conflicts,
    drop_conflicting_lines,
    find_fact_conflicts,
)

_OPERATOR = ["Giannis Antetokounmpo was traded to the Miami Heat on June 22, 2026"]


class TestTradeDirection(unittest.TestCase):
    def test_conflicting_destination_flags(self):
        source = "News headlines:\n- Giannis traded to the Golden State Warriors (rumor mill)"
        conflicts = find_fact_conflicts(_OPERATOR, source)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].kind, "trade_direction")
        self.assertIn("Giannis", conflicts[0].detail)

    def test_agreeing_destination_is_clean(self):
        source = "- Giannis Antetokounmpo traded to the Miami Heat, sources say"
        self.assertEqual(find_fact_conflicts(_OPERATOR, source), [])

    def test_different_player_is_clean(self):
        source = "- Jimmy Butler was traded to the Golden State Warriors"
        self.assertEqual(find_fact_conflicts(_OPERATOR, source), [])


class TestReversedResult(unittest.TestCase):
    def test_reversed_winner_flags(self):
        operator = ["Justin Gaethje defeated Ilia Topuria at UFC 350"]
        source = "- Ilia Topuria defeated Justin Gaethje in the co-main"
        conflicts = find_fact_conflicts(operator, source)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].kind, "reversed_result")

    def test_same_direction_is_clean(self):
        operator = ["Justin Gaethje defeated Ilia Topuria at UFC 350"]
        source = "- Justin Gaethje defeated Ilia Topuria by TKO"
        self.assertEqual(find_fact_conflicts(operator, source), [])


class TestChampionConflict(unittest.TestCase):
    def test_different_champion_same_division_flags(self):
        operator = ["Islam Makhachev is the current lightweight champion"]
        source = "- Justin Gaethje is the new lightweight champion after UFC 350"
        conflicts = find_fact_conflicts(operator, source)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].kind, "champion")

    def test_different_division_is_clean(self):
        operator = ["Islam Makhachev is the current lightweight champion"]
        source = "- Tom Aspinall is the reigning heavyweight champion"
        self.assertEqual(find_fact_conflicts(operator, source), [])

    def test_same_champion_name_is_clean(self):
        operator = ["Islam Makhachev is the current lightweight champion"]
        source = "- Makhachev is the reigning lightweight champion"
        self.assertEqual(find_fact_conflicts(operator, source), [])


class TestScope(unittest.TestCase):
    def test_no_operator_facts_returns_empty(self):
        source = "- Giannis traded to the Warriors\n- Giannis traded to the Heat"
        self.assertEqual(find_fact_conflicts([], source), [])
        self.assertEqual(find_fact_conflicts(None, source), [])

    def test_empty_source_returns_empty(self):
        self.assertEqual(find_fact_conflicts(_OPERATOR, "  "), [])

    def test_duplicate_conflicts_deduped(self):
        source = (
            "- Giannis traded to the Golden State Warriors\n"
            "- Giannis traded to the Golden State Warriors"
        )
        self.assertEqual(len(find_fact_conflicts(_OPERATOR, source)), 1)


class TestDropConflictingLines(unittest.TestCase):
    def test_drops_only_the_losing_source_line(self):
        source = (
            "Tapology event: NBA offseason\n"
            "- Giannis traded to the Golden State Warriors (rumor)\n"
            "- Unrelated line stays"
        )
        conflicts = find_fact_conflicts(_OPERATOR, source)
        filtered, dropped = drop_conflicting_lines(source, conflicts)
        self.assertEqual(dropped, 1)
        self.assertNotIn("Warriors", filtered)
        self.assertIn("Unrelated line stays", filtered)
        self.assertIn("Tapology event", filtered)

    def test_no_conflicts_is_noop(self):
        source = "- line a\n- line b"
        filtered, dropped = drop_conflicting_lines(source, [])
        self.assertEqual((filtered, dropped), (source, 0))


class TestEnvAndDisplay(unittest.TestCase):
    def test_filter_enabled_by_default(self):
        with patch.dict("os.environ", {"FACT_CONFLICT_FILTER": ""}, clear=False):
            self.assertTrue(conflict_filter_enabled())
        with patch.dict("os.environ", {"FACT_CONFLICT_FILTER": "false"}, clear=False):
            self.assertFalse(conflict_filter_enabled())

    def test_display_reports_dropped_lines(self):
        out: list[str] = []
        needs = display_fact_conflicts(
            ["Trade direction disagrees for Giannis: Heat (operator) vs Warriors (source)"],
            dropped=1,
            print_fn=lambda *a: out.append(" ".join(str(x) for x in a)),
        )
        self.assertTrue(needs)
        joined = "\n".join(out)
        self.assertIn("operator facts win", joined)
        self.assertIn("kept out of the prompt", joined)

    def test_display_empty_is_silent(self):
        out: list[str] = []
        self.assertFalse(display_fact_conflicts([], print_fn=out.append))
        self.assertEqual(out, [])


class TestFactEngineReportUI(unittest.TestCase):
    def test_reports_all_three_layers(self):
        from core.ui import display_fact_engine_report

        out: list[str] = []
        features = {
            "fact_conflicts": ["Trade direction disagrees for Giannis: Heat vs Warriors"],
            "fact_conflicts_dropped": 1,
            "tier_warnings": ["'Darren Till' only grounds when YouTube titles are counted"],
            "claim_verification": {"total": 2, "supported": 1, "unsupported": ["bad claim"]},
        }
        needs = display_fact_engine_report(
            features, print_fn=lambda *a: out.append(" ".join(str(x) for x in a))
        )
        self.assertTrue(needs)
        joined = "\n".join(out)
        self.assertIn("Fact conflicts", joined)
        self.assertIn("Grounding tiers", joined)
        self.assertIn("Claim check", joined)

    def test_clean_features_need_no_review(self):
        from core.ui import display_fact_engine_report

        out: list[str] = []
        needs = display_fact_engine_report(
            {"fact_conflicts": [], "tier_warnings": [], "claim_verification": None},
            print_fn=lambda *a: out.append(" ".join(str(x) for x in a)),
        )
        self.assertFalse(needs)


class TestDisputedFlag(unittest.TestCase):
    """#332: arbitration must leave a first-class disputed flag, not just a string list."""

    def test_conflicts_stamp_disputed_and_the_losing_claim(self):
        from core.fact_conflicts import features_from_conflicts

        source = "- Giannis traded to the Golden State Warriors (rumor mill)"
        conflicts = find_fact_conflicts(_OPERATOR, source)
        filtered, dropped = drop_conflicting_lines(source, conflicts)
        feats = features_from_conflicts(conflicts, dropped=dropped)
        self.assertTrue(feats["disputed"])
        self.assertEqual(dropped, 1)
        self.assertNotIn("Warriors", filtered)
        self.assertTrue(any("Warriors" in c for c in feats["disputed_claims"]))

    def test_report_card_prints_disputed_not_just_a_bullet_list(self):
        from core.ui import display_fact_engine_report

        out: list[str] = []
        needs = display_fact_engine_report(
            {
                "disputed": True,
                "disputed_claims": ["Giannis traded to the Golden State Warriors"],
                "fact_conflicts": ["Trade direction disagrees for Giannis: Heat vs Warriors"],
                "fact_conflicts_dropped": 1,
            },
            print_fn=lambda *a: out.append(" ".join(str(x) for x in a)),
        )
        self.assertTrue(needs)
        joined = "\n".join(out).lower()
        self.assertIn("disputed", joined)
        self.assertIn("warriors", joined)

    def test_no_conflicts_is_not_disputed(self):
        from core.fact_conflicts import features_from_conflicts

        feats = features_from_conflicts([], dropped=0)
        self.assertFalse(feats.get("disputed"))
        self.assertEqual(feats.get("disputed_claims"), [])

    def test_generate_content_package_stamps_disputed(self):
        from unittest.mock import patch

        from core.content_engine import generate_content_package

        payload = {
            "script": "Giannis is headed to the Heat after the trade. " * 8,
            "title": "Heat trade",
            "description": "desc",
            "tags": ["nba"],
        }
        with (
            patch(
                "core.content_engine.enrich_facts",
                return_value="- Giannis traded to the Golden State Warriors",
            ),
            patch("core.content_engine._call_content_llm", return_value=payload),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="Heat trade"),
            patch("core.content_engine._maybe_improve_hook", side_effect=lambda s: s),
            patch("core.content_engine._maybe_inject_insight", side_effect=lambda s, *_a, **_k: s),
        ):
            result = generate_content_package(
                "Giannis trade",
                {},
                (40, 80),
                "2026-08-21",
                channel_id="tapin",
                key_facts=_OPERATOR,
                length_choice="1",
            )
        self.assertTrue(result.get("disputed"))
        self.assertGreater(result.get("fact_conflicts_dropped") or 0, 0)


if __name__ == "__main__":
    unittest.main()
