"""Wave 108 (2026-10-18): measured defects, and the overnight task that could not wake the PC.

- #1267: goose3's "Publish date 5d could not be resolved to UTC" was a WARNING on a healthy
  overnight - the article's date is never used, only its body.
- #1264: the teaser's ffmpeg read the console (no `-nostdin`, no timeout) and its 5 s were the
  2.15 s channel intro.
- #1288: the YouTube quota day was the Central date; YouTube resets at midnight Pacific. The
  00:03 uploads of 2026-10-18 (4,800 units of Pacific Oct 17) were booked to Oct 18, so the
  morning said 3 uploads left where YouTube allowed 6.
- #1287: hook learning read `run.script`, which a content run does not have (`script_preview`),
  so 0 of 41 videos with a stayed share were ever joined. Decision 67 (the operator): it learns
  from the last 90 days, and a learned note against the rewrite's fixed rules waits until n
  settles.
- #1289 (the operator: "i turned on allow wake timers and it still isnt working"): the task's
  own WakeToRun was never set - `schedule-drafts --wake` only printed the line.
- #1268: run 157's caption band was rgb(136,130,131), 3.8:1 against white; the band now darkens
  until the lightest sampled background reaches 4.5:1.
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---- 1. #1267: goose3's date warning ----------------------------------------------------------


class ParserWarningTests(unittest.TestCase):
    def test_goose3s_unread_publish_date_is_not_a_warning(self):
        from core import link_facts

        link_facts._goose3_body_lines("https://example.com/a", "<html><body></body></html>")
        level = logging.getLogger("goose3.crawler").getEffectiveLevel()
        self.assertGreaterEqual(level, logging.ERROR)


# ---- 2. #1264: the teaser ------------------------------------------------------------------------


class TeaserTests(unittest.TestCase):
    def test_it_reads_no_console_and_starts_after_the_intro(self):
        from video.teaser import teaser_argv

        argv = teaser_argv("in.mp4", "out.mp4", seconds=5.0, start=2.15)
        self.assertIn("-nostdin", argv)
        self.assertLess(argv.index("-ss"), argv.index("-i"))  # input seek
        self.assertEqual(argv[argv.index("-ss") + 1], "2.150")
        self.assertEqual(argv[argv.index("-t") + 1], "5.000")

    def test_ffmpeg_gets_no_stdin_and_a_timeout(self):
        from video import teaser

        with tempfile.TemporaryDirectory() as tmp:
            src, out = os.path.join(tmp, "v.mp4"), os.path.join(tmp, "t.mp4")
            open(src, "wb").close()

            def fake(argv, **kwargs):
                open(out, "wb").close()
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(teaser.subprocess, "run", side_effect=fake) as run:
                teaser.create_teaser(src, out, start=2.15)
        self.assertIs(run.call_args.kwargs.get("stdin"), subprocess.DEVNULL)
        self.assertTrue(run.call_args.kwargs.get("timeout"))

    def test_ops_teaser_starts_after_the_channel_intro(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "run157.mp4")
            open(mp4, "wb").close()
            run = SimpleNamespace(id=157, channel_id="tapin", mp4_path=mp4)
            repo = MagicMock()
            repo.get.return_value = run
            with (
                patch("storage.repositories.content_runs.get_content_run_repository",
                      return_value=repo),
                patch("scripts.probe_sync.intro_offset_seconds", return_value=2.15),
                patch("video.teaser.create_teaser", return_value="t.mp4") as make,
                redirect_stdout(io.StringIO()),
            ):  # fmt: skip
                code = COMMANDS["teaser"][1](Namespace(run_id=157))
        self.assertEqual(code, 0)
        self.assertEqual(make.call_args.kwargs.get("start"), 2.15)


# ---- 3. #1288: the quota day is YouTube's ----------------------------------------------------------


class QuotaDayTests(unittest.TestCase):
    def test_the_day_is_the_pacific_date(self):
        from apis.youtube_quota import quota_day

        self.assertEqual(quota_day("2026-10-18T05:03:00Z"), "2026-10-17")  # 00:03 CDT
        self.assertEqual(quota_day("2026-10-18T07:01:00Z"), "2026-10-18")  # 02:01 CDT, reset

    def test_an_upload_after_local_midnight_counts_against_the_pacific_day(self):
        from apis import youtube_quota

        moment = datetime(2026, 10, 18, 5, 3, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "youtube_quota.json")
            with (
                patch.object(youtube_quota, "_quota_path", return_value=path),
                patch.object(youtube_quota, "_now", return_value=moment),
            ):
                youtube_quota.record_upload_usage()
                summary = youtube_quota.get_usage_summary()
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(list(data), ["2026-10-17"])
        self.assertEqual(summary["day"], "2026-10-17")
        self.assertEqual(summary["used"], 1600)


# ---- 4. #1287: hook learning reads the stored script ----------------------------------------------

NOW = datetime(2026, 10, 18, 13, 0, tzinfo=timezone.utc)
HOOKS = [
    ("Six UFC contracts in one night and two losers got signed.", 0.52),
    ("15 million test players, but can it survive launch day?", 0.50),
    ("Salkilld jumps to 10 after one win - is the system broken?", 0.42),
    ("Topuria fights Gaethje at UFC Freedom 250.", 0.34),
    ("The Hood is not a tank in Marvel Rivals anymore.", 0.30),
    ("Jets and Patriots meet in London on Sunday.", 0.26),
    ("Wembanyama at +200 for MVP this season.", 0.25),
    ("GTA VI ships a code in a box for 79.99.", 0.21),
    ("Arsenal paid 105 million for one midfielder.", 0.18),
    ("The Heat won 11 of 12 preseason games.", 0.12),
]


def _hook_repos(hooks, *, made):
    uploads, runs = [], {}
    for i, (hook, stayed) in enumerate(hooks):
        uploads.append(SimpleNamespace(
            id=i, content_run_id=700 + i, youtube_video_id=f"v{i}", detail=f"Video {i}",
            published_at="2026-10-01T18:00:00+00:00",
            metrics_json=json.dumps({"views": 900, "stayed_share": stayed})))  # fmt: skip
        # The real ContentRun: `script_preview`, no `script` (storage/models.py).
        runs[700 + i] = SimpleNamespace(id=700 + i, script_preview=f"{hook} Then the rest.",
                                        created_at=made(i), quality_json="{}")  # fmt: skip
    return (
        patch("analytics.hook_learning._publish_repo",
              return_value=SimpleNamespace(list_uploaded_for_channel=lambda c: uploads)),
        patch("analytics.hook_learning._run_repo",
              return_value=SimpleNamespace(get=lambda rid: runs.get(rid))),
        patch("analytics.hook_learning._now", return_value=NOW),
    )  # fmt: skip


class HookLearningTests(unittest.TestCase):
    def test_the_join_reads_the_runs_stored_script(self):
        from analytics.hook_learning import learn

        a, b, c = _hook_repos(HOOKS, made=lambda i: NOW - timedelta(days=10))
        with a, b, c:
            got = learn("tapin")
        self.assertEqual(got["n"], 10)
        self.assertTrue(got["ready"])

    def test_only_the_last_90_days_teach(self):
        from analytics.hook_learning import learn

        made = lambda i: NOW - timedelta(days=120 if i < 4 else 10)  # noqa: E731
        a, b, c = _hook_repos(HOOKS, made=made)
        with a, b, c:
            got = learn("tapin")
        self.assertEqual(got["n"], 6)
        self.assertNotIn("Six UFC contracts", " ".join(h for h, _s in got["best_hooks"]))

    def test_a_note_against_the_rewrites_rules_waits_until_n_settles(self):
        from analytics.hook_learning import guidance_from

        learned = {
            "ready": True, "n": 18, "needs": 21,
            "traits": [
                {"trait": "a question", "with": 0.375, "without": 0.202, "gap": 0.173},
                {"trait": "stakes", "with": 0.30, "without": 0.22, "gap": 0.08},
                {"trait": "a number", "with": 0.20, "without": 0.258, "gap": -0.058},
                {"trait": "a weak opener", "with": 0.10, "without": 0.25, "gap": -0.15},
            ],
            "best_hooks": [("One.", 0.52), ("Two?", 0.50), ("Three?", 0.42)],
        }  # fmt: skip
        got = guidance_from(learned)
        self.assertEqual(got["examples"], ["One.", "Two?", "Three?"])
        self.assertEqual([t["trait"] for t in got["prefer"]], ["stakes"])
        self.assertEqual([t["trait"] for t in got["avoid"]], ["a weak opener"])
        settled = guidance_from(dict(learned, n=21))
        self.assertIn("a question", [t["trait"] for t in settled["prefer"]])
        self.assertIn("a number", [t["trait"] for t in settled["avoid"]])
        self.assertEqual(guidance_from(dict(learned, ready=False)), {})

    def test_the_growth_line_says_which_rule_waits(self):
        from analytics import hook_learning

        learned = {"n": 18, "min": 10, "ready": True, "r": -0.413, "needs": 21,
                   "traits": [{"trait": "a question", "with": 0.375, "without": 0.202,
                               "gap": 0.173, "n_with": 4, "n_without": 14}],
                   "best_hooks": []}  # fmt: skip
        with patch.object(hook_learning, "learn", return_value=learned):
            line = hook_learning.render_line("tapin")
        self.assertIn("openers with a question held 38% vs 20%", line)
        self.assertIn("the rewrite keeps its rule on a question until n=21", line)

    def test_the_unconfirmed_check_reads_the_stored_script_too(self):
        from analytics import unconfirmed_check

        run = SimpleNamespace(id=10, selected_topic="UFC week", input_topic="UFC week",
                              script_preview="Early reports say Jon Jones retired. Fans wait.",
                              quality_json=json.dumps({"script_mode": "unconfirmed"}),
                              features_json="{}")  # fmt: skip
        with patch.object(unconfirmed_check, "_runs", return_value=[run]):
            got = unconfirmed_check.check("tapin")
        self.assertEqual(got["claims"], 1)


# ---- 5. #1289: the task may wake the PC ------------------------------------------------------------

XML_NO_WAKE = (
    "<Task><Settings><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
    "<StartWhenAvailable>true</StartWhenAvailable></Settings></Task>"
)
XML_WAKE = XML_NO_WAKE.replace("</Settings>", "<WakeToRun>true</WakeToRun></Settings>")
QUERY = (
    "Last Run Time:                        10/17/2026 12:07:43 PM\n"
    "Next Run Time:                        10/19/2026 5:00:00 AM\n"
    "Last Result:                          0\n"
    "Start Time:                           5:00:00 AM\n"
)
POWERCFG = (
    "    Power Setting GUID: bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d  (Allow wake timers)\n"
    "    Current AC Power Setting Index: 0x00000001\n"
    "    Current DC Power Setting Index: 0x00000000\n"
)


class WakeTests(unittest.TestCase):
    def test_the_task_xml_says_whether_it_may_wake_the_pc(self):
        from core.nightly_task import wake_to_run

        self.assertIs(wake_to_run(XML_NO_WAKE), False)
        self.assertIs(wake_to_run(XML_WAKE), True)
        self.assertIsNone(wake_to_run(""))

    def test_the_missed_line_names_why(self):
        from core.nightly_task import missed_line, task_times

        now = datetime(2026, 10, 18, 8, 4)
        line = missed_line(task_times(QUERY), now=now, wakes=False)
        self.assertIn("not allowed to wake the PC", line)
        self.assertIn("py -m scripts.ops schedule-drafts --wake", line)
        woke = missed_line(task_times(QUERY), now=now, wakes=True)
        self.assertIn("did not wake", woke)
        self.assertNotIn("--wake", woke)

    def test_wake_timers_are_read_from_powercfg(self):
        from core.nightly_task import parse_wake_timers

        self.assertEqual(parse_wake_timers(POWERCFG), {"ac": "on", "dc": "off"})
        self.assertEqual(parse_wake_timers(""), {})

    def test_the_suite_never_queries_the_real_task(self):
        from core import nightly_task

        with patch.object(nightly_task, "run_schtasks") as run:
            self.assertIsNone(nightly_task.task_wakes())
        run.assert_not_called()

    def test_wake_sets_the_flag_and_reads_it_back(self):
        from core import nightly_task
        from scripts.ops import COMMANDS

        out = io.StringIO()
        with (
            patch.object(nightly_task, "_powershell", return_value=(0, "")) as ps,
            patch.object(nightly_task, "task_wakes", return_value=True),
            patch.object(nightly_task, "wake_timers", return_value={"ac": "on", "dc": "on"}),
            redirect_stdout(out),
        ):
            code = COMMANDS["schedule-drafts"][1](Namespace(wake=True, channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("WakeToRun = $true", ps.call_args.args[0])
        self.assertIn("can now wake the PC", out.getvalue())

    def test_a_refused_wake_prints_the_line_for_an_administrator(self):
        from core import nightly_task
        from scripts.ops import COMMANDS

        out = io.StringIO()
        with (
            patch.object(nightly_task, "_powershell", return_value=(1, "Access is denied.")),
            patch.object(nightly_task, "task_wakes", return_value=False),
            patch.object(nightly_task, "wake_timers", return_value={}),
            redirect_stdout(out),
        ):
            code = COMMANDS["schedule-drafts"][1](Namespace(wake=True, channel="tapin"))
        self.assertEqual(code, 1)
        self.assertIn("administrator", out.getvalue())
        self.assertIn("WakeToRun = $true", out.getvalue())

    def test_install_lets_it_wake_too(self):
        from core import nightly_task
        from scripts.ops import COMMANDS

        with (
            patch.object(nightly_task, "run_schtasks", return_value=(0, "SUCCESS")),
            patch.object(nightly_task, "set_wake", return_value=(True, "")) as wake,
            redirect_stdout(io.StringIO()),
        ):
            code = COMMANDS["schedule-drafts"][1](Namespace(install=True, channel="tapin"))
        self.assertEqual(code, 0)
        wake.assert_called_once()


# ---- 6. #1268: the caption band darkens until 4.5:1 ----------------------------------------------

WHITE = (255, 255, 255)
RUN157_BAND = (136, 130, 131)


class ScrimTests(unittest.TestCase):
    def test_run_157s_band_reaches_4_5(self):
        from core.caption_contrast import contrast_ratio, scrim_alpha

        alpha = scrim_alpha(WHITE, [RUN157_BAND, (40, 40, 40)])
        self.assertGreater(alpha, 0.05)
        self.assertLessEqual(alpha, 0.45)
        darker = tuple(round(c * (1 - alpha)) for c in RUN157_BAND)
        self.assertGreaterEqual(contrast_ratio(WHITE, darker), 4.5)

    def test_no_scrim_when_every_band_passes_and_a_cap_when_none_can(self):
        from core.caption_contrast import scrim_alpha

        self.assertEqual(scrim_alpha(WHITE, [(30, 30, 30), (60, 60, 60)]), 0.0)
        self.assertEqual(scrim_alpha(WHITE, []), 0.0)
        self.assertEqual(scrim_alpha(WHITE, [(250, 250, 250)]), 0.45)

    def test_the_grade_is_counted(self):
        from core.caption_contrast import scrim_alpha

        grade = {"saturation": 1.18, "contrast": 1.08, "brightness": 0.01}
        self.assertGreater(scrim_alpha(WHITE, [RUN157_BAND], grade=grade),
                           scrim_alpha(WHITE, [RUN157_BAND]))  # fmt: skip

    def _cmd(self, **extra):
        from video.render_video import build_render_ffmpeg_command

        return build_render_ffmpeg_command(background_path="bg.mp4", mp3_path="voice.mp3",
                                           output_path="out.mp4", subtitle_path="c.ass",
                                           duration=30.0, **extra)  # fmt: skip

    def test_the_command_is_unchanged_without_a_scrim_and_boxed_with_one(self):
        self.assertEqual(self._cmd(), self._cmd(caption_scrim=0.0))
        cmd = self._cmd(caption_scrim=0.12)
        graph = cmd[cmd.index("-filter_complex") + 1]
        box = "drawbox=x=0:y=ih*0.80:w=iw:h=ih*0.20:color=black@0.12:t=fill,"
        self.assertIn(box, graph)
        self.assertLess(graph.index(box), graph.index("subtitles='"))

    def test_the_render_samples_its_background_for_a_publish_only(self):
        from video import render_video

        with tempfile.TemporaryDirectory() as tmp:
            bg = os.path.join(tmp, "bg.mp4")
            open(bg, "wb").close()
            with patch.object(render_video, "_sample_band_rgbs", return_value=[RUN157_BAND]):
                publish = render_video.caption_scrim_for(bg, 30.0, "tapin", "publish")
                draft = render_video.caption_scrim_for(bg, 30.0, "tapin", "draft")
            missing = render_video.caption_scrim_for(os.path.join(tmp, "no.mp4"), 30.0,
                                                     "tapin", "publish")  # fmt: skip
        self.assertGreater(publish, 0.0)
        self.assertEqual((draft, missing), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
