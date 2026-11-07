"""Wave 158 (2026-11-06) - the next five, before W4's freeze.

#1800 ElevenLabs' plan sized to the month's characters; #1807 each monthly subscription with what it
bought, and one to cut; #1830 paid and organic split from the ledger's campaign windows; #1700
part-2 Shorts, a day apart. #1723 (monthly tier lists) is measured and left.
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
import core.success.bridge
import core.success.formats
import core.success.lanes

UTC = timezone.utc
TODAY = date(2026, 11, 6)
PLANS = [{"name": "Free", "chars": 10000, "usd": 0}, {"name": "Starter", "chars": 30000, "usd": 5},
         {"name": "Creator", "chars": 100000, "usd": 22}, {"name": "Pro", "chars": 500000, "usd": 99},
         {"name": "Scale", "chars": 2000000, "usd": 330}]  # fmt: skip
CREATOR = {"name": "Creator", "chars": 100000, "usd": 22.0}


def _run(day, **cost):
    return SimpleNamespace(created_at=datetime.combine(day, datetime.min.time()),
                           features_json=json.dumps({"cost": cost}))  # fmt: skip


class VoicePlanTests(unittest.TestCase):
    """#1800 (B09.4): ElevenLabs' plan sized to the month's characters used."""

    def test_the_months_characters_from_the_runs_voice_cost(self):
        from core.money.plans import month_use

        runs = [_run(date(2026, 11, 2), tts=0.3082, llm=0.0118, apify=0.02),
                _run(date(2026, 11, 3), tts=0.0, llm=0.0078),
                _run(date(2026, 10, 30), tts=0.5)]  # fmt: skip
        with patch.dict(os.environ, {"COST_TTS_PER_1K_CHARS": "0.22"}):
            use = month_use(TODAY, runs)
        self.assertEqual(use["chars"], 1401)
        self.assertEqual((use["runs"], use["voiced"]), (2, 1))
        self.assertAlmostEqual(use["llm"], 0.0196)

    def test_the_pace_names_the_plan_and_when_the_current_one_runs_out(self):
        from core.money.plans import plan_fit

        fit = plan_fit(31_000, TODAY, PLANS, CREATOR)
        self.assertEqual(fit["pace"], 155_000)
        self.assertEqual(fit["fits"]["name"], "Pro")
        self.assertEqual(fit["runs_out"], date(2026, 11, 20))

    def test_a_smaller_plan_that_covers_it_says_what_it_saves(self):
        from core.money.plans import plan_line

        with (
            patch("core.money.plans.elevenlabs_plans", return_value=PLANS),
            patch("core.money.plans._current_plan", return_value=CREATOR),
        ):
            line = plan_line(today=TODAY, use={"chars": 3_000, "voiced": 3})
            over = plan_line(today=TODAY, use={"chars": 31_000, "voiced": 22})
        self.assertIn("on pace for ~15,000", line)
        self.assertIn("Starter (30,000, $5) covers it - $17 a month less than Creator", line)
        self.assertIn("runs out about Nov 20 - Pro (500,000, $99) covers it", over)

    def test_the_plans_are_the_operators_file(self):
        from core.money.plans import elevenlabs_plans

        self.assertEqual([p["name"] for p in elevenlabs_plans()],
                         ["Free", "Starter", "Creator", "Pro", "Scale"])  # fmt: skip


class SubscriptionTests(unittest.TestCase):
    """#1807 (B09.11): each monthly subscription with what it bought, and one to cut."""

    USE: ClassVar[dict[str, Any]] = {"tts": 6.78, "llm": 0.41, "apify": 0.44, "web_search": 0.18, "runs": 22, "voiced": 22,
           "chars": 30_818}  # fmt: skip

    def test_none_entered_says_what_the_runs_used(self):
        from core.money.plans import subscription_lines

        lines = subscription_lines(today=TODAY, entries=[], use=self.USE)
        self.assertEqual(len(lines), 1)
        self.assertIn("none entered", lines[0])
        self.assertIn("voice $6.78", lines[0])
        self.assertIn("--kind subscription --monthly", lines[0])

    def test_each_with_what_it_bought_and_the_one_to_cut(self):
        from core.money.plans import subscription_lines

        entries = [
            {"id": 1, "date": "2026-10-01", "amount": 22, "what": "ElevenLabs Creator",
             "kind": "subscription", "monthly": True},
            {"id": 2, "date": "2026-10-01", "amount": 10, "what": "Epidemic Sound",
             "kind": "subscription", "monthly": True},
            {"id": 3, "date": "2026-09-01", "amount": 5, "what": "Old tool", "kind": "subscription",
             "monthly": True, "ended": "2026-10-15"},
            {"id": 4, "date": "2026-10-26", "amount": 14.55, "what": "Promote", "kind": "ads"},
        ]  # fmt: skip
        lines = subscription_lines(today=TODAY, entries=entries, use=self.USE)
        text = "\n".join(lines)
        self.assertIn("ElevenLabs Creator $22.00/mo - 22 runs used $6.78 of voice, ~30,818 "
                      "characters ($1.00 a run)", text)  # fmt: skip
        self.assertIn("Epidemic Sound $10.00/mo - nothing measured against it", text)
        self.assertIn("Cut first: Epidemic Sound", text)
        self.assertNotIn("Old tool", text)
        self.assertNotIn("Promote", text)

    def test_ops_spend_and_the_weekly_report_print_them(self):
        import analytics.weekly_report
        import scripts.ops

        self.assertIn("money_plan_lines()", inspect.getsource(scripts.ops))
        self.assertIn("money_plan_lines()", inspect.getsource(analytics.weekly_report))


