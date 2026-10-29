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
import re as _re
import sys as _sys

# #1247 (2026-10-16): a bare `python -m unittest` from the repo root imports `publishing` and
# `storage` before this package; they load `config.settings`, which reads `.env` and freezes
# `Settings.database_url` - the suite then ran against the operator's Postgres (133 fake upload
# rows, real job 59 marked failed). Settings loaded first means nothing below can isolate it.
if "config.settings" in _sys.modules:
    raise ImportError(
        "config.settings was imported before the test package, so it holds the real .env "
        "(DATABASE_URL too). Run `python -m unittest discover -s tests -t .` or name "
        "`tests.` modules - never a bare `python -m unittest` from the repo root."
    )
# storage/db.py refuses a network database while this is set (#1247).
os.environ["CONTENT_SUITE"] = "1"
# #1263: `ops status` asks `gh` for the CI verdict - never from a test.
os.environ["CI_STATUS_LINE"] = "false"

# #930: the operator's .env held real keys (Apify, balldontlie), so seven tests reached the
# network on the PC and nowhere else. The suite skips the project .env and blanks any
# secret-shaped variable already in the process environment: it sees what CI sees.
os.environ["CONTENT_SKIP_DOTENV"] = "1"
# #986: no log file from the suite (data/ stays untouched).
os.environ["CONTENT_LOG_FILE"] = ""
_SECRET_NAME = _re.compile(r"(_KEY|_KEYS|_TOKEN|_SECRET|_PASSWORD|_BOT)$")


def blank_secrets(environ) -> None:
    for name in list(environ):
        if _SECRET_NAME.search(name):
            environ[name] = ""


blank_secrets(os.environ)

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
# #848 auto-research is on by default and fetches web pages; no test may. Tests of
# the feature (tests/test_auto_research.py) set it themselves.
os.environ["AUTO_RESEARCH_ENABLED"] = "false"
# #1018 / #1016: default-on extra LLM passes (the hook rewrite, the does-it-answer-the-idea
# check); a test that wants one turns it on, so no other test's scripted replies shift.
os.environ["HOOK_REGEN_ENABLED"] = "false"
os.environ["KEEP_TO_IDEA"] = "false"
# #1089: an idea no cue word reads gets one model call in discovery; the tests of it turn it on.
os.environ["STANCE_MODEL_READ"] = "false"
# #1050: the title check asks YouTube suggest once per run - never in tests.
os.environ["TITLE_SUGGEST"] = "off"
# #1034: the read-aloud pass makes one cheap call when a sentence is hard to say; a test
# that wants it turns it on, so no other test's scripted replies shift.
os.environ["READ_ALOUD_REWRITE"] = "false"
# #1095: a hope or plan run with no supporting fact makes one stance search; never in tests.
os.environ["STANCE_RESEARCH"] = "false"
# #899: event research reads Wikipedia / Google News on a recency miss - never in tests.
os.environ["EVENT_RESEARCH_ENABLED"] = "false"
# #963: the who's-who lookup reads Wikidata / Wikipedia on every run - never in tests.
os.environ["ENTITY_RESEARCH_ENABLED"] = "false"
# #964: with no web results, auto-research reads Google News headlines - never in tests.
os.environ["AUTO_RESEARCH_NEWS_FALLBACK"] = "false"
# #589: the web-search fallback may reach keyless DuckDuckGo when ddgs is installed;
# the fallback tests turn it on with their own fakes.
os.environ["WEB_SEARCH_FALLBACK"] = "false"
# #876: game names learned from the operator's runs must not change a test's verdict.
os.environ["LEARNED_GAME_NAMES"] = "false"
# Wave 110 (#1301): a preview's call is a model call over this week's headlines.
os.environ["PREVIEW_CALLS"] = "false"
# Wave 111 (#83): no overnight pick is a holdout in a test that does not ask for one.
os.environ["HOLDOUT_EVERY"] = "0"
# Wave 111 (#138): overnight's Monday compilation runs ffmpeg and queues an upload.
os.environ["WEEK_COMPILE"] = "false"
# Wave 132 (#1847): the GTA 6 countdown reads the feeds on its days (10-29 to 11-18).
os.environ["SERIES_COUNTDOWN"] = "false"
# Wave 133 (decision 84): the GTA 6 moments and long videos read the feeds on their dates.
os.environ["SERIES_DATED"] = "false"
# Wave 133 (#1747): no test builds a link with a real Associates tag.
os.environ["AFFILIATE_AMAZON_TAG"] = ""
# Wave 112: the first-line rule refuses openers without a call; its own tests turn it on.
os.environ["FIRST_LINE_RULE"] = "false"
# Wave 112 (#1042): the matchup card reads ESPN; a render test that wants it sets it.
os.environ["MATCHUP_CARD"] = "false"
# #771 turned the whisper aligner on by default; no test may load a model.
os.environ["CAPTION_ALIGN_BACKEND"] = "none"
# #782: fast-cut backgrounds run real ffmpeg on the local clip library; render tests mock one
# ffmpeg call and must keep the single-background path.
os.environ["BACKGROUND_FAST_CUT"] = "false"
# #600: the nightly overnight run looks at 48h-old uploads through the YouTube API.
os.environ["POST_PUBLISH_CHECK"] = "false"
# #938: production ranks on 7-day views; the suite's recommender tests describe the
# engaged-rate arithmetic their fixtures carry. The views mode has its own tests
# (tests/test_wave55_five.py), which set RECOMMEND_TARGET themselves.
os.environ["RECOMMEND_TARGET"] = "engaged"
# Competitor-sync caps default on in production; disable in the suite so a test
# that reads youtube_quota cannot skip API because the operator's real remaining
# units are below the upload reserve.
os.environ["COMPETITOR_SYNC_MAX_UNITS"] = "0"
os.environ["COMPETITOR_SYNC_RESERVE_UNITS"] = "0"
# #392: the suite must not call Apify's status page. A real `ops doctor` leaves this unset.
os.environ["DOCTOR_STATUS_OFF"] = "1"
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
# #921: run_discovery syncs competitor RSS from YouTube by default ("auto"); five
# discovery tests turned it off by hand and one did not. Tests that want it set it.
os.environ["COMPETITOR_SYNC_ON_DISCOVERY"] = "false"
# #1023: best bets read ESPN boards. The suite stubs that fetch; a real run does not.
os.environ["BEST_BET_SCHEDULE"] = "false"
# #400: measured words-per-second must not read or write the operator's voice_pace.json.
os.environ["VOICE_PACE_FILE"] = ""

