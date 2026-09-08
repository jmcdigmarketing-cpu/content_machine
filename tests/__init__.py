"""Test package.

Suite-wide isolation guard: neutralise `OBSIDIAN_VAULT_PATH` and `DATABASE_URL`
before any test imports run.

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
# Same class as vault isolation: dotenv override=False, so blanking before
# config.settings import freezes Settings.database_url empty for the process.
os.environ["DATABASE_URL"] = ""
os.environ["DATABASE_KEY"] = ""
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
os.environ["CROSS_CHANNEL_DUP"] = "off"
os.environ["UFC_PPV_BLACKOUT"] = "false"
os.environ["QUIET_HOURS"] = "false"
os.environ["ODDS_MARKET_VOICE"] = "false"
os.environ["GAMBLING_SAFE"] = "false"
os.environ["DESCRIPTION_SEO_FIRST_LINE"] = "false"
os.environ["CONTENT_TRAY_GRADE"] = "false"
os.environ["CONTENT_TRAY_DOMAIN"] = "false"
os.environ["CONTENT_TRAY_PRESENCE"] = "false"
# Unset = off. An operator .env cap must not abort the suite's discovery tests.
os.environ["PROJECTED_COST_MAX_USD"] = ""
# NVENC encode is opt-in at the ffmpeg argv layer; CI/suite stay on libx264.
os.environ["NVENC"] = "off"
# Operator .env / voices.json piper pool must not make local TTS "ready" in CI.
os.environ["PIPER_VOICE"] = ""
os.environ["PIPER_VOICES"] = ""
os.environ["PIPER_VOICES_DIR"] = ""
# Occasional Piper mix is a production default (1/8); the suite pins ElevenLabs
# unless a test sets TTS_PIPER_MIX_EVERY itself.
os.environ["TTS_PIPER_MIX_EVERY"] = "0"

# Redirect the four operator stores tests/CLAUDE.md forbids writing. Per-test
# patches still nest inside these. Bound names (not only config.paths) must move
# because quota_state / youtube_quota / cache_manager import the paths at
# module load. cache_manager also memoizes _resolved_path on first access.
import atexit
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import config.paths as _paths
from apis import cache_manager as _cache_manager
from apis import youtube_quota as _youtube_quota
from core import negative_facts as _negative_facts
from core import quota_state as _quota_state

_SUITE_DATA_TMP = tempfile.mkdtemp(prefix="cm_suite_data_")
atexit.register(shutil.rmtree, _SUITE_DATA_TMP, True)


def _suite_store(name: str) -> str:
    return os.path.join(_SUITE_DATA_TMP, name)


os.environ["OVERNIGHT_PAUSE_FILE"] = _suite_store("overnight.paused")
os.environ["CONTENT_WINDOW_STATE"] = _suite_store("window_state.json")
os.environ["CONTENT_UI_MASCOT_STAMP"] = _suite_store("mascot_shown_day.txt")


_SUITE_STORE_PATCHES = (
    patch.object(_paths, "QUOTA_STATE_FILE", _suite_store("quota_state.json")),
    patch.object(_paths, "CACHE_STATS_FILE", _suite_store("cache_stats.json")),
    patch.object(_paths, "SIGNAL_CACHE_FILE", _suite_store("signal_cache.json")),
    patch.object(_paths, "YOUTUBE_QUOTA_FILE", _suite_store("youtube_quota.json")),
    patch.object(_paths, "TOPIC_GRAPH_FILE", _suite_store("topic_graph.json")),
    patch.object(_paths, "CLIP_INDEX_FILE", _suite_store("clip_index.json")),
    patch.object(_quota_state, "QUOTA_STATE_FILE", _suite_store("quota_state.json")),
    patch.object(_cache_manager, "SIGNAL_CACHE_FILE", _suite_store("signal_cache.json")),
    patch.object(_youtube_quota, "YOUTUBE_QUOTA_FILE", _suite_store("youtube_quota.json")),
    patch.object(_negative_facts, "STORE_PATH", Path(_suite_store("negative_facts.json"))),
)
for _p in _SUITE_STORE_PATCHES:
    _p.start()
_cache_manager._resolved_path = None
