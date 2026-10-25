"""Wave 128 (2026-10-25): the next ten, from the plan written for the cloud the night before.

Diagnosed read-only on 10-24: run 185 was held for "The Chiefs are 5-0" because a dated operator
line read as a "10-14" record and the conflict filter dropped ESPN's line (#1560), and the board
matched the wrong game; "Chicago Bears ... passing game" read as gaming (#1567); run 164's thumbnail
was ours behind a top-and-bottom letterbox (#1565); the suite read data/experiments.json (#1570).
The operator, 10-24 and 10-25: a finished game is what it means with a call, the sport scrapers
stay in their sport (decision 76), and a chapter Short of a public video goes out by itself
(decision 77).
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

OPERATOR = (
    "2026-10-14 · Seahawks rule 3 players OUT for Week 6 showdown with Denver Broncos — "
    "https://sports.yahoo.com/articles/seahawks-rule-3-players-week-222452387.html "
    "(re: Seattle Seahawks miss key players)"
)
ESPN = (
    "ESPN team (as of 2026-10-24):\n"
    "- Kansas City Chiefs: 5-0; next: Kansas City Chiefs at Seattle Seahawks (2026-10-26)\n"
    "- Seattle Seahawks: 3-3; next: Kansas City Chiefs at Seattle Seahawks (2026-10-26)"
)
GAME = {
    "event_name": "Kansas City Chiefs at Seattle Seahawks",
    "completed": True,
    "status": "Final",
    "away_team": "Kansas City Chiefs",
    "home_team": "Seattle Seahawks",
    "away_score": "20",
    "home_score": "24",
    "winner": "Seattle Seahawks",
    "date": "2026-10-26T00:20Z",
}
FINAL_SIGNALS = {"live_scores": {"active": True, "data": {"matched_game": GAME}}}
PICK = (
    "NFL Week 7 picks: Seahawks defeat Chiefs; Rams prevail over Raiders - Los Angeles Times "
    "(22 Oct 2026)"
)


class ExperimentStoreTests(unittest.TestCase):
    """#1570: the suite never reads the operator's experiment arms."""

    def test_the_store_is_the_suites(self):
        import tests
        from config import paths

        self.assertTrue(
            paths.EXPERIMENTS_FILE.startswith(tests._SUITE_DATA_TMP), paths.EXPERIMENTS_FILE
        )


class DateIsNoRecordTests(unittest.TestCase):
    """#1560 (1): "2026-10-14" is a date, not a 10-14 record."""

    def test_a_dated_operator_line_does_not_drop_espn(self):
        from core.facts.conflicts import find_fact_conflicts

        records = [c for c in find_fact_conflicts([OPERATOR], ESPN) if c.kind == "record"]
        self.assertEqual(records, [])

    def test_a_us_date_is_no_record_either(self):
        from core.facts.conflicts import _record_pair

        self.assertIsNone(_record_pair("posted 10-14-2026 by the team"))
        self.assertEqual(_record_pair("Islam is 19-0"), (19, 0))
        self.assertEqual(_record_pair("record 18-0-0 (8 KO, 10 SUB)"), (18, 0))

    def test_espn_then_carries_the_claim(self):
        from core.claim_verifier import carried_by_facts

        self.assertIn("5-0", carried_by_facts("The Chiefs are 5-0.", ESPN.splitlines()))

    def test_a_date_is_no_football_cue(self):
        from apis.nfl_entities import team_names_in

        self.assertEqual(team_names_in("2026-10-14 · best phone chargers"), [])
        self.assertEqual(team_names_in("chargers are 0-4"), ["Los Angeles Chargers"])


def _event(away, home, *, completed=False, scores=("0", "0"), date="2026-10-26T00:20Z"):
    return {
        "name": f"{away} at {home}",
        "date": date,
        "status": {
            "type": {"description": "Final" if completed else "Scheduled", "completed": completed}
        },
        "competitions": [
            {
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {"displayName": away},
                        "score": scores[0],
                        "winner": False,
                    },
                    {
                        "homeAway": "home",
                        "team": {"displayName": home},
                        "score": scores[1],
                        "winner": completed,
                    },
                ]
            }
        ],
    }


