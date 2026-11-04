"""Wave 145 (2026-11-02) - the next 15 (decisions 97-98), S15 the shortfall it takes.

Found live the same evening: the Nov 3 countdown (run 226) held for its own day count, drafted on a
"since launch" angle, opening on a viral fan's death - and no night would have drafted the day
again. #1963 "N days before" counts forward; #1964 a rejected countdown day is drafted again and a
past one is dead; #1965 no launch-assuming angle for a game not yet out; #1966 never a death story
(decision 97).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")
ROW = {"id": "gta6-countdown", "kind": "countdown", "subject": "GTA 6",
       "names": ["GTA 6", "GTA VI"], "title": "GTA 6: {n} days to launch",
       "from": "2026-10-29", "until": "2026-11-19", "domain": "gaming"}  # fmt: skip

# Run 226's own facts: the countdown's line and the Nov 1 snippet that was the only anchor left.
RUN226_FACTS = (
    "GTA 6 launches on November 19, 2026 - 16 days from November 3.\n"
    "Today is November 1, and GTA 6 is 18 days from its November 19 launch."
)


# ---- #1963: "N days before <event>" counts forward ------------------------------------------------


class AheadCountTests(unittest.TestCase):
    def test_run226s_own_day_count_is_grounded(self):
        from core.facts.date_math import find_elapsed_mismatches

        script = "Sixteen days before launch, the conversation is about cost, not gameplay."
        self.assertEqual(find_elapsed_mismatches(script, RUN226_FACTS, today=date(2026, 11, 2)), [])

    def test_a_wrong_count_to_launch_is_still_flagged_against_the_launch(self):
        from core.facts.date_math import find_elapsed_mismatches

        found = find_elapsed_mismatches(
            "Ten days before launch, the hype peaks.", RUN226_FACTS, today=date(2026, 11, 2)
        )
        self.assertEqual(len(found), 1)
        self.assertIn("2026-11-19", found[0])
        self.assertIn("away", found[0])

    def test_before_a_past_event_is_not_measured_from_today(self):
        from core.facts.date_math import find_elapsed_mismatches

        facts = "The Knicks completed the trade on March 3, 2024."
        script = "Ten years before the trade, the Knicks were rebuilding."
        self.assertEqual(find_elapsed_mismatches(script, facts, today=date(2026, 11, 2)), [])

    def test_since_still_counts_back(self):
        from core.facts.date_math import find_elapsed_mismatches

        facts = "The Knicks completed the trade on March 3, 2026."
        found = find_elapsed_mismatches(
            "It's been 18 months since the trade.", facts, today=date(2026, 11, 2)
        )
        self.assertEqual(len(found), 1)

    def test_today_may_be_an_iso_string(self):
        from core.facts.date_math import find_elapsed_mismatches, find_meta_mismatches

        script = "Sixteen days before launch, the hype is loud."
        self.assertEqual(find_elapsed_mismatches(script, RUN226_FACTS, today="2026-11-02"), [])
        self.assertEqual(find_meta_mismatches(script, "", RUN226_FACTS, today="2026-11-02"), [])


# ---- #1964: a rejected countdown day is drafted again; a past one is dead -------------------------


class CountdownRedoTests(unittest.TestCase):
    def _idea(self, runs, metas, *, now=datetime(2026, 11, 2, 23, tzinfo=UTC), ahead=1):
        from core.series import countdown

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for i, meta in enumerate(metas):
            folder = os.path.join(tmp.name, f"d{i}")
            os.makedirs(folder)
            with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f)
        repo = SimpleNamespace(list_for_channel=lambda _c: runs)
        with (
            patch.dict(os.environ, {"SERIES_COUNTDOWN": "true"}),
            patch.object(countdown, "series_rows", return_value=[ROW]),
            patch.object(countdown, "channel_zone", return_value=EASTERN),
            patch("core.batch_generation._drafts_dir", return_value=tmp.name),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
        ):
            return countdown.countdown_idea("tapin", now=now, headlines=lambda *_a: [], ahead=ahead)

    @staticmethod
    def _run(run_id, topic, **features):
        return SimpleNamespace(id=run_id, input_topic=topic, selected_topic=topic,
                               features_json=json.dumps(features))  # fmt: skip

    def test_a_rejected_day_is_drafted_again(self):
        topic = "GTA 6: 16 days to launch"
        meta = {"run_id": 226, "topic": topic, "created_at": "2026-11-02T16:53:51",
                "review": {"decision": "rejected", "reason": "other"}}  # fmt: skip
        idea = self._idea([self._run(226, topic)], [meta])
        self.assertIsNotNone(idea)
        self.assertEqual(idea.topic, topic)

    def test_a_retired_render_is_drafted_again(self):
        topic = "GTA 6: 16 days to launch"
        run = self._run(226, topic, retired_at="2026-11-02T18:00:00", retired_why="wrong")
        self.assertIsNotNone(self._idea([run], []))

    def test_a_live_run_still_counts(self):
        topic = "GTA 6: 16 days to launch"
        self.assertIsNone(self._idea([self._run(226, topic)], []))

    def test_a_held_draft_waiting_for_you_still_counts(self):
        topic = "GTA 6: 16 days to launch"
        meta = {"run_id": 226, "topic": topic,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "hold": {"reason": "it names something the facts do not"}}  # fmt: skip
        self.assertIsNone(self._idea([], [meta]))

    def test_a_countdown_past_its_day_is_dead(self):
        from core.batch_review import _is_dead, dead_reason

        meta = {"run_id": 226, "series": "countdown", "topic": "GTA 6: 16 days to launch",
                "event_at": "2026-11-04T05:00:00+00:00",
                "created_at": "2026-11-02T16:53:51"}  # fmt: skip
        why = dead_reason(meta, now=datetime(2026, 11, 4, 6, tzinfo=UTC))
        self.assertTrue(why.startswith("its countdown day has passed"), why)
        self.assertTrue(_is_dead(why))
        self.assertEqual(dead_reason(meta, now=datetime(2026, 11, 3, 6, tzinfo=UTC)), "")


# ---- #1965: no launch-assuming angle for a game not yet out ---------------------------------------


class PreLaunchAngleTests(unittest.TestCase):
    def test_a_countdown_is_news(self):
        from core.angle_intent import ANGLE_NEWS
        from core.batch_generation import draft_intent

        self.assertEqual(draft_intent(own_idea=False, preview="", source="countdown"), ANGLE_NEWS)

    def test_an_unreleased_subject_gets_the_pre_launch_frames(self):
        from apis import topic_variants as tv

        later = {**ROW, "until": "2099-01-01"}  # the frames read today's date
        with patch("core.series.countdown.series_rows", return_value=[later]):
            self.assertTrue(tv.unreleased_subject("GTA 6 Update Cycles", "tapin",
                                                  today=date(2026, 11, 2)))  # fmt: skip
            frames = tv.established_gaming_frames("GTA 6: 16 days to launch", "tapin")
        self.assertNotIn("what_changed_since_launch", frames)
        self.assertNotIn("meta_evolution_analysis", frames)
        self.assertEqual(len(frames), 5)

    def test_a_released_game_keeps_its_frames(self):
        from apis import topic_variants as tv

        with patch("core.series.countdown.series_rows", return_value=[ROW]):
            self.assertFalse(tv.unreleased_subject("GTA 6 launch week", "tapin",
                                                   today=date(2026, 11, 19)))  # fmt: skip
            frames = tv.established_gaming_frames("Marvel Rivals season 5", "tapin")
        self.assertIn("what_changed_since_launch", frames)

    def test_a_frame_key_before_a_quoted_angle_is_stripped(self):
        from apis.topic_variants import _clean_angle_lines

        raw = 'what_changed_since_launch "GTA 6 Update Cycles: A 16-Day Countdown to Launch'
        self.assertEqual(
            _clean_angle_lines(raw, []), ["GTA 6 Update Cycles: A 16-Day Countdown to Launch"]
        )


# ---- #1966: never a death story (decision 97) -----------------------------------------------------


class DeathStoryTests(unittest.TestCase):
    def test_run229s_title_and_run226s_first_line_are_deaths(self):
        from core.authenticity import death_reason

        self.assertTrue(
            death_reason("GTA 6 Community Mourns Loss of Devoted Fan 17 Days Before Launch")
        )
        first = ("Sixteen days out from GTA 6, a fan who went viral for hoping to live long enough "
                 "to play it has *died*. Dexerto reported it.")  # fmt: skip
        self.assertIn("death", death_reason("GTA 6: 16 days to launch", first))

    def test_game_titles_and_sport_words_are_not_deaths(self):
        from core.authenticity import death_words

        for text in ("Red Dead Redemption 2 gets a next-gen patch", "Dead Island 2 tops 10M",
                     "Death Stranding 2 PC date", "Sudden death overtime decides it",
                     "Team deathmatch returns to Black Ops 7", "The hype dies down",
                     "Jets were killed by turnovers", "RIP to the old meta"):  # fmt: skip
            self.assertEqual(death_words(text), [], text)

    def test_a_death_in_the_title_limits_the_render(self):
        from core.authenticity import ad_limit_reason

        why = ad_limit_reason("Mike Ditka dies at 86", "The Bears play Sunday.")
        self.assertIn("death", why)
        self.assertEqual(ad_limit_reason("Bears at Falcons", "The Bears play Sunday."), "")

    def test_a_death_headline_is_never_an_idea(self):
        from core.best_bet import _consider_candidate

        headline = (
            "GTA 6 fan who went viral for hoping to live long enough to play the game has died"
        )
        self.assertIsNone(
            _consider_candidate(
                headline, "rss", allowed={"gaming"}, exclude=set(), seen_local=set()
            )
        )

    def test_a_death_story_fills_no_overnight_slot(self):
        from core.batch_generation import story_passes_gate

        self.assertFalse(story_passes_gate("Mike Ditka dies at 86", source="series", outlets=9,
                                           names=[]))  # fmt: skip
        self.assertTrue(story_passes_gate("Bears at Falcons preview", source="series", outlets=0,
                                          names=[]))  # fmt: skip

    def test_a_death_headline_is_not_a_countdown_fact(self):
        from core.series.countdown import subject_headlines

        now = datetime(2026, 11, 2, 21, tzinfo=UTC)
        items = [
            {
                "title": "GTA 6 fan who wanted to play it has died",
                "published": now - timedelta(hours=2),
            },
            {"title": "GTA 6 install size is 210GB", "published": now - timedelta(hours=3)},
        ]
        found = subject_headlines(["GTA 6"], items, now=now, hours=24)
        self.assertEqual([i["title"] for i in found], ["GTA 6 install size is 210GB"])


# ---- #1967: directions are not the operator's idea ------------------------------------------------


RUN231_DESCRIPTION = (
    "Your boss already knows why you want Nov. 19 off. GTA 6 launches November 19, 2026 - 16 "
    "days out - and workplaces are already flagging leave requests. Pre-loading starts Nov. 12. "
    "Meanwhile, reports say a staggering number of fans would give up their pets to play early, "
    "and a terminally ill fan who went viral has died three weeks before launch. Subscribe for "
    "daily gaming takes.\n\nMade with AI-assisted narration and editing."
)


class DeathDescriptionTests(unittest.TestCase):
    def test_run231s_death_sentence_is_dropped_before_upload(self):
        from publishing.base import PublishRequest
        from publishing.prepublish import without_death_lines

        request = PublishRequest(file_path="x.mp4", title="GTA 6: 16 days to launch",
                                 description=RUN231_DESCRIPTION, tags=[])  # fmt: skip
        cleaned, dropped = without_death_lines(request)
        self.assertEqual(dropped, 1)
        self.assertNotIn("died", cleaned.description)
        self.assertIn("Pre-loading starts Nov. 12.", cleaned.description)
        self.assertIn("Made with AI-assisted narration and editing.", cleaned.description)

    def test_a_clean_description_is_left_alone(self):
        from publishing.base import PublishRequest
        from publishing.prepublish import without_death_lines

        request = PublishRequest(file_path="x.mp4", title="t", description="Red Dead news.",
                                 tags=[])  # fmt: skip
        self.assertEqual(without_death_lines(request), (request, 0))

    def test_the_publisher_runs_it(self):
        import inspect

        from publishing import youtube_publisher

        self.assertIn("without_death_lines(request)", inspect.getsource(youtube_publisher))


def _draft_kwargs(topic, best_bet):
    """generate_draft with the pipeline faked; the kwargs it handed `run_pipeline`."""
    from core import batch_generation as bg
    from core.pipeline import DiscoveryResult

    discovery = DiscoveryResult(input_topic="t", base_signals={}, evaluated=[("Angle", 80.0, {})],
                                timings={}, channel_id="tapin")  # fmt: skip
    result = SimpleNamespace(aborted=False, abort_reason=None, script="Hook!\nBody.", title="T",
                             description="", tags=[], run_id=7, features={})  # fmt: skip
    with (
        tempfile.TemporaryDirectory() as out_tmp,
        patch("core.output_paths.channel_output_root", return_value=out_tmp),
        patch("core.facts.enrichment.enrich_facts", return_value=""),
        patch(
            "core.authenticity.evaluate_authenticity", return_value=SimpleNamespace(verdict="ok")
        ),  # fmt: skip
        patch("core.length_recommender.get_recommended_length", side_effect=RuntimeError("no")),
        patch("core.experiments.next_arm", return_value=None),
        patch("core.pipeline.run_discovery", return_value=discovery),
        patch("core.pipeline.run_pipeline", return_value=result) as rp,
    ):
        bg.generate_draft(topic, "tapin", best_bet=best_bet)
    return rp.call_args.kwargs


class DirectionsTests(unittest.TestCase):
    def test_a_headlines_follow_line_is_a_direction(self):
        topic = "Valve's Steam AI crackdown stance"
        bet = {"offered": [{"topic": topic, "source": "trending", "domain": "gaming"}],
               "picked": 1}  # fmt: skip
        kwargs = _draft_kwargs(topic, bet)
        self.assertEqual(kwargs["creative_brief"], "")
        self.assertIn("follow", kwargs["directions"].lower())

    def test_a_countdowns_tomorrow_line_is_a_direction(self):
        topic = "GTA 6: 16 days to launch"
        bet = {"offered": [{"topic": topic, "source": "countdown", "domain": "gaming"}],
               "picked": 1, "title_stem": topic}  # fmt: skip
        kwargs = _draft_kwargs(topic, bet)
        self.assertEqual(kwargs["creative_brief"], "")
        self.assertIn("15 days to go", kwargs["directions"])

    def test_the_pipeline_writes_them_as_a_style_directive(self):
        import inspect

        from core import pipeline

        self.assertIn("directions", inspect.signature(pipeline.run_pipeline).parameters)
        self.assertIn("extra_directive=directions", inspect.getsource(pipeline.run_pipeline))


# ---- #1968 (S15): a menu counted once; the night carries the menu's gaming share ------------------


def _bet(topic, domain, source="trending"):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain=domain, avg_engaged_rate=0.0, source=source,
                         supporting_runs=0, rationale="", outlets=4)  # fmt: skip


class MenuMixTests(unittest.TestCase):
    def test_a_nights_menu_is_counted_once(self):
        from core.predictions.ledger import menu_mix

        night = [{"topic": "Picks", "domain": "nfl"}, {"topic": "Gane vs Hokit", "domain": "ufc"},
                 {"topic": "GTA story", "domain": "gaming"}]  # fmt: skip
        countdown = [{"topic": "GTA 6: 16 days", "domain": "gaming"}]
        menus = [(229, night, 3), (228, night, 2), (227, night, 1), (226, countdown, 1)]
        runs = [
            SimpleNamespace(
                id=run_id,
                features_json=json.dumps({"best_bet": {"offered": offered, "picked": picked}}),
            )
            for run_id, offered, picked in menus
        ]
        repo = SimpleNamespace(list_for_channel=lambda _c: runs)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            offered, taken, menus = menu_mix("tapin")
        self.assertEqual(menus, 2)
        self.assertEqual(offered, {"nfl": 1, "ufc": 1, "gaming": 2})
        self.assertEqual(sum(taken.values()), 4)


class NightShareTests(unittest.TestCase):
    def test_a_plain_headline_gives_way_while_gaming_leads(self):
        from core.batch_generation import night_gaming_share

        chosen = [_bet("Picks, graded", "nfl", "series"), _bet("Gane vs Hokit", "ufc", "schedule"),
                  _bet("NBA Cup scores", "nba")]  # fmt: skip
        spare = _bet("GTA 6 install size", "gaming")
        with patch("core.best_bet._gaming_leads", return_value=True):
            swaps = night_gaming_share("tapin", chosen, [*chosen, spare], [])
        self.assertEqual(swaps, 1)
        self.assertEqual([b.topic for b in chosen],
                         ["Picks, graded", "Gane vs Hokit", "GTA 6 install size"])  # fmt: skip

    def test_two_countdowns_already_carry_the_share(self):
        from core.batch_generation import night_gaming_share

        chosen = [_bet("Picks", "nfl", "series"), _bet("Gane vs Hokit", "ufc", "schedule"),
                  _bet("GTA story", "gaming")]  # fmt: skip
        extra = [_bet("GTA 6: 17 days", "gaming", "countdown"),
                 _bet("GTA 6: 16 days", "gaming", "countdown")]  # fmt: skip
        with patch("core.best_bet._gaming_leads", return_value=True):
            self.assertEqual(
                night_gaming_share("tapin", chosen, [*chosen, _bet("x", "gaming")], extra), 0
            )

    def test_nothing_moves_when_gaming_does_not_lead(self):
        from core.batch_generation import night_gaming_share

        chosen = [_bet("NBA Cup scores", "nba"), _bet("NFL deadline", "nfl")]
        with patch("core.best_bet._gaming_leads", return_value=False):
            self.assertEqual(
                night_gaming_share("tapin", chosen, [*chosen, _bet("GTA", "gaming")], []), 0
            )

    def test_the_night_is_built_with_it(self):
        from core import batch_generation as bg

        ideas = [_bet("NBA Cup scores", "nba"), _bet("NFL deadline deals", "nfl"),
                 _bet("GTA 6 install size", "gaming")]  # fmt: skip
        with (
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.best_bet._gaming_leads", return_value=True),
            patch.object(bg, "_swap_holdouts", return_value=set()),
            patch.object(bg, "_with_follow_up", side_effect=lambda _c, topics, *_a: topics),
        ):
            topics = bg.collect_topics("tapin", count=2)
        self.assertEqual(topics, ["NBA Cup scores", "GTA 6 install size"])


# ---- #1961: the leak rule reads the hedged clause -------------------------------------------------

RUN138_TITLE = "Knicks' half-court offense vs Toronto's new-look spacing in Raptors showdown"
RUN138_LINE = ("The Knicks' half-court offense, reportedly ranked No. 1 entering 2026-27, will face "
               "its first test against Toronto's new-look spacing.")  # fmt: skip


class LeakClauseTests(unittest.TestCase):
    def test_a_title_naming_only_the_subject_is_clear(self):
        from core.youtube_meta import leak_as_fact

        self.assertEqual(leak_as_fact(RUN138_TITLE, RUN138_LINE), "")

    def test_a_countdown_title_is_not_a_leak(self):
        from core.youtube_meta import leak_as_fact

        line = "GTA 6 is 17 days out, so let's sort the leaks from the wishful thinking."
        self.assertEqual(leak_as_fact("GTA 6: 17 days to launch", line), "")

    def test_a_title_stating_the_rumour_still_warns(self):
        from core.youtube_meta import leak_as_fact

        line = ("The rumor is Detroit's bench flipped momentum in a key stretch - unconfirmed, but "
                "that's the talk around this matchup.")  # fmt: skip
        self.assertTrue(leak_as_fact(
            "Detroit Pistons bench outplays Boston Celtics reserves in key stretch", line))  # fmt: skip


# ---- #1713: unsubscribes a week -------------------------------------------------------------------


class UnsubscribeTests(unittest.TestCase):
    def test_the_flow_keeps_both_sides(self):
        from analytics.youtube_metrics import _subscriber_change, _subscriber_flow

        resp = {"columnHeaders": [{"name": "subscribersGained"}, {"name": "subscribersLost"}],
                "rows": [[14, 3]]}  # fmt: skip
        query = SimpleNamespace(execute=lambda: resp)
        service = SimpleNamespace(reports=lambda: SimpleNamespace(query=lambda **_k: query))
        self.assertEqual(_subscriber_flow(service, "2026-10-26", "2026-11-02"), (14, 3))
        self.assertEqual(_subscriber_change(service, "2026-10-26", "2026-11-02"), 11)

    def test_ops_ypp_says_them(self):
        from core.ypp_readiness import path_lines

        numbers = {"subscribers": 189, "subs_net_28d": 121, "pace_days": 28,
                   "subs_gained_7d": 14, "subs_lost_7d": 3}  # fmt: skip
        lines = path_lines(numbers)
        self.assertTrue(any("Unsubscribes: 3 in the last 7 days, against 14 gained" in line
                            for line in lines), lines)  # fmt: skip


# ---- #1779: weekly per-platform rows --------------------------------------------------------------


class WeeklyPlatformTests(unittest.TestCase):
    def test_each_platform_by_week(self):
        from publishing.platform_metrics import weekly_platform_lines

        now = datetime(2026, 11, 2, 20, tzinfo=UTC)  # a Monday
        rows = {
            "226": {"tiktok": {"measured": True, "views": 100, "avg_watch_s": 3.0, "follows": None},
                    "instagram": {"measured": True, "views": 40, "avg_watch_s": 1.5}},
            "220": {"tiktok": {"measured": True, "views": 50, "avg_watch_s": 6.0}},
            "100": {"tiktok": {"measured": False, "views": 0}},
        }  # fmt: skip
        posts = {
            "226": {"tiktok": {"sent_at": "2026-11-02T17:05:00Z"},
                    "instagram": {"sent_at": "2026-11-02T17:06:00Z"}},
            "220": {"tiktok": {"sent_at": "2026-10-31T17:00:00Z"}},
            "100": {"tiktok": {"sent_at": "2026-10-01T17:00:00Z"}},
        }  # fmt: skip
        lines = weekly_platform_lines(rows, posts, now=now)
        tiktok = next(line for line in lines if line.startswith("Tiktok"))
        self.assertIn("1 posts 100 views 3.0 s | 1 posts 50 views 6.0 s | - | -", tiktok)
        self.assertTrue(any(line.startswith("Instagram") for line in lines))

    def test_the_weekly_report_carries_them(self):
        from publishing import platform_metrics as pm

        rows = {"226": {"tiktok": {"measured": True, "views": 10, "avg_watch_s": 2.0}}}
        posts = {"226": {"tiktok": {"sent_at": datetime.now(UTC).isoformat()}}}
        with (
            patch.object(pm, "load", return_value={"rows": rows}),
            patch("publishing.crosspost._load", return_value={"posts": posts}),
        ):
            lines = pm.tiktok_lines("tapin")
        self.assertTrue(any("weeks newest first" in line for line in lines), lines)


# ---- #1440: the policy site's pages read live -----------------------------------------------------


def _site(missing=""):
    pages = {
        "index.html": "<h1>Content OS</h1>",
        "privacy.html": "<h1>Privacy Policy</h1>",
        "terms.html": "<h1>Terms of Service</h1>",
        "data-deletion.html": "<h1>Data deletion</h1>",
    }

    def fetch(url):
        page = url.rsplit("/", 1)[-1]
        return (404, "Not found") if page == missing else (200, pages[page])

    return fetch


class PolicySiteTests(unittest.TestCase):
    def test_four_pages_answer(self):
        from publishing.policy_site import policy_site_lines

        lines = policy_site_lines("https://example.github.io/policy/", fetch=_site())
        self.assertEqual(
            lines, ["Policy site: 4 of 4 pages answer at https://example.github.io/policy/"]
        )

    def test_a_dead_page_is_named(self):
        from publishing.policy_site import policy_site_lines

        lines = policy_site_lines("https://example.github.io/policy", fetch=_site("privacy.html"))
        self.assertIn("3 of 4", lines[0])
        self.assertIn("  privacy.html: HTTP 404", lines)

    def test_unset_says_what_to_set(self):
        from publishing.policy_site import policy_site_lines

        with patch.dict(os.environ, {"POLICY_SITE_URL": ""}):
            self.assertIn("POLICY_SITE_URL is not set", policy_site_lines()[0])

    def test_check_youtube_prints_them(self):
        import inspect

        from youtube import check_setup

        self.assertIn("policy_site_lines()", inspect.getsource(check_setup))


# ---- #1601: a follow-up on a breakout --------------------------------------------------------------


def _log_row(title, views, judged):
    metrics = {"first_day": {"views": views, "judged_at": judged.isoformat(), "verdict": "high"}}
    return SimpleNamespace(title=title, metrics_json=json.dumps(metrics),
                           published_at=judged - timedelta(days=1), content_run_id=1)  # fmt: skip


class BreakoutTests(unittest.TestCase):
    NOW = datetime(2026, 11, 2, 23, tzinfo=UTC)

    def _breakouts(self, rows):
        from core.batch_generation import breakouts

        repo = SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch(
                "storage.repositories.publish_log.video_title",
                side_effect=lambda row, fallback="": row.title,
            ),  # fmt: skip
        ):
            return breakouts("tapin", now=self.NOW)

    def test_a_short_past_300_on_day_one_is_a_breakout(self):
        rows = [_log_row("GTA 6 trailer reactions", 350, self.NOW - timedelta(hours=10)),
                _log_row("A quiet Short", 120, self.NOW - timedelta(hours=10)),
                _log_row("An old breakout", 900, self.NOW - timedelta(days=3))]  # fmt: skip
        self.assertEqual([t for t, _p in self._breakouts(rows)], ["GTA 6 trailer reactions"])

    def test_the_night_drafts_its_follow_up(self):
        from core import batch_generation as bg

        published = self.NOW - timedelta(days=1)
        with (
            patch("analytics.growth._rows", return_value=[]),
            patch.object(bg, "breakouts", return_value=[("GTA 6 trailer reactions", published)]),
            patch.object(bg, "_followed_up", return_value=False),
        ):
            topic = bg.follow_up_topic("tapin", now=self.NOW)
        self.assertTrue(topic.startswith('Follow-up to "GTA 6 trailer reactions" (Nov 1)'), topic)


# ---- #1853 + #1873 + #1885: the calendar rows; one fetch per domain -------------------------------


class CalendarRowTests(unittest.TestCase):
    def test_the_rows_are_on_the_calendar(self):
        from core.series.countdown import series_rows

        days = {r["id"]: r.get("on") for r in series_rows("tapin")}
        self.assertEqual(days.get("gta6-early-money"), "2026-11-22")
        self.assertEqual(days.get("ufc334-main-event"), "2026-11-09")
        self.assertEqual(days.get("ufc334-weigh-ins"), "2026-11-13")
        self.assertEqual(days.get("ufc334-results"), "2026-11-15")
        self.assertEqual(days.get("thanksgiving-nfl"), "2026-11-25")
        self.assertEqual(days.get("gta6-week-one"), "2026-11-23")

    def test_two_domains_on_one_day_read_their_own_feeds(self):
        from core.series import dated

        now = datetime(2026, 11, 9, 14, tzinfo=UTC)
        seen = []

        def feeds(_channel, row, _now):
            seen.append(row.get("domain"))
            title = "UFC 334 fight week: the main event set" if row.get("domain") == "ufc" else (
                "GTA 6 editions compared")  # fmt: skip
            return [{"title": title, "source": "RSS", "published": now - timedelta(hours=3)}]

        with (
            patch.dict(os.environ, {"SERIES_DATED": "true"}),
            patch("core.batch_generation.series_drafted", return_value=False),
        ):
            ideas = dated.dated_ideas("tapin", now=now, headlines=feeds)
        topics = [i.topic for i in ideas]
        self.assertIn("UFC 334 fight week: the main event and what is at stake", topics)
        self.assertEqual(sorted(set(seen)), ["gaming", "ufc"])


# ---- #1866: the week-one special ------------------------------------------------------------------

SPECIAL = {"id": "gta6-week-one", "kind": "week_special", "subject": "GTA 6",
           "names": ["GTA 6"], "on": "2026-11-23",
           "title": "GTA 6 Launch Week: Every Story in One Video"}  # fmt: skip


class WeekSpecialTests(unittest.TestCase):
    def test_its_monday_finds_it(self):
        # Loaded before the patch: `dated` imports series_rows by name, and its first import
        # under this patch bound the mock for every later calendar test (the reversed run).
        import core.series.dated
        from video.week_compile import week_special

        with patch("core.series.countdown.series_rows", return_value=[SPECIAL]):
            self.assertEqual(week_special("tapin", now=datetime(2026, 11, 23, 15, tzinfo=UTC)),
                             SPECIAL)  # fmt: skip
            self.assertIsNone(week_special("tapin", now=datetime(2026, 11, 30, 15, tzinfo=UTC)))

    def test_the_subjects_shorts_alone(self):
        from video.week_compile import special_items

        items = [{"title": f"GTA 6 story {i}"} for i in range(6)] + [{"title": "UFC 334 recap"}]
        self.assertEqual(len(special_items(items, SPECIAL)), 6)

    def test_a_thin_week_keeps_the_regular_one(self):
        from video.week_compile import special_items

        items = [{"title": f"GTA 6 story {i}"} for i in range(3)] + [{"title": "UFC 334 recap"}]
        self.assertEqual(special_items(items, SPECIAL), items)


# ---- #1413: a long video under 2% after 1,000 impressions gets its second cover ---------------


def _reach_row(run_id, impressions, ctr, privacy="public"):
    metrics = {"thumbnail_impressions": impressions, "thumbnail_ctr": ctr}
    return SimpleNamespace(content_run_id=run_id, youtube_video_id=f"v{run_id}",
                           privacy_status=privacy, metrics_json=json.dumps(metrics))  # fmt: skip


class CoverSwapTests(unittest.TestCase):
    def _patched(self, rows, *, swapped=()):
        repo = SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)
        runs = {r.content_run_id: SimpleNamespace(title=f"Long {r.content_run_id}",
                                                  mp4_path="x.mp4") for r in rows}  # fmt: skip

        def features(run):
            done = run is not None and run.title in swapped
            return {"cover_swapped_at": "x"} if done else {}

        return (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch("publishing.prepublish._is_long", return_value=True),
            patch("publishing.prepublish._run", side_effect=lambda rid: runs.get(rid)),
            patch("publishing.prepublish._features", side_effect=features),
        )

    def test_only_a_low_long_video_past_1000_qualifies(self):
        from analytics.packaging import cover_swap_candidates

        rows = [_reach_row(300, 1500, 0.012), _reach_row(301, 1500, 0.031),
                _reach_row(302, 500, 0.0), _reach_row(303, 2000, 0.01, privacy="unlisted"),
                _reach_row(304, 1800, 0.015)]  # fmt: skip
        patches = self._patched(rows, swapped=("Long 304",))
        with patches[0], patches[1], patches[2], patches[3]:
            found = cover_swap_candidates("tapin")
        self.assertEqual([f["run_id"] for f in found], [300])

    def test_the_sync_swaps_it_once_and_records_it(self):
        from analytics.packaging import swap_low_ctr_covers

        patches = self._patched([_reach_row(300, 1500, 0.012)])
        uploads = []
        with (
            patches[0], patches[1], patches[2], patches[3],
            patch("core.run_features.merge_features") as merged,
            patch.dict(os.environ, {"COVER_SWAP": "true"}),
        ):  # fmt: skip
            lines = swap_low_ctr_covers(
                "tapin", apply=True, cover=lambda c, _ch: "cover2.jpg",
                upload=lambda vid, path: uploads.append((vid, path)) or True,
            )  # fmt: skip
        self.assertEqual(uploads, [("v300", "cover2.jpg")])
        self.assertIn("its second cover is up", lines[0])
        self.assertIn("cover_swapped_at", merged.call_args.args[1])

    def test_ops_packaging_shows_what_would_swap(self):
        from analytics.packaging import swap_low_ctr_covers

        patches = self._patched([_reach_row(300, 1500, 0.012)])
        with patches[0], patches[1], patches[2], patches[3]:
            lines = swap_low_ctr_covers("tapin")
        self.assertIn("1,500 impressions at 1.2%", lines[0])
        self.assertIn("next metrics sync", lines[0])

    def test_the_metrics_sync_runs_it(self):
        import inspect

        from analytics import sync_metrics

        self.assertIn("swap_low_ctr_covers(channel_id, apply=True)",
                      inspect.getsource(sync_metrics))  # fmt: skip


# ---- #1902: the 16:9 cut laid out for 16:9 -------------------------------------------------------

VERTICAL_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, \
Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, \
Alignment, MarginL, MarginR, MarginV, Encoding
Style: Body,Arial,90,&H003539E5&,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,2,\
130,130,450,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.09,Body,,0,0,0,,{\\fs100}{\\k15}The {\\k37}UFC
"""


