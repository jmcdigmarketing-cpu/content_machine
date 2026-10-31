"""Wave 133, the next ten (2026-10-28) - the GTA 6 window and the verdicts (decision 84).

#1596 the verdicts rank on what was rated; #1748 + #1747 the affiliates map, long-form only;
#1868 two GTA 6 slots a day in launch week; #1867 a GTA 6 story jumps the queue then; the launch
moments and the long videos as dated entries; #1870 launch day at its unlock time; #1850 the
long-form draft kind (16:9, renders after review); #1856 long-form titles from search; #1731 +
#1869 long-form thumbnails from our own frames; #1855 the GTA playlist in countdown order.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _bet(topic, source="trending", *, outlets=0, **extra):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain="gaming", avg_engaged_rate=0.0, source=source,
                         supporting_runs=0, rationale="why", outlets=outlets, **extra)  # fmt: skip


def _video(vid, *, d7=None, life=None, views=0):
    from core.success.videos import Video

    return Video(video_id=vid, title=vid, published_at=None, views=views, engaged_rate=None,
                 run_id=None, seeded=False, views_7d=d7, lifetime_views=life)  # fmt: skip


class VerdictTests(unittest.TestCase):
    """#1596: `review-week` said "1 rated video(s) with views" - 28 rated, 3 with 7-day views."""

    def test_the_ranking_uses_a_measure_the_rated_videos_have(self):
        from core.success.videos import comparable_views

        videos = [_video(f"new{i}", d7=100 + i, life=200 + i) for i in range(10)]
        videos += [_video(f"rated{i}", life=50 + i) for i in range(5)]
        rated = {f"rated{i}" for i in range(5)}
        _ranked, heading, _unit = comparable_views(videos)
        self.assertIn("7 days", heading)  # the control: 7-day views win on count alone
        ranked, heading, _unit = comparable_views(videos, cover=rated, cover_min=3)
        self.assertNotIn("7 days", heading)
        self.assertEqual(sum(1 for v, _n in ranked if v.video_id in rated), 5)

    def test_the_live_shape_ranks_on_lifetime(self):
        # Live, 10-28: 28 rated, 3 of them with 7-day views, 24 with lifetime views; 40 videos
        # had 7-day views. A floor of 3 let 7-day views win and compared 3 ratings.
        from core.success import verdicts

        videos = [_video(f"new{i}", d7=100 + i, life=200 + i) for i in range(40)]
        videos += [_video(f"old{i}", d7=10 + i, life=60 + i) for i in range(3)]
        videos += [_video(f"rated{i}", life=50 + i) for i in range(21)]
        rated = {v: {"rating": 3} for v in [*(f"old{i}" for i in range(3)),
                                             *(f"rated{i}" for i in range(21)),
                                             *(f"gone{i}" for i in range(4))]}  # fmt: skip
        with (
            patch.object(verdicts, "load", return_value=rated),
            patch("core.success.videos.channel_videos", return_value=videos),
        ):
            scored = verdicts._scored("tapin")
        self.assertEqual(scored["rated"], 24)
        self.assertNotIn("7 days", scored["heading"])

    def test_the_report_compares_every_rated_video(self):
        from core.success import verdicts

        videos = [_video(f"new{i}", d7=100 + i, life=200 + i) for i in range(10)]
        videos += [_video(f"rated{i}", life=50 + i) for i in range(5)]
        rated = {f"rated{i}": {"rating": 3} for i in range(5)}
        with (
            patch.object(verdicts, "load", return_value=rated),
            patch("core.success.videos.channel_videos", return_value=videos),
        ):
            self.assertEqual(verdicts._scored("tapin")["rated"], 5)


AFFILIATES = {"tapin": [{"keys": ["gta 6", "gta vi", "grand theft auto vi"],
                         "url": "https://www.amazon.com/dp/B0EXAMPLE1",
                         "label": "GTA 6 on Amazon"}]}  # fmt: skip


