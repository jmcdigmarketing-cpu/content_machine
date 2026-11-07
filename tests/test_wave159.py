"""Wave 159 (2026-11-07) - the operator's "next 10", and one defect.

Defect: a series idea naming a coming card was drafted as a preview. #1669 public Shorts a week;
#1692 a format rotates out; #1614 trades and signings; #1680 explainers for coming events; #1651 a
Week in Review Short; #1663 the worker every 5 minutes; #1799 a cheaper voice on news Shorts as a
trial; #1702 / #1703 / #1710 the channel page.
"""

from __future__ import annotations

import inspect
import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.batch_generation
import core.best_bet
import core.chapter_shorts
import core.success.formats
import core.success.lanes
import core.tts
import jobs.fast_lane
import publishing.channel_page as page

UTC = timezone.utc
NOW = datetime(2026, 11, 7, 20, 0, tzinfo=UTC)


def _pick(topic, source):
    return {"offered": [{"topic": topic, "source": source}], "picked": 1}


class SeriesShapeDefectTests(unittest.TestCase):
    """Live 11-07: "Gane vs. Hokit: who wins at UFC 334?" named the card and was drafted as a preview."""

    def test_a_series_source_keeps_its_own_shape(self):
        keeps = core.batch_generation.keeps_own_shape
        for source in ("debate", "long", "explainer", "profile", "part2", "patch"):
            self.assertTrue(keeps(source), source)
        for source in ("schedule", "trending", ""):
            self.assertFalse(keeps(source), source)

    def test_no_preview_brief_for_the_debate_or_the_match_up(self):
        topic = "Gane vs. Hokit: who wins at UFC 334?"
        with patch("core.batch_generation.draft_brief", return_value="PREVIEW") as brief:
            self.assertEqual(core.batch_generation.preview_for(topic, _pick(topic, "debate"),
                                                               upcoming=True), "")  # fmt: skip
            long_topic = "UFC 334: Gane vs. Hokit - how they match up"
            self.assertEqual(core.batch_generation.preview_for(long_topic, _pick(long_topic, "long"),
                                                               upcoming=True), "")  # fmt: skip
            game = "Bills at Chiefs"
            self.assertEqual(core.batch_generation.preview_for(game, _pick(game, "schedule"),
                                                               upcoming=True), "PREVIEW")  # fmt: skip
        self.assertEqual(brief.call_count, 1)
        self.assertIn("preview_for(topic, best_bet, upcoming=upcoming)",
                      inspect.getsource(core.batch_generation.generate_draft))  # fmt: skip


class VolumeLaneTests(unittest.TestCase):
    """#1669 (B03.23): public Shorts a week (target 21) with organic views per Short not falling."""

    def test_last_weeks_count_and_the_run(self):
        weeks = iter([{"days": 7, "shorts": 22, "per_short": 60, "n": 9, "organic_a_day": 1},
                      {"days": 7, "shorts": 21, "per_short": 64, "n": 9, "organic_a_day": 1},
                      {"days": 7, "shorts": 23, "per_short": 70, "n": 9, "organic_a_day": 1},
                      {"days": 7, "shorts": 21, "per_short": 72, "n": 9, "organic_a_day": 1}])  # fmt: skip
        with patch("core.success.cadence.window_stats", side_effect=lambda *a, **k: next(weeks)):
            line = core.success.lanes.shorts_week_lane([], today=date(2026, 11, 9))
        self.assertIn("21 public Shorts last week (2026-W45) against 21", line)
        self.assertIn(
            "72 organic views per Short in its first week against 70 the week before", line
        )
        self.assertIn("3 of 4 weeks at 21", line)

    def test_a_short_week_breaks_the_run(self):
        weeks = iter([{"days": 7, "shorts": s, "per_short": p, "n": 3, "organic_a_day": 1}
                      for s, p in ((21, 60), (21, 64), (21, 66), (14, 90))])  # fmt: skip
        with patch("core.success.cadence.window_stats", side_effect=lambda *a, **k: next(weeks)):
            line = core.success.lanes.shorts_week_lane([], today=date(2026, 11, 9))
        self.assertIn("14 public Shorts last week", line)
        self.assertIn("0 of 4 weeks", line)

    def test_it_is_a_lane_line(self):
        self.assertIn("shorts_week_lane(rows, today=day)",
                      inspect.getsource(core.success.lanes.lane_lines))  # fmt: skip