CAMPAIGNS = [
    {"id": 2, "date": "2026-10-26", "amount": 14.55, "kind": "ads", "ended": "2026-10-27",
     "result": {"subscribers": 27}},
    {"id": 3, "date": "2026-10-26", "amount": 1.1, "kind": "ads", "ended": "2026-10-27",
     "result": {"subscribers": 2}},
    {"id": 1, "date": "2026-09-26", "amount": 10.0, "kind": "ads"},
]  # fmt: skip


class OrganicSplitTests(unittest.TestCase):
    """#1830 (B10.9): paid and organic split from the ledger's campaign windows."""

    def test_a_campaigns_window_and_its_share_of_a_period(self):
        bridge = core.success.bridge
        self.assertEqual(
            bridge.campaign_window(CAMPAIGNS[0]), (date(2026, 10, 26), date(2026, 10, 27))
        )
        self.assertEqual(bridge.campaign_subscribers(CAMPAIGNS, date(2026, 10, 10), TODAY), 29)
        self.assertEqual(bridge.campaign_subscribers(CAMPAIGNS, date(2026, 10, 27), TODAY), 14.5)
        self.assertEqual(bridge.campaign_subscribers(CAMPAIGNS, date(2026, 10, 28), TODAY), 0)

    def test_the_28_days_are_organic(self):
        text = core.success.bridge.organic_net_text(41, CAMPAIGNS, TODAY, days=28)
        self.assertEqual(text, "+12 organic in 28 days (+41 with the campaigns' 29)")
        alone = core.success.bridge.organic_net_text(9, CAMPAIGNS, date(2026, 12, 20), days=28)
        self.assertEqual(alone, "+9 in 28 days, organic (no campaign ran)")

    def test_the_subscribers_lane_takes_the_campaigns_out(self):
        numbers = {"subs_gained_7d": 33, "subs_lost_7d": 1,
                   "subs_weeks": {"2026-W43": 4, "2026-W44": 35, "2026-W45": 3}}  # fmt: skip
        line = core.success.lanes.subscribers_lane(numbers, entries=CAMPAIGNS,
                                                   today=date(2026, 10, 30))  # fmt: skip
        self.assertIn(
            "+3 subscribers in the last 7 days organic (+32 with the campaigns' 29)", line
        )
        self.assertIn("0 of 4 weeks at +10", line)  # W44's 35 is 6 of its own
        weeks = core.success.lanes.organic_weeks(numbers["subs_weeks"], CAMPAIGNS)
        self.assertEqual(weeks["2026-W44"], 6.0)

    def test_without_a_campaign_the_line_is_as_it_was(self):
        line = core.success.lanes.subscribers_lane({"subs_gained_7d": 3, "subs_lost_7d": 1},
                                                   entries=[], today=TODAY)  # fmt: skip
        self.assertIn("+2 subscribers in the last 7 days (ads off", line)

    def test_the_scoreboard_prints_the_organic_28_days(self):
        numbers = {"subscribers": 195, "subs_net_28d": 41, "subs_gained_7d": 3, "subs_lost_7d": 1}
        with patch("core.money.ledger.money_line", return_value="money"):
            lines = core.success.bridge.scoreboard_lines("tapin", numbers=numbers,
                                                         entries=CAMPAIGNS, today=TODAY)  # fmt: skip
        text = "\n".join(lines)
        self.assertIn("+12 organic in 28 days (+41 with the campaigns' 29)", text)
        self.assertNotIn("ads included", text)


