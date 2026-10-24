"""Wave 83 (#1148-#1152): what the 2026-10-13 overnight run got wrong.

That run rendered two videos and both were wrong. Run 139 was titled and written as a Thunder
win over Indiana before the game was played; the title check flagged it and the flag never
reached the draft's record. Run 136 previewed a game two days after it was played and its last
line ended "in convincing fashion on tennessee." Run 137's claim check said 9 of 9 unsupported
while the run's own facts carried the score, the scorer and the signings; four finished videos
were waiting with nothing able to send them, and overnight would have rendered two more.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_batch_generation import BatchCase, _discovery, _pipeline_result
from tests.test_overnight_renders import _DraftsCase

# ---- #1148: a claim the facts carry is not unsupported -------------------------------------

SUMMARY = (
    "Summary: The Cleveland Cavaliers defeated the Orlando Magic with a final score of 119-105 "
    "on October 11, 2026. James Harden led the Cavaliers with 24 points, while Evan Mobley and "
    "Donovan Mitchell contributed 14 and 13 points."
)
PREVIEW = (
    "- Cleveland Cavaliers season preview: Lineup, roster and prediction (USA Today) - The "
    "Cleveland Cavaliers re-signed Donovan Mitchell and James Harden, while adding Peyton "
    "Watson. Is it enough to make them NBA title contenders?"
)
RECORDS = "Preseason notes: the Knicks are 0-3 and the Raptors are 1-1 ahead of Tuesday."
KAWHI = (
    "Summary: The New York Knicks are set to play a preseason game against the Toronto Raptors "
    "on October 13, 2026, and Kawhi Leonard is expected to debut."
)
FACTS = [SUMMARY, PREVIEW, RECORDS, KAWHI]


class CarriedByFactsTests(unittest.TestCase):
    def _carried(self, claim, facts=None, **kw):
        from core.claim_verifier import carried_by_facts

        return carried_by_facts(claim, FACTS if facts is None else facts, **kw)

    def test_run137_the_score_is_in_the_facts(self):
        self.assertEqual(self._carried("The Cavs beat Orlando 119-105 on October 11."), SUMMARY)

    def test_run137_the_scorer(self):
        self.assertEqual(self._carried("James Harden led the team with 24 points."), SUMMARY)

    def test_run127_a_score_said_another_way(self):
        line = (
            "Summary: The sources indicate that Spain's 2-0 victory over France in the World "
            "Cup semi-final led to scathing ratings."
        )
        self.assertEqual(
            self._carried("Spain beat France 2-0 in the World Cup semi-final.", [line]), line
        )
        self.assertEqual(self._carried("France beat Spain 2-0 in the semi-final.", [line]), "")

    def test_a_claim_with_no_number_stays_with_the_model(self):
        """ "Re-signed" and "added" sit in one sentence about three players: names sharing a
        line is not a claim, so the second look does not read them."""
        self.assertEqual(
            self._carried("The Cavaliers re-signed Donovan Mitchell and James Harden."), ""
        )
        self.assertEqual(self._carried("The Cavaliers re-signed Peyton Watson."), "")

    def test_a_number_inside_a_name_pins_nothing(self):
        """Measured on runs 128 and 129: "UFC Vegas 122" and "Modern Warfare 4" matched a
        headline that only named the event and the game."""
        self.assertEqual(
            self._carried(
                "Allen entered UFC Vegas 122 on a three-fight win streak.",
                ["- UFC Vegas 122 Results: Allen vs. Duncan (MMA Fighting)"],
            ),
            "",
        )
        self.assertEqual(
            self._carried(
                "Modern Warfare 4 is selling pricey DMZ spawn options.",
                ["- Modern Warfare 4 DMZ Early Access announced: How to play early (Dexerto)"],
            ),
            "",
        )

    def test_the_number_has_to_be_about_the_same_thing(self):
        self.assertEqual(self._carried("James Harden missed 24 shots."), "")

    def test_a_wrong_number_is_not_carried(self):
        self.assertEqual(self._carried("The Cavs beat Orlando 119-101 on October 11."), "")
        self.assertEqual(self._carried("James Harden led the team with 34 points."), "")

    def test_the_other_teams_record_is_not_carried(self):
        self.assertEqual(self._carried("The Knicks have started the preseason 0-3."), RECORDS)
        self.assertEqual(self._carried("The Raptors have started the preseason 0-3."), "")

    def test_run138_two_records_in_one_clause(self):
        line = "Preseason Game Details  Who: New York Knicks (0-3) at Toronto Raptors (1-1)   Date: Tuesday"
        self.assertEqual(self._carried("The Knicks have started the preseason 0-3.", [line]), line)
        self.assertEqual(self._carried("The Raptors are 1-1 in the preseason.", [line]), line)
        self.assertEqual(self._carried("The Raptors are 0-3 in the preseason.", [line]), "")

    def test_the_reverse_result_is_not_carried(self):
        self.assertEqual(self._carried("Orlando beat the Cavaliers 119-105 on October 11."), "")
        self.assertEqual(self._carried("The Cavaliers lost to Orlando 119-105."), "")

    def test_a_denial_is_not_carried(self):
        self.assertEqual(self._carried("James Harden did not score 24 points."), "")

    def test_two_names_on_a_line_are_not_a_claim(self):
        """Run 138: both names are on the fact line; "hands him the ball for the first time"
        is not."""
        claim = "Toronto is about to hand the ball to Kawhi Leonard for the first time."
        self.assertEqual(self._carried(claim), "")

    def test_nothing_to_check_is_not_carried(self):
        self.assertEqual(self._carried("The offense looked better."), "")

    def test_a_line_a_model_wrote_carries_nothing(self):
        self.assertEqual(
            self._carried("The Cavs beat Orlando 119-105 on October 11.", weak={SUMMARY.lower()}),
            "",
        )


def _all_unsupported(claims):
    return {
        "claims": [
            {"claim": claim, "supported": False, "citation": None, "type": kind}
            for claim, kind in claims
        ]
    }


class VerifierBackstopTests(unittest.TestCase):
    SCRIPT = (
        "The Cavs beat Orlando 119-105 on October 11. James Harden led the team with 24 points. "
        "Rookie Meleek Thomas averaged 27.3 points in Summer League."
    )
    CLAIMS = (
        ("The Cavs beat Orlando 119-105 on October 11.", "result"),
        ("James Harden led the team with 24 points.", "stat"),
        ("Rookie Meleek Thomas averaged 27.3 points in Summer League.", "stat"),
    )

    def _verify(self, facts_text, **kw):
        from core.claim_verifier import verify_claims

        seen = {}

        def fake(prompt, **kwargs):
            seen["prompt"] = prompt
            return _all_unsupported(self.CLAIMS)

        with (
            patch("core.llm_router.complete_json", side_effect=fake),
            patch.dict("os.environ", {"CLAIM_VERIFIER_ENABLED": "true"}),
        ):
            return verify_claims(self.SCRIPT, facts_text, topic="Cavaliers", **kw), seen

    def test_run137_a_wholesale_no_is_checked_against_the_facts(self):
        verification, _seen = self._verify("\n".join(FACTS))
        by = {c.claim: c for c in verification.claims}
        score = by["The Cavs beat Orlando 119-105 on October 11."]
        self.assertTrue(score.supported)
        self.assertEqual(score.citation_line, SUMMARY)
        self.assertEqual(score.by, "match")
        self.assertTrue(by["James Harden led the team with 24 points."].supported)
        self.assertFalse(
            by["Rookie Meleek Thomas averaged 27.3 points in Summer League."].supported
        )
        stored = verification.to_dict()
        self.assertEqual(stored["matched"], 2)
        self.assertEqual(stored["unsupported"], [self.CLAIMS[2][0]])
        self.assertEqual(stored["claims"][0]["by"], "match")
        self.assertNotIn("by", stored["claims"][2])

    def test_the_review_screen_says_which_were_matched(self):
        from core.claim_verifier import display_claim_verification

        verification, _seen = self._verify("\n".join(FACTS))
        lines: list[str] = []
        display_claim_verification(verification.to_dict(), print_fn=lines.append)
        self.assertIn("2 found word for word in the facts", "\n".join(lines))

    def test_the_fact_a_script_quotes_is_given_to_the_checker_first(self):
        """Run 137's check was sent 3,865 tokens - a full 12,000-character fact list. The
        writer's prompt has no such cap, so a fact past it could be written and not checked."""
        filler = [
            f"- Filler headline number {i} about something else entirely." for i in range(400)
        ]
        # The budget was 12,000 then; #1171 doubled it, so the test keeps the old one.
        with patch("core.claim_verifier._max_fact_chars", return_value=12000):
            verification, seen = self._verify("\n".join([*filler, SUMMARY]))
        self.assertIn("119-105", seen["prompt"])
        stored = verification.to_dict()
        self.assertGreater(stored["facts"]["left_out"], 0)
        self.assertEqual(stored["facts"]["given"] + stored["facts"]["left_out"], 401)

    def test_under_the_budget_the_order_is_untouched(self):
        from core.claim_verifier import _numbered_facts

        text = "\n".join(FACTS)
        self.assertEqual(_numbered_facts(text, script=self.SCRIPT), FACTS)

    def test_left_out_facts_are_said_on_the_review_screen(self):
        from core.claim_verifier import display_claim_verification

        lines: list[str] = []
        display_claim_verification(
            {
                "total": 1,
                "supported": 0,
                "unsupported": ["x"],
                "claims": [],
                "facts": {"given": 40, "left_out": 23},
            },
            print_fn=lines.append,
        )
        self.assertIn("23 of 63 fact lines did not fit", "\n".join(lines))


