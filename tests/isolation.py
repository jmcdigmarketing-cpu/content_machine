"""Shared store isolation so a test cannot poison data/quota_state.json."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from core import quota_state


class IsolatedQuotaStore:
    """Patch quota_state.QUOTA_STATE_FILE onto a temp file for the test."""

    quota_state_file: str

    def setUp(self) -> None:
        super().setUp()
        self._iso_tmp = tempfile.TemporaryDirectory()
        self.quota_state_file = os.path.join(self._iso_tmp.name, "q.json")
        self._iso_patch = patch.object(quota_state, "QUOTA_STATE_FILE", self.quota_state_file)
        self._iso_patch.start()

    def tearDown(self) -> None:
        self._iso_patch.stop()
        self._iso_tmp.cleanup()
        super().tearDown()