def _short(fmt, views, days_ago):
    return {"format": fmt, "views7": views, "when": NOW - timedelta(days=days_ago)}


class RotationTests(unittest.TestCase):
    """#1692 (B04.21): a format rotates out after 4 Shorts below the channel median."""

    # median 82.5: the news Shorts hold it up; every debate is under it, one "who is" is not
    SHORTS: ClassVar[list[dict[str, Any]]] = [_short("news", 80 + 5 * i, 40 - i) for i in range(8)] + \
        [_short("debate", v, d) for v, d in ((10, 20), (15, 15), (20, 10), (12, 5))] + \
        [_short("who is", v, d) for v, d in ((200, 12), (10, 9), (15, 6), (12, 3))]  # fmt: skip

    def test_four_below_the_median_rest(self):
        rotated = core.success.formats.rotated_out("tapin", shorts=self.SHORTS, today=NOW.date())
        self.assertEqual(sorted(rotated), ["debate"])

    def test_the_spine_never_rotates_and_a_month_brings_a_retry(self):
        news = [_short("news", v, d) for v, d in ((5, 9), (5, 8), (5, 7), (5, 6))]
        rest = [_short("headline", 100, d) for d in (20, 19, 18, 17)]
        self.assertEqual(core.success.formats.rotated_out("tapin", shorts=news + rest,
                                                          today=NOW.date()), {})  # fmt: skip
        later = (NOW + timedelta(days=30)).date()
        self.assertEqual(
            core.success.formats.rotated_out("tapin", shorts=self.SHORTS, today=later), {}
        )

    def test_a_rotated_formats_ideas_leave_the_night(self):
        bet = core.best_bet.BestBetResult(topic="Gane vs. Hokit: who wins at UFC 334?", domain="ufc",
                                          avg_engaged_rate=0.0, source="debate",
                                          supporting_runs=0, rationale="")  # fmt: skip
        self.assertEqual(core.success.formats.idea_format(bet), "debate")
        self.assertEqual(core.success.formats.without_rotated([bet], {"debate": 60.0}), [])
        source = inspect.getsource(core.batch_generation.collect_topics)
        self.assertIn("without_rotated(extra, rotated)", source)
        self.assertIn("without_rotated(ideas, rotated)", source)
        self.assertIn(
            "rotated_out(channel_id)", inspect.getsource(core.batch_generation.generate_draft)
        )

    def test_the_weekly_report_names_them(self):
        with patch("core.success.formats.rotated_out", return_value={"debate": 63.0}):
            lines = core.success.formats.rotation_lines("tapin")
        self.assertIn("Rotated out (#1692): debate", lines[0])
        import analytics.weekly_report

        self.assertIn("rotation_lines(channel_id)", inspect.getsource(analytics.weekly_report))


