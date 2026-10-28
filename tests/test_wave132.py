"""Wave 132, the first five (2026-10-28) - the defects the operator's 10-25 session exposed, from
docs/cloud_brief_wave132.md items 1-5:

- #1587 two scripts were read aloud with a stranded fragment ("...offensive line. for the first
  time in his *career*.") - the hook's first sentence ended at a spoken "...";
- #1588 every game preview was read as an explainer ask - its own brief says "what is at stake";
- #1589 run 196 listed four Week-6 links as the sources of a Week-7 game;
- #1590 auto-research kept "please consider supporting ... independent journalism" as facts;
- #1591 run 195's title was flagged by the title check and shipped anyway.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

RUN196 = (
    "Kansas City fell to 5-1 after a 20-3 loss, and Denver will capitalize on that vulnerable "
    "offensive line. for the first time in his *career*. Seattle held Kansas City to three points."
)
RUN187 = (
    "Jackson scored twice and ended Man City's perfect start, and City's defence will pay for it. "
    "and Manchester City's perfect start is gone. The same afternoon, Arsenal beat Everton 2-0."
)
DONATION = (
    "We hope you found this article worthwhile. Before you close this tab, please consider "
    "supporting The Press and the future of independent community journalism."
)
COMMITMENT = (
    "Our commitment is to fund independent journalism that serves the public interest.Humanity, "
    "curiosity and honesty guide us, and our work is rooted in solidarity"
)
FACT = "Kylian Mbappe scored his 100th goal for Real Madrid in a 2-1 win at Barcelona on Sunday"
PREVIEW_BRIEF = (
    "This game has not been played yet - it is on Oct 25. Write a preview: the matchup, who is in "
    "form or hurt, what to watch and what is at stake. Never describe plays, a score or a result "
    "as if the game happened."
)
SNF = "Sunday Night Football: Jaxon Smith-Njigba, Seahawks defense dominate Chiefs, win 20-3"
WEEK6 = [
    "2026-10-14 · How to Watch: Denver Broncos vs. Seattle Seahawks — "
    "https://www.denverbroncos.com/news/denver-broncos-vs-seattle-seahawks-how-to-watch",
    "2026-10-14 · Seahawks rule 3 players OUT for Week 6 showdown with Denver Broncos — "
    "https://sports.yahoo.com/articles/seahawks-rule-3-players-week-222452387.html",
]


class DonationLinesTests(unittest.TestCase):
    """#1590: a donation ask is page boilerplate - in the reader and in the paste filter."""

    def test_the_page_reader(self):
        from core.link_facts import is_page_boilerplate

        self.assertTrue(is_page_boilerplate(DONATION))
        self.assertTrue(is_page_boilerplate(COMMITMENT))
        self.assertFalse(is_page_boilerplate(FACT))

    def test_the_paste_filter(self):
        from core.operator_facts import is_article_chrome

        self.assertTrue(is_article_chrome(DONATION))
        self.assertTrue(is_article_chrome(COMMITMENT))
        self.assertFalse(is_article_chrome(FACT))


class HookFragmentTests(unittest.TestCase):
    """#1587: a spoken pause does not end the hook, and a swap never strands a fragment."""

    def test_a_pause_before_a_lowercase_word_is_not_a_sentence_end(self):
        from apis.topic_tokens import split_sentences
        from core.hook_score import extract_hook

        self.assertEqual(
            extract_hook(
                "Patrick Mahomes didn't reach the red zone... for the first time in his *career*. "
                "Seattle held Kansas City to three points."
            ),
            "Patrick Mahomes didn't reach the red zone... for the first time in his *career*.",
        )
        self.assertEqual(
            extract_hook(
                "Jackson scored twice... and Manchester City's perfect start is gone. The same "
                "afternoon, Arsenal beat Everton 2-0."
            ),
            "Jackson scored twice... and Manchester City's perfect start is gone.",
        )
        self.assertEqual(
            split_sentences("Wait... What happened next? He won."),
            ["Wait...", "What happened next?", "He won."],
        )

    def test_a_swap_whose_rest_starts_lowercase_is_refused(self):
        from core.content_engine import replace_opener

        new = "Kansas City fell to 5-1 after a 20-3 loss in Seattle."
        self.assertIsNone(
            replace_opener(
                "Mahomes didn't reach the red zone. for the first time ever.",
                "Mahomes didn't reach the red zone.",
                new,
            )
        )
        self.assertEqual(
            replace_opener("Old opener. Seattle held them to three.", "Old opener.", new),
            new + " Seattle held them to three.",
        )

    def test_the_script_check_names_a_sentence_that_starts_mid_thought(self):
        from core.script_craft import mid_thought_starts, script_check

        self.assertEqual(
            mid_thought_starts(RUN187), ["and Manchester City's perfect start is gone."]
        )
        self.assertEqual(mid_thought_starts(RUN196), ["for the first time in his *career*."])
        why = script_check(script=RUN187)["why"]
        self.assertTrue(any("mid-thought" in w for w in why), why)
        # A brand written in lower case is not a fragment; nor is a number or a quote.
        self.assertEqual(
            mid_thought_starts(
                'The phone sold out. iPhone sales rose 4%. 2027 is next. "Wow," he said.'
            ),
            [],
        )