# Redirect the four operator stores tests/CLAUDE.md forbids writing. Per-test
# patches still nest inside these. Bound names (not only config.paths) must move
# because quota_state / youtube_quota / cache_manager import the paths at
# module load. cache_manager also memoizes _resolved_path on first access.
import atexit
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import config.competitors as _competitors
import config.paths as _paths
from analytics import mailbag as _mailbag
from analytics import reach_report as _reach_report
from analytics import sync_metrics as _sync_metrics
from apis import cache_manager as _cache_manager
from apis import youtube_quota as _youtube_quota
from config import seo as _seo
from core import angle_intent as _angle_intent
from core import channel_health as _channel_health
from core import correction_dossier as _correction_dossier
from core import counterfactual as _counterfactual
from core import incident_ledger as _incident_ledger
from core import moat_backup as _moat_backup
from core import negative_facts as _negative_facts
from core import operator_minutes as _operator_minutes
from core import ops_doctor as _ops_doctor
from core import playlists as _playlists
from core import policy_canary as _policy_canary
from core import quota_state as _quota_state
from core import recommender_history as _recommender_history
from core import retraction_watch as _retraction_watch
from core import run_trace as _run_trace
from core import topic_trajectory as _topic_trajectory
from core import trace_secrets as _trace_secrets
from core import win_notify as _win_notify
from core import ypp_readiness as _ypp_readiness
from core.money import ledger as _spend_ledger
from core.predictions import calls as _preview_calls
from core.predictions import holdouts as _holdouts
from core.runs import signal_skips as _signal_skips
from core.success import goals as _goals
from core.success import review as _review
from core.success import verdicts as _verdicts
from publishing import buffer_api as _buffer_api
from publishing import crosspost as _crosspost
from publishing import platform_metrics as _platform_metrics
from storage.repositories import channel_memory as _channel_memory
from storage.repositories import performance_memory as _performance_memory
from storage.repositories import publish_log as _publish_log
from video import subtitles as _subtitles

_SUITE_DATA_TMP = tempfile.mkdtemp(prefix="cm_suite_data_")
atexit.register(shutil.rmtree, _SUITE_DATA_TMP, True)


def _suite_store(name: str) -> str:
    return os.path.join(_SUITE_DATA_TMP, name)