class TradeTests(unittest.TestCase):
    """#1614 (B01.18): trades and signings of marquee teams as fast ideas."""

    def test_a_marquee_trade_or_signing(self):
        story = core.best_bet.trade_story
        self.assertTrue(story("Cowboys sign Micah Parsons to 4-year, $188M extension", ["Cowboys"]))
        self.assertTrue(story("Lakers acquire a 3-and-D wing in a three-team trade", ["Lakers"]))
        self.assertFalse(story("Cowboys beat the Eagles 24-20", ["Cowboys"]))
        self.assertFalse(story("Bills sign a backup kicker", ["Cowboys"]))
        self.assertTrue(story("Lakers agree to terms with Austin Reaves", ["Lakers"]))

    def test_a_fight_agreed_or_images_released_are_not_trades(self):
        # Live 11-07, the build's own read of the pool
        story = core.best_bet.trade_story
        self.assertFalse(story("Dana White: 'Islam Makhachev verbally agreed to fight at UFC 336",
                               ["Islam Makhachev"]))  # fmt: skip
        self.assertFalse(story("GTA 6: Lots Of New Images Have Been Released", ["GTA 6"]))

    def test_a_contract_is_not_a_shopping_headline(self):
        commerce = core.best_bet._is_commerce_headline
        self.assertFalse(commerce("Cowboys sign Micah Parsons to 4-year, $188M extension"))
        self.assertFalse(commerce("Lakers agree to a deal with Austin Reaves"))
        self.assertTrue(commerce("Black Friday deal: PS5 Pro for $399"))
        self.assertTrue(commerce("GameStop trade-in offer: $50 credit for your PS5"))

    def test_the_fast_lane_takes_it_as_news(self):
        self.assertIn("trade", jobs.fast_lane.NEWS_KINDS)
        pool = [{"topic": "Cowboys sign Micah Parsons to 4-year, $188M extension",
                 "outlets": ["ESPN", "NFL.com", "CBS"], "first": NOW - timedelta(minutes=20),
                 "domain": "nfl"}]  # fmt: skip
        with (
            patch("core.best_bet.marquee_names", return_value=["Cowboys"]),
            patch("jobs.fast_lane._drafted", return_value=False),
        ):
            found = jobs.fast_lane.quick_stories("tapin", now=NOW, pool=pool, done=set(), week=[])
        self.assertEqual(found["kind"], "trade")

    def test_it_leads_the_night_above_fight_week(self):
        def bet(topic):
            return core.best_bet.BestBetResult(topic=topic, domain="nfl", avg_engaged_rate=0.0,
                                               source="trending", supporting_runs=0, rationale="")  # fmt: skip

        ideas = [bet("UFC 334 weigh-ins set"), bet("Cowboys sign Micah Parsons to an extension")]
        with (
            patch("core.best_bet.marquee_names", return_value=["Cowboys"]),
            patch("core.best_bet.crossover_names", return_value=[]),
            patch("core.series.dated.launch_names", return_value=[]),
        ):
            led = core.batch_generation.lead_first(ideas, "tapin", week=["UFC 334"])
        self.assertEqual(led[0].topic, "Cowboys sign Micah Parsons to an extension")


class ExplainerTests(unittest.TestCase):
    """#1680 (B04.9): 'In 60 seconds' explainers for coming events."""

    BOARD: ClassVar[dict[str, Any]] = {"leagues": [{"calendar": [
        {"label": "UFC 334: Gane vs. Hokit", "startDate": "2026-11-15T01:00Z"},
        {"label": "UFC Fight Night: Walker vs. Rountree", "startDate": "2026-11-09T01:00Z"}]}]}  # fmt: skip

    def _ideas(self, now, drafted=False):
        import core.series.explainers as explainers

        with patch.dict(os.environ, {"EXPLAINERS": "true"}):
            return explainers.explainer_ideas("tapin", now=now, board=self.BOARD,
                                              fetch=lambda *a, **k: {},
                                              headlines=lambda *a: [],
                                              drafted=lambda *_a: drafted)  # fmt: skip

    def test_a_numbered_card_two_to_five_days_out(self):
        ideas = self._ideas(datetime(2026, 11, 11, 12, tzinfo=UTC))
        self.assertEqual([i.topic for i in ideas], ["UFC 334 in 60 seconds: what to know"])
        self.assertEqual(ideas[0].source, "explainer")
        self.assertIn("Gane vs. Hokit is its main event", ideas[0].facts[0])
        self.assertEqual(self._ideas(datetime(2026, 11, 11, 12, tzinfo=UTC), drafted=True), [])
        self.assertEqual(self._ideas(datetime(2026, 11, 14, 12, tzinfo=UTC)), [])  # under 2 days

    def test_an_award_in_the_window(self):
        ideas = self._ideas(datetime(2026, 12, 8, 12, tzinfo=UTC))
        self.assertEqual(
            [i.topic for i in ideas], ["The Game Awards 2026 in 60 seconds: what to know"]
        )

    def test_off_in_the_suite(self):
        import core.series.explainers as explainers

        self.assertEqual(explainers.explainer_ideas("tapin", board=self.BOARD), [])

    def test_explainer_intent_at_about_60_seconds(self):
        from core.angle_intent import ANGLE_EXPLAINER

        self.assertEqual(core.batch_generation.draft_intent(own_idea=False, preview="",
                                                            source="explainer"), ANGLE_EXPLAINER)  # fmt: skip
        self.assertEqual(core.batch_generation.EXPLAINER_WORDS, (165, 200))
        self.assertIn("EXPLAINER_WORDS", inspect.getsource(core.batch_generation.generate_draft))
        self.assertIn("explainer_ideas(channel_id)",
                      inspect.getsource(core.batch_generation.collect_topics))  # fmt: skip
        self.assertEqual(
            core.success.formats.run_format(
                {"best_bet": _pick("UFC 334 in 60 seconds: what to know", "explainer")}
            ),
            "explainer",
        )


