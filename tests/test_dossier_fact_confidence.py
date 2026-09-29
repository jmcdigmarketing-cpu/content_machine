"""#911: the run dossier says how confident each fact was.

#548 printed a confidence beside vault lines at the key-facts step and ranked the facts
room by it, but nothing was kept: the dossier - where a run is read afterwards - could not
say whether the script leaned on high- or low-confidence facts. `KeyFactSelection` now
carries one `{claim, tier, value, label}` per fact, `run_pipeline` stores it as
`features["fact_confidence"]`, and both the vault dossier's Audit block and
`ops dossier` print one summary line with the weakest fact.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from core.facts.store import FactRecord

RECORDS = [
    FactRecord(claim="Topuria is the champion.", tier="operator"),
    FactRecord(
        claim="Topuria knocked out Holloway in round 3 at UFC 308.",
        tier="link",
        source_url="https://espn.com/a",
    ),
    FactRecord(
        claim="Holloway held the BMF belt.",
        tier="vault",
        relevance_score=0.2,
        verified_at=date.today() - timedelta(days=500),
    ),
]


class SelectionTests(unittest.TestCase):
    def test_one_entry_per_fact(self):
        from core.facts.confidence import selection_confidences

        items = selection_confidences(RECORDS)
        self.assertEqual([i["claim"] for i in items], [r.claim for r in RECORDS])
        self.assertEqual(items[0]["tier"], "operator")
        self.assertEqual(items[0]["label"], "high")
        self.assertEqual(items[2]["label"], "low")
        self.assertTrue(all(0.0 <= i["value"] <= 1.0 for i in items))

    def test_the_selection_carries_them(self):
        from core.ui import KeyFactSelection

        sel = KeyFactSelection(facts=[], source_urls=[], relevance_corpus="", vault_audit=[])
        self.assertEqual(sel.confidences, [])


class SummaryTests(unittest.TestCase):
    def test_the_line(self):
        from core.facts.confidence import confidence_summary, selection_confidences

        line = confidence_summary(selection_confidences(RECORDS))
        self.assertIn("2 high", line)  # operator 1.00, link 0.85
        self.assertIn("1 low", line)
        self.assertIn("lowest", line)
        self.assertIn("Holloway held the BMF belt.", line)

    def test_nothing_recorded_says_nothing(self):
        from core.facts.confidence import confidence_summary

        self.assertIsNone(confidence_summary([]))
        self.assertIsNone(confidence_summary(None))


class DossierTests(unittest.TestCase):
    def test_the_vault_dossier_audit(self):
        from core.facts.confidence import selection_confidences
        from core.vault.dossiers import audit_lines

        lines = audit_lines({"fact_confidence": selection_confidences(RECORDS)}, {})
        self.assertTrue(any(line.startswith("- **Fact confidence:**") for line in lines), lines)
        self.assertFalse(any("Fact confidence" in line for line in audit_lines({}, {})))

    def test_ops_dossier(self):
        import json
        from unittest.mock import patch

        from core.facts.confidence import selection_confidences
        from core.run_ledger import render_dossier
        from storage.repositories.content_runs import ContentRunRecord

        record = ContentRunRecord(
            id=7, channel_id="tapin", input_topic="t", selected_topic="t", status="drafted",
            composite_score=60.0,
            features_json=json.dumps({"fact_confidence": selection_confidences(RECORDS)}),
        )  # fmt: skip

        class _Repo:
            def get(self, run_id):
                return record

        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=_Repo()
        ):
            text = render_dossier(7)
        self.assertIn("Facts   :", text)
        self.assertIn("lowest", text)


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_takes_it(self):
        import inspect

        from core.pipeline import run_pipeline

        self.assertIn("fact_confidence", inspect.signature(run_pipeline).parameters)

    def test_main_passes_it(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("fact_confidence=fact_selection.confidences", text)


if __name__ == "__main__":
    unittest.main()
