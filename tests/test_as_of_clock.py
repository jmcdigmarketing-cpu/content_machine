"""#331: kept facts older than a week are dated, not spoken as present tense.

Stamping happens when vault records become prompt lines. Operator key facts
pasted this run are not dated (they have no verified_at). The finished script
is not regex-rewritten.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from core import vault_index
from core.fact_store import TIER_OPERATOR, TIER_VAULT, FactRecord, stamp_as_of


class TestStampAsOf(unittest.TestCase):
    def test_twenty_day_old_ufc_fact_is_labeled(self):
        rec = FactRecord(
            claim="Islam Makhachev is the lightweight champion",
            tier=TIER_VAULT,
            verified_at=date(2026, 8, 1),
        )
        stamped = stamp_as_of(rec, today=date(2026, 8, 21))
        self.assertIn("as of", stamped.lower())
        self.assertIn("Islam Makhachev is the lightweight champion", stamped)

    def test_fresh_fact_is_not_dated(self):
        rec = FactRecord(
            claim="Islam Makhachev is the lightweight champion",
            tier=TIER_VAULT,
            verified_at=date(2026, 8, 20),
        )
        stamped = stamp_as_of(rec, today=date(2026, 8, 21))
        self.assertNotIn("as of", stamped.lower())
        self.assertEqual(stamped, rec.claim)

    def test_operator_key_fact_without_verified_at_is_not_dated(self):
        rec = FactRecord(
            claim="Giannis was traded to the Heat today",
            tier=TIER_OPERATOR,
            verified_at=None,
        )
        self.assertEqual(stamp_as_of(rec, today=date(2026, 8, 21)), rec.claim)

    def test_load_facts_stamps_old_vault_notes(self):
        from core.obsidian_facts import load_facts

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        vault = Path(tmp.name)
        (vault / "tapin").mkdir()
        verified = (date.today() - timedelta(days=20)).isoformat()
        (vault / "tapin" / "ufc.md").write_text(
            f"---\nchannel: tapin\nverified_at: {verified}\n---\n"
            "# UFC lightweight\n- Islam Makhachev is the lightweight champion\n",
            encoding="utf-8",
        )
        vault_index.clear_cache()
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}):
            facts = load_facts("UFC lightweight", "tapin")
        vault_index.clear_cache()
        self.assertTrue(facts)
        self.assertTrue(any("as of" in f.lower() for f in facts))
        self.assertTrue(any("Makhachev" in f for f in facts))

    def test_interactive_packing_stamps_old_vault_records(self):
        from core.ui import prompt_key_facts_result

        rec = FactRecord(
            claim="Islam Makhachev is the lightweight champion",
            tier=TIER_VAULT,
            verified_at=date.today() - timedelta(days=20),
            relevance_band="confident",
        )
        with (
            patch("core.obsidian_facts.load_fact_records", return_value=[rec]),
            patch("core.operator_facts.capture_facts_to_vault", return_value=None),
        ):
            result = prompt_key_facts_result(
                "UFC lightweight",
                "tapin",
                signals={},
                print_fn=lambda *_a, **_k: None,
                input_fn=lambda *_a, **_k: "",
            )
        self.assertTrue(any("as of" in f.lower() for f in result.facts))
        self.assertTrue(any("Makhachev" in f for f in result.facts))
