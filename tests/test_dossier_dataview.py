"""#136 Dataview keys and #137 wiki-links on run dossiers."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import vault_dossiers, vault_index
from core.vault_index import _parse_frontmatter
from tests.test_vault_pillar4 import VaultCase, _run_record


class TestDossierDataviewAndLinks(VaultCase):
    def test_frontmatter_has_dataview_keys(self):
        record = _run_record(8)
        repo = MagicMock()
        repo.get.return_value = record
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        publish_repo.list_timed_outcomes.return_value = []
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
            patch("core.video_grade.grade_run", return_value=MagicMock(letter="B", score=80)),
        ):
            path = vault_dossiers.write_run_dossier(8)
        self.assertIsNotNone(path)
        meta, _body = _parse_frontmatter(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(meta.get("channel"), "tapin")
        self.assertEqual(str(meta.get("run_id")), "8")
        self.assertEqual(meta.get("grade"), "B")
        self.assertIn(str(meta.get("published")).lower(), {"false", "no", "0"})

    def test_wiki_link_to_previous_same_franchise_run(self):
        first = _run_record(10)
        first.selected_topic = "GTA 6 leak week 1"
        first.input_topic = "GTA 6 leak week 1"
        second = _run_record(11)
        second.selected_topic = "GTA 6 leak week 2"
        second.input_topic = "GTA 6 leak week 2"
        repo = MagicMock()
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = []
        publish_repo.list_timed_outcomes.return_value = []

        def _get(run_id):
            return {10: first, 11: second}[int(run_id)]

        repo.get.side_effect = _get
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            p1 = vault_dossiers.write_run_dossier(10)
            p2 = vault_dossiers.write_run_dossier(11)
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        body = Path(p2).read_text(encoding="utf-8")
        self.assertIn(f"[[{Path(p1).stem}]]", body)
        vault_index.clear_cache()
