"""Wave 111 (2026-10-18): the next ten from hands_off_plan.md, in the operator's answers.

- #1303 (answered yes): NFL and NBA news join TapIn's ideas - half the recent videos are NFL or
  NBA, and the ideas covered gaming, UFC and soccer only.
"""

from __future__ import annotations

import unittest


class NflNbaIdeasTests(unittest.TestCase):
    """#1303."""

    def test_tapin_counts_nfl_and_nba_as_on_brand(self):
        from core.channel_context import on_brand_domains

        domains = on_brand_domains("tapin")
        self.assertLessEqual({"nfl", "nba", "ufc", "gaming"}, domains)

    def test_the_idea_pool_reads_their_feeds_within_the_cap(self):
        from core.best_bet import _IDEA_FEED_CAP, idea_feeds
        from core.channel_context import on_brand_domains

        feeds = idea_feeds("tapin", on_brand_domains("tapin"))
        names = {f["name"] for f in feeds}
        self.assertIn("Yahoo NFL", names)
        self.assertIn("Yahoo NBA", names)
        self.assertLessEqual(len(feeds), _IDEA_FEED_CAP)


LIVE_STATUS = {
    "uploadStatus": "processed",
    "privacyStatus": "private",
    "publishAt": "2026-10-21T02:00:00Z",
    "license": "youtube",
    "embeddable": True,
    "publicStatsViewable": True,
    "madeForKids": False,
    "selfDeclaredMadeForKids": False,
}


def _service(status=None):
    from unittest.mock import MagicMock

    service = MagicMock()
    items = [{"id": "vid", "status": dict(status or LIVE_STATUS)}]
    service.videos.return_value.list.return_value.execute.return_value = {"items": items}
    return service


class StatusKeptTests(unittest.TestCase):
    """#1306: measured 2026-10-18 - go-public and reschedule sent `status` with the privacy only,
    and YouTube cleared what the update left out: 7 of 56 videos (52tS6g1fu_k, 3nlkdFTjxe0 and
    five earlier go-publics) had embedding and public view counts switched off."""

    def test_a_change_keeps_what_youtube_holds(self):
        from publishing.snippet_update import writable_status

        body = writable_status(LIVE_STATUS, privacyStatus="public")
        self.assertEqual(body["privacyStatus"], "public")
        self.assertIs(body["embeddable"], True)
        self.assertIs(body["publicStatsViewable"], True)
        self.assertEqual(body["license"], "youtube")
        self.assertNotIn("publishAt", body)  # public now: the slot goes
        self.assertNotIn("uploadStatus", body)  # read-only
        self.assertNotIn("madeForKids", body)

    def test_a_scheduled_video_keeps_its_slot(self):
        from publishing.snippet_update import writable_status

        body = writable_status(LIVE_STATUS, embeddable=True)
        self.assertEqual(body["publishAt"], "2026-10-21T02:00:00Z")
        self.assertEqual(body["privacyStatus"], "private")

    def test_nothing_read_falls_back_to_the_upload_defaults(self):
        from publishing.snippet_update import writable_status

        body = writable_status({}, privacyStatus="public")
        self.assertIs(body["embeddable"], True)
        self.assertIs(body["publicStatsViewable"], True)

    def _send(self, call, service):
        import os
        from unittest.mock import MagicMock, patch

        from publishing import go_public

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = []
        repo.list_future_scheduled.return_value = []
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch.object(go_public, "override_held", return_value=False),
            patch.object(go_public, "_run_title", return_value=""),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=service),
            patch("publishing.crosspost.step", return_value=[]),
        ):
            call(go_public, repo)
        return service.videos.return_value.update.call_args.kwargs["body"]["status"]

    def test_go_public_sends_the_kept_fields(self):
        status = self._send(lambda gp, repo: gp.apply_go_public("vid", dry_run=False, repo=repo),
                            _service())  # fmt: skip
        self.assertEqual(status["privacyStatus"], "public")
        self.assertIs(status["embeddable"], True)
        self.assertIs(status["publicStatsViewable"], True)

    def test_a_reschedule_sends_the_kept_fields(self):
        from datetime import datetime, timezone

        when = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)
        status = self._send(
            lambda gp, repo: gp.apply_schedule_public("vid", when=when, repo=repo), _service()
        )
        self.assertEqual(status["publishAt"], "2026-10-18T22:00:00.000Z")
        self.assertIs(status["embeddable"], True)

    def test_the_repair_restores_what_an_update_switched_off(self):
        from publishing.snippet_update import status_repairs

        off = dict(LIVE_STATUS, embeddable=False, publicStatsViewable=False)
        fixes = status_repairs({"a": off, "b": LIVE_STATUS})
        self.assertEqual(list(fixes), ["a"])
        self.assertIs(fixes["a"]["embeddable"], True)
        self.assertEqual(fixes["a"]["publishAt"], "2026-10-21T02:00:00Z")  # still scheduled


