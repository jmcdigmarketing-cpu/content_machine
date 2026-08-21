"""Tripwire: the suite must not be pointed at the operator's real data/ stores.

`python -m unittest discover -s tests` (no ``-t .``) never imports this package's
``__init__.py``, so the suite-wide redirect never starts. CI and CLAUDE.md use
``-t .``; this test fails loudly if someone drops it.
"""

from __future__ import annotations

import os
import unittest

import config.paths
from apis import cache_manager, youtube_quota
from core import quota_state


def _under_data_dir(path: str) -> bool:
    data = os.path.normcase(os.path.abspath(config.paths.DATA_DIR))
    target = os.path.normcase(os.path.abspath(path))
    return target == data or target.startswith(data + os.sep)


class TestSuiteStoreIsolation(unittest.TestCase):
    def test_quota_state_file_is_not_under_data(self):
        self.assertFalse(
            _under_data_dir(quota_state.QUOTA_STATE_FILE), quota_state.QUOTA_STATE_FILE
        )

    def test_youtube_quota_file_is_not_under_data(self):
        self.assertFalse(
            _under_data_dir(youtube_quota.YOUTUBE_QUOTA_FILE), youtube_quota.YOUTUBE_QUOTA_FILE
        )

    def test_cache_stats_file_is_not_under_data(self):
        self.assertFalse(
            _under_data_dir(config.paths.CACHE_STATS_FILE), config.paths.CACHE_STATS_FILE
        )

    def test_signal_cache_file_is_not_under_data(self):
        self.assertFalse(
            _under_data_dir(cache_manager.SIGNAL_CACHE_FILE), cache_manager.SIGNAL_CACHE_FILE
        )
