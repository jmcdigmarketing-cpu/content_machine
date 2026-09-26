"""Run 98: a Premier League topic on TapIn was routed as a gaming video.

`_infer_domain_from_text` had no football branch, so "Manchester City ofund guilty,
what does this mean for the prem" matched nothing and fell back to TapIn's channel
domain, "gaming". That one word then:

- gated out every sports signal and ran RAWG/Twitch/Steam/IGDB on a football story
  (`register_signals._gated_signal_names`, whose docstring promised "when unsure,
  run everything");
- put "DOMAIN: gaming" and the GAMING SCRIPT MATRIX in the script prompt;
- chose the gaming angle templates (patch_or_update_hook, meta_or_balance_take);
- ended the description with "Subscribe for daily gaming & UFC takes." and the tags
  with "gaming, esports".

The operator decided football is part of TapIn's niche (2026-09-26), so soccer is a
real domain now. Separately, a typed topic that names no domain at all is neutral
for gating and for the brief - the channel default no longer stands in for "unsure".
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from apis.signal_contract import make_signal

RUN98 = "Manchester City ofund guilty, what does this mean for the prem"
OFF_NICHE = "Election night results in Ohio"


class TestTopicDomain(unittest.TestCase):
    def test_football_topics_are_soccer(self) -> None:
        from apis.topic_scorer import infer_topic_domain

        for topic in (
            RUN98,
            "Rodri's Golden Ball proves he's underrated",
            "Tottenham sack their manager",
            "Premier League standings after round 6",
        ):
            with self.subTest(topic=topic):
                self.assertEqual(infer_topic_domain(topic), "soccer")

    def test_the_football_video_game_stays_gaming(self) -> None:
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain("EA FC 26 Ultimate Team promo"), "gaming")
        self.assertEqual(infer_topic_domain("FIFA 23 career mode tips"), "gaming")

    def test_basketball_spurs_are_still_nba(self) -> None:
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain("Spurs beat the Lakers"), "nba")

    def test_franchise_names_are_gaming_without_the_word_game(self) -> None:
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain("Fortnite chapter 6 map changes"), "gaming")
        self.assertEqual(infer_topic_domain("Valorant new agent leak"), "gaming")

    def test_no_keyword_is_neutral_not_the_channel(self) -> None:
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain(OFF_NICHE), "neutral")

    def test_effective_domain_uses_the_channel_only_with_evidence(self) -> None:
        from apis.topic_scorer import effective_domain

        rawg = {"rawg": make_signal(connected=True, active=True, score=45, data=[{"name": "x"}])}
        self.assertEqual(effective_domain("Silksong review", "tapin", signals=rawg), "gaming")
        self.assertEqual(effective_domain("Silksong review", "tapin"), "neutral")

    def test_soccer_has_a_sports_weight_profile(self) -> None:
        from apis.topic_scorer import get_default_weights

        weights = get_default_weights("soccer")
        self.assertGreater(weights.get("api_sports", 0), 0)
        self.assertEqual(weights.get("rawg", 0), 0)


class TestGating(unittest.TestCase):
    def test_run98_runs_sports_signals_not_gaming_ones(self) -> None:
        from apis.register_signals import _gated_signal_names

        gated = _gated_signal_names(RUN98, "tapin")
        self.assertEqual({"sports", "live_scores", "odds", "api_sports"} & gated, set())
        self.assertTrue({"rawg", "twitch", "steam", "igdb"} <= gated, gated)
        self.assertTrue({"ufc_context", "tapology"} <= gated, "MMA-only signals on football")

    def test_an_unclassified_topic_gates_nothing(self) -> None:
        from apis.register_signals import _gated_signal_names

        self.assertEqual(_gated_signal_names(OFF_NICHE, "tapin"), set())

    def test_a_gaming_topic_still_gates_sports(self) -> None:
        from apis.register_signals import _gated_signal_names

        self.assertIn("tapology", _gated_signal_names("Fortnite chapter 6 map changes", "tapin"))


class TestScriptBrief(unittest.TestCase):
    def test_run98_gets_the_soccer_matrix(self) -> None:
        from core.script_brief import build_script_brief

        with patch("core.script_brief.channel_history_block", return_value=""):
            brief = build_script_brief(RUN98, "tapin")
        self.assertIn("DOMAIN: soccer", brief)
        self.assertIn("SOCCER SCRIPT MATRIX", brief)
        self.assertNotIn("GAMING SCRIPT MATRIX", brief)

    def test_an_off_niche_topic_is_not_briefed_as_gaming(self) -> None:
        from core.script_brief import build_script_brief

        history = "Recent channel topics: GTA 6\nPrimary franchise focus lately: GTA"
        with patch("core.script_brief.channel_history_block", return_value=history):
            brief = build_script_brief(OFF_NICHE, "tapin")
        self.assertIn("DOMAIN: neutral", brief)
        self.assertNotIn("GAMING SCRIPT MATRIX", brief)
        self.assertNotIn("Primary franchise focus", brief)


class TestAngleTemplates(unittest.TestCase):
    def _types(self, topic: str) -> list[str]:
        from apis import topic_variants

        seen: dict[str, list[str]] = {}

        def _capture(t, angle_types, **kwargs):
            seen["types"] = list(angle_types)
            return ["angle"]

        with patch.object(topic_variants, "generate_ai_titles", side_effect=_capture):
            topic_variants.generate_variants(topic, channel_id="tapin", repeat_count=0)
        return seen.get("types", [])

    def test_run98_does_not_get_patch_notes_angles(self) -> None:
        types = self._types(RUN98)
        self.assertTrue(types)
        self.assertNotIn("patch_or_update_hook", types)
        self.assertNotIn("meta_or_balance_take", types)

    def test_a_game_topic_keeps_the_gaming_angles(self) -> None:
        self.assertIn("patch_or_update_hook", self._types("Marvel Rivals season 4 balance patch"))


class TestChannelPackaging(unittest.TestCase):
    def test_tags_follow_the_topic(self) -> None:
        from config.seo import default_tags_for_channel

        tags = [t.lower() for t in default_tags_for_channel("tapin", RUN98)]
        self.assertIn("football", tags)
        for gone in ("gaming", "esports", "ufc", "mma"):
            self.assertNotIn(gone, tags)

    def test_the_description_signoff_follows_the_topic(self) -> None:
        from config.seo import build_seo_prompt_block

        block = build_seo_prompt_block("tapin", topic=RUN98)
        self.assertIn("Subscribe for daily football takes.", block)
        self.assertNotIn("gaming & UFC takes", block)

    def test_without_a_topic_the_channel_signoff_stays(self) -> None:
        from config.seo import build_seo_prompt_block

        self.assertIn("Subscribe for daily", build_seo_prompt_block("tapin"))

    def test_football_is_on_brand_for_tapin(self) -> None:
        from core.channel_context import on_brand_domains

        self.assertTrue({"gaming", "ufc", "soccer"} <= on_brand_domains("tapin"))


class TestOffNicheNote(unittest.TestCase):
    def test_on_brand_topics_get_no_note(self) -> None:
        from core.channel_context import off_niche_note

        self.assertIsNone(off_niche_note(RUN98, "tapin"))
        self.assertIsNone(off_niche_note("Marvel Rivals season 4 balance patch", "tapin"))

    def test_an_off_niche_topic_is_named(self) -> None:
        from core.channel_context import off_niche_note

        note = off_niche_note(OFF_NICHE, "tapin")
        self.assertIsNotNone(note)
        self.assertIn("off-niche", note.lower())


if __name__ == "__main__":
    unittest.main()
