"""Next 15 after Stage 3: #608 #669 #633 #632 #638 #554 #557 #593 #581
#448 #623 #447 #672 #683 #341.

Fail-then-fix on HEAD 0e1c73e. Do not mock the unit under test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestDeferGoogleAndEspn(unittest.TestCase):
    def test_youtube_api_imports_without_discovery(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys, types\n"
            "sys.modules['googleapiclient'] = types.ModuleType('googleapiclient')\n"
            "sys.modules.pop('googleapiclient.discovery', None)\n"
            "sys.modules.pop('apis.youtube_api', None)\n"
            "import apis.youtube_api as y\n"
            "assert hasattr(y, '_get_youtube_client')\n"
            "print('ok')\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(root),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok", proc.stdout)

    def test_live_scores_imports_without_sports_espn(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys, types\n"
            "sys.modules['sports'] = types.ModuleType('sports')\n"
            "sys.modules.pop('sports.espn', None)\n"
            "sys.modules.pop('apis.live_scores_api', None)\n"
            "import apis.live_scores_api as live\n"
            "assert hasattr(live, 'get_live_scores_signal')\n"
            "print('ok')\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(root),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok", proc.stdout)


class TestIntroOffsetFromConfig(unittest.TestCase):
    def test_tapin_offset_is_not_a_hardcoded_only_constant(self):
        from video.intro_waveform import intro_offset_seconds

        self.assertAlmostEqual(intro_offset_seconds("tapin"), 2.15, places=2)
        money = intro_offset_seconds("moneywise")
        self.assertGreaterEqual(money, 0.0)
        self.assertNotEqual(money, intro_offset_seconds("tapin"))


class TestOpsVerbsNamedInDocsExist(unittest.TestCase):
    def test_backticked_ops_verbs_are_registered(self):
        from core.ops_doc_verbs import verbs_named_in_docs
        from scripts.ops import COMMANDS

        named = verbs_named_in_docs()
        self.assertIn("review-room", named)
        missing = sorted(v for v in named if v not in COMMANDS)
        self.assertEqual(missing, [], f"docs name ops verbs that do not exist: {missing}")


class TestSizeTagsOnOpenItems(unittest.TestCase):
    def test_numbered_open_items_carry_a_size_tag(self):
        from core.backlog_index import untagged_open_items

        leftover = untagged_open_items()
        self.assertEqual(leftover, [], f"untagged open items: {leftover[:12]}")


class TestSteamKeyIsRead(unittest.TestCase):
    def test_steam_signal_sends_the_env_key(self):
        from apis.steam_api import steam_search_url

        with patch.dict(os.environ, {"STEAM_API_KEY": "steam-test-key"}, clear=False):
            url = steam_search_url("GTA 6")
        self.assertIn("steam-test-key", url)
        self.assertIn("storesearch", url)

    def test_sportsdata_key_is_not_a_dead_env_name(self):
        example = Path(".env.example").read_text(encoding="utf-8")
        sources = Path("config/data_sources.json").read_text(encoding="utf-8")
        self.assertNotIn("SPORTSDATA_API_KEY", example)
        self.assertNotIn("SPORTSDATA_API_KEY", sources)


class TestSingleSourceFactFlag(unittest.TestCase):
    def test_one_host_among_several_is_flagged(self):
        from core.source_diversity import singleton_source_claims

        flags = singleton_source_claims(
            [
                (
                    "Ilia Topuria kept the belt Saturday",
                    ["https://www.espn.com/mma/story/1"],
                ),
                (
                    "The gate was 2.1 million PPV buys",
                    [
                        "https://www.espn.com/mma/story/1",
                        "https://www.mmafighting.com/2026/6/7",
                    ],
                ),
            ]
        )
        joined = " ".join(flags).lower()
        self.assertIn("topuria", joined)
        self.assertNotIn("2.1 million", joined)


class TestFactAgeAtPrompt(unittest.TestCase):
    def test_preview_prints_age_for_a_dated_vault_line(self):
        from datetime import date, timedelta

        from core.fact_store import FactRecord, stamp_as_of
        from core.ui import display_fact_preview

        old = date.today() - timedelta(days=21)
        record = FactRecord(
            claim="Ilia Topuria is the featherweight champion",
            verified_at=old,
        )
        stamped = stamp_as_of(record)
        lines: list[str] = []

        def capture(*a, **_k):
            lines.append(a[0] if a else "")

        display_fact_preview(stamped, print_fn=capture)
        blob = "\n".join(lines).lower()
        self.assertTrue("as of" in blob or "21" in blob or "week" in blob or "month" in blob)


class TestDomainGatingInHealth(unittest.TestCase):
    def test_ufc_topic_names_gated_team_sports(self):
        from core.ui import display_signal_health

        lines: list[str] = []

        def capture(*a, **_k):
            lines.append(a[0] if a else "")

        display_signal_health(
            {"youtube": {"connected": True, "active": True, "status": "ok"}},
            topic="UFC 318 results Saturday",
            channel_id="tapin",
            print_fn=capture,
            ask=False,
        )
        blob = "\n".join(lines).lower()
        self.assertIn("gated", blob)
        self.assertTrue("live_scores" in blob or "odds" in blob)


class TestEdgeFallbackIsVisible(unittest.TestCase):
    def test_alt_tts_failure_sets_a_readable_flag(self):
        from core.tts import last_tts_fell_back_to_paid, mark_tts_paid_fallback

        mark_tts_paid_fallback("edge", "endpoint gone")
        self.assertTrue(last_tts_fell_back_to_paid())
        from core.ui import display_summary

        lines: list[str] = []

        def capture(*a, **_k):
            lines.append(a[0] if a else "")

        display_summary(timings={}, title="t", print_fn=capture)
        self.assertTrue(any("edge" in ln.lower() and "eleven" in ln.lower() for ln in lines))


class TestWhySlow(unittest.TestCase):
    def test_slowest_phase_is_named(self):
        from core.why_slow import why_slow_lines

        lines = why_slow_lines(
            {
                "signals_and_variants": 32.0,
                "script": 4.0,
                "tts": 1.2,
            }
        )
        blob = "\n".join(lines)
        self.assertIn("signals_and_variants", blob)
        self.assertIn("32", blob)


class TestDbSizeInReliability(unittest.TestCase):
    def test_gather_reports_sqlite_bytes(self):
        from core.reliability import gather, render

        data = gather()
        self.assertIn("store", data)
        blob = render(data)
        self.assertRegex(blob.lower(), r"db |sqlite|database")


class TestConfigDiff(unittest.TestCase):
    def test_channels_json_drift_is_reported(self):
        from core.config_diff import channels_fingerprint, diff_against

        current = channels_fingerprint()
        self.assertTrue(current)
        lines = diff_against({"channels_sha256": "deadbeef"})
        self.assertTrue(any("drift" in ln.lower() or "changed" in ln.lower() for ln in lines))
        same = diff_against({"channels_sha256": current})
        self.assertTrue(any("match" in ln.lower() or "same" in ln.lower() for ln in same))


class TestGrainEncodesNoise(unittest.TestCase):
    def test_tapin_filter_raises_pixel_stddev_on_a_flat_frame(self):
        from video.grain_grade import measure_look_noise

        with tempfile.TemporaryDirectory() as tmp:
            result = measure_look_noise(tmp, channel_id="tapin")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreater(result["with_look"], result["plain"])


class TestHudDetector(unittest.TestCase):
    def test_bright_top_bar_is_hud_and_plain_frame_is_not(self):
        from PIL import Image

        from core.hud_detect import detect_hud

        with tempfile.TemporaryDirectory() as tmp:
            hud = Path(tmp) / "hud.png"
            plain = Path(tmp) / "plain.png"
            img = Image.new("RGB", (64, 64), (20, 80, 20))
            for x in range(64):
                for y in range(8):
                    img.putpixel((x, y), (255, x * 4 % 256, 40))
            img.save(hud)
            Image.new("RGB", (64, 64), (20, 80, 20)).save(plain)
            self.assertTrue(detect_hud(str(hud)))
            self.assertFalse(detect_hud(str(plain)))

    def test_assign_skips_detected_hud_clips(self):
        from core.owned_beats import assign_owned_clips
        from video.scene_plan import plan_scenes

        scenes = plan_scenes("Gameplay only please.", "GTA 6 leak", 6.0, max_scenes=1)
        index = {
            "clips": {
                "C:/clips/gta/hud.mp4": {
                    "duration_s": 12.0,
                    "hud": True,
                    "source": "gta",
                },
                "C:/clips/gta/clean.mp4": {
                    "duration_s": 12.0,
                    "hud": False,
                    "source": "gta",
                },
            }
        }
        paths = assign_owned_clips(scenes, index, topic="GTA 6 leak")
        self.assertEqual(paths, ["C:/clips/gta/clean.mp4"])


class TestRetractionWatch(unittest.TestCase):
    def test_changed_body_is_a_hit(self):
        from core.retraction_watch import watch_urls

        def fake_fetch(url: str) -> str:
            if "old" in url:
                return "RETRACTION: the June date was wrong"
            return "unchanged story"

        hits = watch_urls(
            [
                ("https://example.com/old", "the June date is locked"),
                ("https://example.com/ok", "unchanged story"),
            ],
            fetch=fake_fetch,
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("RETRACTION", hits[0])


class TestOpsVerbsRegistered(unittest.TestCase):
    def test_new_verbs_are_live(self):
        from scripts.ops import COMMANDS

        self.assertIn("why-slow", COMMANDS)
        self.assertIn("config-diff", COMMANDS)
        self.assertIn("retraction-watch", COMMANDS)