class WeekReviewShortTests(unittest.TestCase):
    """#1651 (B03.5): each Week in Review deep dive yields one chapter Short."""

    def _run(self, run_id, **features):
        return SimpleNamespace(id=run_id, mp3_path=__file__, mp4_path=__file__, title=f"run {run_id}",
                               features_json=json.dumps(features))  # fmt: skip

    def _go(self, done=(), used=()):
        wir = self._run(400, compilation={"week": "2026-11-02", "runs": [301, 302, 303, 304, 305]})
        runs = {r: self._run(r) for r in (301, 302, 303, 304, 305)}
        made = []

        def make(_c, plan, extra=None):
            made.append((plan, extra))
            return 501, "x.mp4"

        repo = SimpleNamespace(get=lambda rid: runs.get(int(rid)))
        with (
            patch.dict(os.environ, {"WIR_SHORT": "true"}),
            patch.object(core.chapter_shorts, "_public_compilations", return_value=[(None, wir)]),
            patch.object(core.chapter_shorts, "_cut_parents", return_value=(set(done), set(used))),
            patch.object(core.chapter_shorts, "get_content_run_repository", return_value=repo),
            patch.object(core.chapter_shorts, "load_word_timings", return_value=[{"word": "a"}]),
            patch("video.hook_copy.run_opening", return_value=""),
            patch("video.hook_copy.hook_offset", return_value=0.5),
        ):
            lines = core.chapter_shorts.week_review_short(
                "tapin", make=make, queue=lambda rid, _c: 77,
                plan=lambda cand: {"run_id": int(cand["run"].id), "sentence": "A new hook"})  # fmt: skip
        return lines, made

    def test_the_top_deep_dive_cut_with_a_new_hook(self):
        lines, made = self._go()
        self.assertEqual(made[0][0]["run_id"], 305)  # deep dive #1 plays last
        self.assertEqual(made[0][1], {"short_source": "chapter_cut", "parent_run_id": 400,
                                      "chapter_index": 0, "week_review_cut": True})  # fmt: skip
        self.assertIn("run 501 from deep dive #1", lines[0])

    def test_once_per_week_in_review_and_never_a_short_already_used(self):
        self.assertEqual(self._go(done={400}), ([], []))
        _lines, made = self._go(used={305})
        self.assertEqual(made[0][0]["run_id"], 304)

    def test_a_cut_of_an_older_short_is_not_in_next_weeks_compilation(self):
        from video.week_compile import _new_short

        self.assertTrue(_new_short({"domain": "nfl"}))
        for key in ("compilation", "rehook_of", "recut_of", "week_review_cut"):
            self.assertFalse(_new_short({key: {"run_id": 1}}), key)

    def test_off_in_the_suite_and_called_by_overnight(self):
        import core.overnight

        self.assertEqual(core.chapter_shorts.week_review_short("tapin"), [])
        self.assertIn(
            "week_review_short(channel)", inspect.getsource(core.overnight._run_overnight_body)
        )


class WorkerCadenceTests(unittest.TestCase):
    """#1663 (B03.17): the upload worker every 5 minutes for fast-lane jobs."""

    def test_every_five_minutes_and_the_lane_looks_every_ten(self):
        from core import nightly_task

        self.assertEqual(nightly_task.WORKER_EVERY_MINUTES, 5)
        argv = nightly_task.worker_install_argv(python="py", repo="r")
        self.assertEqual(argv[argv.index("/MO") + 1], "5")
        self.assertEqual(jobs.fast_lane.CHECK_MINUTES, 10)


