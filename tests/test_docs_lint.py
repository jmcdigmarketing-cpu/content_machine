"""Docs metric lint (morning candidate) — relative links, shipped boxes, tests exist.

No network. Does not rewrite historical July docs.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


class TestDocsLint(unittest.TestCase):
    def test_test_package_has_many_modules(self):
        files = list((ROOT / "tests").glob("test_*.py"))
        self.assertGreaterEqual(len(files), 80)

    def test_roadmap_has_shipped_and_open_checkboxes(self):
        text = (DOCS / "roadmap.md").read_text(encoding="utf-8")
        self.assertGreater(text.count("- [x]"), 40)
        self.assertGreater(text.count("- [ ]"), 20)

    def test_docs_relative_links_resolve(self):
        missing: list[str] = []
        for md in sorted(DOCS.glob("*.md")):
            body = md.read_text(encoding="utf-8")
            for match in re.finditer(r"\]\(([^)]+)\)", body):
                href = match.group(1).strip().split()[0].split("#")[0]
                if not href or href.startswith(("http://", "https://", "mailto:")):
                    continue
                target = (md.parent / href).resolve()
                if not target.exists():
                    missing.append(f"{md.name} -> {href}")
        self.assertEqual(missing[:12], [], msg="; ".join(missing[:12]))


if __name__ == "__main__":
    unittest.main()
