"""Wave 160, the next 10 (2026-11-07): #2020 a render that stops moving is killed and retried,
and ffmpeg never reads the console; #2021 an accepted draft past its window is set aside; #2022
the playlist store keeps every id; #1810 / #2018 no voice for a draft with no slot; #1719 the
follow line's wording A/B; #1828 the 7-day bridge card; #1786 the Week in Review's deep dives
crossposted; #1826 next-five by lane share; #1856 launch-week titles from autocomplete; #2007
headlines unescaped."""

from __future__ import annotations

import os
import subprocess
import threading
import time
import unittest
from typing import Any, ClassVar
from unittest.mock import patch

from core import render_progress
from core.render_progress import RenderProgress, run_ffmpeg_with_progress


class _Quiet(RenderProgress):
    def note(self, message: str) -> None:
        pass


def _fake_ffmpeg(lines_fn):
    """A Popen stand-in: `lines_fn(proc)` yields its stdout lines; kill() ends it."""

    class _P:
        made: ClassVar[list[Any]] = []

        def __init__(self, cmd, **kw):
            self.cmd, self.kw = cmd, kw
            self.killed = threading.Event()
            self.returncode = None
            self.stderr = iter([])
            self.stdout = lines_fn(self)
            _P.made.append(self)

        def poll(self):
            return self.returncode

        def wait(self):
            if self.returncode is None:
                self.killed.wait(5)
                self.returncode = -9 if self.killed.is_set() else 0
            return self.returncode

        def kill(self):
            self.killed.set()

    return _P


