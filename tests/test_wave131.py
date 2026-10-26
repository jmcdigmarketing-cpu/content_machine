"""Wave 131 (2026-10-25): the next ten.

Measured first: runs 185 and 186, the Chiefs-Seahawks preview and its Short, were held for a claim
until their game started and nothing pushed them; the captions spelled numbers the way the voice
said them ("UFC 333" as "three thirty three") on 5 of the last 12 renders; 36 of 317 recent
sentences ran over 25 words; the youtube and youtube_comments signals each paid a 100-unit search
for the same topic (comment reads, 312-527 units a day); the 11 playlists were never made; NFL
brings 32 organic views a video against UFC's 127; why a draft waited was never written down.
The operator, 10-25 (decision 80): share the search within a run, create the playlists with new
uploads joining, order the menu's domains by organic views per video.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class ClaimHeldSoonTests(unittest.TestCase):
    """#1582: a preview render held for a claim is pushed before its game, not only listed."""

    def _rows(self):
        return [
            SimpleNamespace(
                content_run_id=185, youtube_video_id="V185", title="Chiefs at Seahawks"
            ),
            SimpleNamespace(content_run_id=186, youtube_video_id="V186", title="Bengals at Ravens"),
            SimpleNamespace(content_run_id=187, youtube_video_id="V187", title="GTA 6 map"),
        ]

    def test_the_held_ones_whose_game_is_ahead(self):
        from core import stale_renders

        events = {185: NOW + timedelta(hours=4), 186: NOW - timedelta(hours=1), 187: None}
        with (
            patch("publishing.go_public.unlisted_holds", return_value=self._rows()),
            patch("publishing.go_public.override_held", side_effect=lambda r: r in (185, 186)),
            patch.object(stale_renders, "_event_for", side_effect=lambda r, ch: events[int(r)]),
        ):
            got = stale_renders.claim_holds_ahead("tapin", now=NOW)
        self.assertEqual([h["run_id"] for h in got], [185])
        self.assertEqual(got[0]["event"], NOW + timedelta(hours=4))

    def _watch(self, hours):
        from core import batch_review, stale_renders
        from jobs import worker

        hold = {"run_id": 185, "title": "Chiefs at Seahawks", "event": NOW + timedelta(hours=hours)}
        with (
            patch.object(batch_review, "next_decision", return_value=None),
            patch("config.channels.active_channel_ids", return_value=["tapin"]),
            patch.object(stale_renders, "claim_holds_ahead", return_value=[hold]),
            patch("core.win_notify.toast_daily") as toast,
        ):
            worker._decide_watch(now=NOW)
        return toast

    def test_within_six_hours_it_toasts_with_the_command(self):
        toast = self._watch(4)
        toast.assert_called_once()
        self.assertEqual(toast.call_args.args[0], "claim-185")
        self.assertIn("verify-claim --run-id 185", toast.call_args.args[2])
        self.assertIn("Chiefs at Seahawks", toast.call_args.args[2])

    def test_further_off_it_waits(self):
        self._watch(9).assert_not_called()

    def test_the_status_row_names_its_game(self):
        from core import stale_renders

        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[]),
            patch("publishing.go_public.unlisted_holds", return_value=self._rows()[:1]),
            patch("publishing.go_public.override_held", return_value=True),
            patch.object(stale_renders, "_hold_after_its_game", return_value=False),
            patch.object(stale_renders, "_event_for", return_value=NOW + timedelta(hours=4)),
            patch.object(stale_renders, "_now", return_value=NOW),
        ):
            rows = stale_renders.shelf_rows("tapin")
        self.assertEqual(len(rows), 1)
        self.assertIn("held for a claim", rows[0]["state"])
        self.assertIn("its game is", rows[0]["state"])
        self.assertIn("verify-claim --run-id 185", rows[0]["command"])


def _timed(text: str) -> list[dict]:
    return [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(text.split())]


