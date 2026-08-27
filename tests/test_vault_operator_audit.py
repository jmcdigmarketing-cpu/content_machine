"""Operator-facing vault relevance decisions must be usable and persisted."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.fact_store import FactRecord


class TestStructuredFactSelection(unittest.TestCase):
    def test_signal_and_manual_facts_form_the_non_circular_corpus(self):
        from core.ui import prompt_key_facts_result

        inputs = iter(["Microsoft received the subpoena.", "", "n"])
        record = FactRecord(
            claim="Wolverine Rage is trending.",
            source_url="https://example.com/wolverine",
            uncertain=True,
            relevance_score=0.45,
            relevance_band="uncertain",
            relevance_breakdown={"bullet_cosine": 0.1},
            relevance_scorer_version="vault_relevance_v1",
        )
        signals = {
            "news": {
                "connected": True,
                "active": True,
                "data": {
                    "headlines": [
                        {"title": "Rockstar asks Microsoft for records", "source": "wire"}
                    ]
                },
            }
        }
        with (
            patch("core.obsidian_facts.load_fact_records", return_value=[record]) as loader,
            patch("core.operator_facts.capture_facts_to_vault", return_value=None),
        ):
            result = prompt_key_facts_result(
                "GTA 6 leak",
                "tapin",
                signals=signals,
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: next(inputs),
            )
        corpus = loader.call_args.kwargs["corpus"]
        self.assertIn("Rockstar asks Microsoft for records", corpus)
        self.assertIn("Microsoft received the subpoena.", corpus)
        self.assertNotIn(record.claim, corpus)
        self.assertEqual(result.facts, ["Microsoft received the subpoena."])
        self.assertEqual(result.source_urls, [])
        self.assertEqual(result.vault_audit[0]["operator_override"], "rejected")

    def test_selected_source_url_and_score_are_carried_forward(self):
        from core.ui import prompt_key_facts_result

        inputs = iter([""])
        record = FactRecord(
            claim="Rockstar confirmed the investigation.",
            source_url="https://example.com/rockstar",
            relevance_score=0.82,
            relevance_band="confident",
            relevance_breakdown={"bullet_cosine": 0.31},
            relevance_scorer_version="vault_relevance_v1",
        )
        with patch("core.obsidian_facts.load_fact_records", return_value=[record]):
            result = prompt_key_facts_result(
                "GTA 6 leak",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: next(inputs),
            )
        self.assertIn(record.claim, result.facts)
        self.assertEqual(result.source_urls, ["https://example.com/rockstar"])
        self.assertEqual(result.vault_audit[0]["score"], 0.82)
        self.assertEqual(result.vault_audit[0]["operator_override"], "auto")

    def test_uncertain_pick_uses_the_printed_index(self):
        """Typing '2' must mean the line numbered 2, not uncertain-record #2."""
        from core.ui import prompt_key_facts_result

        outputs: list[str] = []
        inputs = iter(["", "2"])
        records = [
            FactRecord(
                claim="Rockstar Games confirms the leak investigation is ongoing.",
                relevance_score=0.82,
                relevance_band="confident",
            ),
            FactRecord(
                claim="Wolverine Rage is trending after the summer of hate trailer.",
                uncertain=True,
                relevance_score=0.45,
                relevance_band="uncertain",
            ),
        ]
        with patch("core.obsidian_facts.load_fact_records", return_value=records):
            result = prompt_key_facts_result(
                "GTA 6 leak",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(inputs),
            )
        numbered = [line for line in outputs if "Wolverine Rage" in line]
        self.assertTrue(any(line.strip().startswith("2.") for line in numbered), numbered)
        self.assertIn(records[0].claim, result.facts)
        self.assertIn(records[1].claim, result.facts)

    def test_n_drops_all_uncertain_and_keeps_confident(self):
        """Typing n on the uncertain prompt must drop those rows, not the list."""
        from core.ui import prompt_key_facts_result

        inputs = iter(["", "n"])
        records = [
            FactRecord(
                claim="Rockstar Games confirms the leak investigation is ongoing.",
                relevance_score=0.82,
                relevance_band="confident",
            ),
            FactRecord(
                claim="Wolverine Rage is trending after the summer of hate trailer.",
                uncertain=True,
                relevance_score=0.45,
                relevance_band="uncertain",
            ),
        ]
        with patch("core.obsidian_facts.load_fact_records", return_value=records):
            result = prompt_key_facts_result(
                "GTA 6 leak",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: next(inputs),
            )
        self.assertIn(records[0].claim, result.facts)
        self.assertNotIn(records[1].claim, result.facts)
        self.assertEqual(result.vault_audit[1]["operator_override"], "rejected")

    def test_near_threshold_reject_is_shown_and_not_attached(self):
        from core.ui import prompt_key_facts_result

        outputs: list[str] = []
        inputs = iter([""])
        records = [
            FactRecord(
                claim="Rockstar Games confirms the leak investigation is ongoing.",
                relevance_score=0.82,
                relevance_band="confident",
            ),
            FactRecord(
                claim="SEGA announced a new Sonic racing title for next spring.",
                relevance_score=0.24,
                relevance_band="reject",
            ),
        ]
        with patch("core.obsidian_facts.load_fact_records", return_value=records):
            result = prompt_key_facts_result(
                "GTA 6 leak",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(inputs),
            )
        self.assertTrue(any("SEGA announced" in line for line in outputs))
        self.assertIn("not attached", "\n".join(outputs).lower())
        self.assertIn(records[0].claim, result.facts)
        self.assertNotIn(records[1].claim, result.facts)

    def test_audit_keeps_pre_and_post_tiebreak(self):
        from core.ui import prompt_key_facts_result

        record = FactRecord(
            claim="The subpoena demands account IDs and last-login IP addresses.",
            relevance_score=0.45,
            relevance_band="confident",
            relevance_pre_tiebreak_band="uncertain",
            relevance_tiebreak_status="ok",
            relevance_scorer_version="vault_relevance_v1",
        )
        with patch("core.obsidian_facts.load_fact_records", return_value=[record]):
            result = prompt_key_facts_result(
                "GTA 6 leak",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: "",
            )
        row = result.vault_audit[0]
        self.assertEqual(row["band"], "confident")
        self.assertEqual(row["pre_tiebreak_band"], "uncertain")
        self.assertEqual(row["tiebreak_status"], "ok")

    def test_run_features_keep_the_full_vault_decision(self):
        from core.run_features import build_features

        audit = [
            {
                "claim": "Rockstar confirmed it.",
                "pre_score_verdict": "legacy_uncertain",
                "band": "confident",
                "score": 0.82,
                "breakdown": {"bullet_entity": 0.3},
                "operator_override": "auto",
            }
        ]
        features = build_features(
            topic="GTA 6 leak",
            channel_id="tapin",
            content_package={},
            vault_relevance_audit=audit,
        )
        self.assertEqual(features["vault_relevance"], audit)


if __name__ == "__main__":
    unittest.main()
