"""Expert Panel: second original persona, persist evidence, default off, no extra warning."""

from __future__ import annotations

import logging
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.grade import _load_personas, expert_panel_review
from core.providers import ProviderResult


class TestSecondPersona(unittest.TestCase):
    def test_two_original_personas_ship(self):
        personas = dict(_load_personas())
        self.assertIn("skeptical_editor", personas)
        self.assertIn("shorts_pacing", personas)
        self.assertGreater(len(personas["shorts_pacing"]), 80)
        self.assertNotIn("ai-marketing-skills", personas["shorts_pacing"].lower())

    def test_default_off_is_silent(self):
        with (
            patch.dict(os.environ, {}, clear=False),
            self.assertNoLogs("content_machine.core.grade", level=logging.WARNING),
        ):
            os.environ.pop("EXPERT_PANEL_ENABLED", None)
            result = expert_panel_review("Hook line. Body.")
        self.assertFalse(result.ok)


class TestPanelPersistence(unittest.TestCase):
    def test_persist_writes_panel_onto_quality(self):
        from core.grade import persist_expert_panel

        reviews = [{"persona": "skeptical_editor", "review": "SCORE: 70"}]
        repo = MagicMock()
        record = MagicMock(quality_json="{}")
        repo.get.return_value = record
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=repo,
        ):
            persist_expert_panel(12, reviews)
        repo.update.assert_called_once()
        payload = repo.update.call_args.args[1]["quality_json"]
        self.assertIn("expert_panel", payload)
        self.assertIn("skeptical_editor", payload)

    def test_ops_grade_shows_persisted_panel_when_enabled(self):
        from core.video_grade import expert_panel_for_run

        record = MagicMock()
        record.script_preview = "Hook. Body."
        record.channel_id = "tapin"
        record.quality_json = (
            '{"expert_panel": [{"persona": "shorts_pacing", "review": "SCORE: 80"}]}'
        )
        with (
            patch.dict(os.environ, {"EXPERT_PANEL_ENABLED": "true"}, clear=False),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=MagicMock(get=MagicMock(return_value=record)),
            ),
        ):
            section = expert_panel_for_run(12)
        self.assertIn("shorts_pacing", section)
        self.assertIn("SCORE: 80", section)


if __name__ == "__main__":
    unittest.main()