class LandscapeTests(unittest.TestCase):
    def test_the_captions_get_a_16x9_canvas(self):
        from video.render_profiles import landscape_ass

        out = landscape_ass(VERTICAL_ASS)
        self.assertIn("PlayResX: 1920", out)
        self.assertIn("PlayResY: 1080", out)
        style = next(line for line in out.splitlines() if line.startswith("Style: Body"))
        fields = style.split(",")
        self.assertEqual(fields[2], "65")  # 90 at 72%
        self.assertEqual(fields[-2], "110")  # the lower band, not 450 px up
        self.assertEqual(fields[-4], "231")  # side margins re-measured for 1920
        self.assertIn("{\\fs72}", out)

    def test_a_vertical_background_is_kept_whole_in_16x9(self):
        from video.render_profiles import _PROFILES
        from video.render_video import build_render_ffmpeg_command

        args = {"background_path": "bg.mp4", "mp3_path": "a.mp3", "output_path": "o.mp4",
                "subtitle_path": "s.ass", "duration": 10.0}  # fmt: skip
        wide = " ".join(build_render_ffmpeg_command(**args, profile=_PROFILES["landscape"]))
        self.assertIn("boxblur", wide)
        self.assertIn("overlay=(W-w)/2:0", wide)
        tall = " ".join(build_render_ffmpeg_command(**args))
        self.assertNotIn("boxblur", tall)

    def test_the_16x9_cut_burns_the_landscape_copies(self):
        from video import render_video as rv

        with tempfile.TemporaryDirectory() as tmp:
            subs = os.path.join(tmp, "x.ass")
            with open(subs, "w", encoding="utf-8") as f:
                f.write(VERTICAL_ASS)
            seen = {}

            def capture(**kwargs):
                seen.update(kwargs)
                return ["ffmpeg"]

            with (
                patch.dict(os.environ, {"RENDER_FORMATS": "landscape"}),
                patch.object(rv, "build_render_ffmpeg_command", side_effect=capture),
                patch.object(rv, "_ffmpeg_run", return_value=SimpleNamespace(returncode=1,
                                                                             stderr="")),
            ):  # fmt: skip
                rv._render_extra_formats(background_path="bg.mp4", mp3_path="a.mp3",
                                         primary_output=os.path.join(tmp, "o.mp4"),
                                         subtitle_path=subs, duration=5.0,
                                         stage=lambda _m: None)  # fmt: skip
        self.assertTrue(seen["subtitle_path"].endswith("x_16x9.ass"), seen["subtitle_path"])


