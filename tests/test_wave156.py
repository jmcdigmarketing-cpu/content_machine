"""Wave 156 (2026-11-06) - the next five, before W4's freeze.

#1605 a subject a casual fan knows (Wikipedia's 30-day pageviews above a floor) passes the topic
gate; #1629 a game's stills count as its footage, the matching edition wins and another edition
under a story is flagged; #1686 "Who is ...?" for a name that just trended; #1652 a Short past
300 organic views re-cut with a new hook 14 days on; #1666 overnight's draft step also at 1 PM.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import apis.wikipedia_pageviews_api as wiki
import assets.clip_ingest
import assets.clip_tags
import assets.footage_gaps
import assets.local_provider
import core.batch_generation
import core.best_bet

UTC = timezone.utc


class KnownSubjectTests(unittest.TestCase):
    """#1605 (B01.9): "the best Shorts tell a big subject plainly" - a one-outlet story about a
    subject a casual fan knows passes the gate the marquee list alone held it at."""

    VIEWS: ClassVar[dict[str, int]] = {"Derrick_Henry": 134_234, "Josh_Hokit": 72_794}

    def _fetch(self, article):
        return self.VIEWS.get(article)

    def test_a_name_above_the_floor_is_known(self):
        found = wiki.known_subject("Frustrated Derrick Henry responds to trade rumors",
                                   fetch=self._fetch)  # fmt: skip
        self.assertEqual(found, ("Derrick Henry", 134_234))

    def test_a_name_below_the_floor_is_not(self):
        self.assertEqual(wiki.known_subject("Josh Hokit releases a diss track", fetch=self._fetch),
                         ("", 0))  # fmt: skip

    def test_the_floor_is_a_hundred_thousand_in_thirty_days(self):
        self.assertEqual(wiki.KNOWN_FLOOR, 100_000)

    def test_lookups_stop_at_the_cap(self):
        asked = []
        wiki.known_subject("Aaa Bbb and Ccc Ddd and Eee Fff and Ggg Hhh meet",
                           fetch=lambda a: asked.append(a), limit=2)  # fmt: skip
        self.assertEqual(len(asked), 2)

    def test_the_signal_reads_thirty_days(self):
        seen = []

        class _Resp:
            status_code = 200

            def json(self):
                return {"items": [{"views": 10, "timestamp": "2026110100"}] * 30}

        def get(url, **_kw):
            seen.append(url)
            return _Resp()

        with patch.object(wiki.requests, "get", side_effect=get), \
                patch.object(wiki, "check"):  # fmt: skip
            got = wiki._fetch_pageviews("Derrick_Henry")
        start, end = seen[0].rstrip("/").split("/")[-2:]
        days = (datetime.strptime(end, "%Y%m%d") - datetime.strptime(start, "%Y%m%d")).days
        self.assertEqual(days, 30)
        self.assertEqual(got["views_30d"], 300)

    def test_the_gate_passes_a_known_subject(self):
        gate = core.batch_generation.story_passes_gate
        topic = "Frustrated Derrick Henry responds to trade rumors"
        self.assertFalse(gate(topic, source="trending", outlets=1, names=[]))
        self.assertTrue(gate(topic, source="trending", outlets=1, names=[], known=lambda t: True))
        self.assertFalse(gate(topic, source="trending", outlets=1, names=[], known=lambda t: False))

    def test_collect_topics_keeps_a_known_subject(self):
        bet = core.best_bet.BestBetResult(
            topic="Frustrated Derrick Henry responds to trade rumors", domain="nfl",
            avg_engaged_rate=0.0, source="trending", supporting_runs=0, rationale="", outlets=1)  # fmt: skip
        with (
            patch.dict(os.environ, {"KNOWN_SUBJECTS": "true"}),
            patch("apis.wikipedia_pageviews_api.known_subject",
                  return_value=("Derrick Henry", 134_234)),
            patch("core.best_bet.get_idea_menu", return_value=([bet], [])),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.best_bet.crossover_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[]),
            patch("core.series.recap.debate_ideas", return_value=[]),
            patch("core.series.last_night.last_night_ideas", return_value=[]),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.series.recap.fight_week", return_value=[]),
        ):  # fmt: skip
            topics = core.batch_generation.collect_topics("tapin", count=1)
        self.assertEqual(topics, ["Frustrated Derrick Henry responds to trade rumors"])


class FootageMatchTests(unittest.TestCase):
    """#1629 (B02.8): another game's gameplay under a story - the matching footage or stills win."""

    def test_the_matching_edition_wins(self):
        pick = assets.local_provider._keyword_choose_folder
        folders = [os.path.join("lib", "GTA V"), os.path.join("lib", "GTA 6")]
        self.assertEqual(pick("GTA 6 online mode may repeat old mistakes", folders), folders[1])
        self.assertEqual(pick("GTA 6 online mode may repeat old mistakes", list(reversed(folders))),
                         folders[1])  # fmt: skip
        roman = [os.path.join("lib", "GTA V"), os.path.join("lib", "GTA VI")]
        self.assertEqual(pick("GTA 6 trailer three", roman), roman[1])
        self.assertEqual(pick("GTA V mods are back", roman), roman[0])

    def test_last_years_footage_still_serves_alone(self):
        pick = assets.local_provider._keyword_choose_folder
        only = [os.path.join("lib", "GTA V")]
        self.assertEqual(pick("GTA 6 online mode", only), only[0])

    def test_an_older_edition_under_a_story_is_flagged(self):
        gap = assets.footage_gaps.edition_gap
        self.assertIn("GTA V", gap("GTA 6 online mode may repeat GTA Online's mistakes", "GTA V"))
        self.assertIn("GTA 6", gap("GTA 6 online mode may repeat GTA Online's mistakes", "GTA V"))
        self.assertEqual(gap("GTA V mods are back", "GTA V"), "")
        self.assertEqual(gap("Madden 26 ratings drop", "Madden 26"), "")
        self.assertEqual(gap("Fortnite adds a map", "Fortnite"), "")

    def test_a_still_clip_is_never_a_menu_by_motion(self):
        ui = assets.clip_tags.is_ui_clip
        self.assertFalse(ui(os.path.join("x", "Spider-Man shot.still.mp4"), {"motion": 1.2}))
        self.assertTrue(ui(os.path.join("x", "Spider-Man shot.mp4"), {"motion": 1.2}))

    def test_the_still_command_zooms_to_a_vertical_clip(self):
        from assets.stills import STILL_SECONDS, still_argv

        argv = still_argv("a.png", "a.still.mp4")
        self.assertEqual(argv[0], "ffmpeg")
        self.assertIn("-loop", argv)
        graph = argv[argv.index("-vf") + 1]
        self.assertIn("zoompan", graph)
        self.assertIn("1080x1920", graph)
        self.assertIn(f"{STILL_SECONDS:g}", argv)
        self.assertEqual(argv[-1], "a.still.mp4")

    def test_each_still_becomes_one_clip_once(self):
        from assets.stills import make_still_clips

        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, "solo games", "Marvel's Spider-Man 2")
            os.makedirs(game)
            for name in ("a.png", "b.jpg", "b.still.mp4", "notes.txt"):
                with open(os.path.join(game, name), "w", encoding="utf-8") as fh:
                    fh.write("x")
            made_by = []

            def run(argv, **_kw):
                made_by.append(argv)
                with open(argv[-1], "w", encoding="utf-8") as fh:
                    fh.write("x")
                return SimpleNamespace(returncode=0)

            made = make_still_clips(root, run=run)
            again = make_still_clips(root, run=run)
        self.assertEqual([os.path.basename(p) for p in made], ["a.still.mp4"])
        self.assertEqual(again, [])
        self.assertEqual(len(made_by), 1)

    def test_a_stills_only_folder_becomes_footage_in_the_library_step(self):
        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, "solo games", "Marvel's Spider-Man 2")
            os.makedirs(game)
            with open(os.path.join(game, "shot.png"), "w", encoding="utf-8") as fh:
                fh.write("x")

            def run(argv, **_kw):
                with open(argv[-1], "w", encoding="utf-8") as fh:
                    fh.write("x")
                return SimpleNamespace(returncode=0)

            index = os.path.join(root, "index.json")
            with (
                patch.dict(os.environ, {"STILL_CLIPS": "true"}),
                patch("assets.stills.subprocess.run", side_effect=run),
                patch.object(assets.clip_ingest, "CLIP_INDEX_FILE", index),
                patch("assets.clip_bands.measure_bands", return_value={}),
                patch("assets.clip_tags.measure_motion", return_value=1.0),
            ):
                tally = assets.clip_ingest.measure_library(library_root=root)
            self.assertTrue(os.path.isfile(os.path.join(game, "shot.still.mp4")))
            self.assertEqual(tally.get("stills"), 1)
            self.assertIn(game, assets.local_provider._get_subfolders(root))