class StoredFragmentTests(unittest.TestCase):
    """#1587, live 2026-10-28: 6 of the last 60 stored drafts carry a stranded fragment -
    today's run 213 among them - and overnight reads the script check stored at draft time."""

    def test_overnight_holds_a_stored_draft_with_a_fragment(self):
        from core import batch_review

        draft = batch_review.PendingDraft(
            folder="",
            meta={"run_id": 213, "title": "UFC 333 bonuses", "script_clean": {"ok": True}},
            script=RUN187,
        )
        with (
            patch.object(batch_review, "dead_reason", return_value=""),
            patch.object(batch_review, "_blocking_claims", return_value=[]),
            patch.object(batch_review, "follow_up_since", return_value=""),
            patch.object(batch_review, "authenticity_now", return_value=("ok", "")),
        ):
            why = batch_review.unattended_block_reason(draft)
        self.assertIn("mid-thought", why)


class TitleRetryTests(unittest.TestCase):
    """#1591: a title the facts do not back is tried once more, and kept only when it is clean."""

    def test_a_clean_retry_replaces_it(self):
        from core.content_engine import retry_unbacked_title

        title, warnings, was = retry_unbacked_title(
            "Breaking down Real Madrid's set-piece adjustments that won El Clasico",
            ["title claim not backed by the facts: the win came via set-piece adjustments"],
            regenerate=lambda: "Mbappe's 100th goal sinks Barcelona in a 2-1 El Clasico",
            lint=lambda t: [],
        )
        self.assertEqual(title, "Mbappe's 100th goal sinks Barcelona in a 2-1 El Clasico")
        self.assertEqual(warnings, [])
        self.assertTrue(was.startswith("Breaking down"))

    def test_a_flagged_retry_keeps_the_first_and_its_warning(self):
        from core.content_engine import retry_unbacked_title

        first = "Breaking down Real Madrid's set-piece adjustments that won El Clasico"
        title, warnings, was = retry_unbacked_title(
            first, ["w"], regenerate=lambda: "Another unbacked title", lint=lambda t: ["w2"]
        )
        self.assertEqual((title, warnings, was), (first, ["w"], ""))

    def test_a_clean_title_is_not_retried(self):
        from core.content_engine import retry_unbacked_title

        called = []
        title, warnings, _was = retry_unbacked_title(
            "Fine title", [], regenerate=lambda: called.append(1) or "x", lint=lambda t: []
        )
        self.assertEqual((title, warnings, called), ("Fine title", [], []))


