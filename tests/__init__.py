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
# #827 survey: config/settings.py loads .env without override, so an operator box
# with Ollama configured could make a real localhost probe from any test that uses
# clear=False. Tests that exercise Ollama set these themselves via patch.dict.
os.environ["OLLAMA_MODEL"] = ""
os.environ["OLLAMA_BASE_URL"] = ""
# Same class as vault isolation: dotenv override=False, so blanking before
# config.settings import freezes Settings.database_url empty for the process.
os.environ["DATABASE_URL"] = ""
os.environ["DATABASE_KEY"] = ""
# TTS cache writes under data/tts_cache when on; isolate the suite (tests that
# exercise the cache patch TTS_CACHE / TTS_CACHE_DIR themselves).
os.environ["TTS_CACHE"] = "false"
# #828 (found by `ops test --order reverse`): run_discovery stores its result in the
# signal cache, which is file-backed and shared by every test in the process. Two
# tests that discover the same topic string read each other's variants. Off for the
# suite; tests/test_discovery_persist.py turns it on for itself.
os.environ["DISCOVERY_CACHE"] = "false"
# #771 turned the whisper aligner on by default; no test may load a model.
os.environ["CAPTION_ALIGN_BACKEND"] = "none"
# #782: fast-cut backgrounds run real ffmpeg on the local clip library; render tests mock one
# ffmpeg call and must keep the single-background path.
os.environ["BACKGROUND_FAST_CUT"] = "false"
# #600: the nightly overnight run looks at 48h-old uploads through the YouTube API.
os.environ["POST_PUBLISH_CHECK"] = "false"
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
# Wave 14 wired a cheap-tier LLM judge into run_discovery; the discovery tests made
# real `complete()` calls with the operator's .env keys. Tests that want it set it.
os.environ["ANGLE_LLM_JUDGE"] = "false"

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
from core import correction_dossier as _correction_dossier
from core import counterfactual as _counterfactual
from core import moat_backup as _moat_backup
from core import negative_facts as _negative_facts
from core import quota_state as _quota_state
from core import recommender_history as _recommender_history
from core import retraction_watch as _retraction_watch
from core import run_trace as _run_trace
from core import trace_secrets as _trace_secrets

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
    # CI run 34781351080: a test listed the operator's real data/traces, found run 72
    # and passed locally; the runner had no traces and failed. Reads count too.
    patch.object(_paths, "TRACES_DIR", _suite_store("traces")),
    patch.object(_run_trace, "TRACES_DIR", _suite_store("traces")),
    patch.object(_trace_secrets, "TRACES_DIR", _suite_store("traces")),
    patch.object(_moat_backup, "TRACES_DIR", _suite_store("traces")),
    patch.object(_quota_state, "QUOTA_STATE_FILE", _suite_store("quota_state.json")),
    patch.object(_cache_manager, "SIGNAL_CACHE_FILE", _suite_store("signal_cache.json")),
    patch.object(_youtube_quota, "YOUTUBE_QUOTA_FILE", _suite_store("youtube_quota.json")),
    patch.object(_negative_facts, "STORE_PATH", Path(_suite_store("negative_facts.json"))),
    patch.object(_counterfactual, "STORE_PATH", Path(_suite_store("counterfactual.json"))),
    patch.object(_retraction_watch, "STAMP_PATH", _suite_store("retraction_toast.json")),
    patch.object(
        _correction_dossier,
        "STAMP_PATH_TEMPLATE",
        _suite_store("correction_scan_{channel}.json"),
    ),
    patch.object(
        _recommender_history,
        "STAMP_PATH_TEMPLATE",
        _suite_store("recommend_pick_{channel}.json"),
    ),
)
for _p in _SUITE_STORE_PATCHES:
    _p.start()
_cache_manager._resolved_path = None

# #827: one reset point for process-global state, run before EVERY test. A module
# that caches a probe result, a client, a token or a session breaker at module level
# registers its reset with core.process_state at import; this hook calls them all, so
# what one test cached cannot decide what the next one sees. Before this,
# tests/test_run69_fixes.py passed 13/13 alone and failed 5 under discovery because
# tests/test_run66_fixes.py had left `(False, [])` in llm_router._ollama_probe_cache.
import unittest as _unittest

from core import process_state as _process_state

_original_testcase_run = _unittest.TestCase.run


def _run_with_clean_process_state(self, result=None):
    _process_state.reset_all()
    return _original_testcase_run(self, result)


_unittest.TestCase.run = _run_with_clean_process_state  # type: ignore[method-assign]

# #829: on a partial install the suite used to report ~90 import errors across ~470
# tests, and a real failure could not be told from a missing wheel. One line, once,
# naming what is missing; CI installs everything so it never prints there.
import importlib.util as _ilu
import sys as _sys

_OPTIONAL_RUNTIME_MODULES = (
    "sqlalchemy",
    "bs4",
    "googleapiclient",
    "elevenlabs",
    "PIL",
    "numpy",
    "yt_dlp",
    "goose3",
)
_missing = [m for m in _OPTIONAL_RUNTIME_MODULES if _ilu.find_spec(m) is None]
if _missing:
    print(
        f"tests: {len(_missing)} runtime module(s) not installed — {', '.join(_missing)}. "
        "Import errors below are that, not defects: pip install -e .",
        file=_sys.stderr,
    )
