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

    # ------------------------------------------------------------------
    # The four-file split (2026-08-28). roadmap.md had grown to 1,981 lines with
    # 291 open items in one flat section and August's shipped-wave narratives
    # sitting above the actual next work, so nobody read it. Each file now has one
    # job, and these assert the split cannot quietly collapse back.

    def test_roadmap_stays_short_enough_to_read(self):
        """The whole point. If this grows past a screenful or two it has started
        absorbing the inventory again."""
        lines = (DOCS / "roadmap.md").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 200, f"roadmap.md is {len(lines)} lines")

    def test_roadmap_points_at_its_three_siblings(self):
        text = (DOCS / "roadmap.md").read_text(encoding="utf-8")
        for sibling in ("desktop_app.md", "backlog.md", "roadmap_archive.md"):
            self.assertIn(sibling, text)

    def test_the_backlog_holds_the_open_items(self):
        text = (DOCS / "backlog.md").read_text(encoding="utf-8")
        self.assertGreater(text.count("- [ ]"), 200)

    def test_the_archive_holds_no_open_work(self):
        """History is never edited again. An open checkbox in here is work that
        has been filed where nobody will look for it."""
        body = (DOCS / "roadmap_archive.md").read_text(encoding="utf-8")
        stray = [ln.strip()[:70] for ln in body.splitlines() if re.match(r"^\s*- \[ \]", ln)]
        self.assertEqual(stray[:8], [], f"{len(stray)} open item(s) in the archive")

    def test_no_numbered_item_is_open_in_two_files(self):
        """A candidate that lives in two files drifts: one copy gets ticked."""
        seen: dict[str, str] = {}
        clash: list[str] = []
        for name in ("roadmap.md", "backlog.md", "desktop_app.md", "roadmap_archive.md"):
            for ln in (DOCS / name).read_text(encoding="utf-8").splitlines():
                hit = re.match(r"^\s*- \[ \] \*{0,2}(\d+)\.", ln)
                if not hit:
                    continue
                num = hit.group(1)
                if num in seen and seen[num] != name:
                    clash.append(f"#{num} open in {seen[num]} and {name}")
                seen[num] = name
        self.assertEqual(clash[:8], [], "; ".join(clash[:8]))

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


class TestRoadmapIndex(unittest.TestCase):
    """`ops roadmap-index` exists because the hand-written header was measurably
    wrong — "318 open" against a real 317 before the split."""

    def test_counts_match_a_plain_grep(self):
        from core.roadmap_index import counts

        data = counts()
        grepped = 0
        for name in ("roadmap.md", "desktop_app.md", "backlog.md", "roadmap_archive.md"):
            body = (DOCS / name).read_text(encoding="utf-8")
            grepped += sum(1 for ln in body.splitlines() if re.match(r"^\s*- \[ \]", ln))
        self.assertEqual(data["open_total"], grepped)

    def test_render_is_cp1252_safe(self):
        from core.roadmap_index import render

        render().encode("cp1252")

    def test_the_verb_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("roadmap-index", COMMANDS)


if __name__ == "__main__":
    unittest.main()