os.environ["OVERNIGHT_PAUSE_FILE"] = _suite_store("overnight.paused")
os.environ["OVERNIGHT_RECORD_FILE"] = _suite_store("overnight_last.json")  # #1223
# #1078: overnight may render when a channel says so (tapin: 2). Never from a test - a test of
# the render step sets its own limit and stubs the render.
os.environ["OVERNIGHT_RENDERS"] = "0"
# #1152: the shelf limit reads the operator's own finished videos. A test of it sets its own.
os.environ["OVERNIGHT_SHELF_MAX"] = "0"
# #1167 / #1168: never query the operator's scheduled task or set aside their drafts.
os.environ["NIGHTLY_TASK_QUERY"] = "false"
os.environ["OVERNIGHT_BEAT"] = "false"  # #1468: no beat thread from a real cmd_overnight
os.environ["OVERNIGHT_BEAT_FILE"] = _suite_store("overnight_beat.json")
# wave 123 (#1467 / #1465): no real 2-second ffmpeg render and no read of this box's free memory
# before an unattended render. A test of either sets its own.
os.environ["OVERNIGHT_SMOKE"] = "false"
# #1369: live_scores reads each team's ESPN schedule - a request the guard would count. A test of
# it sets its own.
os.environ["ESPN_SEASON_CONTEXT"] = "false"
os.environ["OVERNIGHT_MIN_FREE_GB"] = "0"
os.environ["OVERNIGHT_MIN_DISK_GB"] = "0"
os.environ["OVERNIGHT_EXPIRE_DRAFTS"] = "false"
# #1190: never post to the operator's TikTok or Instagram. A test of the round sets it itself.
os.environ["CROSSPOST_AUTO"] = "false"
# #1193: the startup line check reads a .env; never the operator's.
os.environ["ENV_LINT_FILE"] = _suite_store("env_lint.env")
os.environ["CONTENT_WINDOW_STATE"] = _suite_store("window_state.json")
os.environ["CONTENT_LAUNCH_STATE"] = _suite_store("launch_state.json")
os.environ["CONTENT_UI_MASCOT_STAMP"] = _suite_store("mascot_shown_day.txt")
os.environ["TOPIC_RECALL_FILE"] = _suite_store("last_topics.json")
os.environ["PIN_COMMENT_FILE"] = _suite_store("pin_comments.json")
# #1327: the call comments - never posted, never data/call_comments.json from a test.
os.environ["CALL_COMMENT_FILE"] = _suite_store("call_comments.json")
os.environ["YOUTUBE_CALL_COMMENT"] = "false"
os.environ["PLAYLISTS_AUTO_CREATE"] = "false"  # #1584: the worker never creates one in the suite
# #1284: the worker lock - never data/worker.lock from a test.
os.environ["WORKER_LOCK_FILE"] = _suite_store("worker.lock")


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
    # #1058: the reach sync now records what it found, so it writes even with no sign-in.
    patch.object(_reach_report, "REACH_TEMPLATE", _suite_store("reach_{channel}.json")),
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
    # #892: the measured run wrote these five data/ stores and output/video subtitles.
    patch.object(_operator_minutes, "MINUTES_FILE", _suite_store("operator_minutes.json")),
    patch.object(_incident_ledger, "INCIDENTS_FILE", _suite_store("incidents.json")),
    patch.object(_buffer_api, "REQUESTS_FILE", _suite_store("buffer_requests.json")),
    patch.object(_paths, "RELIABILITY_HISTORY_FILE", _suite_store("reliability_history.json")),
    # #1570: overnight's first hook-rewrite assignment wrote data/experiments.json on 10-24, and
    # three tests then read the operator's arms through core/experiments._load.
    patch.object(_paths, "EXPERIMENTS_FILE", _suite_store("experiments.json")),
    # Wave 115 (#1402): the morning reads the upload worker's last pass.
    patch.object(_paths, "WORKER_TASK_LOG", _suite_store("worker_task.log")),
    # Wave 115 (#1399, #1372): the once-a-day toast stamps.
    patch.object(_win_notify, "TOAST_DAYS_FILE", _suite_store("toast_days.json")),
    patch.object(_competitors, "DATA_DIR", _SUITE_DATA_TMP),
    patch.object(_channel_memory, "MEMORY_DIR", _suite_store("channel_memory")),
    patch.object(_subtitles, "SUBTITLE_DIR", _suite_store("subtitles")),
    # Wave 48: the ledger's post-time claim reads the run's publish-log row (#916); on the
    # operator's PC that was the real data/publish_log.json, as it was for every reader.
    patch.object(_publish_log, "LOG_FILE", _suite_store("publish_log.json")),
    # #927: seeding writes performance memory under a relative data/ path.
    patch.object(_performance_memory, "MEMORY_DIR", _suite_store("performance_memory")),
    patch.object(_performance_memory, "MEMORY_FILE", _suite_store("performance_memory.json")),
    # #574: the operator's approved signal skips.
    patch.object(_signal_skips, "SKIPS_FILE", _suite_store("signal_skips.json")),
    # Wave 54: the goal (a committed file the operator edits), and the stores that track it.
    patch.object(_goals, "GOALS_FILE", _suite_store("goals.json")),
    patch.object(_goals, "CHANNEL_VIEWS_TEMPLATE", _suite_store("channel_views_{channel}.json")),
    patch.object(_goals, "FOCUS_FILE", _suite_store("weekly_focus.json")),
    patch.object(_goals, "HISTORY_TEMPLATE", _suite_store("review_history_{channel}.json")),
    patch.object(_verdicts, "VERDICTS_FILE", _suite_store("verdicts.json")),
    patch.object(_review, "REVIEWS_ROOT", _suite_store("output")),
    patch.object(_mailbag, "MAILBAG_TEMPLATE", _suite_store("mailbag_{channel}.json")),
    # #1305 (wave 111): measured 2026-10-18, 117 tests read these from the operator's data/.
    patch.object(_crosspost, "CROSSPOST_TEMPLATE", _suite_store("crosspost_{channel}.json")),
    patch.object(
        _platform_metrics, "METRICS_TEMPLATE", _suite_store("platform_metrics_{channel}.json")
    ),
    patch.object(_paths, "FEED_HEALTH_FILE", _suite_store("feed_health.json")),
    patch.object(_spend_ledger, "LEDGER_FILE", _suite_store("spend_ledger.json")),
    patch.object(_angle_intent, "PICKS_FILE", Path(_suite_store("angle_picks.json"))),
    patch.object(_playlists, "store_path_for", lambda cid: _suite_store(f"playlists_{cid}.json")),
    patch.object(_ypp_readiness, "YPP_TEMPLATE", _suite_store("ypp_{channel}.json")),
    patch.object(_policy_canary, "SNAPSHOT_FILE", _suite_store("policy_canary.json")),
    patch.object(_topic_trajectory, "_TRAJECTORY_FILE", _suite_store("topic_trajectory.json")),
    patch.object(_seo, "HINTS_DIR", _SUITE_DATA_TMP),
    # #1304: the calls ledger.
    patch.object(_preview_calls, "CALLS_FILE", _suite_store("preview_calls.json")),
    # #83: the holdout count.
    patch.object(_holdouts, "HOLDOUT_FILE", _suite_store("holdouts.json")),
    # Wave 121 (#1475): health keeps one line a day.
    patch.object(
        _channel_health, "HISTORY_TEMPLATE", _suite_store("health_history_{channel}.jsonl")
    ),
    # Wave 112: the doctor's last result.
    patch.object(_ops_doctor, "DOCTOR_LAST_FILE", _suite_store("doctor_last.json")),
    # Wave 113: when the metrics sync last ran (overnight and the worker sync once a day).
    patch.object(_sync_metrics, "SYNC_STAMP_FILE", _suite_store("metrics_synced.json")),
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