class SourcesTests(unittest.TestCase):
    """#1589: a source is listed because it backed a claim, and another game's lines are not
    confident for this one."""

    def test_another_games_line(self):
        from core.vault.relevance import other_game_teams

        self.assertEqual(other_game_teams(SNF, WEEK6[1]), ["Denver Broncos"])
        self.assertEqual(other_game_teams(SNF, WEEK6[0]), ["Denver Broncos"])
        self.assertEqual(
            other_game_teams(SNF, "Seattle Seahawks beat the Kansas City Chiefs 20-3"), []
        )
        self.assertEqual(other_game_teams("GTA 6 map leak", WEEK6[1]), [])

    def test_it_is_never_confident(self):
        from core.vault import relevance

        config = relevance.load_relevance_config()
        with (
            patch.object(relevance, "_entity_support", return_value=(1.0, 2, 2, ["Seahawks"])),
            patch.object(relevance, "_scaled_cosine", return_value=(1.0, 1.0)),
            patch.object(relevance, "_anchor_alignment", return_value=(1.0, ["nfl"], ["nfl"])),
        ):
            decision = relevance.score_vault_fact(
                topic=SNF, corpus=SNF, bullet=WEEK6[1], note_context="", tier="web", config=config
            )
            control = relevance.score_vault_fact(
                topic=SNF,
                corpus=SNF,
                bullet="Seahawks held the Chiefs to 3 points",
                note_context="",
                tier="web",
                config=config,
            )
        self.assertEqual(control.band, "confident")
        self.assertEqual(decision.band, "uncertain")
        self.assertEqual(decision.breakdown.get("other_game"), ["Denver Broncos"])

    def test_only_what_backed_a_claim_is_listed(self):
        from core.description_extras import collect_source_urls

        backed = "Smith-Njigba had 150 yards and a touchdown — https://www.espn.com/nfl/recap/x"
        facts = [*WEEK6, backed]
        with patch("core.obsidian_facts.load_fact_records", return_value=[]):
            urls = collect_source_urls(
                channel_id="tapin",
                topic=SNF,
                key_facts=facts,
                citations=["Smith-Njigba had 150 yards and a touchdown"],
            )
            unchanged = collect_source_urls(channel_id="tapin", topic=SNF, key_facts=facts)
        self.assertEqual(urls, ["https://www.espn.com/nfl/recap/x"])
        self.assertEqual(len(unchanged), 3)  # no citations given: today's behaviour


class MachineIntentTests(unittest.TestCase):
    """#1588: a draft the machine made carries its own intent; cues are the operator's words."""

    def test_the_brief_was_read_as_an_explainer(self):
        from core.angle_intent import detect_angle_intent

        self.assertEqual(
            detect_angle_intent(PREVIEW_BRIEF), "explainer"
        )  # what the fix routes around

    def test_draft_intent(self):
        from core.batch_generation import draft_intent

        self.assertEqual(draft_intent(own_idea=False, preview=PREVIEW_BRIEF), "preview")
        self.assertEqual(draft_intent(own_idea=False, preview=""), "default")
        self.assertEqual(draft_intent(own_idea=True, preview=""), "")

    def test_the_preview_intent_has_its_frames_and_stance(self):
        from apis.topic_variants import INTENT_ANGLES
        from core.angle_intent import ALL_INTENTS, stance_rule

        self.assertIn("preview", ALL_INTENTS)
        self.assertEqual(len(INTENT_ANGLES["preview"]), 5)
        self.assertIn("call", stance_rule("preview"))

    def test_discovery_takes_the_intent_given(self):
        from core.angle_intent import IntentRead
        from core.pipeline import discovery_intent

        with patch("core.angle_intent.resolve_intent") as resolve:
            read = discovery_intent(
                "Cincinnati Bengals at Baltimore Ravens", PREVIEW_BRIEF, "preview"
            )
        resolve.assert_not_called()
        self.assertEqual((read.intent, read.source), ("preview", "machine"))
        with patch(
            "core.angle_intent.resolve_intent", return_value=IntentRead("explainer", "cue")
        ) as resolve:
            self.assertEqual(
                discovery_intent("what is the Steam Machine", "", "").intent, "explainer"
            )
        resolve.assert_called_once()

    def test_a_headline_draft_asks_discovery_for_default(self):
        from core import batch_generation

        class Stop(Exception):
            pass

        seen = {}

        def capture(topic, **kwargs):
            seen.update(kwargs)
            raise Stop

        with (
            patch("core.pipeline.run_discovery", side_effect=capture),
            patch.object(batch_generation, "_game_start", return_value=None),
            patch.object(batch_generation, "_named_event_start", return_value=None),
        ):
            try:
                batch_generation.generate_draft(
                    "Alexander Volkanovski vs. Movsar Evloev full fight video highlights", "tapin"
                )
            except Stop:
                pass
        self.assertEqual(seen.get("intent"), "default")


if __name__ == "__main__":
    unittest.main()