NOW = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)


def _row(topic, outlets, hours_ago=5, domain="ufc"):
    return {"topic": topic, "outlets": outlets, "first": NOW - timedelta(hours=hours_ago),
            "domain": domain}  # fmt: skip


class WhoIsTests(unittest.TestCase):
    """#1686 (B04.15): "Who is ...?" in 45 s for a name that just trended."""

    POOL: ClassVar[list[dict]] = [
        _row(
            "UFC 334: Fight card, date, complete guide as Ciryl Gane takes on Josh Hokit",
            ["ESPN", "MMA Junkie", "Bloody Elbow"],
        ),
        _row(
            "Josh Hokit releases a diss track targeting top UFC heavyweights",
            ["MMA Fighting", "Sherdog"],
            hours_ago=30,
        ),
        _row("Islam Makhachev reveals his mother may have the final say", ["ESPN", "BBC", "MMA"]),
        _row("Old news about Josh Hokit", ["A", "B", "C"], hours_ago=80),
    ]

    def _ideas(self, views=None, describe="American mixed martial artist", pool=None):
        import core.series.profiles as profiles

        seen = views if views is not None else {"Josh_Hokit": {"views": 72_794, "rise": 2.1}}
        with (
            patch.dict(os.environ, {"WHO_IS": "true"}),
            patch("core.best_bet.marquee_names", return_value=["Islam Makhachev"]),
            patch("core.batch_generation.series_drafted", return_value=False),
        ):
            return profiles.profile_ideas("tapin", now=NOW, pool=pool or self.POOL,
                                          read=lambda a: seen.get(a),
                                          describe=lambda a: describe)  # fmt: skip

    def test_names_on_three_outlets_in_two_days(self):
        from core.series.profiles import trending_names

        found = trending_names(self.POOL, ["Islam Makhachev"], now=NOW)
        names = [f[0] for f in found]
        self.assertEqual(names[0], "Josh Hokit")
        self.assertEqual(found[0][2], 5)  # ESPN, MMA Junkie, Bloody Elbow, MMA Fighting, Sherdog
        self.assertNotIn("Islam Makhachev", names)

    def test_a_rising_unknown_person_gets_a_who_is(self):
        ideas = self._ideas()
        self.assertEqual([i.topic for i in ideas], ["Who is Josh Hokit?"])
        self.assertEqual(ideas[0].source, "profile")
        self.assertEqual(ideas[0].domain, "ufc")
        self.assertIn("American mixed martial artist", ideas[0].facts[0])
        self.assertTrue(any("diss track" in f for f in ideas[0].facts))

    def test_a_name_fans_know_is_no_who_is(self):
        self.assertEqual(self._ideas(views={"Josh_Hokit": {"views": 134_000, "rise": 2.1}}), [])

    def test_a_name_not_rising_is_no_who_is(self):
        self.assertEqual(self._ideas(views={"Josh_Hokit": {"views": 52_000, "rise": 1.0}}), [])

    def test_a_team_or_a_place_is_no_who_is(self):
        self.assertEqual(self._ideas(describe="American football team"), [])

    def test_off_by_default_in_the_suite(self):
        import core.series.profiles as profiles

        self.assertEqual(profiles.profile_ideas("tapin", now=NOW, pool=self.POOL), [])

    def test_it_is_news_at_the_short_preset(self):
        from core.angle_intent import ANGLE_NEWS

        self.assertEqual(core.batch_generation.draft_intent(own_idea=False, preview="",
                                                            source="profile"), ANGLE_NEWS)  # fmt: skip
        pick = {"offered": [{"topic": "Who is Josh Hokit?", "source": "profile"}], "picked": 1}
        self.assertEqual(core.batch_generation.profile_length("Who is Josh Hokit?", pick), "1")
        self.assertEqual(core.batch_generation.profile_length("Chiefs trade", {}), "")

    def test_overnight_takes_it_beside_the_nights_ideas(self):
        bet = core.best_bet.BestBetResult(topic="Who is Josh Hokit?", domain="ufc",
                                          avg_engaged_rate=0.0, source="profile",
                                          supporting_runs=0, rationale="")  # fmt: skip
        with (
            patch("core.series.profiles.profile_ideas", return_value=[bet]),
            patch("core.best_bet.get_idea_menu", return_value=([], [])),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.best_bet.crossover_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[]),
            patch("core.series.recap.debate_ideas", return_value=[]),
            patch("core.series.last_night.last_night_ideas", return_value=[]),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.series.recap.fight_week", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=1)
        self.assertEqual(topics, ["Who is Josh Hokit?"])


