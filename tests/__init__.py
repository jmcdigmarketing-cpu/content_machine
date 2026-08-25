"""Test package.

Suite-wide isolation guard: neutralise `OBSIDIAN_VAULT_PATH` before any test
imports run.

`core.obsidian_facts` / `core.operator_facts` read the vault path from the
environment, and `.env` is loaded for real runs, so any test that exercised the
key-facts capture path wrote notes into the operator's ACTUAL Obsidian vault. It
had been doing so for weeks -- 17 stray `<date>_topic.md` notes holding test
fixtures ("A"/"C", "Fact one"/"Fact two") accumulated there, and they then fed
back into live runs as "facts".

Tests that genuinely exercise vault behaviour set the variable themselves via
`patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(tmp)})`, which still works
-- this only removes the ambient real-vault default. Same rule as the
`data/`-store isolation described in tests/CLAUDE.md.
"""

import os

# Loaded only when tests are imported as the `tests` package. That happens for
# `python -m unittest tests.test_*`, pytest, and `unittest discover -s tests -t .`.
# Bare `discover -s tests` (no `-t .`) never imports this file — see tests/CLAUDE.md.

os.environ["OBSIDIAN_VAULT_PATH"] = ""
# TTS cache writes under data/tts_cache when on; isolate the suite (tests that
# exercise the cache patch TTS_CACHE / TTS_CACHE_DIR themselves).
os.environ["TTS_CACHE"] = "false"
# Competitor-sync caps default on in production; disable in the suite so a test
# that reads youtube_quota cannot skip API because the operator's real remaining
# units are below the upload reserve.
os.environ["COMPETITOR_SYNC_MAX_UNITS"] = "0"
os.environ["COMPETITOR_SYNC_RESERVE_UNITS"] = "0"
# C9: do not open googleapis HTTPS (discovery warmup / unclosed SSLSocket).
os.environ["CONTENT_SKIP_YOUTUBE_WARMUP"] = "1"
os.environ["CONTENT_FORBID_LIVE_YOUTUBE"] = "1"
# Operator .env can leave analytics sync on; never hit youtubeanalytics from tests.
os.environ["YOUTUBE_ANALYTICS_SYNC"] = "false"
# Opt-in governors that would abort the suite or read the operator's quota file.
os.environ["DISK_MIN_FREE_GB"] = "0"
os.environ["OVERNIGHT_QUOTA_GATE"] = "false"
os.environ["LUFS_NORMALIZE"] = "false"
os.environ["CLIP_MEMORY"] = "false"
os.environ["POLICY_CANARY_FETCH"] = "false"
os.environ["CONTENT_TOAST"] = "false"
os.environ["CONTENT_HTML_OPEN"] = "false"
os.environ["YOUTUBE_UNLISTED_REVIEW"] = "false"
os.environ["RAM_MIN_GB"] = "0"
os.environ["VRAM_MIN_GB"] = "0"
os.environ["TITLE_UNIQUENESS"] = "off"
os.environ["UFC_PPV_BLACKOUT"] = "false"
os.environ["QUIET_HOURS"] = "false"
os.environ["ODDS_MARKET_VOICE"] = "false"
os.environ["GAMBLING_SAFE"] = "false"
os.environ["DESCRIPTION_SEO_FIRST_LINE"] = "false"
os.environ["CONTENT_TRAY_GRADE"] = "false"
os.environ["CONTENT_TRAY_DOMAIN"] = "false"

# Redirect the four operator stores tests/CLAUDE.md forbids writing. Per-test
# patches still nest inside these. Bound names (not only config.paths) must move
# because quota_state / youtube_quota / cache_manager import the paths at
# module load. cache_manager also memoizes _resolved_path on first access.
import atexit
import shutil
import tempfile
from unittest.mock import patch

import config.paths as _paths
from apis import cache_manager as _cache_manager
from apis import youtube_quota as _youtube_quota
from core import quota_state as _quota_state

_SUITE_DATA_TMP = tempfile.mkdtemp(prefix="cm_suite_data_")
atexit.register(shutil.rmtree, _SUITE_DATA_TMP, True)


def _suite_store(name: str) -> str:
    return os.path.join(_SUITE_DATA_TMP, name)


_SUITE_STORE_PATCHES = (
    patch.object(_paths, "QUOTA_STATE_FILE", _suite_store("quota_state.json")),
    patch.object(_paths, "CACHE_STATS_FILE", _suite_store("cache_stats.json")),
    patch.object(_paths, "SIGNAL_CACHE_FILE", _suite_store("signal_cache.json")),
    patch.object(_paths, "YOUTUBE_QUOTA_FILE", _suite_store("youtube_quota.json")),
    patch.object(_quota_state, "QUOTA_STATE_FILE", _suite_store("quota_state.json")),
    patch.object(_cache_manager, "SIGNAL_CACHE_FILE", _suite_store("signal_cache.json")),
    patch.object(_youtube_quota, "YOUTUBE_QUOTA_FILE", _suite_store("youtube_quota.json")),
)
for _p in _SUITE_STORE_PATCHES:
    _p.start()
_cache_manager._resolved_path = None
