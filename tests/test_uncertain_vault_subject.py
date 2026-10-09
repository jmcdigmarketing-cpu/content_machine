"""#1017: an uncertain vault fact must name what the topic names.

Run 124 ("How the 0-4 chargers can turn it around this year") offered eight uncertain vault
facts and none was about the Chargers: "Never done this before? Read Start here.", Marvel
Rivals Season 9, NetEase, France vs England, MMA flyweights, an AI-jobs story, Braves
biweekly. Each scored "bullet entity +0.30" - the feature asks whether the bullet's
capitalised words appear anywhere in the corpus (every signal plus the pasted article), and
"Start" (the article's "Nightmare Start"), "Season", "England" all did. The operator: "lets be
smart and realize why they were uncertain, shouldn't be excusable when there isnt even any
topic similarity."

`core.obsidian_facts.load_fact_records` (operator policy) now keeps an uncertain fact only
when the bullet or its note names the topic's subject - a name from
`core.facts.entity_lookup.names_for(topic, angle)` (or a team's nickname), else a
distinctive topic word when the topic names nobody. Confident facts are unchanged. The
count dropped is reported back to the vault scan line.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.vault.relevance import VaultRelevanceDecision

TOPIC = "How the 0-4 chargers can turn it around this year"

NOTES = {
    "marvel_rivals.md": ("# Marvel Rivals Season 9", [
        "While new heroes always grab the headlines, arguably the biggest change in Season 9 is one players will feel every match.",
        "As you can see, NetEase hasn't just introduced a new hero and a new map.",
    ]),
    "start.md": ("# Guide", ["Never done this before? Read Start here."]),
    "braves.md": ("# Braves biweekly", ["Braves biweekly: awful - Yahoo Sports"]),
    "chargers.md": ("# Chargers 2026", [
        "Justin Herbert has thrown six interceptions through four games.",
    ]),
    "afc_west.md": ("# AFC West", [
        "The Chargers have allowed 12 sacks, most in the AFC West.",
    ]),
}  # fmt: skip


def _uncertain(**_kwargs):
    return VaultRelevanceDecision(
        score=0.55, band="uncertain", scorer_version="t", policy="operator", breakdown={}
    )


def _load(topic=TOPIC, *, report=None, decision=_uncertain, **kw):
    from core.obsidian_facts import load_fact_records

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "vault" / "tapin"
        root.mkdir(parents=True)
        for name, (heading, bullets) in NOTES.items():
            body = "\n".join(f"- {b}" for b in bullets)
            (root / name).write_text(
                f"---\nchannel: tapin\ntags: [facts]\n---\n{heading}\n{body}\n", encoding="utf-8"
            )
        with (
            patch.dict(
                os.environ,
                {"OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"), "VAULT_RELEVANCE_MODE": "scored"},
            ),
            patch("core.vault.relevance.score_vault_fact", side_effect=decision),
            patch("core.vault.relevance.maybe_tiebreak_uncertain", side_effect=lambda d, **k: d),
        ):
            return load_fact_records(
                topic, "tapin", corpus="Chargers Start Season England Braves NetEase",
                require_distinctive=True, report=report, **kw,
            )  # fmt: skip


class UncertainSubjectTests(unittest.TestCase):
    def test_run_124_keeps_only_the_chargers(self):
        report: dict = {}
        claims = [r.claim for r in _load(report=report)]
        self.assertTrue(any("Herbert" in c for c in claims), claims)
        self.assertTrue(any("12 sacks" in c for c in claims), claims)
        for unrelated in ("Season 9", "NetEase", "Start here", "Braves"):
            self.assertFalse(any(unrelated in c for c in claims), unrelated)
        self.assertEqual(report.get("uncertain_off_subject"), 4)

    def test_a_note_about_the_subject_carries_its_bullets(self):
        # "Justin Herbert ..." names no Chargers, but the note is "Chargers 2026" - and a
        # player of the team is the subject too.
        claims = [r.claim for r in _load()]
        self.assertTrue(any("six interceptions" in c for c in claims))

    def test_confident_facts_are_not_gated(self):
        def confident(**_kwargs):
            return VaultRelevanceDecision(
                score=0.8, band="confident", scorer_version="t", policy="operator", breakdown={}
            )

        claims = [r.claim for r in _load(decision=confident)]
        self.assertTrue(any("Braves" in c for c in claims))

    def test_a_topic_with_no_names_falls_back_to_its_words(self):
        claims = [r.claim for r in _load("why sacks pile up behind a rookie line")]
        self.assertTrue(any("12 sacks" in c for c in claims), claims)
        self.assertFalse(any("NetEase" in c for c in claims))

    def test_the_vault_scan_line_says_so(self):
        from core.ui import format_vault_scan_line

        line = format_vault_scan_line(confident=0, uncertain=2, off_subject=4)
        self.assertIn("4", line)
        self.assertIn("nothing the topic names", line)


if __name__ == "__main__":
    unittest.main()