RUN_126_VARIANTS = json.dumps([
    ["Ben Affleck's Fortnite arguments reveal toxic parenting or generational clash", 69.62],
    ["Fortnite updates may worsen Ben Affleck's online confrontations with teens", 69.62],
    ["Ben Affleck vs Fortnite: A look at celebrity influence on youth gaming culture", 73.22],
    ["Why Ben Affleck keeps losing Fortnite matches to 12-year-olds", 69.62],
])  # fmt: skip


def _word(text, start):
    return {"word": text, "start": start, "end": start + 0.3}


WORDS = [_word("Ben", 0.0), _word("admits.", 0.4), _word("He", 2.0), _word("told", 2.4),
         _word("them.", 2.8), _word("Kids", 10.0), _word("win.", 30.0)]  # fmt: skip


class RehookTests(unittest.TestCase):
    """#1652 (B03.6): a Short past 300 organic views is re-cut with a new hook 14 days later."""

    def setUp(self):
        import video.recut as recut

        self.recut = recut
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mp4 = os.path.join(self.tmp.name, "run126.mp4")
        self.mp3 = os.path.join(self.tmp.name, "run126.mp3")
        for path in (self.mp4, self.mp3):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x")

    def _run(self, run_id=126, **features):
        return SimpleNamespace(
            id=run_id, title="Ben Affleck Gets Destroyed by 12-Year-Olds in Fortnite",
            mp4_path=self.mp4, mp3_path=self.mp3, variants_json=RUN_126_VARIANTS,
            features_json=json.dumps({"hook_text": "Ben Affleck admits 12-year-olds destroy him.",
                                      **features}))  # fmt: skip

    def _row(self, run_id=126, days=21, views=411, paid=0, privacy="public"):
        return SimpleNamespace(
            content_run_id=run_id, privacy_status=privacy, youtube_video_id=f"vid{run_id}",
            published_at=NOW - timedelta(days=days),
            metrics_json=json.dumps({"lifetime_views": views, "paid_views": paid}))  # fmt: skip

    def _candidates(self, rows, runs, done=()):
        repo = SimpleNamespace(
            get=lambda rid: runs.get(rid), list_for_channel=lambda _c: list(done)
        )
        with (
            patch("video.subtitles.load_word_timings", return_value=WORDS),
            patch("video.hook_copy.run_opening", return_value=""),
            patch("video.hook_copy.hook_offset", return_value=0.5),
        ):
            return self.recut.rehook_candidates("tapin", now=NOW, rows=rows, repo=repo)

    def test_a_short_past_300_organic_views_14_days_on(self):
        runs = {126: self._run(), 127: self._run(127), 128: self._run(128), 129: self._run(129)}
        rows = [self._row(), self._row(127, days=10), self._row(128, views=420, paid=200),
                self._row(129, days=40)]  # fmt: skip
        found = self._candidates(rows, runs)
        self.assertEqual([int(c["run"].id) for c in found], [126])
        self.assertEqual(found[0]["organic"], 411)

    def test_a_cut_or_a_short_already_rehooked_is_not_one(self):
        runs = {126: self._run(), 130: self._run(130, short_source="chapter_cut")}
        done = [SimpleNamespace(features_json=json.dumps({"rehook_of": {"run_id": 126}}))]
        self.assertEqual(self._candidates([self._row(), self._row(130)], runs, done), [])

    def test_the_new_hook_is_an_unused_variant_of_twelve_words_or_fewer(self):
        self.assertEqual(self.recut.new_hook(self._run()),
                         "Ben Affleck's Fortnite arguments reveal toxic parenting or generational "
                         "clash")  # fmt: skip
        used = SimpleNamespace(title="Only one", variants_json=json.dumps([["Only one", 70]]),
                               features_json="{}")  # fmt: skip
        self.assertEqual(self.recut.new_hook(used), "")

    def test_a_hook_that_names_no_one_is_not_a_new_hook(self):
        # Live 11-06: run 133's best variant named no one - the Short was Wembanyama at +200.
        run_133 = SimpleNamespace(
            title="2027 NBA Finals & Award Predictions: Wembanyama at +200 for MVP",
            features_json="{}",
            variants_json=json.dumps(
                [["This season's strongest contenders: A breakdown of top teams' strengths.", 76.2],
                 ["Wembanyama at +200: the shortest MVP price ever", 70.0]]))  # fmt: skip
        self.assertEqual(
            self.recut.new_hook(run_133), "Wembanyama at +200: the shortest MVP price ever"
        )
        run_133.variants_json = json.dumps([["This season's strongest contenders, ranked", 76.2]])
        self.assertEqual(self.recut.new_hook(run_133), "")

    def test_it_opens_on_sentence_two_and_runs_to_the_end(self):
        candidate = {"run": self._run(), "organic": 411, "days": 21, "words": WORDS,
                     "offset": 0.5, "video_id": "vid126"}  # fmt: skip
        plan = self.recut.plan_rehook(candidate, duration=45.0)
        self.assertEqual(plan["start"], 2.5)
        self.assertEqual(plan["end"], 45.0)
        self.assertEqual(plan["sentence"], self.recut.new_hook(self._run()))
        self.assertLessEqual(len(plan["title"]), 100)

    def test_one_a_night_queued_for_its_slot(self):
        candidate = {"run": self._run(), "organic": 411, "days": 21, "words": WORDS,
                     "offset": 0.5, "video_id": "vid126"}  # fmt: skip
        queued = []
        with (
            patch.dict(os.environ, {"REHOOK": "true"}),
            patch.object(self.recut, "rehook_candidates", return_value=[candidate, candidate]),
            patch.object(self.recut, "_duration", return_value=45.0),
            patch("core.stale_renders.run_event", return_value=None),
            patch("core.stale_renders.render_age_days", return_value=21),
        ):
            lines = self.recut.rehook_step("tapin", now=NOW, slot_soon=lambda *_a: True,
                                           make=lambda _c, plan: (300, "x.rehook.mp4"),
                                           queue=lambda rid, _c: queued.append(rid) or 91)  # fmt: skip
        self.assertEqual(queued, [300])
        self.assertEqual(len(lines), 1)
        self.assertIn("run 300 from run 126", lines[0])

    def test_no_free_slot_soon_no_rehook(self):
        with patch.dict(os.environ, {"REHOOK": "true"}), \
                patch.object(self.recut, "rehook_candidates") as found:  # fmt: skip
            self.assertEqual(self.recut.rehook_step("tapin", now=NOW, slot_soon=lambda *_a: False),
                             [])  # fmt: skip
        found.assert_not_called()

    def test_a_preview_of_a_played_game_is_not_rehooked(self):
        candidate = {"run": self._run(), "organic": 411, "days": 21, "words": WORDS,
                     "offset": 0.5, "video_id": "vid126"}  # fmt: skip
        made = []
        with (
            patch.dict(os.environ, {"REHOOK": "true"}),
            patch.object(self.recut, "rehook_candidates", return_value=[candidate]),
            patch("core.stale_renders.run_event", return_value=NOW - timedelta(days=3)),
            patch("core.stale_renders.render_age_days", return_value=21),
        ):
            lines = self.recut.rehook_step("tapin", now=NOW, slot_soon=lambda *_a: True,
                                           make=lambda *a: made.append(a) or (1, ""))  # fmt: skip
        self.assertEqual((lines, made), ([], []))

    def test_off_in_the_suite_and_called_by_overnight(self):
        import inspect

        import core.overnight

        self.assertEqual(self.recut.rehook_step("tapin", now=NOW), [])
        self.assertIn("rehook_step(channel)", inspect.getsource(core.overnight._run_overnight_body))