class AffiliateTests(unittest.TestCase):
    """#1748 + #1747 (B07.1-2): a Short's description links are not clickable - long-form only."""

    def _lines(self, *, long_form, tag):
        from core import description_extras

        with (
            patch.object(description_extras, "affiliate_rows", return_value=AFFILIATES["tapin"]),
            patch.dict(os.environ, {"AFFILIATE_AMAZON_TAG": tag}),
        ):
            return description_extras.affiliate_lines(
                "tapin", "GTA 6 - everything we know before launch", long_form=long_form
            )

    def test_the_three_fixtures(self):
        lines = self._lines(long_form=True, tag="tapin-20")
        self.assertEqual(
            lines[0], "GTA 6 on Amazon: https://www.amazon.com/dp/B0EXAMPLE1?tag=tapin-20"
        )
        self.assertEqual(len(lines), 2)
        self.assertIn("affiliate", lines[1].lower())  # the FTC line
        self.assertEqual(self._lines(long_form=False, tag="tapin-20"), [])
        self.assertEqual(self._lines(long_form=True, tag=""), [])

    def test_a_long_description_carries_them(self):
        from core import description_extras

        with (
            patch.object(description_extras, "affiliate_rows", return_value=AFFILIATES["tapin"]),
            patch.dict(
                os.environ, {"AFFILIATE_AMAZON_TAG": "tapin-20", "DESCRIPTION_SOURCES": "false"}
            ),
        ):
            long_text = description_extras.apply_description_extras(
                "Body.", "tapin", title="GTA 6 - everything we know", length_choice="4"
            )
            short_text = description_extras.apply_description_extras(
                "Body.", "tapin", title="GTA 6 - everything we know", length_choice="2"
            )
        self.assertIn("?tag=tapin-20", long_text)
        self.assertNotIn("amazon", short_text.lower())

    def test_the_real_map_has_no_invented_product(self):
        from core.description_extras import affiliate_rows

        rows = affiliate_rows("tapin")
        self.assertTrue(rows)
        self.assertTrue(all("/s?k=" in r["url"] for r in rows if "amazon." in r["url"]))

    def test_the_suite_has_no_tag(self):
        self.assertEqual(os.environ.get("AFFILIATE_AMAZON_TAG"), "")


SLOTS_ROW = {"id": "gta6-launch-slots", "kind": "slots", "subject": "GTA 6",
             "names": ["GTA 6", "GTA VI"], "from": "2026-11-16", "to": "2026-11-22",
             "extra_hours": [18]}  # fmt: skip


class LaunchSlotTests(unittest.TestCase):
    """#1868 (B11.22): two GTA 6 slots a day in launch week."""

    def _hours(self, title, day):
        from core.series import dated

        with patch.object(dated, "series_rows", return_value=[SLOTS_ROW]):
            return dated.slot_hours("tapin", title, day)

    def test_the_three_fixtures(self):
        self.assertEqual(self._hours("GTA 6 pre-load times", "2026-11-18"), (12, 18, 22))
        self.assertEqual(self._hours("UFC 335 preview", "2026-11-18"), (12, 22))
        self.assertEqual(self._hours("GTA 6 pre-load times", "2026-11-23"), (12, 22))

    def test_the_slots_follow_the_day(self):
        from core.spaced_queue import twice_daily_slots

        now = datetime(2026, 11, 18, 5, tzinfo=timezone.utc)

        def hours_on(day):
            return (12, 18, 22) if day == date(2026, 11, 18) else (12, 22)

        with patch("core.spaced_queue._channel_tz", return_value=timezone.utc):
            got = twice_daily_slots("tapin", 4, now=now, hours_on=hours_on)
        self.assertEqual([s.hour for s in got], [12, 18, 22, 12])

    def test_the_run_slot_reads_it(self):
        import inspect

        from core import spaced_queue

        self.assertIn("slot_hours(", inspect.getsource(spaced_queue.slot_for_run))


