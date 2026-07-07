"""Pillar 3 (Fact Engine) — structured fact store: tiers, freshness, expiry,
frontmatter parsing, and the provenance-ranked vault read path."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core import obsidian_facts as of
from core.fact_store import (
    TIER_CONTEXT,
    TIER_LINK,
    TIER_OPERATOR,
    TIER_VAULT,
    FactRecord,
    freshness_bonus,
    infer_tier_from_path,
    note_metadata,
    parse_iso_date,
    rank_bonus,
    tier_weight,
)

_TODAY = date(2026, 7, 6)


class TestParseIsoDate(unittest.TestCase):
    def test_plain_date(self):
        self.assertEqual(parse_iso_date("2026-07-01"), date(2026, 7, 1))

    def test_embedded_date(self):
        self.assertEqual(parse_iso_date("verified 2026-07-01 by op"), date(2026, 7, 1))

    def test_garbage_and_empty(self):
        self.assertIsNone(parse_iso_date("not a date"))
        self.assertIsNone(parse_iso_date(""))
        self.assertIsNone(parse_iso_date(None))
        self.assertIsNone(parse_iso_date("2026-13-45"))


class TestTierWeights(unittest.TestCase):
    def test_operator_outranks_everything(self):
        self.assertGreater(tier_weight(TIER_OPERATOR), tier_weight(TIER_LINK))
        self.assertGreater(tier_weight(TIER_LINK), tier_weight("web"))
        self.assertGreater(tier_weight("web"), tier_weight("brief"))

    def test_context_carries_zero_trust(self):
        self.assertEqual(tier_weight(TIER_CONTEXT), 0.0)

    def test_unknown_tier_falls_back_to_vault(self):
        self.assertEqual(tier_weight("nonsense"), tier_weight(TIER_VAULT))


class TestFreshness(unittest.TestCase):
    def test_fresh_fact_gets_max_bonus(self):
        self.assertAlmostEqual(freshness_bonus(_TODAY, today=_TODAY), 0.45)

    def test_bonus_decays_to_zero_past_window(self):
        old = date(2026, 1, 1)  # > 90 days before _TODAY
        self.assertEqual(freshness_bonus(old, today=_TODAY), 0.0)

    def test_undated_is_neutral(self):
        self.assertEqual(freshness_bonus(None, today=_TODAY), 0.0)

    def test_rank_bonus_stays_below_one_overlap_token(self):
        best = rank_bonus(tier=TIER_OPERATOR, verified_at=_TODAY, today=_TODAY)
        self.assertLess(best, 1.0)
        self.assertAlmostEqual(best, 0.95)


class TestFactRecord(unittest.TestCase):
    def test_expiry(self):
        rec = FactRecord(claim="x", expires=date(2026, 7, 5))
        self.assertTrue(rec.is_expired(_TODAY))
        self.assertFalse(FactRecord(claim="x").is_expired(_TODAY))

    def test_age_days(self):
        rec = FactRecord(claim="x", verified_at=date(2026, 7, 1))
        self.assertEqual(rec.age_days(_TODAY), 5)
        self.assertIsNone(FactRecord(claim="x").age_days(_TODAY))

    def test_to_dict_shape(self):
        rec = FactRecord(claim="c", tier=TIER_LINK, verified_at=date(2026, 7, 1))
        d = rec.to_dict()
        self.assertEqual(d["claim"], "c")
        self.assertEqual(d["tier"], "link")
        self.assertEqual(d["verified_at"], "2026-07-01")
        self.assertEqual(d["expires"], "")


class TestNoteMetadata(unittest.TestCase):
    def test_declared_tier_wins(self):
        tier, *_ = note_metadata({"tier": "link"}, Path("tapin/note.md"))
        self.assertEqual(tier, TIER_LINK)

    def test_operator_facts_path_inferred(self):
        self.assertEqual(
            infer_tier_from_path(Path("tapin/_operator_facts/2026-07-06_x.md")), TIER_OPERATOR
        )
        self.assertEqual(infer_tier_from_path(Path("tapin/_sources.md")), TIER_LINK)
        self.assertEqual(infer_tier_from_path(Path("tapin/notes.md")), TIER_VAULT)

    def test_verified_at_falls_back_to_date(self):
        _, verified_at, _, _ = note_metadata({"date": "2026-07-02"}, Path("n.md"))
        self.assertEqual(verified_at, date(2026, 7, 2))

    def test_source_url_only_when_http(self):
        *_, url = note_metadata({"source": "https://espn.com/x"}, Path("n.md"))
        self.assertEqual(url, "https://espn.com/x")
        *_, no_url = note_metadata({"source": "content-machine (operator)"}, Path("n.md"))
        self.assertEqual(no_url, "")


class TestVaultRecordsIntegration(unittest.TestCase):
    """load_fact_records: provenance ranking + expiry through the real reader."""

    def _vault(self, d):
        vault = Path(d)
        (vault / "tapin").mkdir()
        (vault / "tapin" / "_operator_facts").mkdir()
        return vault

    def test_expired_note_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            vault = self._vault(d)
            (vault / "tapin" / "stale.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\nexpires: 2026-06-01\n---\n"
                "# Makhachev\n- Islam Makhachev is the lightweight champion\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                records = of.load_fact_records("Makhachev lightweight title", "tapin", today=_TODAY)
            self.assertEqual(records, [])

    def test_fresh_operator_note_outranks_undated_vault_note(self):
        with tempfile.TemporaryDirectory() as d:
            vault = self._vault(d)
            (vault / "tapin" / "old-note.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Makhachev\n- Makhachev fought at UFC 302 last year\n",
                encoding="utf-8",
            )
            (vault / "tapin" / "_operator_facts" / "2026-07-05_makhachev.md").write_text(
                "---\nchannel: tapin\ntags: [facts, operator, research]\n"
                "date: 2026-07-05\ntier: operator\nverified_at: 2026-07-05\n---\n"
                "# Operator facts — Makhachev\n- Makhachev defended the title at UFC 311\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                records = of.load_fact_records("Makhachev title defense", "tapin", today=_TODAY)
            self.assertGreaterEqual(len(records), 2)
            self.assertEqual(records[0].tier, TIER_OPERATOR)
            self.assertIn("UFC 311", records[0].claim)

    def test_load_facts_strings_match_records(self):
        with tempfile.TemporaryDirectory() as d:
            vault = self._vault(d)
            (vault / "tapin" / "note.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Topuria\n- Topuria is undefeated at 16-0\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                facts = of.load_facts("Topuria record", "tapin")
                records = of.load_fact_records("Topuria record", "tapin")
            self.assertEqual(facts, [r.claim for r in records])

    def test_on_topic_beats_provenance(self):
        # A fresh operator fact with weaker topic overlap must NOT outrank a
        # more on-topic undated note (rank bonus stays under one overlap token).
        with tempfile.TemporaryDirectory() as d:
            vault = self._vault(d)
            (vault / "tapin" / "gaethje.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Gaethje\n- Gaethje knocked out Topuria in round two at UFC 350\n",
                encoding="utf-8",
            )
            (vault / "tapin" / "_operator_facts" / "2026-07-06_other.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\nverified_at: 2026-07-06\n---\n"
                "# Operator facts — other\n- Topuria signed a new contract for next year\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                records = of.load_fact_records(
                    "Gaethje Topuria UFC 350 knockout", "tapin", today=_TODAY
                )
            self.assertGreaterEqual(len(records), 2)
            self.assertIn("Gaethje", records[0].claim)  # 2-token overlap wins
            self.assertEqual(records[1].tier, TIER_OPERATOR)


class TestWriterFrontmatter(unittest.TestCase):
    def test_operator_capture_stamps_tier_and_verified_at(self):
        from core.operator_facts import capture_facts_to_vault

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tapin").mkdir()
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                path = capture_facts_to_vault("tapin", "topic", ["A fact"], today=date(2026, 7, 6))
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("tier: operator", text)
            self.assertIn("verified_at: 2026-07-06", text)

    def test_source_capture_header_stamps_link_tier(self):
        from core.source_capture import capture_sources

        with tempfile.TemporaryDirectory() as d:
            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                path = capture_sources("tapin", "topic", [{"url": "https://a.com", "title": "A"}])
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("tier: link", text)


if __name__ == "__main__":
    unittest.main()
