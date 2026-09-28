"""#862: auto-research lines can be kept in the vault, at link tier, when asked.

Auto-research (#848) reads the search result pages for the chosen angle and keeps the
on-topic lines for that run only. `AUTO_RESEARCH_SAVE=true` writes them to the vault's
`_link_facts/` - never `_operator_facts/`, since nobody reviewed them - under their own
file name: `capture_facts_to_vault` names a note `{day}_{slug}.md`, so an auto-research
note for the same topic on the same day would have replaced the operator's pasted-link
note. Off by default.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from apis.signal_contract import make_signal

TOPIC = "Manchester City found guilty"
DAY = date(2026, 9, 27)
REPORT = {
    "pages": 2,
    "lines": 2,
    "off_topic": 1,
    "urls": ["https://news.example.com/city-verdict"],
    "kept_lines": [
        "Manchester City were found guilty of 114 of the 115 Premier League charges.",
        "A separate commission will decide City's sanctions.",
    ],
    "reason": "ok",
}


class VaultCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        self._env = patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(self.vault)})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def notes(self, folder: str) -> list[Path]:
        return sorted((self.vault / "tapin" / folder).glob("*.md"))


class SaveKeptLinesTests(VaultCase):
    def test_lines_land_in_link_facts_at_link_tier(self):
        from core.auto_research import save_kept_lines

        path = save_kept_lines("tapin", TOPIC, dict(REPORT), today=DAY)
        self.assertIsNotNone(path)
        [note] = self.notes("_link_facts")
        self.assertEqual(str(note), path)
        self.assertTrue(note.name.endswith("-auto-research.md"), note.name)
        text = note.read_text(encoding="utf-8")
        self.assertIn("tier: link", text)
        self.assertIn("auto-research", text)
        self.assertIn("114 of the 115", text)
        self.assertIn("pages: https://news.example.com/city-verdict", text)
        self.assertEqual(self.notes("_operator_facts"), [])

    def test_the_page_urls_are_not_fact_bullets(self):
        """Every bullet in a note is a fact candidate, so the URLs go in frontmatter."""
        from core.auto_research import save_kept_lines
        from core.vault.index import iter_notes

        save_kept_lines("tapin", TOPIC, dict(REPORT), today=DAY)
        [note] = [n for n in iter_notes(self.vault) if "_link_facts" in str(n.rel_path)]
        self.assertEqual(list(note.bullets), REPORT["kept_lines"])
        self.assertIn("city-verdict", note.meta.get("pages", ""))

    def test_a_pasted_link_note_the_same_day_survives(self):
        from core.auto_research import save_kept_lines
        from core.operator_facts import capture_facts_to_vault

        pasted = capture_facts_to_vault(
            "tapin", TOPIC, ["The operator pasted this line."], today=DAY, tier="link"
        )
        save_kept_lines("tapin", TOPIC, dict(REPORT), today=DAY)
        self.assertEqual(len(self.notes("_link_facts")), 2)
        self.assertIn("The operator pasted this line.", Path(pasted).read_text(encoding="utf-8"))

    def test_nothing_kept_writes_nothing(self):
        from core.auto_research import save_kept_lines

        self.assertIsNone(save_kept_lines("tapin", TOPIC, {"kept_lines": []}, today=DAY))
        self.assertEqual(self.notes("_link_facts"), [])

    def test_the_existing_writer_is_unchanged(self):
        from core.operator_facts import capture_facts_to_vault

        path = capture_facts_to_vault("tapin", TOPIC, ["A typed fact."], today=DAY)
        self.assertEqual(Path(path).name, "2026-09-27_manchester-city-found-guilty.md")


class PipelineSaveTests(VaultCase):
    def _run(self, flag: str):
        from core.pipeline import DiscoveryResult, run_pipeline

        signals = {"web_search": make_signal(connected=True, active=True, score=50)}
        discovery = DiscoveryResult(
            input_topic=TOPIC,
            base_signals=signals,
            evaluated=[(TOPIC, 90.0, signals)],
            channel_id="tapin",
        )
        with (
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=42),
            patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
            patch("core.pipeline.generate_content_package") as content,
            patch(
                "core.pipeline.attach_web_research",
                side_effect=lambda s, **k: (dict(s), dict(REPORT)),
            ),
            patch.dict(os.environ, {"AUTO_RESEARCH_ENABLED": "true", "AUTO_RESEARCH_SAVE": flag}),
        ):
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
            return run_pipeline(
                TOPIC, discovery=discovery, variant_index=0, proceed_video=False, channel_id="tapin"
            )

    def test_off_by_default_writes_nothing(self):
        result = self._run("false")
        self.assertEqual(self.notes("_link_facts"), [])
        self.assertNotIn("saved_to", result.features["auto_research"])

    def test_on_saves_and_records_where(self):
        result = self._run("true")
        [note] = self.notes("_link_facts")
        self.assertEqual(result.features["auto_research"]["saved_to"], str(note))

    def test_the_run_summary_says_where(self):
        from core.auto_research import report_lines

        lines = report_lines({**REPORT, "saved_to": "vault/tapin/_link_facts/x.md"})
        self.assertTrue(any("saved to vault" in line for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