# #921: no network in the suite, enforced. Wave 49's CI failure was a test that scraped
# live stats (CI has network; the dev container does not). Every lookup or connection
# that is not loopback raises NetworkBlocked - an OSError, so fail-open code behaves as
# it does offline - and is recorded; the test it happened in is then failed by name,
# whatever the code did with the error. Proxy variables go too: a loopback proxy would
# otherwise carry a request out past a loopback allow-list.
import ipaddress as _ipaddress
import socket as _socket
import threading as _threading

for _proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(_proxy_var, None)


class NetworkBlocked(OSError):
    """A test tried to reach a host that is not this machine."""


_network_attempts: list[str] = []
_network_lock = _threading.Lock()
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", "ip6-localhost"})


def _is_loopback(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    name = str(host).strip().strip("[]").lower()
    if not name or name in _LOOPBACK_NAMES:
        return True
    try:
        addr = _ipaddress.ip_address(name.split("%")[0])
    except ValueError:
        return False
    return addr.is_loopback or addr.is_unspecified


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _caller() -> str:
    """The deepest repo frame (not this guard) that asked - names the fetcher to stub."""
    import traceback as _traceback

    for frame in reversed(_traceback.extract_stack()):
        path = os.path.abspath(frame.filename)
        if path.startswith(_REPO_ROOT) and not path.endswith(os.path.join("tests", "__init__.py")):
            rel = os.path.relpath(path, _REPO_ROOT).replace(os.sep, "/")
            return f"{rel}:{frame.lineno} {frame.name}"
    return "?"


def _blocked(host) -> NetworkBlocked:
    with _network_lock:
        _network_attempts.append(f"{host} via {_caller()} [{_threading.current_thread().name}]")
    return NetworkBlocked(f"network blocked in tests: {host}")


def take_network_attempts() -> list[str]:
    """The hosts tried since the last call, cleared (a test that tries on purpose calls it)."""
    with _network_lock:
        out = list(_network_attempts)
        _network_attempts.clear()
    return out


_real_getaddrinfo = _socket.getaddrinfo
_real_connect = _socket.socket.connect
_real_connect_ex = _socket.socket.connect_ex


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_loopback(host):
        raise _blocked(host)
    return _real_getaddrinfo(host, *args, **kwargs)


def _remote_host(sock, address):
    if sock.family not in (_socket.AF_INET, _socket.AF_INET6):
        return None
    host = address[0] if isinstance(address, tuple) and address else address
    return None if _is_loopback(host) else host


def _guarded_connect(self, address):
    host = _remote_host(self, address)
    if host is not None:
        raise _blocked(host)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    host = _remote_host(self, address)
    if host is not None:
        raise _blocked(host)
    return _real_connect_ex(self, address)


_socket.getaddrinfo = _guarded_getaddrinfo
_socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
_socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]


