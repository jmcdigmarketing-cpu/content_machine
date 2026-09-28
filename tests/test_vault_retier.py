"""#857: old `_operator_facts` notes that hold scraped page lines, listed and moved on request.

Until run 98 the key-facts prompt saved pasted-link lines as operator facts: a
`Source: <page title>` line, then the page's paragraphs. Wave 33 (#845) sends new ones
to `_link_facts/` and stopped vault lines pinning, but the old notes still sit at
operator tier and still surface as suggestions. `ops vault-retier` lists them; only
`--apply` moves anything - it is the operator's vault.
"""

from __future__ import annotations

import argparse
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

SCRAPED = """---
channel: tapin
tags: [facts, operator, research]
topic: marvel rivals season 4
date: 2026-09-12
tier: operator
verified_at: 2026-09-12
source: content-machine (operator key facts)
---

# Operator facts — marvel rivals season 4

- Source: Marvel Rivals Season 4 patch notes | NetEase
- Blade joins the roster as a Duelist with a lifesteal passive.
- Sign up for our newsletter to get the latest patch notes.
"""

TYPED = """---
channel: tapin
tags: [facts, operator, research]
topic: ufc 320
date: 2026-09-14
tier: operator
---

- Ankalaev defends the light heavyweight title against Pereira.
- The card is in Las Vegas.
"""


class RetierCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        self._env = patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(self.vault)})
        self._env.start()
        ops = self.vault / "tapin" / "_operator_facts"
        ops.mkdir(parents=True)
        self.scraped = ops / "2026-09-12_marvel-rivals-season-4.md"
        self.scraped.write_text(SCRAPED, encoding="utf-8")
        self.typed = ops / "2026-09-14_ufc-320.md"
        self.typed.write_text(TYPED, encoding="utf-8")
        self.target = self.vault / "tapin" / "_link_facts" / self.scraped.name

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()


class PlanTests(RetierCase):
    def test_a_scraped_note_is_listed_and_a_typed_one_is_not(self):
        from core.vault.retier import plan_retier

        plans = plan_retier("tapin")
        self.assertEqual([Path(p.rel_path).name for p in plans], [self.scraped.name])
        self.assertEqual((plans[0].scraped, plans[0].total), (2, 3))
        self.assertTrue(plans[0].samples[0].startswith("Source:"))

    def test_the_line_rule(self):
        from core.vault.retier import scraped_line

        self.assertTrue(scraped_line("Source: Some page title"))
        self.assertTrue(scraped_line('Source video: "UFC 320 preview" by MMA Junkie'))
        self.assertTrue(scraped_line("Subscribe to the newsletter for more"))
        self.assertFalse(scraped_line("Ankalaev defends the title against Pereira."))

    def test_another_channel_is_not_listed(self):
        from core.vault.retier import plan_retier

        self.assertEqual(plan_retier("moneywise"), [])


class ApplyTests(RetierCase):
    def test_apply_moves_the_note_to_link_tier(self):
        from core.fact_store import note_metadata
        from core.vault.index import _parse_frontmatter
        from core.vault.retier import apply_retier, plan_retier

        results = apply_retier(plan_retier("tapin"), today=date(2026, 9, 27))
        self.assertEqual([r["status"] for r in results], ["moved"])
        self.assertFalse(self.scraped.exists())
        self.assertTrue(self.typed.exists())
        text = self.target.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        tier, *_ = note_metadata(meta, self.target.relative_to(self.vault))
        self.assertEqual(tier, "link")
        self.assertIn("link", meta["tags"])
        self.assertNotIn("operator", meta["tags"])
        self.assertEqual(meta["retiered"], "2026-09-27 from _operator_facts")
        self.assertIn("Blade joins the roster", body)

    def test_an_existing_target_is_never_overwritten(self):
        from core.vault.retier import apply_retier, plan_retier

        self.target.parent.mkdir(parents=True)
        self.target.write_text("already here", encoding="utf-8")
        results = apply_retier(plan_retier("tapin"))
        self.assertEqual([r["status"] for r in results], ["exists"])
        self.assertTrue(self.scraped.exists())
        self.assertEqual(self.target.read_text(encoding="utf-8"), "already here")


class OpsVerbTests(RetierCase):
    def _ops(self, apply: bool) -> str:
        from scripts import ops

        out = io.StringIO()
        with redirect_stdout(out):
            code = ops.COMMANDS["vault-retier"][1](argparse.Namespace(channel="tapin", apply=apply))
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_the_default_is_a_dry_run(self):
        text = self._ops(apply=False)
        self.assertIn(self.scraped.name, text)
        self.assertIn("2 of 3", text)
        self.assertIn("--apply", text)
        self.assertTrue(self.scraped.exists())
        self.assertFalse(self.target.exists())

    def test_apply_moves_and_says_how_to_undo(self):
        text = self._ops(apply=True)
        self.assertTrue(self.target.exists())
        self.assertIn("moved", text)
        self.assertIn("undo", text.lower())

    def test_no_vault_says_so(self):
        with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": ""}):
            text = self._ops(apply=False)
        self.assertIn("OBSIDIAN_VAULT_PATH", text)


if __name__ == "__main__":
    unittest.main()