class JumpTests(unittest.TestCase):
    """#1867 (B11.21): in launch week a GTA 6 story on 5+ outlets is drafted first."""

    def _topics(self, day):
        from core import batch_generation as bg

        ideas = [_bet("UFC 335 main event changes", outlets=7),
                 _bet("GTA 6 trailer 3 breaks the record", outlets=6)]  # fmt: skip
        with (
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
            patch("core.series.dated.series_rows", return_value=[SLOTS_ROW]),
            patch("core.series.dated.channel_day", return_value=date.fromisoformat(day)),
        ):
            return bg.collect_topics("tapin", count=2)

    def test_inside_the_window_gta_leads(self):
        self.assertEqual(self._topics("2026-11-18")[0], "GTA 6 trailer 3 breaks the record")

    def test_outside_it_the_ranking_stands(self):
        self.assertEqual(self._topics("2026-11-10")[0], "UFC 335 main event changes")


MOMENTS = [
    {"id": "gta6-online", "kind": "moment", "subject": "GTA 6", "names": ["GTA 6"],
     "topic": "GTA 6 Online - what is confirmed", "on": "2026-11-12", "domain": "gaming"},
    {"id": "gta6-pc", "kind": "moment", "subject": "GTA 6", "names": ["GTA 6"],
     "topic": "When does GTA 6 come to PC?", "on": "2026-11-14", "needs": ["PC"],
     "domain": "gaming"},
    {"id": "gta6-launch-day", "kind": "moment", "subject": "GTA 6", "names": ["GTA 6"],
     "topic": "GTA 6 is out: unlock times, file size and what to do first", "on": "2026-11-18",
     "publish_at": "2026-11-19T05:00:00Z", "domain": "gaming"},
    {"id": "gta6-reviews", "kind": "moment", "subject": "GTA 6", "names": ["GTA 6"],
     "topic": "GTA 6 review scores, rounded up", "on": None, "domain": "gaming"},
    {"id": "gta6-everything", "kind": "long", "subject": "GTA 6", "names": ["GTA 6"],
     "topic": "GTA 6 - everything we know before launch", "on": "2026-11-06", "domain": "gaming"},
]  # fmt: skip


class DatedTests(unittest.TestCase):
    """The launch moments (#1848 #1849 #1854 #1860-#1865 #1679) and the long videos (#1850 #1851
    #1853): each drafted on its date, as an extra draft (the operator, decision 84)."""

    def _ideas(self, day, *, drafted=False, headlines=(), notes=None):
        from core.series import dated

        with (
            patch.dict(os.environ, {"SERIES_DATED": "true"}),
            patch.object(dated, "series_rows", return_value=MOMENTS),
            patch.object(dated, "channel_day", return_value=date.fromisoformat(day)),
            patch("core.batch_generation.series_drafted", return_value=drafted),
        ):
            return dated.dated_ideas("tapin", now=datetime.fromisoformat(f"{day}T15:00:00+00:00"),
                                     headlines=lambda *_a: list(headlines), notes=notes)  # fmt: skip

    def test_on_its_date_only(self):
        self.assertEqual([i.topic for i in self._ideas("2026-11-12")],
                         ["GTA 6 Online - what is confirmed"])  # fmt: skip
        self.assertEqual(self._ideas("2026-11-11"), [])
        self.assertEqual(self._ideas("2026-11-12", drafted=True), [])

    def test_a_null_date_is_never_drafted(self):
        for day in ("2026-11-06", "2026-11-12", "2026-11-19", "2026-11-27"):
            self.assertNotIn("GTA 6 review scores, rounded up", [i.topic for i in self._ideas(day)])

    def test_the_pc_question_needs_a_headline_naming_it(self):
        notes: list[str] = []
        self.assertEqual(self._ideas("2026-11-14", notes=notes), [])
        self.assertIn("PC", notes[0])
        when = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
        lines = [{"title": "GTA 6 PC port rumour grows", "source": "PC Gamer", "published": when}]
        got = self._ideas("2026-11-14", headlines=lines)
        self.assertEqual([i.topic for i in got], ["When does GTA 6 come to PC?"])
        self.assertIn("PC Gamer reported: GTA 6 PC port rumour grows", got[0].facts)

    def test_a_long_entry_is_a_long_draft(self):
        idea = self._ideas("2026-11-06")[0]
        self.assertEqual((idea.source, idea.draft_kind), ("long", "long"))

    def test_launch_day_carries_its_unlock(self):
        idea = self._ideas("2026-11-18")[0]
        self.assertEqual(idea.publish_at, "2026-11-19T05:00:00Z")

    def test_overnight_takes_them_on_top_of_the_count(self):
        from core import batch_generation as bg

        moment = _bet("GTA 6 Online - what is confirmed", "moment")
        long_one = _bet("GTA 6 - everything we know before launch", "long", draft_kind="long")
        ideas = [moment, long_one, *(_bet(f"idea {i}", outlets=4) for i in range(4))]
        picks: dict = {}
        with patch("core.best_bet.get_idea_menu", return_value=(ideas, [])):
            topics = bg.collect_topics("tapin", count=2, picks=picks)
        self.assertEqual(topics, [moment.topic, long_one.topic, "idea 0", "idea 1"])
        self.assertEqual(picks[long_one.topic]["draft_kind"], "long")

    def test_the_real_config_dates(self):
        from core.series.countdown import series_rows

        rows = {r["id"]: r for r in series_rows("tapin")}
        self.assertEqual(rows["gta6-everything"]["on"], "2026-11-06")
        self.assertEqual(rows["gta6-map-story"]["on"], "2026-11-12")
        self.assertEqual(rows["gta6-first-things"]["on"], "2026-11-20")
        self.assertEqual(rows["gta6-launch-day"]["on"], "2026-11-18")
        self.assertIsNone(rows["gta6-launch-day"]["publish_at"])  # until Rockstar states it
        self.assertIsNone(rows["gta6-review-scores"]["on"])
        self.assertEqual(rows["gta6-countdown"]["playlist"], "GTA")

    def test_the_suite_keeps_them_off(self):
        from core.series import dated

        with patch.object(dated, "series_rows", return_value=MOMENTS):
            self.assertEqual(dated.dated_ideas("tapin"), [])