class StatusRepairTests(unittest.TestCase):
    """#1306: `ops status-fields` lists the seven, and --apply restores them."""

    def _run(self, apply):
        import os
        from unittest.mock import MagicMock, patch

        from publishing import go_public

        off = dict(LIVE_STATUS, embeddable=False, publicStatsViewable=False)
        service = MagicMock()
        service.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "off1", "status": off}, {"id": "ok1", "status": LIVE_STATUS}]
        }
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [MagicMock(youtube_video_id="off1")]
        repo.list_future_scheduled.return_value = [MagicMock(youtube_video_id="ok1")]
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=service),
        ):
            lines = go_public.repair_status_fields("tapin", apply=apply, repo=repo)
        return lines, service.videos.return_value.update

    def test_the_dry_run_names_them_and_sends_nothing(self):
        lines, update = self._run(apply=False)
        self.assertIn("off1", "\n".join(lines))
        self.assertNotIn("ok1", "\n".join(lines))
        update.assert_not_called()

    def test_apply_restores_with_the_slot_kept(self):
        _lines, update = self._run(apply=True)
        body = update.call_args.kwargs["body"]
        self.assertEqual(body["id"], "off1")
        self.assertIs(body["status"]["embeddable"], True)
        self.assertEqual(body["status"]["publishAt"], "2026-10-21T02:00:00Z")


class VoiceNamesTests(unittest.TestCase):
    """#1296: a test memo was heard "Malott" as "Molot" - the run's own names correct it."""

    NAMES_FROM = "UFC Fight Night: Buckley vs. Malott"

    def test_a_near_name_is_corrected_to_the_runs(self):
        from core.facts.voice_notes import correct_names, known_names

        lines, fixes = correct_names(
            ["Molot finished Buckley in the second round."], known_names(self.NAMES_FROM)
        )
        self.assertEqual(lines, ["Malott finished Buckley in the second round."])
        self.assertEqual(fixes, [("Molot", "Malott")])

    def test_other_words_are_left_alone(self):
        from core.facts.voice_notes import correct_names, known_names

        line = "Mike Buckley had the better jab. Edmonton was loud."
        lines, fixes = correct_names([line], known_names(self.NAMES_FROM))
        self.assertEqual(lines, [line])
        self.assertEqual(fixes, [])


class DataReadGuardTests(unittest.TestCase):
    """#1305: measured 2026-10-18 - 117 tests opened files under the operator's real data/
    (traces, crosspost, platform metrics, the spend ledger, ...), so a verdict could change on
    their PC only. CI has no data/; the suite now sees what CI sees."""

    REPO = __import__("pathlib").Path(__file__).resolve().parents[1]

    def test_an_open_under_the_real_data_is_refused_and_recorded(self):
        import os
        import tempfile

        import tests

        tests.take_data_attempts()
        with self.assertRaises(FileNotFoundError):
            tests._guard_data_open("open", (str(self.REPO / "data" / "x.json"), "r", 0))
        with tempfile.TemporaryDirectory() as tmp:
            tests._guard_data_open("open", (os.path.join(tmp, "elsewhere.json"), "r", 0))
        named = tests.take_data_attempts()
        self.assertEqual(len(named), 1)
        self.assertIn("data/x.json", named[0])

    def test_a_test_that_opens_the_real_data_is_failed_by_name(self):
        import unittest as ut

        repo = self.REPO

        class Reads(ut.TestCase):
            def test_reads(self):
                try:
                    with open(repo / "data" / "crosspost_tapin.json", encoding="utf-8"):
                        pass
                except OSError:
                    pass  # fail-open code swallows it; the guard still names the test

        result = ut.TestResult()
        Reads("test_reads").run(result)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("#1305", result.failures[0][1])

    def test_the_stores_point_away_from_the_real_data(self):
        from analytics import reach_report
        from config import paths, seo
        from core import angle_intent, playlists, policy_canary, topic_trajectory, ypp_readiness
        from core.money import ledger
        from publishing import crosspost, platform_metrics

        real = str(self.REPO / "data").lower()
        stores = {
            "crosspost": crosspost.CROSSPOST_TEMPLATE,
            "platform_metrics": platform_metrics.METRICS_TEMPLATE,
            "feed_health": paths.FEED_HEALTH_FILE,
            "spend_ledger": ledger.LEDGER_FILE,
            "angle_picks": str(angle_intent.PICKS_FILE),
            "playlists": playlists.store_path_for("tapin"),
            "ypp": ypp_readiness.YPP_TEMPLATE,
            "policy_canary": policy_canary.SNAPSHOT_FILE,
            "topic_trajectory": topic_trajectory._TRAJECTORY_FILE,
            "seo_hints": seo.HINTS_DIR,
        }
        import os

        home = [k for k, v in stores.items() if os.path.abspath(str(v)).lower().startswith(real)]
        self.assertEqual(home, [])

    def test_the_tts_cache_line_reads_the_trace_dir_the_runs_write(self):
        import json
        import os
        import tempfile
        from unittest.mock import patch

        from core import run_trace, tts

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "7.json"), "w", encoding="utf-8") as handle:
                json.dump({"run_id": 7, "tts_cached": True}, handle)
            with patch.object(run_trace, "TRACES_DIR", tmp):
                flags = tts._tts_cached_flags_from_traces()
        self.assertEqual(len(flags), 1)


