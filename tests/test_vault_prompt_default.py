"""#887: Enter at the vault review prompt takes the confident lines, not every line.

With `VAULT_FACTS_AUTO=false` the vault matches are listed and the operator is asked
"Use these? [Enter=all / n=none]". Enter took every line that was not an inspect-reject,
so the uncertain ones came too - the lines #878 made opt-in on the automatic path after
six of them (Gane / Pereira, Topuria) wrote run 99's false title. Both paths now agree:
confident lines on Enter, uncertain ones only by number or `a`.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.fact_store import FactRecord

CONFIDENT = "Contender Series week 2 handed out five contracts."
UNCERTAIN = "Gane stops Pereira at UFC Oklahoma City."


class VaultReviewPromptTests(unittest.TestCase):
    def _run(self, answer: str):
        from core.ui import prompt_key_facts_result

        inputs = iter(["", answer])
        prompts: list[str] = []
        records = [
            FactRecord(claim=CONFIDENT, relevance_score=0.82, relevance_band="confident"),
            FactRecord(
                claim=UNCERTAIN, uncertain=True, relevance_score=0.45, relevance_band="uncertain"
            ),
        ]

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            return next(inputs)

        with (
            patch.dict(os.environ, {"VAULT_FACTS_AUTO": "false"}),
            patch("core.obsidian_facts.load_fact_records", return_value=records),
        ):
            result = prompt_key_facts_result(
                "UFC week 2",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: None,
                input_fn=fake_input,
            )
        return result, prompts

    def test_enter_takes_the_confident_line_only(self):
        result, _ = self._run("")
        self.assertIn(CONFIDENT, result.facts)
        self.assertNotIn(UNCERTAIN, result.facts)

    def test_enter_records_the_uncertain_line_as_rejected(self):
        result, _ = self._run("")
        overrides = {row["claim"]: row["operator_override"] for row in result.vault_audit}
        self.assertEqual(overrides.get(CONFIDENT), "accepted")
        self.assertEqual(overrides.get(UNCERTAIN), "rejected")

    def test_a_takes_both(self):
        result, _ = self._run("a")
        self.assertIn(CONFIDENT, result.facts)
        self.assertIn(UNCERTAIN, result.facts)

    def test_a_number_picks_the_uncertain_line(self):
        result, _ = self._run("2")
        self.assertEqual([f for f in result.facts if f in (CONFIDENT, UNCERTAIN)], [UNCERTAIN])

    def test_n_takes_none(self):
        result, _ = self._run("n")
        self.assertNotIn(CONFIDENT, result.facts)
        self.assertNotIn(UNCERTAIN, result.facts)

    def test_the_prompt_says_what_enter_does(self):
        _, prompts = self._run("")
        review = [p for p in prompts if "Use these?" in p]
        self.assertEqual(len(review), 1)
        self.assertIn("Enter=confident", review[0])

    def test_the_parser(self):
        from core.ui import parse_vault_review_choice

        self.assertEqual(parse_vault_review_choice(""), "confident")
        self.assertEqual(parse_vault_review_choice("y"), "confident")
        self.assertEqual(parse_vault_review_choice("a"), "all")
        self.assertEqual(parse_vault_review_choice("all"), "all")
        self.assertEqual(parse_vault_review_choice("n"), "none")
        self.assertEqual(parse_vault_review_choice("1, 3"), [1, 3])


if __name__ == "__main__":
    unittest.main()