class VoiceTrialTests(unittest.TestCase):
    """#1799 (B09.3): a cheaper voice on news Shorts as an automated arm."""

    def test_balanced_within_the_length_arm(self):
        from core.angle_intent import ANGLE_NEWS
        from core.voice.trial import voice_trial_arm

        length = [{"run_id": 1, "arm": "format"}, {"run_id": 2, "arm": "learned"},
                  {"run_id": 3, "arm": "format"}]  # fmt: skip
        voice = [{"run_id": 1, "arm": "piper"}, {"run_id": 2, "arm": "piper"},
                 {"run_id": 3, "arm": "elevenlabs"}]  # fmt: skip
        day = date(2026, 11, 9)
        with patch.dict(os.environ, {"VOICE_TRIAL": "true"}):
            self.assertEqual(voice_trial_arm("tapin", ANGLE_NEWS, length_arm="format", today=day,
                                             rows=voice, length_rows=length), "piper")  # fmt: skip
            self.assertEqual(voice_trial_arm("tapin", ANGLE_NEWS, length_arm="learned", today=day,
                                             rows=voice, length_rows=length), "elevenlabs")  # fmt: skip
            self.assertIsNone(
                voice_trial_arm("tapin", "preview", today=day, rows=[], length_rows=[])
            )
            self.assertIsNone(voice_trial_arm("tapin", ANGLE_NEWS, today=date(2026, 11, 22),
                                              rows=[], length_rows=[]))  # fmt: skip
        self.assertIsNone(voice_trial_arm("tapin", ANGLE_NEWS, today=day, rows=[], length_rows=[]))

    def test_each_arm_is_what_it_says_at_render(self):
        with (
            patch.object(core.tts, "_resolve_tts_provider", return_value="elevenlabs"),
            patch("core.run_mode._tts_provider_ready", return_value=True),
            patch.object(core.tts, "_piper_mix_every", return_value=6),
            patch.object(core.tts.random, "randrange", return_value=0),  # the mix would pick Piper
        ):
            with core.tts.forced_voice("piper"):
                self.assertTrue(core.tts._should_piper_mix())
            with core.tts.forced_voice("elevenlabs"):
                self.assertFalse(core.tts._should_piper_mix())
            self.assertTrue(core.tts._should_piper_mix())  # no trial: the 1-in-6 mix as before

    def test_the_draft_records_it_and_the_render_reads_it(self):
        from core.voice import trial

        with patch.object(trial, "_rows", return_value=[{"run_id": 9, "arm": "piper"}]):
            self.assertEqual(trial.arm_for_run("tapin", 9), "piper")
            self.assertIsNone(trial.arm_for_run("tapin", 10))
        import core.pipeline

        self.assertIn("forced_voice(arm_for_run(channel_id, content_run_id))",
                      inspect.getsource(core.pipeline.run_media_only))  # fmt: skip
        self.assertIn(
            "VOICE_LEVER, voice_arm", inspect.getsource(core.batch_generation.generate_draft)
        )

    def test_the_weekly_readout(self):
        from core.voice.trial import voice_trial_lines

        shorts = [
            {"run_id": 1, "views7": 80, "stayed": 0.5},
            {"run_id": 2, "views7": 60, "stayed": 0.4},
        ]
        with patch("core.success.formats.measured_shorts", return_value=shorts):
            lines = voice_trial_lines("tapin", arms={1: "elevenlabs", 2: "piper"})
        self.assertIn("elevenlabs 80 (n=1, stayed 50%)", lines[0])
        self.assertIn("piper 60 (n=1, stayed 40%)", lines[0])


class _Call:
    def __init__(self, result=None, log=None, name=""):
        self.result, self.log, self.name = result or {}, log, name

    def execute(self):
        return self.result


class _Service:
    def __init__(self, sections=None, channel=None):
        self.log: list[tuple[str, dict]] = []
        self.sections, self.channel = sections or [], channel or {}

    def channelSections(self):
        svc = self

        class _S:
            def list(self, **kw):
                return _Call({"items": svc.sections})

            def insert(self, **kw):
                svc.log.append(("channelSections.insert", kw))
                return _Call()

        return _S()

    def channels(self):
        svc = self

        class _C:
            def list(self, **kw):
                return _Call({"items": [svc.channel]})

            def update(self, **kw):
                svc.log.append(("channels.update", kw))
                return _Call()

        return _C()

    def playlistItems(self):
        svc = self

        class _P:
            def insert(self, **kw):
                svc.log.append(("playlistItems.insert", kw))
                return _Call()

        return _P()


CHANNEL = {"id": "UC1", "brandingSettings": {"channel": {"description": "old", "keywords": "gaming ufc",
                                                        "country": "US"}}}  # fmt: skip
