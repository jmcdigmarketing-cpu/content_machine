"""Corpus-aware vault relevance scorer (candidate 329 P2).

These are behavioral tests over the real run-71 strings.  The scorer must use the
corpus, not the ambiguous angle, and the production loader must call it for real.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.fact_store import TIER_LINK, TIER_VAULT

TOPIC = "GTA 6 Leak and Wolverine Rage Signal a Cultural Backlash"
CORPUS = (
    "To find the Grand Theft Auto 6 leaker, the parent company of Rockstar Games "
    "has resorted to filing subpoenas in a US court to force Microsoft and Discord "
    "to hand over their records. Rockstar Games Reportedly Remains In The Dark "
    "About Who's Leaking GTA 6."
)


class TestRun71FeatureMatrix(unittest.TestCase):
    def test_corpus_separates_rockstar_from_wolverine(self):
        from core.vault_relevance import score_vault_fact

        good = score_vault_fact(
            topic=TOPIC,
            corpus=CORPUS,
            bullet="Rockstar Games confirms the leak investigation is ongoing.",
            note_context="rockstar Rockstar investigation",
            tier=TIER_LINK,
        )
        bad = score_vault_fact(
            topic=TOPIC,
            corpus=CORPUS,
            bullet="Wolverine Rage is trending after the summer of hate trailer.",
            note_context="wolverine Wolverine rage",
            tier=TIER_VAULT,
        )
        self.assertGreater(good.score, bad.score)
        self.assertEqual(good.band, "confident")
        self.assertEqual(bad.band, "reject")
        self.assertEqual(good.breakdown["bullet_entities_supported"], 1)
        self.assertEqual(bad.breakdown["bullet_entities_supported"], 0)

    def test_note_context_rescues_entityless_follow_up(self):
        from core.vault_relevance import score_vault_fact

        result = score_vault_fact(
            topic=TOPIC,
            corpus=CORPUS,
            bullet="The subpoena demands account IDs and last-login IP addresses.",
            note_context="gta6-subpoenas GTA 6 leak",
            tier=TIER_LINK,
        )
        self.assertIn(result.band, {"uncertain", "confident"})
        self.assertEqual(result.breakdown["bullet_entities_total"], 0)
        self.assertGreater(result.breakdown["note_cosine"], 0)

    def test_competing_family_is_a_penalty_not_a_hidden_gate(self):
        from core.vault_relevance import score_vault_fact

        result = score_vault_fact(
            topic=TOPIC,
            corpus=CORPUS,
            bullet=(
                "Marvel Rivals season 9 adds a Wolverine costume from the " "Horseman of Death era."
            ),
            note_context="rivals Marvel Rivals season 9",
            tier=TIER_VAULT,
        )
        self.assertEqual(result.breakdown["anchor_alignment"], -1.0)
        self.assertLess(result.breakdown["anchor_contribution"], 0)
        self.assertEqual(result.band, "reject")

    def test_no_entity_is_recorded_as_missing_not_supported(self):
        from core.vault_relevance import score_vault_fact

        result = score_vault_fact(
            topic=TOPIC,
            corpus=CORPUS,
            bullet="SEGA announced a new Sonic racing title for next spring.",
            note_context="sega SEGA revival",
            tier=TIER_VAULT,
        )
        self.assertEqual(result.breakdown["bullet_entities_total"], 0)
        self.assertIsNone(result.breakdown["bullet_entity_support"])


class TestCorpusBuilder(unittest.TestCase):
    def test_uses_signal_text_and_operator_facts_without_an_angle(self):
        from core.vault_relevance import build_relevance_corpus

        signals = {
            "news": {
                "connected": True,
                "active": True,
                "data": {"headlines": [{"title": "Rockstar faces a subpoena", "source": "wire"}]},
            },
            "web_search": {
                "connected": True,
                "active": True,
                "data": {
                    "provider": "tavily",
                    "results": [{"title": "Live result", "snippet": "fresh"}],
                },
            },
        }
        corpus = build_relevance_corpus(
            signals,
            operator_facts=["Microsoft received the request."],
            include_web=False,
        )
        self.assertIn("Rockstar faces a subpoena", corpus)
        self.assertIn("Microsoft received the request.", corpus)
        self.assertNotIn("Live result", corpus)
        self.assertNotIn(TOPIC, corpus)


class TestProductionLoaderUsesTheScorer(unittest.TestCase):
    def test_scored_mode_attaches_good_and_rejects_shared_token(self):
        from core.obsidian_facts import load_fact_records

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            (root / "rockstar.md").write_text(
                "---\nchannel: tapin\ntier: link\ntags: [facts]\n---\n"
                "# Rockstar investigation\n"
                "- Rockstar Games confirms the leak investigation is ongoing.\n",
                encoding="utf-8",
            )
            (root / "wolverine.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Wolverine rage\n"
                "- Wolverine Rage is trending after the summer of hate trailer.\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                    "VAULT_RELEVANCE_MODE": "scored",
                },
                clear=False,
            ):
                records = load_fact_records(
                    TOPIC,
                    "tapin",
                    corpus=CORPUS,
                    require_distinctive=True,
                )
        joined = "\n".join(r.claim for r in records)
        self.assertIn("Rockstar Games", joined)
        self.assertNotIn("Wolverine Rage", joined)
        rockstar = next(r for r in records if "Rockstar Games" in r.claim)
        self.assertEqual(rockstar.relevance_band, "confident")
        self.assertTrue(rockstar.relevance_breakdown)

    def test_near_threshold_reject_is_kept_for_inspection(self):
        from core.obsidian_facts import load_fact_records
        from core.vault_relevance import VaultRelevanceDecision, is_inspect_reject

        near = VaultRelevanceDecision(
            score=0.24,
            band="reject",
            scorer_version="vault_relevance_v1",
            policy="operator",
            breakdown={},
        )
        far = VaultRelevanceDecision(
            score=0.05,
            band="reject",
            scorer_version="vault_relevance_v1",
            policy="operator",
            breakdown={},
        )
        self.assertTrue(is_inspect_reject(near))
        self.assertFalse(is_inspect_reject(far))

        def fake_score(**kwargs):
            bullet = kwargs["bullet"]
            if "Rockstar" in bullet:
                return VaultRelevanceDecision(
                    score=0.82,
                    band="confident",
                    scorer_version="vault_relevance_v1",
                    policy="operator",
                    breakdown={"bullet_entity_contribution": 0.3},
                )
            if "SEGA" in bullet:
                return near
            return far

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            (root / "rockstar.md").write_text(
                "---\nchannel: tapin\ntier: link\ntags: [facts]\n---\n"
                "# Rockstar investigation\n"
                "- Rockstar Games confirms the leak investigation is ongoing.\n",
                encoding="utf-8",
            )
            (root / "sega.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# SEGA revival\n"
                "- SEGA announced a new Sonic racing title for next spring.\n",
                encoding="utf-8",
            )
            (root / "noise.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Unrelated\n"
                "- Completely unrelated filler with no shared tokens at all.\n",
                encoding="utf-8",
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                        "VAULT_RELEVANCE_MODE": "scored",
                    },
                    clear=False,
                ),
                patch("core.vault_relevance.score_vault_fact", side_effect=fake_score),
            ):
                records = load_fact_records(
                    TOPIC,
                    "tapin",
                    corpus=CORPUS,
                    require_distinctive=True,
                    limit=8,
                )
        bands = {r.claim: r.relevance_band for r in records}
        self.assertEqual(
            bands.get("Rockstar Games confirms the leak investigation is ongoing."), "confident"
        )
        self.assertEqual(
            bands.get("SEGA announced a new Sonic racing title for next spring."),
            "reject",
        )
        self.assertNotIn(
            "Completely unrelated filler with no shared tokens at all.",
            bands,
        )

    def test_default_mode_is_scored_after_the_holdout_gate(self):
        from core.vault_relevance import load_relevance_config, relevance_mode

        load_relevance_config(refresh=True)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(relevance_mode(), "scored")


class TestShippedScorerConfig(unittest.TestCase):
    def test_shipped_config_is_valid_and_versioned(self):
        from core.vault_relevance import load_relevance_config

        config = load_relevance_config(refresh=True)
        self.assertRegex(config.scorer_version, r"^vault_relevance_v\d+$")
        self.assertGreater(config.cosine_reference, 0)
        self.assertEqual(
            set(config.weights),
            {
                "bullet_entity",
                "note_entity",
                "bullet_cosine",
                "note_cosine",
                "anchor",
                "tier",
            },
        )
        self.assertLess(config.weights["tier"], config.weights["bullet_entity"])
        self.assertLess(
            config.thresholds["operator"]["uncertain"],
            config.thresholds["operator"]["confident"],
        )


if __name__ == "__main__":
    unittest.main()