# ---- the audit's own fixes ------------------------------------------------------------------------


class EmptyAnswerTests(unittest.TestCase):
    def test_an_empty_answer_fails_over(self):
        from core import llm_router

        calls = []

        def answer(provider, model, messages, **_kw):
            calls.append(provider)
            return ("" if provider == "openrouter" else "OK"), 1, 1

        chain = [("openrouter", "m:free"), ("deepseek", "deepseek-chat")]
        with (
            patch.object(llm_router, "_resolve_chain", return_value=chain),
            patch.object(llm_router, "_openai_complete", side_effect=answer),
            patch.object(llm_router, "_model_is_dead", return_value=False),
            patch.object(llm_router, "_record_usage"),
        ):
            self.assertEqual(llm_router.complete("Reply OK", tier="cheap"), "OK")
        self.assertEqual(calls, ["openrouter", "deepseek"])

    def test_the_cheap_default_is_not_the_retired_slug(self):
        from core import llm_router

        self.assertNotEqual(llm_router._default_model("openrouter", "cheap"),
                            "poolside/laguna-s-2.1:free")  # fmt: skip


class CorrectionScanTests(unittest.TestCase):
    def _scan(self, stamp, fetch, *, urls):
        from core import correction_dossier as cd

        rows = [SimpleNamespace(content_run_id=i, youtube_video_id=f"v{i}") for i in (1, 2)]
        claims = [{"claim": "Volkanovski fights at UFC 333"}]
        with patch.object(cd, "_claims_and_sources", return_value=(claims, urls)):
            return cd.scan_published_for_corrections(
                "tapin", published=rows, run_lookup={1: object(), 2: object()}, fetch=fetch,
                negative_store=lambda *_a: None, stamp_path=stamp, force=True,
            )  # fmt: skip

    def test_one_fetch_per_source_and_a_dead_one_rests(self):
        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "correction_scan_tapin.json")
            fetched = []

            def fetch(url):
                fetched.append(url)
                raise OSError("HTTP Error 403: Forbidden")

            for _night in range(3):
                self._scan(stamp, fetch, urls=["https://dead.example/a"])
            # two runs share the source: once a scan, and not at all after two failed scans
            self.assertEqual(fetched, ["https://dead.example/a"] * 2)