IDS = {"GTA": "PLg", "UFC / MMA": "PLu", "Full Videos": "PLf", "Week in Review": "PLw"}


class ChannelPageTests(unittest.TestCase):
    """#1702 / #1703 / #1710: the channel page."""

    def setUp(self):
        p = patch.object(page, "record_call")
        p.start()
        self.addCleanup(p.stop)

    def test_sections_in_order_only_with_a_playlist(self):
        wanted = page.wanted_sections("tapin", ids=IDS, filled=set(IDS))
        self.assertEqual(
            [n for n, _p in wanted], ["Week in Review", "GTA", "UFC / MMA", "Full Videos"]
        )
        shown = [{"contentDetails": {"playlists": ["PLg"]}}]
        self.assertEqual([n for n, _p in page.missing_sections(shown, wanted)],
                         ["Week in Review", "UFC / MMA", "Full Videos"])  # fmt: skip

    def test_a_dry_run_writes_nothing_and_apply_adds_the_missing(self):
        svc = _Service(sections=[{"contentDetails": {"playlists": ["PLg"]}}])
        with patch.object(
            page,
            "wanted_sections",
            return_value=page.wanted_sections("tapin", ids=IDS, filled=set(IDS)),
        ):
            dry = page.sync_sections(svc, "tapin", apply=False)
            self.assertEqual(svc.log, [])
            self.assertIn('would add "Week in Review"', dry[0])
            page.sync_sections(svc, "tapin", apply=True)
        inserts = [kw for name, kw in svc.log if name == "channelSections.insert"]
        self.assertEqual(len(inserts), 3)
        self.assertEqual(inserts[0]["body"]["snippet"]["position"], 0)  # the Week in Review first
        self.assertEqual(inserts[0]["body"]["contentDetails"]["playlists"], ["PLw"])

    def test_the_description_says_when_and_why_under_1000(self):
        text = page.channel_description("tapin")
        self.assertLessEqual(len(text), 1000)
        self.assertIn("every Sunday at 7 PM ET", text)
        self.assertIn("noon and 10 PM ET", text)
        self.assertIn("AI voice", text)
        self.assertIn("Subscribe", text)

    def test_only_the_description_and_trailer_change(self):
        body = page.branding_update(CHANNEL, description="new", trailer="vidW")
        self.assertEqual(body["channel"], {"description": "new", "keywords": "gaming ufc", "country": "US",
                                           "unsubscribedTrailer": "vidW"})  # fmt: skip
        svc = _Service(channel=json.loads(json.dumps(CHANNEL)))
        with patch("video.week_compile.latest_public_compilation", return_value="vidW"):
            self.assertEqual(len(page.sync_branding(svc, "tapin", apply=False)), 2)
            self.assertEqual(svc.log, [])
            page.sync_branding(svc, "tapin", apply=True)
        sent = svc.log[0][1]["body"]
        self.assertEqual(sent["id"], "UC1")
        self.assertEqual(sent["brandingSettings"]["channel"]["keywords"], "gaming ufc")
        self.assertEqual(sent["brandingSettings"]["channel"]["unsubscribedTrailer"], "vidW")

    def test_the_weekly_trailer_refresh_leaves_the_description(self):
        svc = _Service(channel=json.loads(json.dumps(CHANNEL)))
        with patch("video.week_compile.latest_public_compilation", return_value="vidW"):
            page.sync_branding(svc, "tapin", apply=True, trailer="vidW", with_description=False)
        self.assertEqual(svc.log[0][1]["body"]["brandingSettings"]["channel"]["description"], "old")
        self.assertEqual(page.refresh_page("tapin", service=svc), [])  # off in the suite

    def test_a_week_in_review_naming_gta_joins_its_own_playlist_first(self):
        from core.playlists import playlists_for

        self.assertEqual(playlists_for("tapin", "The Week in Review: GTA 6's big week",
                                       tags=["week in review"])[0], "Week in Review")  # fmt: skip
        self.assertEqual(
            playlists_for("tapin", "Picks, graded: the week of Nov 2")[0], "Picks, graded"
        )
        self.assertEqual(playlists_for("tapin", "GTA 6 trailer three")[0], "GTA")

    def test_an_ended_sign_in_says_what_to_do(self):
        # Live 11-07: the sign-in had ended and the dry run died on 'NoneType' ... 'channelSections'
        with (
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=None),
        ):
            lines = page.channel_page_lines("tapin", apply=False)
        self.assertEqual(len(lines), 1)
        self.assertIn(
            "no usable YouTube sign-in - py -m youtube.oauth_setup --channel tapin", lines[0]
        )

    def test_ops_and_the_worker_call_it(self):
        import jobs.worker
        import scripts.ops

        self.assertIn(
            "channel_page_lines(args.channel", inspect.getsource(scripts.ops.cmd_channel_page)
        )
        self.assertIn("_channel_page()", inspect.getsource(jobs.worker.main))
        self.assertIn("refresh_page(channel)", inspect.getsource(jobs.worker._channel_page))