class LeadPairTests(unittest.TestCase):
    """#1560 (2): the board is matched on the topic's first two teams, in topic order."""

    TEAM = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "signal_payloads" / "live_scores.json")
        .read_text(encoding="utf-8")
    )["response"]  # fmt: skip

    def test_the_lead_pair(self):
        from apis.live_scores_api import _lead_pair

        topic = "NFL Week 7 picks: Chiefs edge Seahawks, Bengals over Ravens"
        self.assertEqual(
            _lead_pair(["bengals", "ravens", "chiefs", "seahawks"], topic), ["chiefs", "seahawks"]
        )

    def test_run_185s_board_matches_chiefs_at_seahawks(self):
        from apis import live_scores_api

        board = {"events": [_event("Cincinnati Bengals", "Baltimore Ravens"),
                            _event("Kansas City Chiefs", "Seattle Seahawks")]}  # fmt: skip
        topic = (
            "NFL Week 7 picks and score predictions: Chiefs edge Seahawks, Bengals over Ravens - "
            "all 5 angles"
        )
        with (
            patch("sports.espn.get_team", return_value=self.TEAM),
            patch("sports.espn.get_scoreboard", return_value=board),
        ):
            sig = live_scores_api.get_live_scores_signal(topic)
        self.assertEqual(
            sig["data"]["matched_game"]["event_name"], "Kansas City Chiefs at Seattle Seahawks"
        )

    def test_the_nba_board_too(self):
        from apis import live_scores_api

        board = {"events": [_event("Los Angeles Lakers", "Miami Heat"),
                            _event("Boston Celtics", "New York Knicks")]}  # fmt: skip
        with patch("sports.espn.get_scoreboard", return_value=board):
            sig = live_scores_api.get_live_scores_signal(
                "NBA: Knicks edge Celtics, Lakers over Heat"
            )
        self.assertEqual(
            sig["data"]["matched_game"]["event_name"], "Boston Celtics at New York Knicks"
        )


class GameWordTests(unittest.TestCase):
    """#1567: a named NFL team and a football word outrank the bare word "game"."""

    def test_the_two_live_topics_read_nfl(self):
        from apis.register_signals import _gated_signal_names
        from apis.topic_scorer import infer_topic_domain

        for topic in (
            "Chicago Bears defense struggles against Atlanta's early passing game",
            "Green Bay's running game faces Chicago's defensive front",
        ):
            self.assertEqual(infer_topic_domain(topic), "nfl", topic)
            self.assertNotIn("live_scores", _gated_signal_names(topic, "tapin"))

    def test_games_stay_games(self):
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain("Madden 27: the Bears' ratings"), "gaming")
        self.assertEqual(infer_topic_domain("best co-op game of 2026"), "gaming")
        self.assertEqual(infer_topic_domain("Saints Row game review"), "gaming")


class LetterboxTests(unittest.TestCase):
    """#1565: a 16:9 thumbnail letterboxed top and bottom is still ours."""

    def _ours(self):
        """Run 164's shape: a dark arena whose edges are near black - averaged over the frame's
        black rows too, those columns read as bars and were cut."""
        from PIL import Image, ImageDraw

        ours = Image.new("RGB", (1280, 720), (22, 22, 22))
        draw = ImageDraw.Draw(ours)
        draw.rectangle((220, 0, 1060, 250), fill=(30, 60, 190))  # the lit arena top
        draw.rectangle((540, 140, 760, 720), fill=(225, 190, 160))  # the fighter
        draw.rectangle((240, 320, 900, 420), fill=(250, 250, 250))  # the headline
        return ours

    def test_a_wide_image_in_the_frame(self):
        from PIL import Image

        from youtube.thumbnail_check import same_image

        ours = self._ours()
        live = Image.new("RGB", (480, 360), (0, 0, 0))
        live.paste(ours.resize((480, 270)), (0, 45))
        self.assertTrue(same_image(ours, live))
        other = Image.new("RGB", (480, 360), (0, 0, 0))
        other.paste(Image.new("RGB", (480, 270), (200, 200, 200)), (0, 45))
        self.assertFalse(same_image(ours, other))

    def test_the_tall_case_still_holds(self):
        from PIL import Image, ImageDraw

        from youtube.thumbnail_check import same_image

        ours = Image.new("RGB", (1080, 1920), (20, 60, 200))
        ImageDraw.Draw(ours).rectangle((100, 600, 980, 1300), fill=(250, 220, 30))
        live = Image.new("RGB", (480, 360), (0, 0, 0))
        live.paste(ours.resize((202, 360)), (139, 0))
        self.assertTrue(same_image(ours, live))