BRIEF = (
    "Key facts: Cleveland beat Orlando 119-105 on October 11; James Harden led the Cavaliers "
    "with 24 points."
)


def _cites_the_last_line_with(needle, claim, kind="result"):
    """A model that backs `claim` with the last numbered fact naming `needle` - the brief,
    when the brief is on the list, because the brief says it most plainly."""

    def fake(prompt, **kwargs):
        listed = prompt.split("VERIFIED FACTS:", 1)[1].split("SCRIPT:", 1)[0]
        facts = [line for line in listed.splitlines() if line.strip()]
        cited = [int(line.split(".", 1)[0]) for line in facts if needle in line]
        return {
            "claims": [
                {
                    "claim": claim,
                    "supported": bool(cited),
                    "citation": cited[-1] if cited else None,
                    "type": kind,
                }
            ]
        }

    return fake


class BriefNotCitedTests(unittest.TestCase):
    """Replayed on run 137 with a brief that restated the facts: the model cited the brief for
    five claims, and the #966 rule turned all five into "unsupported"."""

    CLAIM = "The Cavs beat Orlando 119-105 on October 11."
    SCRIPT = "The Cavs won big. " + CLAIM

    def _verify(self, facts_text):
        from core.claim_verifier import verify_claims

        seen = {}
        fake = _cites_the_last_line_with("119-105", self.CLAIM)

        def spy(prompt, **kwargs):
            seen["prompt"] = prompt
            return fake(prompt, **kwargs)

        with patch("core.llm_router.complete_json", side_effect=spy):
            verification = verify_claims(
                self.SCRIPT, facts_text, topic="Cavaliers", weak_lines={BRIEF}
            )
        return verification, seen["prompt"]

    def test_the_brief_is_not_shown_as_a_fact_to_cite(self):
        verification, prompt = self._verify("\n".join([PREVIEW, SUMMARY, BRIEF]))
        self.assertNotIn("Key facts: Cleveland beat Orlando", prompt)
        (claim,) = verification.claims
        self.assertTrue(claim.supported)
        self.assertEqual(claim.citation_line, SUMMARY)
        self.assertEqual(claim.by, "")

    def test_a_brief_with_no_source_behind_it_still_backs_nothing(self):
        verification, _prompt = self._verify("\n".join([PREVIEW, BRIEF]))
        (claim,) = verification.claims
        self.assertFalse(claim.supported)

    def test_only_a_brief_is_still_checked(self):
        verification, prompt = self._verify(BRIEF)
        self.assertIn("Key facts: Cleveland beat Orlando", prompt)
        (claim,) = verification.claims
        self.assertFalse(claim.supported)  # #966 as before