class WrittenNumbersTests(unittest.TestCase):
    """#1583: the captions show the script's digits, timed to the words the voice said."""

    def test_an_event_number(self):
        from video.caption_timing import written_numbers

        words = _timed("he's already open to Song Yadong at UFC three thirty-four if he wins.")
        got = written_numbers(words, "And he's already open to Song Yadong at UFC 334 if he wins.")
        texts = [w["word"] for w in got]
        self.assertIn("334", texts)
        self.assertNotIn("three", texts)
        made = got[texts.index("334")]
        self.assertEqual((made["start"], made["end"]), (words[8]["start"], words[9]["end"]))

    def test_a_record_and_a_three_part_record(self):
        from video.caption_timing import written_numbers

        got = written_numbers(
            _timed("Rakhmonov is nineteen zero and he went twelve two one before that."),
            "Rakhmonov is 19-0, and he went 12-2-1 before that.",
        )
        self.assertEqual(
            [w["word"] for w in got],
            ["Rakhmonov", "is", "19-0,", "and", "he", "went", "12-2-1", "before", "that."],
        )

    def test_spaced_words_and_a_score(self):
        from video.caption_timing import written_numbers

        got = written_numbers(
            _timed("UFC three thirty three ended twenty zero"), "UFC 333 ended 20-0"
        )
        self.assertEqual([w["word"] for w in got], ["UFC", "333", "ended", "20-0"])

    def test_everything_else_is_left_alone(self):
        from video.caption_timing import written_numbers

        words = _timed("Ten turnovers, six picks, and Jones versus Aspinall.")
        got = written_numbers(words, "Ten turnovers, six picks, and Jones vs Aspinall.")
        self.assertEqual(got, words)
        self.assertEqual(written_numbers([], "UFC 334"), [])

    def test_the_caption_file_shows_the_digits(self):
        from video import subtitles

        script = "Merab defends at UFC 334 against Yan."
        words = _timed("Merab defends at UFC three thirty-four against Yan.")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "captions.srt")
            with patch.object(subtitles, "SUBTITLE_DIR", tmp):
                path = subtitles.generate_subtitle_file(
                    script, 5.0, channel_id="tapin", output_path=out, words=words
                )
            with open(path, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("334", text)
        self.assertNotIn("thirty", text)


class SharedSearchTests(unittest.TestCase):
    """#1579 (decision 80): one 100-unit search per topic per run, shared by both signals."""

    def _client(self):
        client = MagicMock()
        items = [{"id": {"kind": "youtube#video", "videoId": "v1"}, "snippet": {"title": "t"}}]
        client.search.return_value.list.return_value.execute.return_value = {"items": items}
        client.videos.return_value.list.return_value.execute.return_value = {"items": []}
        return client

    def test_the_second_caller_gets_the_first_result(self):
        from apis import youtube_api

        client = self._client()
        execute = client.search.return_value.list.return_value.execute
        first = youtube_api._search_videos(client, "Chiefs at Seahawks")
        self.assertFalse(youtube_api.search_was_shared())
        second = youtube_api._search_videos(client, "Chiefs at Seahawks")
        self.assertTrue(youtube_api.search_was_shared())
        self.assertEqual(first, second)
        self.assertEqual(execute.call_count, 1)
        youtube_api._search_videos(client, "Bengals at Ravens")
        self.assertEqual(execute.call_count, 2)

    def test_two_threads_at_once_make_one_call(self):
        from apis import youtube_api

        client = self._client()
        execute = client.search.return_value.list.return_value.execute
        started, release = threading.Event(), threading.Event()

        def slow():
            started.set()
            release.wait(5)
            return {"items": []}

        execute.side_effect = slow
        got: list = []
        one = threading.Thread(target=lambda: got.append(youtube_api._search_videos(client, "q")))
        two = threading.Thread(target=lambda: got.append(youtube_api._search_videos(client, "q")))
        one.start()
        started.wait(5)
        two.start()
        release.set()
        one.join(5)
        two.join(5)
        self.assertEqual(got, [{"items": []}, {"items": []}])
        self.assertEqual(execute.call_count, 1)

    def test_it_lasts_a_run_not_a_day(self):
        from apis import youtube_api

        client = self._client()
        execute = client.search.return_value.list.return_value.execute
        with patch.object(youtube_api, "_monotonic", return_value=1000.0):
            youtube_api._search_videos(client, "q")
        with patch.object(youtube_api, "_monotonic", return_value=1000.0 + 121):
            youtube_api._search_videos(client, "q")
        self.assertEqual(execute.call_count, 2)

    def test_the_comments_signal_books_no_second_search(self):
        from apis import youtube_api
        from apis import youtube_comments_signal as comments

        client = self._client()
        youtube_api._search_videos(client, "Chiefs at Seahawks")  # the youtube signal's search
        with (
            patch.object(youtube_api, "_get_youtube_client", return_value=client),
            patch.object(comments, "record_usage") as booked,
            patch.object(comments, "_fetch_comments", return_value=[]),
            patch.object(comments, "has_quota_for_search", return_value=True),
        ):
            comments.gather_comment_intel("Chiefs at Seahawks")
        booked.assert_not_called()

    def test_the_youtube_signal_books_only_its_videos_read_after_the_comments(self):
        from apis import youtube_api
        from apis import youtube_comments_signal as comments

        client = self._client()
        with (
            patch.object(youtube_api, "_get_youtube_client", return_value=client),
            patch.object(youtube_api, "_youtube_key", return_value="k"),
            patch.object(youtube_api, "has_quota_for_search", return_value=True),
            patch.object(youtube_api, "_LIGHTWEIGHT", False),
            patch.object(youtube_api, "record_usage") as booked_search,
            patch.object(comments, "record_usage") as booked_comments,
            patch.object(comments, "_fetch_comments", return_value=[]),
            patch.object(comments, "has_quota_for_search", return_value=True),
        ):
            comments.gather_comment_intel("Chiefs at Seahawks")
            youtube_api.search_youtube("Chiefs at Seahawks")
        self.assertEqual(booked_comments.call_count, 1)  # the one search, booked once
        self.assertEqual([c.kwargs.get("units") for c in booked_search.call_args_list], [1])


class LongSentenceTests(unittest.TestCase):
    """#1360: a sentence over 25 words goes through the read-aloud split."""

    LONG = (
        "Houston has led in the fourth quarter in three of their four losses this season, and "
        "the Texans keep finding new ways to lose games they controlled late against teams "
        "they should beat."
    )

    def test_over_25_words_is_hard_to_say(self):
        from core.script_craft import hard_to_say

        self.assertEqual([r["why"] for r in hard_to_say(self.LONG)], ["long"])
        self.assertEqual(hard_to_say("Houston has led late in three of four losses."), [])

    def test_the_pass_splits_it(self):
        from core.script_craft import read_aloud_pass

        split = (
            "Houston has led in the fourth quarter in three of their four losses this season. "
            "The Texans keep finding new ways to lose games they controlled late against teams "
            "they should beat."
        )
        with patch.dict(os.environ, {"READ_ALOUD_REWRITE": "true"}):
            out, report = read_aloud_pass(
                self.LONG, lambda s, u: {"rewrites": [{"old": self.LONG, "new": split}]}
            )
        self.assertEqual(out, split)
        self.assertEqual(report["rewritten"], 1)
        self.assertIn("long", report["why"])


def _draft(tmp: str, run_id: int, **meta) -> object:
    from core.batch_review import PendingDraft

    folder = os.path.join(tmp, f"d{run_id}")
    os.makedirs(folder)
    data = {"run_id": run_id, "title": f"draft {run_id}", **meta}
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)
    return PendingDraft(folder=folder, meta=data, script="A script.")