class PartTwoTests(unittest.TestCase):
    """#1700 (B05.4): part-2 Shorts, a day apart."""

    def setUp(self):
        import core.series.parts as parts

        self.parts = parts
        path = parts.store_path("tapin")
        if os.path.isfile(path):
            os.remove(path)
        self.addCleanup(lambda: os.path.isfile(path) and os.remove(path))
        self.env = patch.dict(os.environ, {"PART_SHORTS": "true"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _bet(self, topic, outlets, source="trending"):
        return SimpleNamespace(topic=topic, outlets=outlets, source=source)

    def test_the_lead_story_on_five_outlets_naming_a_marquee_name(self):
        names = ["Derrick Henry"]
        ideas = [self._bet("Chiefs trade for a receiver", 6),
                 self._bet("Derrick Henry traded to the Bills", 4),
                 self._bet("Derrick Henry responds to trade rumors", 5)]  # fmt: skip
        self.assertEqual(self.parts.part_one(ideas, names, "tapin"),
                         "Derrick Henry responds to trade rumors")  # fmt: skip
        self.assertEqual(self.parts.part_one(ideas[:2], names, "tapin"), "")

    def test_part_one_opens_the_pair_with_its_question(self):
        script = ("Derrick Henry is done waiting. He told the Ravens he wants out. "
                  "Part 2: why Baltimore let its best runner go.")  # fmt: skip
        self.assertEqual(self.parts.question_of(script), "why Baltimore let its best runner go")
        self.parts.record_part_one("tapin", "Derrick Henry responds to trade rumors", 301, script,
                                   ["ESPN reported: Henry wants out"], names=["Derrick Henry"],
                                   now=datetime(2026, 11, 7, 10, tzinfo=UTC))  # fmt: skip
        pair = self.parts.load_store("tapin")["open"]
        self.assertEqual(pair["subject"], "Derrick Henry")
        self.assertEqual(pair["run_id"], 301)
        ideas = [self._bet("Derrick Henry traded", 9)]
        self.assertEqual(self.parts.part_one(ideas, ["Derrick Henry"], "tapin"), "")  # one pair

    def _open(self, hours_ago):
        self.parts.save_store("tapin", {"open": {
            "topic": "Derrick Henry responds to trade rumors", "run_id": 301,
            "question": "why Baltimore let its best runner go", "subject": "Derrick Henry",
            "facts": ["ESPN reported: Henry wants out"],
            "drafted": (datetime(2026, 11, 8, 10, tzinfo=UTC) - timedelta(hours=hours_ago)).isoformat()}})  # fmt: skip

    def _two(self, rendered=True, drafted=False):
        return self.parts.part_two_ideas("tapin", now=datetime(2026, 11, 8, 10, tzinfo=UTC),
                                         rendered=lambda _r: rendered,
                                         drafted=lambda *_a: drafted)  # fmt: skip

    def test_part_two_the_next_night_once_part_one_rendered(self):
        self._open(20)
        ideas = self._two()
        self.assertEqual([i.topic for i in ideas],
                         ["Derrick Henry, part 2: why Baltimore let its best runner go"])  # fmt: skip
        self.assertEqual(ideas[0].source, "part2")
        self.assertIn("ended on the question", ideas[0].facts[-1])

    def test_too_soon_waits_and_a_dead_pair_closes(self):
        self._open(8)
        self.assertEqual(self._two(), [])
        self.assertIsNotNone(self.parts.load_store("tapin")["open"])
        self._open(20)
        self.assertEqual(self._two(rendered=False), [])
        self.assertIsNone(self.parts.load_store("tapin")["open"])
        self._open(80)
        self.assertEqual(self._two(), [])
        self.assertIsNone(self.parts.load_store("tapin")["open"])

    def test_the_briefs(self):
        follow = core.batch_generation.follow_brief
        one = {"offered": [{"topic": "Derrick Henry responds", "source": "trending"}], "picked": 1,
               "part": 1}  # fmt: skip
        two = {"offered": [{"topic": "Derrick Henry, part 2: why he left", "source": "part2"}],
               "picked": 1}  # fmt: skip
        self.assertIn('"Part 2: <the question>"', follow(one))
        self.assertIn('"why he left"', follow(two))
        self.assertEqual(core.batch_generation.draft_intent(own_idea=False, preview="",
                                                            source="part2"), "news")  # fmt: skip

    def test_overnight_marks_part_one_and_the_draft_opens_the_pair(self):
        lead = core.best_bet.BestBetResult(topic="Derrick Henry responds to trade rumors",
                                           domain="nfl", avg_engaged_rate=0.0, source="trending",
                                           supporting_runs=0, rationale="", outlets=6)  # fmt: skip
        picks: dict = {}
        with (
            patch("core.best_bet.get_idea_menu", return_value=([lead], [])),
            patch("core.best_bet.marquee_names", return_value=["Derrick Henry"]),
            patch("core.best_bet.crossover_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[]),
            patch("core.series.recap.debate_ideas", return_value=[]),
            patch("core.series.last_night.last_night_ideas", return_value=[]),
            patch("core.series.profiles.profile_ideas", return_value=[]),
            patch("core.series.shapes.patch_ideas", return_value=[]),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.series.recap.fight_week", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=1, picks=picks)
        self.assertEqual(topics, ["Derrick Henry responds to trade rumors"])
        self.assertEqual(picks[topics[0]].get("part"), 1)
        self.assertIn("record_part_one(", inspect.getsource(core.batch_generation.generate_draft))

    def test_each_part_is_its_own_format(self):
        fmt = core.success.formats.run_format
        one = {
            "best_bet": {"offered": [{"topic": "t", "source": "trending"}], "picked": 1, "part": 1}
        }
        two = {"best_bet": {"offered": [{"topic": "t", "source": "part2"}], "picked": 1}}
        self.assertEqual((fmt(one), fmt(two)), ("part 1", "part 2"))


if __name__ == "__main__":
    unittest.main()