class LaunchDayTests(unittest.TestCase):
    """#1870 (B11.24): the launch-day Short goes public at the unlock hour its entry names."""

    def _slot(self, publish_at):
        from core import spaced_queue

        now = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)
        with (
            patch("core.batch_review.draft_meta_for_run", return_value={"publish_at": publish_at}),
            patch.object(spaced_queue, "_taken_slots", return_value=set()),
            patch.object(spaced_queue, "_window_days", return_value=2.0),
            patch.object(spaced_queue, "_age_days", return_value=0.0),
            patch.object(spaced_queue, "preview_event", return_value=None),
            patch.object(spaced_queue, "_channel_tz", return_value=timezone.utc),
        ):
            return spaced_queue.slot_for_run("tapin", 300, title="GTA 6 is out", now=now)

    def test_the_unlock_time(self):
        when, why = self._slot("2026-11-19T05:00:00Z")
        self.assertEqual((when, why), (datetime(2026, 11, 19, 5, tzinfo=timezone.utc), ""))

    def test_no_time_yet_is_the_next_slot(self):
        when, _why = self._slot(None)
        self.assertEqual(when, datetime(2026, 11, 18, 12, tzinfo=timezone.utc))


class LongDraftTests(unittest.TestCase):
    """#1850 (B11.4): the channel's first 16:9 long videos - Extended, chapters, after review."""

    def test_a_long_pick_is_drafted_long(self):
        from core import batch_generation as bg

        discovery = SimpleNamespace(
            evaluated=[(f"angle {i}", 50.0, {}) for i in range(5)], raw_scores=[50.0] * 5,
            angle_scores={}, base_signals={}, meta={},
        )  # fmt: skip
        result = SimpleNamespace(abort_reason="proceed_video=False", aborted=True, script="Words.",
                                 title="GTA 6 Release Date: everything", run_id=None,
                                 features={"fact_lines": 3}, description="", tags=[])  # fmt: skip
        record = {"offered": [{"topic": "GTA 6 - everything we know", "source": "long"}],
                  "picked": 1, "draft_kind": "long"}  # fmt: skip
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("core.pipeline.run_discovery", return_value=discovery),
            patch("core.pipeline.run_pipeline", return_value=result) as run,
            patch.object(bg, "_drafts_dir", return_value=tmp),
            patch("core.pipeline.best_variant_index", return_value=0),
        ):
            out = bg.generate_draft("GTA 6 - everything we know", "tapin", best_bet=record)
            with open(os.path.join(out.path, "meta.json"), encoding="utf-8") as handle:
                meta = json.load(handle)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["length_choice"], "4")
        self.assertGreaterEqual(len(kwargs["chapter_angles"]), 3)
        self.assertEqual(meta["kind"], "long")
        self.assertEqual(meta["length_choice"], "4")

    def test_a_long_draft_waits_for_review(self):
        from core.batch_review import PendingDraft, unattended_block_reason

        draft = PendingDraft(folder="f", meta={"kind": "long", "run_id": 1, "topic": "GTA 6"},
                             script="One. Two.")  # fmt: skip
        self.assertIn("after your review", unattended_block_reason(draft))

    def test_the_render_is_16x9_and_the_run_points_at_it(self):
        from core import batch_review

        seen: dict = {}

        def fake_media(*_a, **_k):
            seen["formats"] = os.environ.get("RENDER_FORMATS")

        with tempfile.TemporaryDirectory() as tmp:
            primary = os.path.join(tmp, "run300.mp4")
            wide = os.path.join(tmp, "run300_16x9.mp4")
            for path in (primary, wide):
                open(path, "wb").close()
            run = SimpleNamespace(id=300, mp4_path=primary, mp3_path="a.mp3", title="GTA 6")
            draft = batch_review.PendingDraft(
                folder=tmp, meta={"kind": "long", "run_id": 300, "topic": "GTA 6",
                                  "title": "GTA 6 - everything", "channel_id": "tapin"},
                script="One.")  # fmt: skip
            with (
                patch("core.pipeline.run_media_only", side_effect=fake_media),
                patch("storage.repositories.content_runs.get_content_run_repository") as repo,
                patch("core.run_recorder.update_content_run_media") as media,
                patch("core.series.long_form.long_thumbnail", return_value=""),
                patch("core.run_features.merge_features"),  # wave 135: long_form, no DB
                patch("core.series.long_form.cover_arm", return_value="words"),
            ):
                repo.return_value.get.return_value = run
                batch_review._render(draft, False)
        self.assertEqual(seen["formats"], "landscape")
        self.assertTrue(media.call_args.kwargs["mp4_path"].endswith("_16x9.mp4"))
        self.assertNotEqual(os.environ.get("RENDER_FORMATS"), "landscape")  # restored

    def test_a_short_renders_as_before(self):
        from core import batch_review

        seen: dict = {}

        def fake_media(*_a, **_k):
            seen["formats"] = os.environ.get("RENDER_FORMATS")

        draft = batch_review.PendingDraft(folder="f", meta={"run_id": 301, "topic": "UFC"},
                                          script="One.")  # fmt: skip
        with (
            patch("core.pipeline.run_media_only", side_effect=fake_media),
            patch("core.run_recorder.update_content_run_media") as media,
        ):
            batch_review._render(draft, False)
        self.assertNotEqual(seen["formats"], "landscape")
        media.assert_not_called()


