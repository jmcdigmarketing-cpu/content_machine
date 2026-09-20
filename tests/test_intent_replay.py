"""#801: replay the 38 recorded run topics through detect_angle_intent.

Of the 10 traces that stored an intent, 9 read `default`, so take machinery
stayed on for calm/explanatory ideas. The topics below are the real strings
from `data/traces/*.json` (read 2026-09-20). The suite must not open that
directory.
"""

from __future__ import annotations

import unittest

from core.angle_intent import (
    ANGLE_COMPARISON,
    ANGLE_DEFAULT,
    ANGLE_EXPLAINER,
    ANGLE_LIST,
    ANGLE_REACTION,
    detect_angle_intent,
)

# Full topic strings from traces 47-90, in run-id order. Duplicates are real
# (78 and 79 used the same seed).
TRACE_TOPICS: tuple[str, ...] = (
    "NBA Free Agency Recap 7/7. Where will Lebron Go?",
    "WAYYYYYY too early final standing projections for 2027, award races included",
    "The Alienware 18 Area-51 RTX 5090 Gaming Laptop With 64GB of RAM Drops to $3,000 at Dell Outlet",
    "Marvel Rivals adds X-Men's Jubilee in season 9: first look at gameplay",
    "GTA VI 7/8/26 new information",
    "Palworld's 1.0 patch notes are so massive Steam wouldn't accept them",
    "what to look forward to in the next marvel rivals update",
    "Conor McGregor's UFC comeback ends in injury after barely a minute",
    "UFC 329 Recap: Conor Injury!!",
    "Marvel Rivals S9 opinions + Jubilee Review",
    "GTA Online's newest heist has fans worrying about GTA 6 feature",
    "world cup semi finals reactions analysis",
    "France vs England 3rd Place Game. ABSOLUTE BANGER",
    "Steam Machine may get a price increase, Valve slyly warns",
    "World Cup and Rodri Hot takes",
    "COD Bo2 Playstation return. Is it better or worse than back in the day?",
    "Usman and his COBBLY Knees get dominated by ddp",
    "The Hood added to marvel rivals - new hero breakdown",
    "MMA divisional rankings: Quillan Salkilld, Alexia Thainara break through",
    "GTA VI Trailer netfli only?",
    "Islam Makhachev's UFC GOAT case gets pushback from former champs",
    "Stop Killing Games condemns GTA 6 leaker after their manifesto supports them",
    "Golden Axe: First Look at the New Animated Series Based on the Classic SEGA Game",
    "GTA 6 Leak and Wolverine Rage Are Symptoms of Gaming's Summer of Hate",
    "Chinese Pokemon-like Open-World Game With 15 million Players Is Set to Launch Globally",
    "GTA 6 looks amazing!!!",
    "GTA 6 looks amazing! Extended look analysis",
    "gta 6 extended look analysis/reaction, looks so good",
    "GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting the hype mean, is a goy candidate a failure? Long form predictions and content analysis so far",
    "GTA 6",
    "GTA 6 Online economy: what Rockstar is really selling and what players will pay for",
    "GTA 6 Online economy: what Rockstar is really selling and what players will pay for",
    "GTA week 2",
    "UFC returns to Qatar in November",
    "New R-Rated Survival Sci-Fi Officially Crowned Highest-Rated Video Game Adaptation Ever",
    "BENJYFISHY on Team Heretics' 2026 season, Valorant esports changes, and off-season grinding",
    "Khamzat Chimaev reveals details about injuries requiring time off, plans to challenge for UFC middleweight title again",
    'xQc says he has "no power" over GTA RP invites despite being NoPixel co-owner',
)


class TestIntentReplay(unittest.TestCase):
    def test_replays_all_thirty_eight_recorded_topics(self) -> None:
        self.assertEqual(len(TRACE_TOPICS), 38)
        labels = [detect_angle_intent(t) for t in TRACE_TOPICS]
        self.assertEqual(len(labels), 38)

    def test_calm_and_explanatory_seeds_are_not_a_take(self) -> None:
        """These currently fall to default, so insight injection and short_debate stay on."""
        cases = {
            "what to look forward to in the next marvel rivals update": ANGLE_EXPLAINER,
            "MMA divisional rankings: Quillan Salkilld, Alexia Thainara break through": ANGLE_LIST,
            "Marvel Rivals adds X-Men's Jubilee in season 9: first look at gameplay": ANGLE_REACTION,
            "Golden Axe: First Look at the New Animated Series Based on the Classic SEGA Game": (
                ANGLE_REACTION
            ),
            "GTA 6 Online economy: what Rockstar is really selling and what players will pay for": (
                ANGLE_EXPLAINER
            ),
        }
        for topic, expected in cases.items():
            with self.subTest(topic=topic):
                self.assertEqual(detect_angle_intent(topic), expected)

    def test_topics_we_did_not_mean_to_catch_stay_default(self) -> None:
        """Rule 7: a wider lexicon must not steal news, bare seeds, or hot-take asks."""
        for topic in (
            "GTA 6",
            "GTA week 2",
            "World Cup and Rodri Hot takes",
            "UFC returns to Qatar in November",
            "Khamzat Chimaev reveals details about injuries requiring time off, plans to challenge for UFC middleweight title again",
            "is it really that amazing?",
        ):
            with self.subTest(topic=topic):
                self.assertEqual(detect_angle_intent(topic), ANGLE_DEFAULT)

    def test_breakdown_is_still_not_an_explainer(self) -> None:
        """The established-critique pivot lives on this string."""
        self.assertEqual(
            detect_angle_intent("The Hood added to marvel rivals - new hero breakdown"),
            ANGLE_DEFAULT,
        )
        self.assertEqual(detect_angle_intent("GTA 6 meta breakdown"), ANGLE_DEFAULT)

    def test_already_working_cues_still_fire(self) -> None:
        self.assertEqual(detect_angle_intent("GTA 6 looks amazing!!!"), ANGLE_REACTION)
        self.assertEqual(
            detect_angle_intent("world cup semi finals reactions analysis"),
            ANGLE_REACTION,
        )
        self.assertEqual(
            detect_angle_intent(
                "COD Bo2 Playstation return. Is it better or worse than back in the day?"
            ),
            ANGLE_COMPARISON,
        )


if __name__ == "__main__":
    unittest.main()
