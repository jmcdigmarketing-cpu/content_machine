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