class SearchTitleTests(unittest.TestCase):
    """#1856 (B11.10) + #1725 + #1616: a long video is found by search, not the feed."""

    def test_the_title_carries_the_top_search(self):
        from core.series.long_form import search_title

        got = search_title("GTA 6", ["gta 6 release date", "gta 6 map", "gta 6 price"],
                           "Everything we know about GTA 6 before launch")  # fmt: skip
        self.assertTrue(got.startswith("GTA 6"))
        self.assertIn("release date", got.lower())
        self.assertLessEqual(len(got), 100)

    def test_the_rows_terms_choose_the_suggestion(self):
        from core.series.long_form import search_title

        live = ["gta 6", "gta 6 trailer", "gta 6 gameplay", "gta 6 map", "gta 6 map size"]
        got = search_title("GTA 6", live, "GTA 6's map, characters and story explained",
                           terms=["map", "story"])  # fmt: skip
        self.assertEqual(got, "GTA 6's map, characters and story explained")  # it says map already
        got = search_title("GTA 6", ["gta 6 trailer", "gta 6 release date"],
                           "GTA 6: Everything We Know Before Launch", terms=["release date"])  # fmt: skip
        self.assertEqual(got, "GTA 6 Release Date: Everything We Know Before Launch")
        self.assertNotIn("Trailer", got)

    def test_a_possessive_keeps_its_subject(self):
        from core.series.long_form import search_title

        got = search_title("GTA 6", ["gta 6 story"], "GTA 6's map and characters explained")
        self.assertNotIn(": 's", got)
        self.assertIn("GTA 6's map", got)

    def test_no_suggestions_keeps_the_title(self):
        from core.series.long_form import search_title

        self.assertEqual(search_title("GTA 6", [], "A title"), "A title")
        self.assertEqual(search_title("GTA 6", None, "A title"), "A title")

    def test_the_pipeline_asks_for_a_long_draft(self):
        import inspect

        from core import pipeline

        self.assertIn("long_title(", inspect.getsource(pipeline.run_pipeline))

    def test_nobody_searches_this_is_said(self):
        from core.batch_review import PendingDraft, _show

        said: list[str] = []
        draft = PendingDraft(folder="f", meta={"kind": "long", "search_suggestions": [],
                                               "run_id": 1, "topic": "GTA 6 obscure thing",
                                               "title": "t"},
                             script="One. Two.")  # fmt: skip
        _show(draft, 1, 1, said.append)
        text = "\n".join(said)
        self.assertIn("nobody searches this", text)
        self.assertIn("16:9", text)