# #1305 (wave 111): measured 2026-10-18, 117 tests opened files under the operator's real
# data/ - traces, crosspost, platform metrics, the spend ledger - so a verdict could change on
# their PC only. CI has no data/ (the repo tracks nothing there): an open is refused as not found,
# so the suite sees what CI sees, and the test it happened in is failed by name, as #921 does
# for the network. An in-process `ops test --order` switches it off afterwards (suite_order).
_REAL_DATA = os.path.normcase(os.path.join(_REPO_ROOT, "data")) + os.sep
_data_attempts: list[str] = []
DATA_GUARD_ON = True  # core.suite_order turns it off after an in-process run


def _guard_data_open(event, args):
    if event != "open" or not args or not DATA_GUARD_ON:
        return
    path = args[0]
    if isinstance(path, int):
        return
    try:
        full = os.path.normcase(os.path.abspath(os.fsdecode(path)))
    except (TypeError, ValueError):
        return
    if not full.startswith(_REAL_DATA):
        return
    rel = os.path.relpath(full, os.path.normcase(_REPO_ROOT)).replace(os.sep, "/")
    with _network_lock:
        _data_attempts.append(f"{rel} via {_caller()}")
    mode = str(args[1]) if len(args) > 1 and args[1] is not None else "r"
    error = PermissionError if any(c in mode for c in "wax+") else FileNotFoundError
    raise error(f"#1305: the suite may not open the operator's {rel}")


def take_data_attempts() -> list[str]:
    """The data/ opens since the last call, cleared."""
    with _network_lock:
        out = list(_data_attempts)
        _data_attempts.clear()
    return out


_sys_for_audit = __import__("sys")
_sys_for_audit.addaudithook(_guard_data_open)


def _run_with_clean_process_state(self, result=None):
    _process_state.reset_all()
    take_network_attempts()
    take_data_attempts()
    outcome = _original_testcase_run(self, result)
    opened = take_data_attempts()
    if opened and result is not None:
        named = ", ".join(sorted(set(opened))[:5])
        result.addFailure(
            self,
            (
                AssertionError,
                AssertionError(
                    f"#1305: this test opened the operator's data/ ({len(opened)}: {named}). "
                    "Redirect the store in tests/__init__.py - CI has no data/."
                ),
                None,
            ),
        )
    hosts = take_network_attempts()
    if hosts and result is not None:
        named = ", ".join(sorted(set(hosts))[:5])
        result.addFailure(
            self,
            (
                AssertionError,
                AssertionError(
                    f"#921: this test tried to reach the network ({len(hosts)} attempt(s): "
                    f"{named}). Stub the fetch - tests may not depend on the network."
                ),
                None,
            ),
        )
    return outcome


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