class FileNameTests(unittest.TestCase):
    def test_a_clipped_name_keeps_its_timestamp(self):
        from core import output_paths

        with tempfile.TemporaryDirectory() as tmp:
            dirs = {"root": tmp, "audio": tmp, "video": tmp, "thumbnails": tmp}
            with (
                patch.dict(os.environ, {"WIN_MAX_PATH": "160"}),
                patch("core.output_paths.ensure_channel_output_dirs", return_value=dirs),
            ):
                _mp3, name, _mp4 = output_paths.media_paths_for_topic(
                    "predicting GTA 6s content analyzing the recent leaks " * 4,
                    channel_id="tapin", timestamp="20261102_170231",
                )  # fmt: skip
        self.assertTrue(name.endswith("_20261102_170231.mp4"), name)


class LivingDocVerbTests(unittest.TestCase):
    def test_a_living_doc_naming_a_removed_command_is_caught(self):
        from core.ops_doc_verbs import unregistered_verbs

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs"))
            for name, status in (("live.md", "living"), ("old.md", "frozen")):
                with open(os.path.join(tmp, "docs", name), "w", encoding="utf-8") as f:
                    f.write(f"# {name}\n\n> **Class:** plan · **Status:** {status}\n\n"
                            "Run `py -m scripts.ops no-such-verb --channel tapin`.\n")  # fmt: skip
            self.assertEqual(unregistered_verbs({"status"}, tmp), {"no-such-verb": ["live.md"]})