class RenderStallTests(unittest.TestCase):
    """#2020, the operator 11-07: "ffmpeg gets to about 80% then just stops ... even 1000s". The
    11-04 batch-review pass rendered one draft and never finished the next; overnight renders
    (no console) reach 100% in ~17 s."""

    def test_ffmpeg_never_reads_the_console(self):
        def lines(proc):
            proc.returncode = 0
            yield "out_time_ms=1000000\n"

        fake = _fake_ffmpeg(lines)
        with patch.object(render_progress.subprocess, "Popen", fake):
            run_ffmpeg_with_progress(["ffmpeg", "-y", "-i", "a.mp4", "o.mp4"], duration_sec=1.0,
                                     progress=_Quiet())  # fmt: skip
        proc = fake.made[-1]
        self.assertIn("-nostdin", proc.cmd)
        self.assertIs(proc.kw.get("stdin"), subprocess.DEVNULL)

    def test_a_frozen_encode_is_killed_and_said(self):
        def lines(proc):
            end = time.monotonic() + 6  # bounded, so code without a watchdog fails, not hangs
            while not proc.killed.is_set() and time.monotonic() < end:
                yield "out_time_ms=8000000\n"  # ffmpeg alive, its output time stuck at 8 of 10 s
                time.sleep(0.02)
            if not proc.killed.is_set():
                proc.returncode = 0

        fake = _fake_ffmpeg(lines)
        with (
            patch.dict(os.environ, {"FFMPEG_STALL_SECONDS": "1"}),
            patch.object(render_progress.subprocess, "Popen", fake),
        ):
            started = time.monotonic()
            res = run_ffmpeg_with_progress(["ffmpeg", "-i", "a.mp4", "o.mp4"], duration_sec=10.0,
                                           progress=_Quiet())  # fmt: skip
        self.assertLess(time.monotonic() - started, 4)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("ffmpeg stalled at 80%", res.stderr)

    def test_a_silent_hang_is_killed_too(self):
        def lines(proc):
            proc.killed.wait(5)  # nothing on stdout at all
            return
            yield

        fake = _fake_ffmpeg(lines)
        with (
            patch.dict(os.environ, {"FFMPEG_STALL_SECONDS": "1"}),
            patch.object(render_progress.subprocess, "Popen", fake),
        ):
            res = run_ffmpeg_with_progress(["ffmpeg", "-i", "a.mp4", "o.mp4"], duration_sec=10.0,
                                           progress=_Quiet())  # fmt: skip
        self.assertIn("ffmpeg stalled at 0%", res.stderr)

    def test_a_stalled_render_is_retried_once_without_the_pipe(self):
        import video.render_video as render_video

        stalled = subprocess.CompletedProcess([], 1, "", "ffmpeg stalled at 80% - no progress")
        ok = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(render_video, "run_ffmpeg_with_progress", return_value=stalled) as prog,
            patch.object(render_video.subprocess, "run", return_value=ok) as simple,
        ):
            res = render_video._ffmpeg_run(["ffmpeg", "-y", "-i", "a.mp4", "o.mp4"],
                                           duration_sec=10.0, progress=_Quiet(),
                                           use_progress=True)  # fmt: skip
        self.assertEqual(res.returncode, 0)
        prog.assert_called_once()
        simple.assert_called_once()
        self.assertIn("-nostdin", simple.call_args.args[0])
        self.assertIs(simple.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertGreater(simple.call_args.kwargs["timeout"], 0)

    def test_a_simple_run_that_never_ends_is_a_failure_not_a_hang(self):
        import video.render_video as render_video

        boom = subprocess.TimeoutExpired(["ffmpeg"], 900)
        with patch.object(render_video.subprocess, "run", side_effect=boom):
            res = render_video._ffmpeg_run(["ffmpeg", "-i", "a.mp4", "o.mp4"], duration_sec=10.0)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("timed out", res.stderr)


def _draft(root, name, *, days_old, decision="", topic="Xbox Game Pass trailer revealed"):
    import json
    from datetime import datetime, timedelta

    from core.batch_review import _SCRIPT_HEADING

    folder = os.path.join(root, name)
    os.makedirs(folder)
    meta = {"run_id": len(os.listdir(root)), "topic": topic, "title": topic,
            "created_at": (datetime.now() - timedelta(days=days_old)).isoformat()}  # fmt: skip
    if decision:
        meta["review"] = {"decision": decision}
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
        f.write(f"# {topic}\n\n{_SCRIPT_HEADING}\nA script line.\n")
    return folder


class AcceptedPastWindowTests(unittest.TestCase):
    """#2021, live 11-07: 6 of the 8 waiting drafts were accepted (11-04, 11-06) and never
    rendered - the render hung (#2020) - and overnight's cap counts them: "drafts 0" tonight,
    nothing scheduled after Sun 11-08. Three were 4 days old and could never go out."""

    def setUp(self):
        import shutil
        import tempfile

        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_an_accepted_draft_past_twice_its_window_is_set_aside(self):
        from core.batch_review import expire_old_drafts, pending_drafts

        _draft(self.root, "a-old", days_old=5, decision="accepted")
        _draft(self.root, "b-new", days_old=1, decision="accepted")
        _draft(self.root, "c-old-undecided", days_old=5)
        old = expire_old_drafts("tapin", root=self.root)
        self.assertEqual(sorted(os.path.basename(d.folder) for d in old),
                         ["a-old", "c-old-undecided"])  # fmt: skip
        left = [os.path.basename(d.folder) for d in pending_drafts("tapin", root=self.root)]
        self.assertEqual(left, ["b-new"])  # still current: it waits for the render


class NoVoiceWithoutSlotTests(unittest.TestCase):
    """#1810 / #2018 (measured in wave 159): the 1 PM step counted tonight's free slots for any
    title, the queue step read the run's own (title, deadline, planned time) - a draft with no
    slot of its own was voiced and went up unlisted; and an accepted draft past its window
    rendered in batch-review without an age check."""

    def test_the_1_pm_step_voices_nothing_the_queue_step_has_no_slot_for(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace

        import jobs.midday as midday

        rendered: list[int] = []
        now = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)
        lines = midday._midday_lines(
            "tapin", now,
            slots=lambda *_a: [now], waiting=lambda _c: 0,
            collect=lambda _c, n, _p: ["Chiefs trade for a receiver"][:n],
            draft=lambda _c, picked, **_k: [SimpleNamespace(topic=picked[0], ok=True, run_id=51)],
            render=lambda _c, run_id: rendered.append(run_id) or ("", 1),
            slot=lambda _c, _r: (None, "no slot inside its window"),
        )  # fmt: skip
        self.assertEqual(rendered, [])
        self.assertIn("run 51 drafted, not voiced - no slot (no slot inside its window)",
                      "\n".join(lines))  # fmt: skip

    def test_batch_review_sets_aside_an_accepted_draft_past_its_window(self):
        import shutil
        import tempfile

        from core import batch_review

        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        _draft(root, "old", days_old=3, decision="accepted")  # a 2-day news window
        out: list[str] = []
        with patch.object(batch_review, "_render") as render:
            batch_review.review_drafts("tapin", root=root, print_fn=out.append,
                                       ask=lambda _q: "n")  # fmt: skip
        self.assertIn("set aside, not rendered", "\n".join(out))
        render.assert_not_called()
        self.assertEqual(batch_review.pending_drafts("tapin", root=root), [])


class UnescapedHeadlineTests(unittest.TestCase):
    """#2007, live 11-06: "&#39;fakest&#39;" and "&quot;To be co" in the idea pool."""

    def test_a_feed_title_is_unescaped_into_its_topic(self):
        from core.best_bet import _consider_candidate

        got = _consider_candidate("Knicks support Taylor Swift after players called her "
                                  "&#39;fakest&#39;", "rss", allowed={"nba"}, exclude=set(),
                                  seen_local=set())  # fmt: skip
        self.assertEqual(
            got["topic"], "Knicks support Taylor Swift after players called her 'fakest'"
        )

    def test_the_shared_tokens_carry_no_entity_names(self):
        from apis.topic_tokens import content_tokens

        self.assertEqual(content_tokens("called her &#39;fakest&#39; &amp; more"),
                         ["called", "her", "fakest", "more"])  # fmt: skip


class FollowTrialTests(unittest.TestCase):
    """#1719: the follow line's wording A/B, Nov 8-21."""

    def test_arms_alternate_inside_the_trial_only(self):
        from datetime import date

        from core.success.follow_trial import follow_arm

        with patch.dict(os.environ, {"FOLLOW_TRIAL": "true"}):
            self.assertEqual(follow_arm("tapin", today=date(2026, 11, 9), rows=[]), "weekly")
            rows = [{"arm": "weekly"}]
            self.assertEqual(follow_arm("tapin", today=date(2026, 11, 9), rows=rows), "first")
            self.assertIsNone(follow_arm("tapin", today=date(2026, 11, 22), rows=[]))
        self.assertIsNone(follow_arm("tapin", today=date(2026, 11, 9), rows=[]))  # off in the suite

    def test_the_trending_line_takes_the_arm_and_a_countdown_keeps_its_own(self):
        from core.batch_generation import follow_brief

        bet = {"offered": [{"topic": "Chiefs trade for a receiver", "source": "trend"}],
               "picked": 1}  # fmt: skip
        self.assertIn("next big story lands here first", follow_brief(bet, arm="first"))
        self.assertIn("the week's Shorts come out as one video", follow_brief(bet, arm="weekly"))
        countdown = {"title_stem": "GTA 6: 12 Days to Launch", "offered": [], "picked": 1}
        self.assertIn("every day until launch", follow_brief(countdown, arm="first"))

    def test_generate_draft_records_the_arm_only_when_its_line_is_used(self):
        import inspect

        import core.batch_generation as bg

        source = inspect.getsource(bg.generate_draft)
        self.assertIn("follow_brief(best_bet, channel_id=channel_id, arm=follow_pick)", source)
        self.assertIn("record_assignment(channel_id, result.run_id, FOLLOW_LEVER, follow_pick)",
                      source)  # fmt: skip

    def test_the_readout_waits_for_both_arms(self):
        from core.success.follow_trial import follow_trial_lines

        shorts = [{"run_id": 1, "views7": 80, "subs": 2}, {"run_id": 2, "views7": 60, "subs": 0}]
        with patch("core.success.formats.measured_shorts", return_value=shorts):
            line = follow_trial_lines("tapin", arms={1: "first", 2: "weekly"})[0]
            self.assertEqual(follow_trial_lines("tapin", arms={1: "first"}), [])
        self.assertIn("first 2 subscribers, 80 views (n=1)", line)
        self.assertIn("weekly 0 subscribers, 60 views (n=1)", line)


class VideoCardTests(unittest.TestCase):
    """#1828: one card per video at 7 days - organic views, stayed, subscribers, hours, cost."""

    def test_a_video_published_7_to_14_days_ago_gets_its_card(self):
        import json
        from datetime import date, datetime, timezone
        from types import SimpleNamespace

        from core.success.video_card import video_card_lines

        def row(run_id, day, views, **m):
            when = datetime(2026, 11, day, 17, tzinfo=timezone.utc)
            daily = [[f"2026-11-{day + i:02d}", views // 7] for i in range(8)]
            return SimpleNamespace(content_run_id=run_id, published_at=when, privacy_status="public",
                                   metrics_json=json.dumps({"daily_views": daily, **m}), detail="")  # fmt: skip

        rows = [row(1, 1, 700, paid_views=70, stayed_share=0.41, subscribers_gained=2,
                    estimated_minutes_watched=30), row(2, 6, 140)]  # fmt: skip
        feats = {1: {"title": "Chiefs trade for a receiver", "cost": {"total": 0.31}},
                 2: {"title": "Too new"}}  # fmt: skip
        lines = video_card_lines("tapin", today=date(2026, 11, 10), rows=rows, features=feats.get)
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("run 1 (Short) Chiefs trade for a receiver:", lines[1])
        self.assertIn("stayed 41% · +2 subscribers · $0.31", lines[1])  # a Short: no YPP hours
        from core.success.video_card import card_line

        long_card = {"run_id": 9, "title": "The Week in Review", "long": True, "organic7": 90,
                     "stayed": 0.3, "subs": 1, "hours": 2.5, "cost": 0.9}  # fmt: skip
        self.assertIn("+1 subscribers · 2.5 hours · $0.90", card_line(long_card))


class WhoIsPeopleFirstTests(unittest.TestCase):
    """#2009, live 11-06: "New York City" and "York City" ranked beside Josh Hokit."""

    def test_people_take_the_lookups_before_places(self):
        from datetime import datetime, timezone

        from core.series import profiles

        now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
        pool = [{"topic": f"Josh Hokit in New York City, story {i}", "first": now,
                 "outlets": [f"outlet{i}"]} for i in range(6)]  # fmt: skip
        found = [("New York City", "New_York_City"), ("York City", "York_City"),
                 ("Josh Hokit", "Josh_Hokit")]  # fmt: skip
        with patch("apis.wikipedia_pageviews_api.subject_articles", return_value=found):
            names = [n for n, *_r in profiles.trending_names(pool, [], now=now)]
        self.assertEqual(names, ["Josh Hokit", "New York City"])
        from core.series.profiles import _PLACE

        for event in ("Main Card Results", "UFC Fight Night", "White House"):  # live 11-07
            self.assertTrue(_PLACE.search(event), event)
        self.assertFalse(_PLACE.search("Cortes Acosta"))


class RecutTitleTests(unittest.TestCase):
    """#2008: `recut_title` took the held moment's first sentence even when it named no one."""

    def test_a_sentence_naming_no_one_falls_back_to_the_original(self):
        from video.recut import recut_title

        original = "Wembanyama drops 40 as the Spurs stun Denver"
        self.assertEqual(recut_title("This season's strongest contenders are taking shape",
                                     original), original + " - the moment that held")  # fmt: skip
        self.assertEqual(recut_title("Wembanyama just made the whole league nervous", original),
                         "Wembanyama just made the whole league nervous")  # fmt: skip


class LaneShareTests(unittest.TestCase):
    """#1826: the next items by lane share - views and hours first, a defect ahead, capped."""

    def test_lanes_share_the_next_items(self):
        from core.roadmap_index import next_by_lane

        def item(n, lane, size="S", extra=""):
            return f"- [ ] {n}. **Item {n}** *(filed)* `[{size}]`{extra} · lane: {lane}"

        lines = [item(1700 + i, "views") for i in range(8)] + \
            [item(1800 + i, "hours") for i in range(5)] + [item(1850, "subscribers"),
             item(1860, "cost"), item(1870, "money"), item(1990, "defect"), item(1991, "defect"),
             item(1992, "defect"), item(1720, "views", "L"),
             item(1730, "views", extra=" **Built, open until it is public:**")]  # fmt: skip
        got = next_by_lane(lines, 10)
        lanes = [lane for _n, lane, _t in got]
        self.assertEqual(lanes[:2], ["defect", "defect"])  # a fifth of ten
        self.assertEqual(lanes.count("views"), 3)
        self.assertEqual(lanes.count("hours"), 2)
        self.assertEqual(len(got), 10)
        numbers = [n for n, _l, _t in got]
        self.assertNotIn(1720, numbers)  # L is not next-five work
        self.assertNotIn(1730, numbers)  # waiting to be public is not building work


class PlaylistIdsKeptTests(unittest.TestCase):
    """#2022, live 11-07: "Picks, graded" was made on YouTube and its id was gone from the store
    an hour later - two writers each saved what they had read; the next try would make a
    second playlist."""

    def setUp(self):
        import shutil
        import tempfile

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.path = os.path.join(tmp, "playlists_tapin.json")

    def test_a_save_keeps_the_ids_already_on_disk(self):
        from core.playlists import _load, _save

        _save(self.path, {"ids": {"GTA": "PLg", "Picks, graded": "PLp"}, "added": {"v1": ["GTA"]}})
        _save(self.path, {"ids": {"GTA": "PLg"}, "added": {"v2": ["GTA"]}})  # read before PLp
        data = _load(self.path)
        self.assertEqual(data["ids"], {"GTA": "PLg", "Picks, graded": "PLp"})
        self.assertEqual(data["added"], {"v1": ["GTA"], "v2": ["GTA"]})

    def test_a_playlist_already_on_the_channel_is_adopted_not_made_twice(self):
        import core.playlists as playlists

        log: list[str] = []

        class _Svc:
            def playlists(self):
                class _P:
                    def list(self, **kw):
                        log.append("list")
                        items = [{"id": "PLp", "snippet": {"title": "Picks, graded"}}]
                        return type("C", (), {"execute": lambda self: {"items": items}})()

                    def insert(self, **kw):
                        log.append("insert " + kw["body"]["snippet"]["title"])
                        return type("C", (), {"execute": lambda self: {"id": "PLnew"}})()

                return _P()

        rows = [{"name": "Picks, graded"}, {"name": "New One"}]
        with (
            patch.object(playlists, "playlist_map", return_value=rows),
            patch.object(playlists, "record_call"),
        ):
            made = playlists.sync_playlists(_Svc(), "tapin", store_path=self.path)
        self.assertEqual(made, ["New One"])
        self.assertEqual(log, ["list", "insert New One"])
        self.assertEqual(
            playlists._load(self.path)["ids"], {"Picks, graded": "PLp", "New One": "PLnew"}
        )


if __name__ == "__main__":
    unittest.main()