class HoldRecordTests(unittest.TestCase):
    """#1585: why a draft waited is written down, and the week's drafts are counted by outcome."""

    def _night(self, draft, why):
        from core import batch_review

        with patch.object(batch_review, "unattended_candidates", return_value=([], [(draft, why)])):
            batch_review.render_unattended("tapin", 2, shelf=lambda channel: 0)
        with open(os.path.join(draft.folder, "meta.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_overnight_writes_the_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = _draft(tmp, 201)
            meta = self._night(draft, "a claim is not supported")
        self.assertEqual(meta["hold"]["reason"], "a claim is not supported")
        self.assertTrue(meta["hold"]["at"])

    def test_the_same_reason_keeps_its_first_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = _draft(
                tmp, 202, hold={"reason": "its facts conflict", "at": "2026-10-24T05:00"}
            )
            meta = self._night(draft, "its facts conflict")
        self.assertEqual(meta["hold"]["at"], "2026-10-24T05:00")

    def test_the_weekly_line(self):
        from analytics.weekly_report import draft_outcome_line

        drafts = [
            {"review": {"decision": "rendered"}},
            {"review": {"decision": "expired"}, "hold": {"reason": "a claim is not supported"}},
            {"review": {"decision": "expired"}, "hold": {"reason": "a claim is not supported"}},
            {
                "review": {"decision": "expired"},
                "hold": {"reason": "script check: 1 thing said twice"},
            },
            {"review": {"decision": "expired"}},
            {"review": {"decision": "rejected"}},
            {},
        ]
        line = draft_outcome_line(drafts)
        self.assertIn("1 rendered, 4 expired, 1 rejected, 1 undecided (7 drafts)", line)
        self.assertIn("a claim is not supported 2", line)
        self.assertIn("script check 1", line)
        self.assertIn("none recorded 1", line)
        self.assertEqual(draft_outcome_line([]), "")


class DomainViewsTests(unittest.TestCase):
    """#1448 (decision 80): the menu's domains by organic views per video, shrunk."""

    GROUPS: ClassVar[dict] = {
        "nba": {"views": 580, "videos": 4},
        "ufc": {"views": 2032, "videos": 16},
        "gaming": {"views": 3616, "videos": 32},
        "nfl": {"views": 192, "videos": 6},
    }

    def test_shrunk_toward_the_channel_mean(self):
        from analytics.growth import shrunk_views_per_video

        rates, mean = shrunk_views_per_video(self.GROUPS)
        self.assertAlmostEqual(mean, 6420 / 58, places=3)
        self.assertEqual(rates["nba"], mean)  # 4 videos: at the mean
        self.assertEqual(
            sorted(rates, key=rates.get, reverse=True), ["ufc", "gaming", "nba", "nfl"]
        )

    def test_organic_shorts_views_by_domain(self):
        from analytics import growth

        kinds = {1: ("nfl", "Shorts"), 2: ("nfl", "Shorts"), 3: ("nfl", "long"), 4: ("", "")}
        rows = [
            {"run_id": 1, "views": 150, "paid": 50},
            {"run_id": 2, "views": 30},
            {"run_id": 3, "views": 900},
            {"run_id": 4, "views": 10},
        ]
        with patch.object(growth, "_kind", side_effect=lambda r: kinds[r]):
            got = growth.organic_views_by_domain(rows)
        self.assertEqual(got, {"nfl": {"views": 130, "videos": 2}})

    def test_the_menu_key(self):
        from core import best_bet

        adjusted, counts = {"nfl": 0.6, "ufc": 0.2}, {"nfl": 6, "ufc": 16}
        views = ({"nfl": 67.8, "ufc": 123.1}, 110.7)

        def key(d, v=None):
            return best_bet._domain_priority(d, adjusted, counts, views=v)

        self.assertGreater(key("ufc", views), key("nba", views))
        self.assertGreater(key("nba", views), key("nfl", views))
        self.assertGreater(key("nfl"), key("ufc"))  # without views: the engaged rate, as before

    def test_the_menu_reads_the_channel(self):
        from analytics import growth
        from core import best_bet

        with (
            patch.object(growth, "_rows", return_value=[{"run_id": 1, "views": 120}] * 6),
            patch.object(growth, "_kind", return_value=("ufc", "Shorts")),
        ):
            rates, mean = best_bet._domain_views("tapin")
        self.assertEqual(mean, 120.0)
        self.assertEqual(rates, {"ufc": 120.0})


class SaidTwiceHookTests(unittest.TestCase):
    """#1353: a hook rewrite that repeats a later sentence fails the script check (#1155)."""

    def test_the_hook_repeated_later(self):
        from core.script_craft import said_twice, script_check

        script = (
            "Jones has finished nine of his last ten fights inside the distance. "
            "Aspinall has never gone past the second round. "
            "Jones has finished nine of his last ten fights, all of them inside the distance. "
            "Tap in for more."
        )
        self.assertEqual(len(said_twice(script)), 1)
        self.assertIn("1 thing said twice", script_check(script=script)["why"])


class Oct13DraftsTests(unittest.TestCase):
    """#1339: the two Oct 13 drafts that rendered wrong, kept whole, and what stops each today."""

    def setUp(self):
        with open(os.path.join(FIXTURES, "oct13_drafts.json"), encoding="utf-8") as f:
            self.drafts = {d["run_id"]: d for d in json.load(f)}

    def test_run_136_fails_the_script_check(self):
        from core.script_craft import script_check

        why = script_check(script=self.drafts[136]["script"], title=self.drafts[136]["title"])[
            "why"
        ]
        self.assertIn("1 thing said twice", why)
        self.assertTrue(any("tennessee" in w for w in why))

    def test_run_139_calls_a_game_not_yet_played(self):
        from core.facts.event_dates import unplayed_result

        draft = self.drafts[139]
        self.assertTrue(unplayed_result(draft["title"], draft["topic"]))
        self.assertTrue(unplayed_result(draft["script"], draft["topic"]))


class PlaylistTests(unittest.TestCase):
    """#1584 (decision 80): an upload joins the playlist its title names once it exists."""

    def test_the_channel_map(self):
        from core.playlists import playlists_for

        self.assertIn("UFC / MMA", playlists_for("tapin", "Fiziev vs Ruffy at UFC 334"))
        self.assertIn("NFL", playlists_for("tapin", "Chiefs at Seahawks: the NFL Week 8 call"))

    def test_an_upload_is_added_and_nothing_is_missing(self):
        from core import playlists

        service = MagicMock()
        names = [str(n) for row in playlists.playlist_map("tapin")
                 for n in (row.get("name"), row.get("parent")) if n]  # fmt: skip
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youtube.oauth.token_has_scope", return_value=True),
            patch.object(playlists, "store_path_for", return_value=os.path.join(tmp, "p.json")),
        ):
            with open(os.path.join(tmp, "p.json"), "w", encoding="utf-8") as f:
                json.dump({"ids": {n: f"PL-{n}" for n in names}}, f)
            playlists.add_to_playlists(service, "tapin", "V1", title="Fiziev vs Ruffy at UFC 334")
            missing = playlists.missing_line("tapin")
        added = [
            c.kwargs["body"]["snippet"]["playlistId"]
            for c in service.playlistItems().insert.call_args_list
        ]
        self.assertIn("PL-UFC / MMA", added)
        self.assertEqual(missing, "")


class PlaylistRefusalTests(unittest.TestCase):
    """#1584, live 2026-10-25: YouTube made 9 of the 11 and refused the 10th with a 429
    (RATE_LIMIT_EXCEEDED); `ops playlists --apply` died in a traceback and nothing would try
    the last two again."""

    def _service(self, outcomes):
        service = MagicMock()
        service.playlists.return_value.insert.return_value.execute.side_effect = outcomes
        return service

    def test_a_refusal_stops_the_run_and_keeps_what_was_made(self):
        from core import playlists

        refused = RuntimeError("<HttpError 429 ... RATE_LIMIT_EXCEEDED>")
        service = self._service([{"id": "PL1"}, refused, {"id": "PL3"}])
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "p.json")
            created = playlists.sync_playlists(service, "tapin", store_path=store)
            with open(store, encoding="utf-8") as f:
                ids = json.load(f)["ids"]
        self.assertEqual(created, ["GTA"])
        self.assertEqual(ids, {"GTA": "PL1"})
        self.assertEqual(service.playlists.return_value.insert.return_value.execute.call_count, 2)

    def _finish(self, tmp, *, today, env="true", scope=True):
        from core import playlists

        service = self._service([{"id": f"PL{i}"} for i in range(20)])
        factory = MagicMock(return_value=service)
        with (
            patch.dict(os.environ, {"PLAYLISTS_AUTO_CREATE": env}),
            patch.object(playlists, "store_path_for", return_value=os.path.join(tmp, "p.json")),
            patch("youtube.oauth.token_has_scope", return_value=scope),
        ):
            made = playlists.finish_playlists("tapin", service_factory=factory, today=today)
        return made, factory

    def test_the_worker_finishes_them_once_a_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            made, _f = self._finish(tmp, today="2026-10-26")
            again, factory = self._finish(tmp, today="2026-10-26")
        self.assertIn("Football", made)
        self.assertEqual(again, [])
        factory.assert_not_called()

    def test_off_or_without_the_scope_it_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            off, factory = self._finish(tmp, today="2026-10-26", env="false")
            factory.assert_not_called()
            unscoped, factory = self._finish(tmp, today="2026-10-26", scope=False)
            factory.assert_not_called()
        self.assertEqual((off, unscoped), ([], []))

    def test_drain_due_runs_it(self):
        from jobs import worker

        with (
            patch.object(worker, "_post_due_pins"),
            patch.object(worker, "_crosspost_scheduled_live"),
            patch.object(worker, "_previews_first"),
            patch.object(worker, "process_one", return_value=False),
            patch.object(worker, "_schedule_chapter_shorts"),
            patch.object(worker, "_post_call_comments"),
            patch.object(worker, "_finish_playlists") as finish,
        ):
            worker.drain_due()
        finish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