class PageFinishTests(unittest.TestCase):
    """#2019, live 11-07 - the first `ops channel-page --apply`: "Full Videos" went up as an empty
    section, and the Week in Review's section (first on the page, #1703) could not go up at all -
    its playlist did not exist yet, and nothing ran the sections again once it did. The worker
    now finishes the page, once a day, calling YouTube only for what is due."""

    def setUp(self):
        import shutil
        import tempfile

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.store = os.path.join(tmp, "playlists_tapin.json")
        for target, value in (
            ("publishing.channel_page.record_call", lambda *a, **k: None),
            ("core.playlists.record_call", lambda *a, **k: None),
            ("core.playlists.store_path_for", lambda cid: self.store),
            ("youtube.oauth.token_has_scope", lambda *a, **k: True),
            ("publishing.snippet_update.manage_scope_problem", lambda cid: ""),
            ("video.week_compile.latest_public_compilation", lambda cid: "vidW"),
        ):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict(os.environ, {"CHANNEL_PAGE": "true"})
        p.start()
        self.addCleanup(p.stop)

    def _store(self, data):
        with open(self.store, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_an_empty_playlist_waits_for_its_section(self):
        wanted = page.wanted_sections("tapin", ids=IDS, filled={"GTA", "Week in Review"})
        self.assertEqual([n for n, _p in wanted], ["Week in Review", "GTA"])
        self._store({"ids": IDS, "added": {"vidG": ["GTA"], "vidU": []}})
        self.assertEqual([n for n, _p in page.wanted_sections("tapin")], ["GTA"])

    def test_the_worker_finishes_the_page_once_a_day(self):
        # the first Week in Review went up before its playlist existed, and before #1736
        self._store({"ids": IDS, "added": {"vidG": ["GTA"], "vidW": ["GTA"]}})
        svc = _Service(sections=[{"contentDetails": {"playlists": ["PLg"]}}],
                       channel=json.loads(json.dumps(CHANNEL)))  # fmt: skip
        lines = page.refresh_page("tapin", service=svc, today="2026-11-08")
        joined = [kw["body"]["snippet"]["playlistId"] for n, kw in svc.log
                  if n == "playlistItems.insert"]  # fmt: skip
        self.assertEqual(sorted(joined), ["PLf", "PLw"])  # its own playlist and Full Videos
        sections = [kw["body"] for n, kw in svc.log if n == "channelSections.insert"]
        self.assertEqual([b["contentDetails"]["playlists"] for b in sections], [["PLw"], ["PLf"]])
        self.assertEqual(sections[0]["snippet"]["position"], 0)  # the Week in Review first
        update = [kw["body"] for n, kw in svc.log if n == "channels.update"]
        self.assertEqual(update[0]["brandingSettings"]["channel"]["unsubscribedTrailer"], "vidW")
        self.assertEqual(update[0]["brandingSettings"]["channel"]["description"], "old")
        self.assertTrue(any('added "Week in Review"' in line for line in lines), lines)
        calls = len(svc.log)
        self.assertEqual(page.refresh_page("tapin", service=svc, today="2026-11-08"), [])
        self.assertEqual(len(svc.log), calls)  # once a day

    def test_a_day_with_nothing_due_calls_nothing(self):
        self._store({"ids": IDS, "added": {"vidW": ["Full Videos", "GTA", "Week in Review"]},
                     "sections": ["PLw", "PLg", "PLf"], "trailer": "vidW"})  # fmt: skip
        with patch("youtube.oauth.get_youtube_service") as factory:
            self.assertEqual(page.refresh_page("tapin", today="2026-11-09"), [])
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