# ---- #1149: no more "on torontos" ----------------------------------------------------------


class CloserTests(unittest.TestCase):
    RUN138 = (
        "The Knicks' half-court offense meets Toronto's new-look spacing. Kawhi's return is "
        "expected to bring a three-point-heavy approach. The answer will come tonight."
    )
    RUN136 = (
        "Houston has won three straight against Tennessee, including a shutout last season. "
        "I expect the Texans to emerge victorious in convincing fashion. Tap in for more."
    )

    def test_run138_the_last_line_is_left_as_written(self):
        from core.authenticity import payoff_closer

        script, verdict = payoff_closer(self.RUN138)
        self.assertEqual(script, self.RUN138)
        self.assertNotIn("on torontos", script)
        self.assertFalse(verdict["closer_answered"])
        self.assertFalse(verdict["rewritten"])

    def test_run136_no_lowercase_word_is_appended(self):
        from core.authenticity import payoff_closer

        script, _verdict = payoff_closer(self.RUN136)
        self.assertNotIn("on tennessee", script)
        self.assertEqual(script, self.RUN136)


# ---- #1150: a flagged title blocks the overnight render -------------------------------------

TITLE_FLAG = (
    "title claim not backed by the facts: Oklahoma City's young core flexed growth in a "
    "statement win over the Indiana Pacers."
)


