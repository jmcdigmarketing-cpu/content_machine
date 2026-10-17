"""Cursor's five after Claude's waves 99-100.

#1221 a neutral headline was made a gaming best bet by its feed.
#1227 the correction scan fetches URL fragments every run.
#1228 a 6.8s fast-cut shot timed out at 120s.
#1043 run 155 cut four untagged Madden clips for a team video.
#1229 a native crash at draft 2 took the rest of the night with it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

DR_FOOD = "TikToker Dr Food walks free months after life sentence for smuggling drugs in sweets"
CHARGERS = "How the 0-4 chargers can turn it around this year"
BOXART = "https://static-cdn.jtvnw.net/ttv-boxart/509672-{widt"
BOXART_BARE = "https://static-cdn.jtvnw.net/ttv-boxart/32"
LASTFM = 'https://www.last.fm/music/Agust+D/_/People"'
ESPN = "https://www.espn.com/nba/story/_/id/123/cavs-beat-magic"


class NeutralHeadlineTests(unittest.TestCase):
    def test_a_neutral_headline_is_not_made_gaming_by_its_feed(self):
        """Overnight 2026-10-16, draft 2. The words name no domain. The feed is gaming."""
        from apis.topic_scorer import infer_topic_domain
        from core.best_bet import _consider_candidate, _domain_for_feed

        self.assertEqual(infer_topic_domain(DR_FOOD), "neutral")
        self.assertEqual(_domain_for_feed("neutral", ["gaming"]), "neutral")
        cand = _consider_candidate(
            DR_FOOD,
            "a gaming feed",
            allowed={"gaming", "ufc", "nba", "nfl"},
            exclude=set(),
            seen_local=set(),
            feed_domains=["gaming"],
        )
        self.assertIsNone(cand)

    def test_a_feed_still_wins_when_the_words_name_another_domain(self):
        """#1208 stays: one domain on the feed beats a headline that names a different one."""
        from core.best_bet import _consider_candidate

        cand = _consider_candidate(
            "Why the Lakers are not a contender yet",
            "MMA Fighting",
            allowed={"gaming", "ufc", "nba", "nfl"},
            exclude=set(),
            seen_local=set(),
            feed_domains=["ufc"],
        )
        self.assertIsNotNone(cand)
        self.assertEqual(cand["domain"], "ufc")


class JunkSourceTests(unittest.TestCase):
    def test_templates_quotes_and_images_are_not_sources(self):
        from core.description_extras import collect_source_urls
        from core.source_diversity import clean_urls

        junk = [
            BOXART,
            BOXART_BARE,
            LASTFM,
            "https://lastfm-img.freetls.fastly.net/i/u/34s/2a96.png",
        ]
        self.assertEqual(collect_source_urls(extra_urls=[*junk, ESPN]), [ESPN])
        self.assertEqual(clean_urls([*junk, ESPN]), [ESPN])

    def test_the_correction_scan_does_not_fetch_them(self):
        from core.correction_dossier import _claims_and_sources

        run = SimpleNamespace(
            features_json=json.dumps(
                {
                    "claim_verification": {"claims": [{"claim": "x", "supported": True}]},
                    "source_urls": [BOXART, BOXART_BARE, LASTFM, ESPN],
                }
            )
        )
        _claims, sources = _claims_and_sources(run)
        self.assertEqual(sources, [ESPN])