RAMS = "Arizona Cardinals at Los Angeles Rams"
SUMMARY = {
    "header": {"competitions": [{
        "status": {"type": {"completed": False}},
        "competitors": [
            {"homeAway": "home", "team": {"id": "14", "displayName": "Los Angeles Rams"}},
            {"homeAway": "away", "team": {"id": "22", "displayName": "Arizona Cardinals"}},
        ],
    }]},
    "predictor": {"homeTeam": {"id": "14", "gameProjection": "87.3"},
                  "awayTeam": {"id": "22", "gameProjection": "12.6"}},
    "injuries": [{"team": {"displayName": "Los Angeles Rams"},
                  "injuries": [{"status": "Questionable", "athlete": {"displayName": "Trent McDuffie"}},
                               {"status": "Active", "athlete": {"displayName": "Someone Fine"}}]}],
    "leaders": [{"team": {"displayName": "Los Angeles Rams"},
                 "leaders": [{"displayName": "Passing Yards",
                              "leaders": [{"athlete": {"displayName": "Matthew Stafford"},
                                           "displayValue": "139/216, 1,572 YDS, 9 TD, 6 INT"}]}]}],
    "lastFiveGames": [{"team": {"displayName": "Los Angeles Rams"},
                       "events": [{"gameResult": r} for r in "LWLWL"]}],
}  # fmt: skip


def _final(winner_home: bool):
    import copy

    final = copy.deepcopy(SUMMARY)
    comp = final["header"]["competitions"][0]
    comp["status"]["type"]["completed"] = True
    comp["competitors"][0]["winner"] = winner_home
    comp["competitors"][1]["winner"] = not winner_home
    return final


class GameReasonTests(unittest.TestCase):
    """#1304: a call's why was the season records - ESPN's game summary has more."""

    def test_the_board_keeps_the_event_id(self):
        from core.seasonal_calendar import game_detail

        detail = game_detail("nfl", {"id": "401872999", "name": RAMS, "competitions": [{}]})
        self.assertEqual(detail["event_id"], "401872999")

    def test_the_summary_becomes_supplied_lines(self):
        from core.predictions.calls import game_lines

        text = "\n".join(game_lines(SUMMARY))
        self.assertIn("Los Angeles Rams 87.3% to win", text)
        self.assertIn("Trent McDuffie (Questionable)", text)
        self.assertNotIn("Someone Fine", text)
        self.assertIn("Matthew Stafford", text)
        self.assertIn("last five: L W L W L", text)


class NumberedNamesTests(unittest.TestCase):
    """Live 2026-10-18: the 49ers' call was dropped as naming no side - `names_any` split
    "49ers" into "49 ers" in the text but not in the marker, so no team with a number in its
    name (49ers, 76ers) was ever named, in story clustering or anywhere else."""

    def test_a_numbered_team_is_named(self):
        from apis.topic_tokens import names_any

        self.assertTrue(names_any("San Francisco 49ers win", ["49ers"]))
        self.assertTrue(names_any("Philadelphia 76ers at New York Knicks", ["76ers"]))
        self.assertTrue(names_any("gta6-subpoenas", ["GTA"]))  # the stem case still holds
        self.assertFalse(names_any("Fortnite comes to Linux", ["49ers"]))