# ---- #1980: a dated draft never goes out before its own day (live 11-03) ---------------------


RUN232_TAKEN = {
    datetime(2026, 11, 4, 3, tzinfo=UTC),  # 10 PM ET Nov 3 - run 224
    datetime(2026, 11, 4, 17, tzinfo=UTC),  # noon Nov 4 - run 222
    datetime(2026, 11, 4, 23, tzinfo=UTC),  # 6 PM Nov 4 - run 227
    datetime(2026, 11, 5, 3, tzinfo=UTC),  # 10 PM Nov 4 - run 228
}


class DatedSlotTests(unittest.TestCase):
    def _slot(self, now, *, planned, taken, event):
        from core import spaced_queue as sq

        with (
            patch.object(sq, "_run_title", return_value="GTA 6: 15 days to launch"),
            patch.object(sq, "_window_days", return_value=7.0),
            patch.object(sq, "_age_days", return_value=0.0),
            patch.object(sq, "preview_event", return_value=event),
            patch.object(sq, "_taken_slots", return_value=set(taken)),
            patch.object(sq, "_planned_time", return_value=planned),
            patch.object(sq, "_channel_tz", return_value=EASTERN),
            patch("core.series.dated.slot_hours", return_value=(12, 22)),
        ):
            return sq.slot_for_run("tapin", 232, now=now)

    def test_run232_waits_for_its_day(self):
        when, why = self._slot(
            datetime(2026, 11, 4, 1, 28, tzinfo=UTC),  # 8:28 PM ET Nov 3
            planned=datetime(2026, 11, 4, 17, tzinfo=UTC),
            taken=RUN232_TAKEN,
            event=datetime(2026, 11, 5, 5, tzinfo=UTC),
        )
        self.assertEqual(why, "")
        self.assertGreaterEqual(when, datetime(2026, 11, 4, 5, tzinfo=UTC))  # midnight ET Nov 4
        self.assertEqual(when, datetime(2026, 11, 4, 17, 10, tzinfo=UTC))  # beside its noon

    def test_a_free_slot_on_its_day_is_taken(self):
        taken = RUN232_TAKEN - {datetime(2026, 11, 4, 23, tzinfo=UTC)}
        when, _why = self._slot(
            datetime(2026, 11, 4, 1, 28, tzinfo=UTC),
            planned=datetime(2026, 11, 4, 17, tzinfo=UTC),
            taken=taken,
            event=datetime(2026, 11, 5, 5, tzinfo=UTC),
        )
        self.assertEqual(when, datetime(2026, 11, 4, 23, tzinfo=UTC))  # 6 PM ET Nov 4

    def test_todays_countdown_drafted_late_still_goes_out_today(self):
        now = datetime(2026, 11, 2, 22, 46, tzinfo=UTC)  # run 225: 5:46 PM ET, its noon gone
        when, _why = self._slot(
            now,
            planned=datetime(2026, 11, 2, 17, tzinfo=UTC),
            taken={datetime(2026, 11, 3, 3, tzinfo=UTC)},
            event=datetime(2026, 11, 3, 5, tzinfo=UTC),
        )
        self.assertEqual(when, now + timedelta(minutes=45))


if __name__ == "__main__":
    unittest.main()