class SentThumbnailTests(unittest.TestCase):
    """#1569: the check reads the thumbnail the upload sent, and says when none was."""

    def test_the_upload_jobs_path_is_ours(self):
        import tempfile

        from youtube import thumbnail_check

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            with patch.object(thumbnail_check, "_asset_thumbnail", return_value=None):
                self.assertEqual(thumbnail_check._uploaded_thumbnail(172, sent=path), path)
        finally:
            os.unlink(path)

    def test_none_sent_is_said(self):
        from youtube import thumbnail_check

        row = SimpleNamespace(youtube_video_id="L5ZAr_1Y72s", content_run_id=191,
                              published_at=datetime.now(timezone.utc))  # fmt: skip
        logs = MagicMock()
        logs.list_uploaded_for_channel.return_value = [row]
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=logs),
            patch.object(thumbnail_check, "_sent_thumbnails", return_value={}),
            patch.object(thumbnail_check, "_uploaded_thumbnail", return_value=None),
        ):
            lines = thumbnail_check.recent_lines("tapin")
        self.assertIn("no thumbnail of ours was sent", "\n".join(lines))


class SportGatingTests(unittest.TestCase):
    """#1566 (decision 76): the MMA scrapers off NBA and NFL, the soccer API on soccer only."""

    def test_team_sports_skip_the_mma_scrapers_and_the_soccer_api(self):
        from apis.register_signals import _gated_signal_names

        for topic in ("NBA Finals Knicks vs Spurs", "Kansas City Chiefs at Seattle Seahawks"):
            gated = _gated_signal_names(topic, "tapin")
            self.assertTrue({"ufc_context", "tapology", "api_sports"} <= gated, (topic, gated))
            self.assertNotIn("live_scores", gated)

    def test_soccer_keeps_its_api_and_ufc_its_scrapers(self):
        from apis.register_signals import _gated_signal_names

        soccer = _gated_signal_names(
            "Manchester City ofund guilty, what does this mean for the prem", "tapin"
        )
        self.assertNotIn("api_sports", soccer)
        ufc = _gated_signal_names("UFC 311 Topuria title defense", "tapin")
        self.assertNotIn("ufc_context", ufc)

    def test_a_neutral_topic_skips_the_soccer_api(self):
        from apis.register_signals import _gated_signal_names

        self.assertIn("api_sports", _gated_signal_names("Election night results in Ohio", "tapin"))


class ChapterShortScheduleTests(unittest.TestCase):
    """#1571 (decision 77): a chapter Short of a public video goes public at a free slot."""

    def _run(self, rows, features, *, held=()):
        from core import chapter_shorts

        logs = MagicMock()
        logs.list_uploaded_for_channel.return_value = rows
        when = datetime(2026, 10, 26, 16, 0, tzinfo=timezone.utc)
        scheduled = MagicMock(
            return_value=SimpleNamespace(status="scheduled", detail="goes public Mon noon")
        )
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=logs),
            patch("core.run_features.load_features", side_effect=lambda rid: features.get(rid, {})),
            patch("core.spaced_queue.slot_for_run", return_value=(when, "")),
            patch("publishing.go_public.apply_schedule_public", scheduled),
            patch("publishing.go_public.override_held", side_effect=lambda rid: rid in held),
        ):
            lines = chapter_shorts.schedule_waiting_shorts("tapin")
        return lines, scheduled

    def _row(self, rid, privacy, vid):
        return SimpleNamespace(
            id=rid, content_run_id=rid, privacy_status=privacy, youtube_video_id=vid
        )

    def test_a_short_of_a_public_video_is_scheduled(self):
        rows = [self._row(92, "public", "P92"), self._row(191, "unlisted", "S191")]
        lines, scheduled = self._run(
            rows, {191: {"short_source": "chapter_cut", "parent_run_id": 92}}
        )
        scheduled.assert_called_once()
        self.assertEqual(scheduled.call_args.args[0], "S191")
        self.assertIn("191", "\n".join(lines))

    def test_the_rest_waits(self):
        rows = [
            self._row(185, "unlisted", "P185"),  # the parent is not public
            self._row(186, "unlisted", "S186"),
            self._row(188, "unlisted", "R188"),  # a render, not a chapter Short
            self._row(92, "public", "P92"),
            self._row(190, "unlisted", "S190"),  # held for a claim
        ]
        features = {
            186: {"short_source": "chapter_cut", "parent_run_id": 185},
            190: {"short_source": "chapter_cut", "parent_run_id": 92},
        }
        _lines, scheduled = self._run(rows, features, held=(190,))
        scheduled.assert_not_called()

    def test_the_worker_pass_runs_it(self):
        from jobs import worker

        with (
            patch.object(worker, "_post_due_pins"),
            patch.object(worker, "_crosspost_scheduled_live"),
            patch.object(worker, "_previews_first"),
            patch.object(worker, "process_one", return_value=False),
            patch.object(worker, "_schedule_chapter_shorts") as shorts,
        ):
            worker.drain_due()
        shorts.assert_called_once()