ONE_PM = datetime(2026, 11, 7, 18, 30, tzinfo=UTC)  # 1:30 PM in New York (EST)
SIX_PM = datetime(2026, 11, 7, 23, 0, tzinfo=UTC)


class MiddayTests(unittest.TestCase):
    """#1666 (B03.20): overnight's draft step also at 1 PM, for the evening's news."""

    def setUp(self):
        import jobs.midday as midday

        self.midday = midday
        path = midday.store_path("tapin")
        if os.path.isfile(path):
            os.remove(path)
        self.addCleanup(lambda: os.path.isfile(path) and os.remove(path))
        self.env = patch.dict(os.environ, {"MIDDAY": "true"})
        self.env.start()
        self.addCleanup(self.env.stop)
        for name, value in (("units_left", 9000), ("on_battery", False),
                            ("overnight_running", False)):  # fmt: skip
            p = patch(f"jobs.fast_lane.{name}", return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch("core.overnight_pause.is_paused", return_value=False)
        p.start()
        self.addCleanup(p.stop)

    def _run(self, now=ONE_PM, slots=(SIX_PM,), waiting=0, topics=("Chiefs trade for a receiver",),
             ok=True, held=""):  # fmt: skip
        drafted, rendered = [], []

        def draft(_c, picked, **_kw):
            drafted.extend(picked)
            return [SimpleNamespace(topic=t, ok=ok, run_id=50 + i, error="" if ok else "no LLM")
                    for i, t in enumerate(picked)]  # fmt: skip

        def render(_c, run_id):
            rendered.append(run_id)
            return held, (0 if held else 77)

        lines = self.midday.run_midday(
            "tapin", now=now, slots=lambda *_a: list(slots), waiting=lambda _c: waiting,
            collect=lambda _c, n, _p: list(topics)[:n], draft=draft, render=render,
            slot=lambda _c, _r: (now, ""))  # fmt: skip
        return lines, drafted, rendered

    def test_after_one_it_drafts_renders_and_queues_for_tonight(self):
        lines, drafted, rendered = self._run()
        self.assertEqual(drafted, ["Chiefs trade for a receiver"])
        self.assertEqual(rendered, [50])
        self.assertIn("run 50 rendered, queued for tonight's slot (job 77)", "\n".join(lines))

    def test_once_a_day(self):
        self._run()
        lines, drafted, _r = self._run(now=ONE_PM + timedelta(minutes=15))
        self.assertEqual((lines, drafted), ([], []))

    def test_not_before_one_or_from_five(self):
        self.assertEqual(self._run(now=datetime(2026, 11, 7, 17, 45, tzinfo=UTC))[0], [])
        self.assertEqual(self._run(now=datetime(2026, 11, 7, 22, 5, tzinfo=UTC))[0], [])

    def test_no_free_slot_tonight_drafts_nothing(self):
        lines, drafted, _r = self._run(slots=())
        self.assertEqual(drafted, [])
        self.assertIn("tonight's slots are taken", lines[0])

    def test_two_drafts_at_most_one_a_free_slot_under_the_wait_cap(self):
        topics = ("A story", "B story", "C story")
        self.assertEqual(self._run(topics=topics)[1], ["A story"])
        os.remove(self.midday.store_path("tapin"))
        self.assertEqual(self._run(topics=topics, slots=(SIX_PM, SIX_PM + timedelta(hours=4)))[1],
                         ["A story", "B story"])  # fmt: skip
        os.remove(self.midday.store_path("tapin"))
        lines, drafted, _r = self._run(waiting=8)
        self.assertEqual(drafted, [])
        self.assertIn("8 drafts wait", lines[0])

    def test_a_held_draft_is_not_queued(self):
        lines, _d, _r = self._run(held="held - a claim needs a source")
        self.assertIn("run 50 held - a claim needs a source", "\n".join(lines))
        self.assertNotIn("queued", "\n".join(lines))

    def test_on_battery_or_while_overnight_runs_it_waits(self):
        with patch("jobs.fast_lane.on_battery", return_value=True):
            self.assertEqual(self._run()[0], [])
        with patch("jobs.fast_lane.overnight_running", return_value=True):
            self.assertEqual(self._run()[0], [])

    def test_off_in_the_suite(self):
        self.env.stop()
        self.assertEqual(self.midday.run_midday("tapin", now=ONE_PM), [])
        self.env.start()

    def test_the_render_is_the_fast_lanes_queued_private_for_its_slot(self):
        import core.batch_review

        with patch("jobs.fast_lane._render_and_queue", return_value=("", 9)) as fast:
            self.assertEqual(self.midday._render("tapin", 50), ("", 9))
        self.assertEqual(fast.call_args.kwargs["by"], "midday")
        self.assertIs(fast.call_args.kwargs["queue"], core.batch_review._queue_scheduled)

    def test_news_only_takes_no_series_or_follow_up(self):
        bet = core.best_bet.BestBetResult(topic="Chiefs trade for a receiver", domain="nfl",
                                          avg_engaged_rate=0.0, source="trending",
                                          supporting_runs=0, rationale="", outlets=3)  # fmt: skip
        never = AssertionError("an extra was read")
        with (
            patch("core.best_bet.get_idea_menu", return_value=([bet], [])),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.best_bet.crossover_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", side_effect=never),
            patch("core.series.recap.recap_ideas", side_effect=never),
            patch("core.series.profiles.profile_ideas", side_effect=never),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=never),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.series.recap.fight_week", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=2, news_only=True)
        self.assertEqual(topics, ["Chiefs trade for a receiver"])

    def test_the_worker_pass_runs_it(self):
        import inspect

        import jobs.worker

        self.assertIn("_midday()", inspect.getsource(jobs.worker.main))
        with patch("jobs.midday.run_midday", return_value=["  run 5 rendered, queued for tonight's "
                                                         "slot (job 7)"]), \
                patch("config.channels.active_channel_ids", return_value=["tapin"]), \
                patch.object(jobs.worker, "process_one", side_effect=[True, False]) as one:  # fmt: skip
            self.assertEqual(jobs.worker._midday(), 1)
        self.assertEqual(one.call_count, 2)


if __name__ == "__main__":
    unittest.main()
