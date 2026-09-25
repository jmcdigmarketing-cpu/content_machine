"""Docs standard lint — the doc card, the taxonomy, and the metric-drift rule.

`docs/docs_standard.md` is the prose; this is the enforcement. AGENTS.md is
explicit that a written rule was not enough on its own in this repo, so every
rule below is a check, not a paragraph.

No network, no repo writes. Sibling of `tests/test_docs_lint.py`, which keeps
the older relative-link and roadmap-checkbox checks.
"""

from __future__ import annotations

import datetime as dt
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

CLASSES = {"index", "charter", "reference", "runbook", "plan", "snapshot", "log"}
STATUSES = {"living", "frozen", "archived"}

# The doc card: line 3 of every doc, immediately under the H1 and a blank line.
CARD = re.compile(
    r"^> \*\*Class:\*\* (?P<cls>[a-z]+) · "
    r"\*\*Status:\*\* (?P<status>[a-z]+) · "
    r"\*\*Reviewed:\*\* (?P<reviewed>\d{4}-\d{2}-\d{2})"
    r"(?P<rest>.*)$"
)
SUPERSEDED = re.compile(r"· \*\*Superseded by:\*\* \[[^\]]+\]\(([^)]+)\)")

# snake_case.md, or a dated snapshot snake_case_YYYY-MM.md / snake_case_YYYY-MM-DD.md.
COMPLIANT_NAME = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*(_\d{4}-\d{2}(-\d{2})?)?\.md$")

# Names that predate the standard. This set may only ever SHRINK — each rename
# lands with a redirect stub (the ROADMAP.md precedent). See docs/master_plan.md M1.
LEGACY_NAMES = frozenset(
    {
        "HANDOFF_SYNOPSIS.md",
        "adding-a-data-source.md",
        "analyst-intelligence.md",
        "apify-data-sources.md",
        "data-sources.md",
        "domain-expansion.md",
        "groundwork_2026Q3.md",
        "signals-and-sources.md",
        "startup-powershell.md",
        "strategy_2026H2.md",
    }
)

# A number that changes is either generated or dated: a bare test count may live
# in a frozen snapshot or an append-only log (where it was true on the day), never
# in a doc that claims to be current. Twelve different counts were in flight
# across the corpus when this rule landed (docs/audit_2026-09.md §2).
VOLATILE_METRIC = re.compile(r"\b\d[\d,]{2,}\+? tests\b")


def _docs() -> list[Path]:
    return sorted(DOCS.glob("*.md"))


def _card(md: Path) -> re.Match[str] | None:
    lines = md.read_text(encoding="utf-8").splitlines()
    return CARD.match(lines[2]) if len(lines) >= 3 else None


class TestDocCard(unittest.TestCase):
    def test_every_doc_opens_with_an_h1(self):
        bad = [m.name for m in _docs() if not m.read_text(encoding="utf-8").startswith("# ")]
        self.assertEqual(bad, [], "docs must open with an H1 on line 1")

    def test_every_doc_has_a_doc_card(self):
        bad = [md.name for md in _docs() if _card(md) is None]
        self.assertEqual(bad, [], "line 3 must be the doc card — see docs/docs_standard.md")

    def test_class_and_status_are_in_the_taxonomy(self):
        bad = []
        for md in _docs():
            card = _card(md)
            if card is None:
                continue
            if card["cls"] not in CLASSES or card["status"] not in STATUSES:
                bad.append(f"{md.name}: {card['cls']}/{card['status']}")
        self.assertEqual(bad, [])

    def test_snapshots_and_logs_are_never_living(self):
        # A dated snapshot or an append-only log cannot claim to be kept current.
        bad = []
        for md in _docs():
            card = _card(md)
            if card and card["cls"] in {"snapshot", "log"} and card["status"] == "living":
                bad.append(md.name)
        self.assertEqual(bad, [], "snapshot/log docs are frozen, not living")

    def test_reviewed_date_is_real_and_not_in_the_future(self):
        today = dt.date.today()
        bad = []
        for md in _docs():
            card = _card(md)
            if card is None:
                continue
            try:
                when = dt.date.fromisoformat(card["reviewed"])
            except ValueError:
                bad.append(f"{md.name}: unparseable {card['reviewed']}")
                continue
            if when > today:
                bad.append(f"{md.name}: {when} is in the future")
        self.assertEqual(bad, [])

    def test_archived_docs_name_their_successor(self):
        bad = []
        for md in _docs():
            card = _card(md)
            if card is None or card["status"] != "archived":
                continue
            link = SUPERSEDED.search(card["rest"])
            if link is None:
                bad.append(f"{md.name}: no 'Superseded by' link")
            elif not (md.parent / link.group(1).split("#")[0]).exists():
                bad.append(f"{md.name}: successor {link.group(1)} missing")
        self.assertEqual(bad, [])

    def test_exactly_one_index(self):
        idx = [md.name for md in _docs() if (c := _card(md)) and c["cls"] == "index"]
        self.assertEqual(idx, ["README.md"])


class TestNaming(unittest.TestCase):
    def test_new_docs_are_snake_case(self):
        bad = [
            md.name
            for md in _docs()
            if md.name not in LEGACY_NAMES
            and md.name != "README.md"  # the index keeps the name GitHub renders
            and not COMPLIANT_NAME.match(md.name)
        ]
        self.assertEqual(bad, [], "snake_case.md, or snake_case_YYYY-MM.md for a snapshot")

    def test_the_legacy_name_list_only_shrinks(self):
        present = {md.name for md in _docs()}
        stale = sorted(LEGACY_NAMES - present)
        self.assertEqual(stale, [], "renamed — drop it from LEGACY_NAMES rather than leaving it")


class TestMetricDrift(unittest.TestCase):
    def test_living_docs_do_not_hardcode_a_test_count(self):
        bad = []
        for md in _docs():
            card = _card(md)
            if card is None or card["status"] != "living":
                continue
            for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                if VOLATILE_METRIC.search(line):
                    bad.append(f"{md.name}:{n}")
        self.assertEqual(bad, [], "cite the command, not a count that rots")


class TestIndexCoverage(unittest.TestCase):
    def test_no_orphan_docs(self):
        index = (DOCS / "README.md").read_text(encoding="utf-8")
        missing = [md.name for md in _docs() if md.name != "README.md" and md.name not in index]
        self.assertEqual(missing, [], "every doc is listed in docs/README.md")


if __name__ == "__main__":
    unittest.main()