class DomainAuditTests(unittest.TestCase):
    """#1370: `ops signal-audit` by topic domain."""

    def test_a_signal_that_ran_and_fed_nothing_is_named(self):
        from core.runs import signal_audit
        from core.runs.signal_audit import RunSignals

        signal = {"active": True, "connected": True}
        runs = [
            RunSignals(
                1, "NBA Finals Knicks vs Spurs", {"ufc_context": dict(signal), "news": dict(signal)}
            ),
            RunSignals(
                2,
                "Lakers trade rumors for the NBA deadline",
                {"ufc_context": dict(signal), "news": dict(signal)},
            ),
        ]
        with patch.object(
            signal_audit,
            "_fed_lines",
            side_effect=lambda name, sig: ["x"] if name == "news" else [],
        ):
            lines = signal_audit.domain_lines(runs)
            report = signal_audit.report_lines(runs)
        nba = next(line for line in lines if line.strip().startswith("nba"))
        self.assertIn("news 2", nba)
        self.assertIn("ufc_context 2", nba.split("never fed")[1])
        self.assertTrue(any("by topic domain" in line for line in report))


class PregameResultTests(unittest.TestCase):
    """#1363: a finished game's facts lose the pre-game lines that state a result."""

    def test_the_pick_is_a_pregame_result(self):
        from core.facts.event_dates import is_pregame_result

        self.assertTrue(is_pregame_result(PICK, GAME))

    def test_what_stays(self):
        from core.facts.event_dates import drop_pregame_results

        kept_lines = [
            "NFL Week 7 early odds: Undefeated Chiefs are underdogs - CBS Sports (19 Oct 2026)",
            "Seahawks beat Chiefs 24-20 as Seattle's defense held - ESPN (25 Oct 2026)",
            "Seahawks beat Chiefs 24-20",
            "ESPN live/final (use as source of truth for score and winner): Kansas City Chiefs 20 at "
            "Seattle Seahawks 24 — Final — winner: Seattle Seahawks",
        ]
        kept, dropped = drop_pregame_results("\n".join([PICK, *kept_lines]), GAME)
        self.assertEqual(dropped, [PICK])
        for line in kept_lines:
            self.assertIn(line, kept)

    def test_defeat_is_a_result_word(self):
        from core.facts.event_dates import unplayed_result

        self.assertIn(
            "defeat",
            unplayed_result(
                "The Seahawks defeat the Chiefs at home.", "Kansas City Chiefs at Seattle Seahawks"
            ),
        )
        self.assertEqual(
            unplayed_result(
                "The undefeated Chiefs visit the Seahawks.",
                "Kansas City Chiefs at Seattle Seahawks",
            ),
            "",
        )

    def test_espn_keeps_the_event_date(self):
        from apis.live_scores_api import _parse_event

        self.assertEqual(_parse_event(_event("A Team", "B Team"))["date"], "2026-10-26T00:20Z")


class FinishedGameTests(unittest.TestCase):
    """#1362 (decision 76): a finished game is written as what it means, ending on a call."""

    def test_a_final_on_the_topic(self):
        from core.facts.event_dates import finished_game

        self.assertEqual(finished_game(FINAL_SIGNALS, "Seahawks beat Chiefs: what it means"), GAME)

    def test_not_a_final_or_not_this_game(self):
        from core.facts.event_dates import PREVIEW_PREFIX, finished_game

        live = {"live_scores": {"data": {"matched_game": {**GAME, "completed": False}}}}
        self.assertIsNone(finished_game(live, "Seahawks beat Chiefs"))
        self.assertIsNone(finished_game(FINAL_SIGNALS, "Bengals over Ravens"))
        self.assertIsNone(
            finished_game(
                FINAL_SIGNALS, "Seahawks vs Chiefs", brief=f"{PREVIEW_PREFIX} - it is on Oct 25."
            )
        )

    def test_the_brief(self):
        from core.facts.event_dates import result_brief

        brief = result_brief(GAME)
        self.assertIn("Kansas City Chiefs 20", brief)
        self.assertIn("Seattle Seahawks 24", brief)
        self.assertIn("call", brief)
        self.assertIn("play-by-play", brief)


if __name__ == "__main__":
    unittest.main()
