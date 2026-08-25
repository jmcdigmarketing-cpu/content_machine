"""Candidate 34: in-repo vault note templates that actually parse.

Hand-written vault notes were the one path into the fact store with no stamping help,
so they arrived without `tier`/`verified_at`. A note missing `tier` falls to the default
vault tier (below `link` and `web`), and one missing `verified_at` loses freshness
ranking — silently, because the parser is deliberately forgiving.

Templates that only live in prose drift from the parser. These tests read the shipped
files through the real reader (`core.vault_index._parse_frontmatter`) and check the
values against the real tier constants, so a contract change breaks here rather than in
the operator's vault.
"""

import pathlib
import unittest

from core.fact_store import TIER_WEIGHTS
from core.vault_index import _parse_frontmatter

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "docs" / "vault_templates"


class TestTemplatesExist(unittest.TestCase):
    def test_the_three_templates_ship(self):
        names = {p.name for p in TEMPLATES.glob("*.md")}
        self.assertEqual(names, {"_operator_facts.md", "_strategy.md", "_sources.md"})


class TestTemplatesParse(unittest.TestCase):
    def _meta(self, name: str) -> dict:
        meta, body = _parse_frontmatter((TEMPLATES / name).read_text(encoding="utf-8"))
        self.assertTrue(meta, f"{name}: frontmatter did not parse")
        self.assertTrue(body.strip(), f"{name}: no body")
        return meta

    def test_every_template_declares_a_known_tier(self):
        for name in ("_operator_facts.md", "_strategy.md", "_sources.md"):
            tier = self._meta(name).get("tier")
            self.assertIn(tier, TIER_WEIGHTS, f"{name} declares unknown tier {tier!r}")

    def test_fact_templates_carry_verified_at(self):
        # The two that feed the grounding corpus must date themselves; strategy is a
        # playbook note and is deliberately exempt.
        for name in ("_operator_facts.md", "_sources.md"):
            self.assertIn("verified_at", self._meta(name), name)

    def test_operator_template_is_the_operator_tier(self):
        self.assertEqual(self._meta("_operator_facts.md").get("tier"), "operator")

    def test_sources_template_is_the_link_tier_and_has_a_url(self):
        # This used to assert `"source_url" in meta` — that a KEY was present. It was
        # green while the template was broken: `note_metadata` reads `source:`, so a
        # note copied from the template produced source_url="" and silently lost its
        # provenance (and could never reach the description Sources block). Assert what
        # the parser actually extracts, not what the frontmatter happens to spell.
        from pathlib import PurePosixPath

        from core.fact_store import note_metadata

        meta = self._meta("_sources.md")
        self.assertEqual(meta.get("tier"), "link")
        tier, _verified, _expires, source_url = note_metadata(
            meta, PurePosixPath("tapin/_sources/example.md")
        )
        self.assertEqual(tier, "link")
        self.assertTrue(
            source_url.startswith("http"),
            f"template's source key did not survive note_metadata: {source_url!r}",
        )

    def test_strategy_template_is_tagged_strategy(self):
        from core.obsidian_facts import _tag_set

        self.assertIn("strategy", _tag_set(self._meta("_strategy.md")))

    def test_channel_scoping_is_present(self):
        for name in ("_operator_facts.md", "_strategy.md", "_sources.md"):
            self.assertIn("channel", self._meta(name), name)


class TestTemplatesAreObviouslyPlaceholders(unittest.TestCase):
    """A template copied without edits must not read as a real fact."""

    def test_bullets_say_replace(self):
        for name in ("_operator_facts.md", "_strategy.md", "_sources.md"):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            bullets = [ln for ln in text.splitlines() if ln.startswith("- ")]
            self.assertTrue(bullets, name)
            self.assertTrue(all("REPLACE" in b for b in bullets), f"{name}: {bullets}")

    def test_no_smart_punctuation(self):
        # cp1252 consoles and the ASCII-safe dump rule (candidate 250).
        for p in TEMPLATES.glob("*.md"):
            bad = [c for c in p.read_text(encoding="utf-8") if ord(c) > 127]
            self.assertEqual(bad, [], f"{p.name} has non-ASCII: {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
