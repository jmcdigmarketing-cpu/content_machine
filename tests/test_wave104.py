"""Wave 104: Cursor's wave 103 re-audited before it was committed, and five items of the audit.

Corrections to wave 103:
- #1249 gated a neutral topic to TapIn's *primary* domain, gaming - "Payton Pritchard signed a
  two-year extension" reads neutral and lost every sports signal: run 98 again (a football
  story on TapIn routed as gaming).
- #1252 dropped a cooling provider from the chain; an empty chain falls back to a paid OpenAI
  call (strict free mode raises instead).
- #1253 counted the drafts before the same night set the old ones aside.
- #1248 offered "at its slot", which did nothing (the operator: remove it).
- #1064 made a video public on one click in the app.

Items: #1263 CI red was said nowhere; #1262 a confirmed claim listed again; #1261 an undated
run counted as this week; #1265 the .env warning once per process; #1266 "Give" was a name.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PRITCHARD = "Payton Pritchard signed a two-year extension"
POKEMON = "Pokemon at 5 PM"
_SPORTS = ("sports", "live_scores", "odds", "api_sports")


# ---- C1 #1249: a neutral topic keeps every group the channel covers -------------------------


class NeutralGatingTests(unittest.TestCase):
    def test_a_player_topic_on_tapin_keeps_its_sports_signals(self):
        from apis.register_signals import _gated_signal_names
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain(PRITCHARD), "neutral")
        gated = _gated_signal_names(PRITCHARD, "tapin")
        for name in _SPORTS:
            self.assertNotIn(name, gated)
        self.assertNotIn("rawg", gated)

    def test_run_158_still_skips_finance_and_music(self):
        from apis.register_signals import _gated_signal_names

        gated = _gated_signal_names(POKEMON, "tapin")
        for name in ("fred", "coingecko", "lastfm", "sec_edgar"):
            self.assertIn(name, gated)

    def test_a_channel_with_one_domain_gates_the_rest(self):
        from apis.register_signals import _gated_signal_names

        gated = _gated_signal_names(PRITCHARD, "moneywise")
        self.assertIn("odds", gated)
        self.assertNotIn("fred", gated)


# ---- C2 #1252: a cooling provider waits at the end of the chain --------------------------------


class CoolingChainTests(unittest.TestCase):
    def setUp(self):
        from core import llm_router

        self.router = llm_router
        self.addCleanup(llm_router._llm_cool_until.clear)

    def _cool(self, provider="openrouter"):
        exc = SimpleNamespace(
            status_code=429, response=SimpleNamespace(headers={"Retry-After": "30"})
        )
        self.router.cool_provider(provider, exc)

    def test_it_moves_to_the_end(self):
        with patch.object(self.router, "_provider_available", return_value=True):
            before = [p for p, _m in self.router._resolve_chain("cheap")]
            self._cool()
            after = [p for p, _m in self.router._resolve_chain("cheap")]
        self.assertIn("openrouter", before)
        self.assertEqual(after[-1], "openrouter")
        self.assertEqual(sorted(after), sorted(before))

    def test_alone_it_is_still_asked_rather_than_a_paid_model(self):
        only = patch.object(
            self.router, "_provider_available", side_effect=lambda p, _t: p == "openrouter"
        )
        with only:
            self._cool()
            chain = [p for p, _m in self.router._resolve_chain("cheap")]
        self.assertEqual(chain, ["openrouter"])


# ---- C3 #1253: the night sets old drafts aside before it counts the waiting ones -------------


class DraftCapAfterExpiryTests(unittest.TestCase):
    def test_drafts_set_aside_tonight_do_not_hold_new_ones(self):
        from core.overnight import OvernightResult, _run_overnight_body

        waiting = [object()] * 9
        order: list[str] = []

        def expire(_channel):
            order.append("expire")
            del waiting[5:]  # four drafts past twice their window leave
            return [1, 2, 3, 4]

        def pending(_channel, **_k):
            order.append("count")
            return list(waiting)

        result = OvernightResult(channel_id="tapin")
        with (
            patch("core.overnight_quota.adjust_count", return_value=(3, "")),
            patch("core.batch_review.expire_enabled", return_value=True),
            patch("core.batch_review.expire_old_drafts", side_effect=expire),
            patch("core.batch_review.pending_drafts", side_effect=pending),
            patch("core.batch_generation.collect_topics", return_value=[]) as collect,
            patch("core.batch_review.unattended_limit", return_value=0),
        ):
            _run_overnight_body("tapin", result, count=3, topics=None, file=None, facts_file=None)
        self.assertEqual(order[:2], ["expire", "count"])
        self.assertEqual(collect.call_args.args[3], 3)  # 5 waiting is under the cap of 8
        self.assertEqual(result.expired, 4)


# ---- C4 #1248: no "at its slot" ---------------------------------------------------------------


class NoSlotChoiceTests(unittest.TestCase):
    def test_the_prompt_and_the_menu_do_not_offer_a_slot(self):
        from core.ui import prompt_startup_mode
        from publishing.go_public import watch_and_publish

        prompts: list[str] = []
        row = SimpleNamespace(id=1, content_run_id=1, youtube_video_id="aaa",
                              privacy_status="unlisted", channel_id="tapin")  # fmt: skip
        with (
            patch("publishing.go_public.unlisted_holds", return_value=[row]),
            patch("publishing.go_public._run_for_hold", return_value=None),
            patch("publishing.go_public.load_features", return_value={}),
            patch("publishing.go_public.apply_go_public") as apply,
        ):
            decisions = watch_and_publish("tapin", ask=lambda p: prompts.append(p) or "s",
                                          print_fn=lambda *_a: None)  # fmt: skip
        apply.assert_not_called()
        self.assertEqual(decisions, ["keep"])
        self.assertNotIn("slot", prompts[0])
        said: list[str] = []
        with patch("core.intelligence_report.intelligence_mode_enabled", return_value=False):
            prompt_startup_mode(print_fn=lambda *a: said.append(" ".join(map(str, a))),
                                input_fn=lambda _p: "1")  # fmt: skip
        self.assertFalse(any("7)" in line and "slot" in line for line in said))


# ---- C5 #1064: the app asks before a video goes public -----------------------------------------

try:
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
except ImportError:
    QApplication = QMessageBox = QPushButton = None  # type: ignore[misc, assignment]

from tests.qt_support import requires_qt


@requires_qt
class GoPublicAsksTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def _window(self):
        from desktop.review import ReviewWindow

        with patch("core.facts.claim_confirm.load_features", return_value={}):
            return ReviewWindow(context={"mp4_path": "", "run_id": 10, "channel_id": "tapin",
                                         "unlisted_url": "https://youtu.be/abc123"})  # fmt: skip

    def _press(self, answer):
        window = self._window()
        self.addCleanup(window.close)
        button = {w.text(): w for w in window.findChildren(QPushButton)}["Go public"]
        with (
            patch("desktop.review.QMessageBox.question", return_value=answer) as asked,
            patch(
                "core.review_bind.go_public_from_room",
                return_value={"status": "public", "detail": ""},
            ) as flip,  # fmt: skip
            patch("core.facts.claim_confirm.load_features", return_value={}),
        ):
            button.click()
        asked.assert_called_once()
        return flip

    def test_no_keeps_it_unlisted(self):
        self._press(QMessageBox.StandardButton.No).assert_not_called()

    def test_yes_makes_it_public(self):
        self._press(QMessageBox.StandardButton.Yes).assert_called_once()


# ---- #1263: CI red is said ---------------------------------------------------------------------


def _run(conclusion, when, run_id):
    return {"status": "completed", "conclusion": conclusion, "createdAt": when,
            "databaseId": run_id, "headSha": f"{run_id:07d}"}  # fmt: skip


class CiLineTests(unittest.TestCase):
    def test_a_red_streak_says_since_when_and_what(self):
        from core.status import ci_red_line

        runs = [_run("failure", "2026-10-17T03:35:57Z", 3), _run("failure", "2026-10-11T02:10:00Z", 2),
                _run("success", "2026-10-10T18:00:00Z", 1)]  # fmt: skip
        line = ci_red_line(runs, ["Type check (ratchet)"])
        self.assertIn("Oct 11", line)
        self.assertIn("2 runs", line)
        self.assertIn("Type check", line)

    def test_green_or_running_says_nothing(self):
        from core.status import ci_red_line

        self.assertEqual(ci_red_line([_run("success", "2026-10-17T18:00:00Z", 4)], []), "")
        running = {"status": "in_progress", "conclusion": "", "createdAt": "2026-10-17T19:00:00Z"}
        self.assertEqual(ci_red_line([running, _run("success", "2026-10-17T18:00:00Z", 4)], []), "")
        self.assertEqual(ci_red_line([], []), "")

    def test_no_gh_and_the_suite_say_nothing(self):
        from core.status import ci_line

        self.assertEqual(ci_line(), "")  # the suite turns it off
        with (
            patch.dict(os.environ, {"CI_STATUS_LINE": "true"}),
            patch("subprocess.run", side_effect=FileNotFoundError("gh")),
        ):
            self.assertEqual(ci_line(), "")


# ---- #1262: a confirmed claim is not listed again ---------------------------------------------


class ConfirmedClaimTests(unittest.TestCase):
    def test_the_fallback_skips_a_claim_confirmed_with_a_source(self):
        from core.facts.claim_confirm import flagged_claims

        claim = "the score was 3-0 in the first half"
        features = {
            "claim_verification": {"unsupported": [], "supported": 1, "total": 1},
            "grounding_override": True,
            "grounding_override_claims": [claim],
            "claims_confirmed": [{"claim": claim, "source": "https://espn.com/score"}],
        }
        self.assertEqual(flagged_claims(features), [])


# ---- #1261: an undated run is not "this week" --------------------------------------------------


class UndatedRunTests(unittest.TestCase):
    def test_a_row_without_a_date_does_not_count(self):
        from core.authenticity import scripts_within

        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        rows = [("Dated today.", now), ("No date at all.", None)]
        self.assertEqual(scripts_within(rows, now=now), ["Dated today."])


# ---- #1265: the .env warning once a run --------------------------------------------------------


class EnvWarningOnceTests(unittest.TestCase):
    def test_a_second_load_and_a_child_do_not_say_it_again(self):
        from config.settings import load_env_file

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("GOOD=1\nthis line has no name\n")
            env = {k: v for k, v in os.environ.items() if k != "CONTENT_ENV_LINES_SAID"}
            with patch.dict(os.environ, env, clear=True):
                with self.assertLogs("config.settings", level=logging.WARNING) as said:
                    load_env_file(path)
                    load_env_file(path)
                    logging.getLogger("config.settings").warning("end")
                self.assertEqual(sum("not NAME=value" in r for r in said.output), 1)
                self.assertEqual(os.environ.get("CONTENT_ENV_LINES_SAID"), "1")


# ---- #1266: a sentence's first verb is not a name ---------------------------------------------


class OpeningVerbTests(unittest.TestCase):
    def test_give_is_not_a_specific(self):
        from core.facts.grounding import find_ungrounded_entities

        script = "Give Buckley credit, he finishes fights. Watch Malott walk him down."
        facts = "Joaquin Buckley meets Mike Malott in Edmonton."
        flagged = find_ungrounded_entities(script, facts)
        self.assertFalse(any("Give" in f or "Watch" in f for f in flagged), flagged)

    def test_a_name_after_the_verb_is_still_checked(self):
        from core.facts.grounding import find_ungrounded_entities

        flagged = find_ungrounded_entities(
            "Give Buckley credit.", "Mike Malott fights in Edmonton."
        )
        self.assertTrue(any("Buckley" in f for f in flagged), flagged)


# ---- D1 #1250: explain prints phases, not every value in `timings` ----------------------------


class ExplainPhasesTests(unittest.TestCase):
    def test_run_157s_timings_are_seconds_only(self):
        # Live, run 157: "Timings: signals_and_variants 19.544217399990885, ... angle_frames
        # ['primary_storyline', ...], intent_read {'intent': 'default', ...}, angle_spread 0.2255".
        from core.run_trace import explain_trace
        from core.why_slow import phase_seconds

        timings = {"signals_and_variants": 19.544217399990885, "angle_frames": ["primary"],
                   "intent_read": {"intent": "default"}, "angle_spread": 0.2255,
                   "research_brief": 11.835618, "word_count": 257}  # fmt: skip
        text = explain_trace({"run_id": 157, "status": "rendered", "timings": timings})
        line = next(ln for ln in text.splitlines() if ln.startswith("Timings:"))
        self.assertEqual(line, "Timings: signals_and_variants 19.5s, research_brief 11.8s")
        self.assertIn("Words: 257", text)
        self.assertNotIn("angle_spread", [name for name, _s in phase_seconds(timings)])


# ---- the angle prompt crashed the console (operator, 2026-10-17) ------------------------------


class ConsolePayloadTests(unittest.TestCase):
    """`py main.py` -> 1 -> best bet 4 died at the angle step: "TypeError:
    TerminalBackend.ask_text() got an unexpected keyword argument 'payload'". `ask_text` has
    passed the discovery read on since 3ef604d (the app's angle step); only the app's backend
    took it. mypy listed the line - the ratchet counted it as a tolerated error."""

    def test_the_terminal_takes_a_payload_and_ignores_it(self):
        from core import ask

        with (
            patch.object(ask, "_backend", ask.TerminalBackend()),
            patch("builtins.input", return_value="2") as typed,
        ):
            self.assertEqual(ask.ask_choice("  Pick an angle: ", payload={"intent": "x"}), "2")
        typed.assert_called_once_with("  Pick an angle: ")

    def test_a_scripted_answer_too(self):
        from core import ask

        with patch.object(ask, "_backend", ask.ScriptedBackend(["3"])):
            self.assertEqual(ask.ask_text("  Pick: ", payload={"intent": "x"}), "3")


# ---- decision 65: no YouTube cadence cap unless one is set ------------------------------------


def _cadence(total, cap=0):
    from core.cadence import CadenceStatus

    return CadenceStatus(recent=total, upcoming=0, cap=cap, window_days=7)


class NoCadenceCapTests(unittest.TestCase):
    """The operator, 2026-10-17: "Remove it" - the start menu warned "Cadence 5/5 in a 7-day
    window", and the cap also blocked uploads (`publish_blockers`) and scheduling
    (`spaced_queue`). MAX_VIDEOS_PER_WEEK still sets one when given."""

    def setUp(self):
        p = patch.dict(os.environ, {"MAX_VIDEOS_PER_WEEK": ""})
        p.start()
        self.addCleanup(p.stop)

    def test_by_default_there_is_no_cap(self):
        from core.cadence import max_videos_per_week

        self.assertEqual(max_videos_per_week(), 0)
        self.assertTrue(_cadence(9).ok)

    def test_the_menu_warns_nothing(self):
        from core.cadence import display_cadence

        said: list[str] = []
        display_cadence(_cadence(9), print_fn=said.append)
        self.assertFalse(any("Cadence" in s or "cap" in s for s in said), said)

    def test_health_is_green_and_the_header_has_no_ceiling(self):
        from core.channel_health import _cadence_sub
        from core.status import _hdr_week

        with patch("core.cadence.cadence_status", return_value=_cadence(9)):
            self.assertEqual(_cadence_sub("tapin").status, "green")
            self.assertEqual(_hdr_week("tapin"), "week 9 of 3+")

    def test_every_video_gets_a_slot(self):
        from core.spaced_queue import plan_spaced_uploads

        when = datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc)
        with (
            patch("core.spaced_queue.cadence_status", return_value=_cadence(9)),
            patch("core.spaced_queue.planned_post_time", return_value=when),
        ):
            slots = plan_spaced_uploads([(i, f"run {i}") for i in range(4)], channel_id="tapin")
        self.assertFalse([s for s in slots if s.skipped])

    def test_the_backlog_has_no_ceiling(self):
        from publishing.backlog import fits_cap

        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        self.assertTrue(fits_cap([now] * 9, now, 0))

    def test_a_cap_still_works_when_set(self):
        from core.cadence import max_videos_per_week

        with patch.dict(os.environ, {"MAX_VIDEOS_PER_WEEK": "5"}):
            self.assertEqual(max_videos_per_week(), 5)
        self.assertFalse(_cadence(5, cap=5).ok)


_ = (json, subprocess, MagicMock)

if __name__ == "__main__":
    unittest.main()
