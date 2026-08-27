"""Suite isolation: DATABASE_URL must not reach the operator's Postgres."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from storage.repositories.content_runs import get_content_run_repository


class TestDatabaseUrlIsolation(unittest.TestCase):
    def test_poison_database_url_does_not_open_postgres(self):
        with (
            patch.dict(
                os.environ,
                {"DATABASE_URL": "postgresql://operator.example.invalid/content_os"},
                clear=False,
            ),
            patch("storage.db.create_engine") as engine,
        ):
            repo = get_content_run_repository()
            repo.list_for_channel("tapin")
        engine.assert_not_called()
        self.assertIsNone(getattr(repo, "_pg", "missing"))