class CallsLedgerTests(unittest.TestCase):
    """#1304: every call kept, made once per event, and scored after the game."""

    def setUp(self):
        import os
        import tempfile
        from unittest.mock import patch

        from core.predictions import calls

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (
            patch.object(calls, "CALLS_FILE", os.path.join(tmp.name, "preview_calls.json")),
            patch.dict(os.environ, {"PREVIEW_CALLS": "true"}),
            patch(
                "core.seasonal_calendar.game_details",
                return_value={
                    "league": "nfl",
                    "event_id": "9",
                    "date": "2026-10-18T20:25Z",
                    "line": "LAR -9.5",
                },
            ),
            patch.object(calls, "_summary", return_value=SUMMARY),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _bet(self):
        from core.best_bet import BestBetResult

        return BestBetResult(topic=RAMS, domain="nfl", avg_engaged_rate=0.0, source="schedule",
                             supporting_runs=0, rationale="Sun 4:05 PM · Cardinals 1-5 at Rams 4-2")  # fmt: skip

    def test_the_prompt_carries_the_game_lines_and_a_call_is_made_once(self):
        from unittest.mock import patch

        from core.predictions import calls

        model = {"call": "Rams win", "why": "ESPN gives the Rams 87.3%"}
        with patch("core.llm_router.complete_json", return_value=model) as llm:
            first = calls.preview_calls([self._bet()], headlines=[])
            second = calls.preview_calls([self._bet()], headlines=[])
        self.assertEqual(llm.call_count, 1)  # the second menu build reused it
        self.assertIn("Trent McDuffie", llm.call_args.args[0])
        self.assertEqual(first, second)
        self.assertEqual(first[RAMS]["why"], "ESPN gives the Rams 87.3%")

    def test_a_finished_game_scores_the_call(self):
        from datetime import datetime, timezone
        from unittest.mock import patch

        from core.predictions import calls

        with patch("core.llm_router.complete_json", return_value={"call": "Rams win", "why": ""}):
            calls.preview_calls([self._bet()], headlines=[])
        later = datetime(2026, 10, 19, 3, 0, tzinfo=timezone.utc)
        with patch.object(calls, "_summary", return_value=_final(winner_home=True)):
            self.assertEqual(calls.score_calls(now=later), 1)
        self.assertIn("Calls: 1 of 1 right", calls.calls_line(now=later))

    def test_a_wrong_call_is_scored_wrong(self):
        from datetime import datetime, timezone
        from unittest.mock import patch

        from core.predictions import calls

        with patch("core.llm_router.complete_json", return_value={"call": "Rams win", "why": ""}):
            calls.preview_calls([self._bet()], headlines=[])
        later = datetime(2026, 10, 19, 3, 0, tzinfo=timezone.utc)
        with patch.object(calls, "_summary", return_value=_final(winner_home=False)):
            calls.score_calls(now=later)
        self.assertIn("Calls: 0 of 1 right", calls.calls_line(now=later))

    def test_a_non_call_is_not_kept(self):
        # Live 2026-10-18: "UFC Fight Night: Moicano vs. Nolan | No prediction available".
        from unittest.mock import patch

        from core.predictions import calls

        with patch("core.llm_router.complete_json",
                   return_value={"call": "No prediction available", "why": ""}):  # fmt: skip
            self.assertEqual(calls.preview_calls([self._bet()], headlines=[]), {})

    def test_home_or_road_that_no_line_says_drops_the_why(self):
        # Live: "Rams are 2-3 at home against Cardinals 1-4 on road" - no line said home or road.
        from unittest.mock import patch

        from core.predictions import calls

        model = {"call": "Rams win", "why": "Rams are 4-2 at home"}
        with patch("core.llm_router.complete_json", return_value=model):
            got = calls.preview_calls([self._bet()], headlines=[])
        self.assertEqual(got[RAMS]["call"], "Rams win")
        self.assertEqual(got[RAMS]["why"], "")

    def test_ops_predictions_prints_the_calls_line(self):
        from argparse import Namespace
        from unittest.mock import patch

        from scripts import ops

        printed: list[str] = []
        with (
            patch("core.predictions.ledger.report_lines", return_value=[]),
            patch("core.predictions.calls.score_calls", return_value=0),
            patch("core.predictions.calls.calls_line", return_value="Calls: 7 of 10 right"),
            patch(
                "builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))
            ),
        ):
            ops.cmd_predictions(Namespace(channel="tapin"))
        self.assertIn("Calls: 7 of 10 right", printed)


if __name__ == "__main__":
    unittest.main()