class ShotTimeoutTests(unittest.TestCase):
    def test_the_shot_command_does_not_wait_on_stdin(self):
        from assets.fast_cut import build_shot_command

        argv = build_shot_command(r"video\backgrounds\madden_clip.mp4", 1.0, 6.8, "shot.mp4")
        self.assertIn("-nostdin", argv)
        self.assertLess(argv.index("-nostdin"), argv.index("-i"))

    def test_a_6_8s_shot_is_allowed_longer_than_120s(self):
        from assets.fast_cut import shot_timeout

        self.assertGreater(shot_timeout(6.8), 120)
        self.assertLess(shot_timeout(2.0), shot_timeout(6.8))

    def test_a_timeout_retries_once_at_ultrafast_and_names_the_shot(self):
        from assets.fast_cut import _render_shot

        source = os.path.join("video", "backgrounds", "madden_clip.mp4")
        calls: list[list[str]] = []

        def fake_run(cmd, **_kwargs):
            calls.append(list(cmd))
            if "ultrafast" not in cmd:
                raise subprocess.TimeoutExpired(cmd, 120)
            with open(cmd[-1], "wb") as fh:
                fh.write(b"x")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("assets.fast_cut.subprocess.run", side_effect=fake_run),
            self.assertLogs("content_machine.assets.fast_cut", level="WARNING") as logs,
        ):
            dest = os.path.join(tmp, "shot.mp4")
            _render_shot(source, 1.0, 6.8, dest)
        self.assertEqual(len(calls), 2)
        self.assertIn("veryfast", calls[0])
        self.assertIn("ultrafast", calls[1])
        self.assertIn("-nostdin", calls[0])
        self.assertTrue(any("madden_clip.mp4" in line and "6.8" in line for line in logs.output))

    def test_a_shot_that_finishes_is_not_retried(self):
        """The ultrafast retry is only for a shot that did not finish."""
        from assets.fast_cut import _render_shot

        def fake_run(cmd, **_kwargs):
            with open(cmd[-1], "wb") as fh:
                fh.write(b"x")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("assets.fast_cut.subprocess.run", side_effect=fake_run) as run,
        ):
            _render_shot("madden_clip.mp4", 0.0, 3.0, os.path.join(tmp, "shot.mp4"))
        self.assertEqual(run.call_count, 1)
        self.assertIn("veryfast", run.call_args.args[0])
        self.assertNotIn("ultrafast", run.call_args.args[0])


def _library(root: str) -> None:
    folder = os.path.join(root, "gaming", "sports", "Madden 26")
    os.makedirs(folder)
    for name in ("clip0.mp4", "clip1.mp4", "clip2.mp4", "clip3.mp4", "chargers_drive.mp4"):
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(b"x")


class TeamFootageTests(unittest.TestCase):
    def setUp(self):
        from assets import local_provider

        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _library(self.root)
        local_provider.reset_footage_choices()
        self.addCleanup(local_provider.reset_footage_choices)

    def _clips(self, topic: str) -> list[str]:
        from assets import local_provider as lp

        with (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch.object(lp, "_ai_choose_folder", return_value=None),
        ):
            return lp.LocalAssetProvider().candidate_clips(topic, "gaming", "tapin")

    def test_a_chargers_video_cuts_chargers_footage_only(self):
        """Run 155 cut four untagged Madden clips. The file that names the team is the one."""
        names = sorted(os.path.basename(path) for path in self._clips(CHARGERS))
        self.assertEqual(names, ["chargers_drive.mp4"])

    def test_a_topic_with_no_team_keeps_the_untagged_clips(self):
        """NFL draft names the game, not a team, so the Madden folder is still the pool."""
        names = sorted(
            os.path.basename(path) for path in self._clips("NFL draft night shock trade")
        )
        self.assertEqual(
            names, ["chargers_drive.mp4", "clip0.mp4", "clip1.mp4", "clip2.mp4", "clip3.mp4"]
        )

    def test_an_index_tag_counts_when_the_file_name_does_not(self):
        from assets import local_provider as lp
        from assets.clip_tags import clips_for_topic

        gameclip = os.path.join(self.root, "gaming", "sports", "Madden 26", "GameClip.mp4")
        with open(gameclip, "wb") as fh:
            fh.write(b"x")
        index = {
            "clips": {
                gameclip: {
                    "teams": ["Los Angeles Chargers"],
                    "players": ["Justin Herbert"],
                    "game": "Madden 26",
                }
            }
        }
        got = clips_for_topic([gameclip], CHARGERS, index)
        self.assertEqual(got, [gameclip])
        with (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch.object(lp, "_ai_choose_folder", return_value=None),
            patch("assets.clip_tags.load_index", return_value=index),
        ):
            names = sorted(os.path.basename(path) for path in self._clips(CHARGERS))
        self.assertEqual(names, ["GameClip.mp4", "chargers_drive.mp4"])

    def test_ingest_records_the_team_and_the_game(self):
        from assets.clip_ingest import _record_index

        dest = os.path.join(self.root, "gaming", "sports", "Madden 26", "chargers_drive.mp4")
        index = os.path.join(self.root, "clips.json")
        with (
            patch("assets.clip_ingest._probe_duration", return_value=12.0),
            patch("assets.clip_ingest._probe_stream", return_value=(1920, 1080, "h264")),
            patch("assets.clip_ingest._hud_flag", return_value=False),
            patch("assets.clip_ingest._bands", return_value=None),
        ):
            _record_index(dest, dest, index_path=index)
        with open(index, encoding="utf-8") as fh:
            row = json.load(fh)["clips"][dest]
        self.assertIn("Los Angeles Chargers", row["teams"])
        self.assertEqual(row["game"], "Madden 26")