class LongThumbnailTests(unittest.TestCase):
    """#1731 + #1869: a long video is chosen by its thumbnail - our own frame, three words."""

    def test_a_card_from_our_frame(self):
        from PIL import Image

        from core.series import long_form

        def fake_frame(_video, _at, dest):
            Image.new("RGB", (1280, 720), (30, 30, 60)).save(dest)
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "v_16x9.mp4")
            open(video, "wb").close()
            dest = os.path.join(tmp, "thumb.png")
            with (
                patch.object(long_form, "_frame", side_effect=fake_frame),
                patch.object(long_form, "_duration", return_value=600.0),
            ):
                path = long_form.long_thumbnail(video, "GTA 6 Release Date Everything We Know",
                                                dest, channel_id="tapin",
                                                palette=["#F25CA2"])  # fmt: skip
            self.assertEqual(path, dest)
            with Image.open(dest) as card:
                self.assertEqual(card.size, (1280, 720))
        self.assertLessEqual(len(long_form.three_words("GTA 6 Release Date Everything").split()), 3)

    def test_the_style_is_gtas_palette(self):
        from core.series.long_form import style_palette

        self.assertTrue(style_palette("tapin", "GTA 6 - everything we know"))
        self.assertEqual(style_palette("tapin", "UFC 335 preview"), [])


class PlaylistOrderTests(unittest.TestCase):
    """#1855 (B11.9): the GTA playlist plays the countdown day 21 to day 1."""

    def test_days_in_order(self):
        from core import playlists

        service = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "playlists.json")
            with open(store, "w", encoding="utf-8") as handle:
                json.dump({"ids": {"GTA": "PL1", "Gaming": "PL2"}}, handle)
            with patch("youtube.oauth.token_has_scope", return_value=True):
                for n in (21, 20, 19):
                    playlists.add_to_playlists(service, "tapin", f"vid{n}",
                                               title=f"GTA 6: {n} days to launch - news",
                                               store_path=store)  # fmt: skip
        bodies = [
            c.kwargs["body"]["snippet"] for c in service.playlistItems().insert.call_args_list
        ]
        gta = [b.get("position") for b in bodies if b["playlistId"] == "PL1"]
        gaming = [b.get("position") for b in bodies if b["playlistId"] == "PL2"]
        self.assertEqual(gta, [0, 1, 2])
        self.assertEqual(gaming, [None, None, None])

    def test_a_countdown_title_names_its_playlist(self):
        from core.series.countdown import countdown_playlist

        self.assertEqual(countdown_playlist("tapin", "GTA 6: 1 day to launch - news"), "GTA")
        self.assertEqual(countdown_playlist("tapin", "GTA 6 leaks a map"), "")


if __name__ == "__main__":
    unittest.main()