class FlaggedTitleTests(_DraftsCase):
    def test_run139_a_flagged_title_waits_for_a_person(self):
        from core.batch_review import pending_drafts, unattended_block_reason

        self._draft(139, title_warnings=[TITLE_FLAG])
        (draft,) = pending_drafts("tapin", root=self.tmp.name)
        self.assertEqual(
            unattended_block_reason(draft), "its title says something the facts do not"
        )

    def test_no_flag_no_wait(self):
        from core.batch_review import pending_drafts, unattended_block_reason

        self._draft(1, title_warnings=[])
        (draft,) = pending_drafts("tapin", root=self.tmp.name)
        self.assertEqual(unattended_block_reason(draft), "")


class DraftRecordTests(BatchCase):
    def _meta(self, result, topic="UFC 320", **kw):
        from core import batch_generation as bg

        with (
            patch("core.pipeline.run_discovery", return_value=_discovery(topic=topic)),
            patch("core.pipeline.run_pipeline", return_value=result),
        ):
            out = bg.generate_draft(topic, "tapin", **kw)
        with open(os.path.join(out.path, "meta.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_the_title_flag_reaches_the_draft_record(self):
        result = _pipeline_result()
        result.features["title_warnings"] = [TITLE_FLAG]
        self.assertEqual(self._meta(result)["title_warnings"], [TITLE_FLAG])

    def test_a_schedule_pick_carries_its_game_time(self):
        """#1151: the board knew the tip-off; the draft did not."""
        game = "Indiana Pacers at Oklahoma City Thunder"
        pick = {"offered": [{"topic": game, "source": "schedule"}], "picked": 1, "by": "batch"}
        result = _pipeline_result(
            script="The Thunder dissected Indiana instead of merely beating them. It was a statement."
        )
        result.title = (
            "Oklahoma City's young core flexes growth in statement win over Indiana Pacers"
        )
        with patch("core.seasonal_calendar.event_start", return_value="2099-10-14T00:00Z"):
            meta = self._meta(result, topic=game, best_bet=pick)
        self.assertEqual(meta["event_at"], "2099-10-14T00:00Z")
        self.assertIn("win over Indiana", meta["unplayed_result"])

    def test_a_typed_topic_has_no_game_time(self):
        meta = self._meta(_pipeline_result())
        self.assertFalse(meta.get("event_at"))
        self.assertFalse(meta.get("unplayed_result"))


# ---- #1151: a game draft knows when its game is --------------------------------------------

NOW = datetime(2026, 10, 13, 21, 0, tzinfo=timezone.utc)


class UnplayedResultTests(unittest.TestCase):
    GAME = "Indiana Pacers at Oklahoma City Thunder"

    def _found(self, text, topic=None):
        from core.facts.event_dates import unplayed_result

        return unplayed_result(text, topic or self.GAME)

    def test_run139_the_title_states_a_result(self):
        title = "Oklahoma City's young core flexes growth in statement win over Indiana Pacers"
        self.assertEqual(self._found(title), title)

    def test_run139_the_script_states_a_result(self):
        script = (
            "Tyrese Haliburton hasn't set foot in Paycom Center since Game 7. The Thunder "
            "dissected Indiana instead of merely beating them. It was a statement."
        )
        self.assertIn("dissected Indiana", self._found(script))

    def test_history_between_the_two_is_not_a_result(self):
        for line in (
            "The Pacers lost the 2025 Finals to OKC.",
            "A year ago, the Thunder beat Indiana for the title.",
            "Houston has won three straight against Tennessee, including a shutout last season.",
        ):
            topic = "Houston Texans at Tennessee Titans" if "Houston" in line else None
            self.assertEqual(self._found(line, topic), "", line)

    def test_a_question_or_a_prediction_is_not_a_result(self):
        for line in (
            "Can the Thunder beat Indiana again?",
            "I expect the Thunder to beat Indiana on Tuesday.",
            "If Haliburton sits, the Thunder will beat Indiana comfortably.",
        ):
            self.assertEqual(self._found(line), "", line)

    def test_another_teams_result_is_not_this_game(self):
        self.assertEqual(self._found("The Spurs beat Dallas by twenty."), "")

    def test_a_topic_that_is_not_a_game_states_nothing(self):
        self.assertEqual(self._found("The Thunder beat Indiana.", "Thunder season outlook"), "")


class GameStartedTests(unittest.TestCase):
    def test_before_and_after_tip_off(self):
        from core.facts.event_dates import game_started

        self.assertIs(game_started("2026-10-14T00:00Z", now=NOW), False)
        self.assertIs(game_started("2026-10-13T17:00Z", now=NOW), True)

    def test_a_board_day_with_no_hour_starts_when_the_day_is_over(self):
        from core.facts.event_dates import game_started

        self.assertIs(game_started("2026-10-13", now=NOW), False)
        self.assertIs(game_started("2026-10-12", now=NOW), True)

    def test_an_unreadable_time_is_unknown(self):
        from core.facts.event_dates import game_started

        self.assertIsNone(game_started("", now=NOW))
        self.assertIsNone(game_started("soon", now=NOW))


class GameDraftTests(_DraftsCase):
    def _reason(self, **over):
        from core.batch_review import pending_drafts, unattended_block_reason

        self._draft(1, **over)
        (draft,) = pending_drafts("tapin", root=self.tmp.name)
        return unattended_block_reason(draft, now=NOW)

    def test_run136_a_preview_after_the_game_waits(self):
        reason = self._reason(
            topic="Houston Texans at Tennessee Titans", event_at="2026-10-11T17:00Z"
        )
        self.assertIn("its game has started", reason)

    def test_a_preview_before_the_game_may_render(self):
        # #1367 (the operator, 2026-10-24): it renders unattended when its script makes a call.
        import os as _os

        from core.batch_review import pending_drafts, unattended_block_reason

        folder = self._draft(
            1, topic="Houston Texans at Tennessee Titans", event_at="2026-10-18T17:00Z"
        )
        with open(_os.path.join(folder, "draft.md"), "w", encoding="utf-8") as fh:
            fh.write("# Draft\n\n## Script\n\nHouston will win in Nashville on the ground.\n")
        (draft,) = pending_drafts("tapin", root=self.tmp.name)
        self.assertEqual(unattended_block_reason(draft, now=NOW), "")

    def test_run139_a_result_before_the_game_waits(self):
        reason = self._reason(
            topic="Indiana Pacers at Oklahoma City Thunder",
            event_at="2026-10-14T00:00Z",
            unplayed_result="The Thunder dissected Indiana instead of merely beating them.",
        )
        self.assertEqual(reason, "it states a result for a game not yet played")

    def test_a_game_draft_with_no_time_waits(self):
        """Drafts written before this wave: the topic is a fixture and nothing says when."""
        self.assertEqual(
            self._reason(topic="New York Knicks at Toronto Raptors"),
            "its game time is not known",
        )

    def test_a_topic_that_is_not_a_fixture_is_untouched(self):
        self.assertEqual(self._reason(topic="Topuria's next title defence"), "")


_BOARD = {
    "events": [
        {"name": "Indiana Pacers at Oklahoma City Thunder", "date": "2026-10-14T00:00Z"},
        {
            "name": "Old Game at Somewhere",
            "date": "2026-10-10T00:00Z",
            "status": {"type": {"completed": True}},
        },
    ]
}


class BoardStartTests(unittest.TestCase):
    def test_the_board_remembers_each_start(self):
        from core import seasonal_calendar as cal

        starts: dict[str, str] = {}
        topics = cal.topics_from_board("nba", _BOARD, today=NOW.date(), starts=starts)
        self.assertEqual(topics, [("Indiana Pacers at Oklahoma City Thunder", "nba")])
        self.assertEqual(starts, {"Indiana Pacers at Oklahoma City Thunder": "2026-10-14T00:00Z"})

    def test_event_start_reads_what_the_week_fetch_kept(self):
        from core import seasonal_calendar as cal

        with (
            patch.dict("os.environ", {"BEST_BET_SCHEDULE": "true"}),
            patch("sports.espn.get_scoreboard", return_value=_BOARD),
            patch.object(cal, "_board_today", return_value=NOW.date()),
            patch.dict(cal._STARTS, {}, clear=True),
        ):
            cal.fetch_week_topics()
            self.assertEqual(
                cal.event_start("Indiana Pacers at Oklahoma City Thunder"), "2026-10-14T00:00Z"
            )
            self.assertEqual(cal.event_start("Something typed"), "")


# ---- #1152: overnight pauses when finished videos pile up -----------------------------------


class ShelfCapTests(_DraftsCase):
    def _run(self, limit, waiting, cap="3"):
        from core.batch_review import render_unattended

        rendered: list[int] = []
        with patch.dict("os.environ", {"OVERNIGHT_SHELF_MAX": cap}):
            out = render_unattended(
                "tapin",
                limit,
                root=self.tmp.name,
                render=lambda draft, override: rendered.append(draft.run_id) or True,
                queue=lambda run_id, channel: 1,
                shelf=lambda channel: waiting,
            )
        return out, rendered

    def test_at_the_limit_nothing_renders(self):
        self._draft(1)
        self._draft(2)
        out, rendered = self._run(2, waiting=4)
        self.assertEqual(rendered, [])
        self.assertIn("4 finished videos are waiting", out["paused"])

    def test_it_stops_when_a_render_reaches_the_limit(self):
        for run_id in (1, 2, 3):
            self._draft(run_id)
        out, rendered = self._run(2, waiting=2)
        self.assertEqual(len(rendered), 1)
        self.assertIn("3 finished videos are waiting", out["paused"])

    def test_an_empty_shelf_renders_the_nightly_number(self):
        for run_id in (1, 2, 3):
            self._draft(run_id)
        out, rendered = self._run(2, waiting=0)
        self.assertEqual(len(rendered), 2)
        self.assertFalse(out.get("paused"))

    def test_zero_turns_the_limit_off(self):
        self._draft(1)
        _out, rendered = self._run(2, waiting=9, cap="0")
        self.assertEqual(rendered, [1])

    def test_the_plan_says_it_is_paused(self):
        from core import batch_review

        self._draft(1)
        with (
            patch.dict("os.environ", {"OVERNIGHT_SHELF_MAX": "3"}),
            patch.object(batch_review, "unattended_limit", return_value=2),
            patch.object(batch_review, "shelf_waiting", return_value=4),
        ):
            text = "\n".join(batch_review.unattended_plan_lines("tapin", root=self.tmp.name))
        self.assertIn("Paused", text)
        self.assertIn("4 finished videos are waiting", text)
        self.assertNotIn("would render", text)

    def test_the_suite_pins_the_limit_off(self):
        self.assertEqual(os.environ.get("OVERNIGHT_SHELF_MAX"), "0")

    def test_the_channel_shelf_is_what_is_counted(self):
        from core import batch_review

        rows = [{"run_id": 132}, {"run_id": 114}]
        with patch("core.stale_renders.shelf_rows", return_value=rows):
            self.assertEqual(batch_review.shelf_waiting("tapin"), 2)


if __name__ == "__main__":
    unittest.main()


class IdeaFlagTests(unittest.TestCase):
    """Found running the proof: the guide said `script-check --idea "..."` and the parser only
    knew `--topic`, so the command printed usage and wrote nothing."""

    def test_idea_is_the_topic(self):
        from scripts import ops

        seen = {}
        with patch(
            "core.runs.script_report.draft_lines",
            side_effect=lambda channel, idea: seen.update(channel=channel, idea=idea) or [],
        ):
            code = ops.main(["script-check", "--channel", "tapin", "--idea", "Chargers hope"])
        self.assertEqual(code, 0)
        self.assertEqual(seen, {"channel": "tapin", "idea": "Chargers hope"})


class MadeUpCitationTests(unittest.TestCase):
    def _verify(self, claim, kind):
        from core.claim_verifier import verify_claims

        answer = {"claims": [{"claim": claim, "supported": True, "citation": 9, "type": kind}]}
        with patch("core.llm_router.complete_json", return_value=answer):
            return verify_claims(claim, PREVIEW, topic="Cavaliers").claims[0]

    def test_a_line_that_was_never_shown_backs_no_result(self):
        self.assertFalse(self._verify("The Cavs won 119-101.", "result").supported)

    def test_a_hedged_rumor_stays_warn_only(self):
        claim = "Harden reportedly could re-sign with the Cavaliers."
        self.assertTrue(self._verify(claim, "rumor").supported)