class DraftIsolationTests(unittest.TestCase):
    def test_a_crashed_draft_is_named_and_the_others_go_on(self):
        """2026-10-16: exit 0xC0000374 at draft 2 of 3 took the set-aside and the renders."""
        from core.batch_generation import render_summary
        from core.overnight import draft_each, render_overnight

        topics = ["Larissa Pacheco", DR_FOOD, "Titans at Colts"]
        with patch.dict(
            os.environ,
            {
                "OVERNIGHT_DRAFT_STUB": "1",
                "OVERNIGHT_CRASH_TOPIC": DR_FOOD,
                "OVERNIGHT_CRASH_CODE": "74",
            },
            clear=False,
        ):
            outcomes = draft_each("tapin", topics)
        self.assertEqual([o.topic for o in outcomes], topics)
        self.assertTrue(outcomes[0].ok)
        self.assertFalse(outcomes[1].ok)
        self.assertIn(DR_FOOD, outcomes[1].error)
        self.assertIn("74", outcomes[1].error)
        self.assertTrue(outcomes[2].ok)
        report = render_summary(outcomes)
        self.assertIn(DR_FOOD, report)
        self.assertIn("74", report)

        from core.overnight import OvernightResult, _run_overnight_body

        result = OvernightResult(channel_id="tapin")
        with (
            patch.dict(
                os.environ,
                {
                    "OVERNIGHT_DRAFT_STUB": "1",
                    "OVERNIGHT_CRASH_TOPIC": DR_FOOD,
                    "OVERNIGHT_CRASH_CODE": "74",
                },
                clear=False,
            ),
            patch("core.batch_generation.collect_topics", return_value=topics),
            patch("core.overnight_quota.adjust_count", return_value=(3, "")),
            patch("core.vault.dossiers.write_run_dossier", return_value=None),
            patch("core.batch_review.expire_enabled", return_value=True),
            patch("core.batch_review.expire_old_drafts", return_value=[114]) as expired,
            patch("core.batch_review.unattended_limit", return_value=1),
            patch("core.batch_review.render_unattended", return_value={"rendered": [1]}) as renders,
            patch("core.channel_health.build_health", return_value=SimpleNamespace()),
            patch("core.channel_health.health_line", return_value=""),
            patch("core.events.emit_event", return_value=True),
            patch("core.signal_canary.check_signals", return_value=[]),
            patch("core.signal_canary.save_results"),
            patch("core.correction_dossier.scan_published_for_corrections", return_value=[]),
        ):
            done = _run_overnight_body(
                "tapin", result, count=3, topics=None, file=None, facts_file=None
            )
        expired.assert_called_once()
        renders.assert_called_once()
        text = render_overnight(done)
        self.assertIn(DR_FOOD, text)
        self.assertIn("74", text)

    def test_the_child_passes_facts_into_the_draft(self):
        from core.batch_generation import DraftOutcome
        from core.overnight import _draft_job

        with tempfile.TemporaryDirectory() as tmp:
            job = os.path.join(tmp, "job.json")
            result = os.path.join(tmp, "out.json")
            with open(job, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "channel": "tapin",
                        "topic": "GTA 6 leak",
                        "key_facts": ["Take-Two filed subpoenas."],
                        "pick": None,
                        "result": result,
                    },
                    fh,
                )
            with (
                patch.dict(os.environ, {"OVERNIGHT_DRAFT_STUB": "0"}, clear=False),
                patch(
                    "core.batch_generation.run_batch",
                    return_value=[DraftOutcome(topic="GTA 6 leak", ok=True)],
                ) as batch,
            ):
                code = _draft_job(job)
        self.assertEqual(code, 0)
        self.assertEqual(batch.call_args.kwargs["key_facts"], ["Take-Two filed subpoenas."])
        self.assertEqual(batch.call_args.args[1], ["GTA 6 leak"])
