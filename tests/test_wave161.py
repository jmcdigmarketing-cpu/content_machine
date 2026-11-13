"""Wave 161 (2026-11-13): one month to improve - what viewers see first (decision 113).

The operator, 11-13, with a comment on "Steam Review Queue Congestion ..." (2 likes): "You are
part of the problem. Do not reccomend channel button smiles for me" - and "Either rapid rapid
improvement or the plug is pulled, 1 month until the potential end."

Read first, on 1804db6:
- nothing kept a story about machine-made content away from a machine-voiced channel: the menu
  drafted it and overnight rendered it (#2026).
- the mailbag read the channel's own comments and kept the questions - this comment and 10-30's
  "lame" were never shown to the operator (#2027).
- every long draft waited on "a long video renders after your review" with the operator away;
  rows were dated 11-06, 11-09 and 11-12 (#2028).
- an ElevenLabs refusal (a cancelled plan, no characters, a dead key) was raised - the render
  failed; only the opt-in character budget fell back to Piper (#2029).
- `RUN_COST_MODE=free` did not reach overnight, the fast lane or the 1 PM step: only main.py,
  auto_generate and batch_generation's own `main` applied it (#2030).
- no line said how the month is going against where it started (#2031).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.isolation import IsolatedQuotaStore

THE_COMMENT = "You are part of the problem.\nDo not reccomend channel button smiles for me"


def _bet(topic, source="trending", *, outlets=5):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain="gaming", avg_engaged_rate=0.0, source=source,
                         supporting_runs=0, rationale="why", outlets=outlets)  # fmt: skip


class SelfStoryTests(unittest.TestCase):
    """#2026: a story about machine-made content waits for the operator."""

    def test_the_story_is_named(self):
        from core.batch_generation import self_story

        for text in (
            "Valve's Steam AI crackdown stance sparks debate among developers",
            "Steam review queue congestion: a flood of AI-generated games buries real releases",
            "Shovelware is clogging the Switch eShop again",
            "YouTube moves against faceless channels and AI slop",
            "Low-effort releases and asset flips swamp the store",
        ):
            self.assertTrue(self_story(text), text)

    def test_a_game_story_is_left_alone(self):
        from core.batch_generation import self_story

        for text in (
            "Madden 27's AI teammates finally hold their blocks",
            "GTA 6 online mode may repeat GTA Online's mistakes",
            "The enemy AI in Modern Warfare 4 is the best in years",
            "Topuria says he will fight again in March",
        ):
            self.assertEqual(self_story(text), "", text)

    def test_overnight_leaves_it_in_the_menu_and_says_so(self):
        from core import batch_generation as bg

        ideas = [_bet("Valve's Steam AI crackdown stance sparks debate"),
                 _bet("GTA 6 trailer 3 breaks the record")]  # fmt: skip
        notes: list[str] = []
        with (
            patch.dict(os.environ, {"SELF_STORY_HOLD": "true"}),
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
        ):
            topics = bg.collect_topics("tapin", count=5, notes=notes)
        self.assertIn("GTA 6 trailer 3 breaks the record", topics)
        self.assertNotIn("Valve's Steam AI crackdown stance sparks debate", topics)
        self.assertTrue(any("machine-made" in n and "Valve" in n for n in notes), notes)
        with (
            patch.dict(os.environ, {"SELF_STORY_HOLD": "false"}),
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
        ):
            self.assertIn("Valve's Steam AI crackdown stance sparks debate",
                          bg.collect_topics("tapin", count=5))  # fmt: skip


def _meta(run_id, **over):
    meta = {
        "run_id": run_id, "channel_id": "tapin", "topic": f"Topic {run_id}",
        "title": f"Title {run_id}", "length_choice": "2", "hook_score": 70,
        "hook_verdict": "strong", "authenticity_verdict": "ok", "claim_verification": {},
        "fact_conflicts": [], "ungrounded_entities": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }  # fmt: skip
    meta.update(over)
    return meta


class _Drafts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name

    def _reason(self, run_id, script="A clean script about the game. It says one thing.", **over):
        from core.batch_review import pending_drafts, unattended_block_reason

        folder = os.path.join(self.root, f"draft_{run_id:04d}")
        os.makedirs(folder)
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(_meta(run_id, **over), fh)
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as fh:
            fh.write(f"# Draft\n\n## Script\n\n{script}\n")
        (draft,) = [d for d in pending_drafts("tapin", root=self.root) if d.run_id == run_id]
        with patch("core.batch_review.authenticity_now", return_value=("ok", "")):
            return unattended_block_reason(draft)


class DraftHoldTests(_Drafts):
    def test_a_draft_about_machine_made_content_waits(self):
        script = ("Steam's review queue is jammed. A flood of AI-generated games is the reason. "
                  "Valve says real releases now wait weeks.")  # fmt: skip
        with patch.dict(os.environ, {"SELF_STORY_HOLD": "true"}):
            why = self._reason(1, script, title="Steam Review Queue Congestion Hits Indies")
            clean = self._reason(2)
        self.assertIn("machine-made", why)
        self.assertIn("yours to decide", why)
        self.assertEqual(clean, "")


class LongAutoTests(_Drafts):
    """#2028 (decision 113 changes decision 84): a long video that passes renders unattended."""

    def test_a_clean_long_draft_renders(self):
        with patch.dict(os.environ, {"LONG_AUTO": "true"}):
            self.assertEqual(self._reason(3, kind="long"), "")

    def test_the_switch_puts_the_review_back(self):
        with patch.dict(os.environ, {"LONG_AUTO": "false"}):
            self.assertIn("after your review", self._reason(4, kind="long"))


COMMENTS = [
    {"text": THE_COMMENT, "likes": 2, "replies": 0, "video_id": "steamq", "comment_id": "c1"},
    {"text": "lame", "likes": 0, "replies": 0, "video_id": "ufc333", "comment_id": "c2"},
    {"text": "❤️❤️❤️", "likes": 0, "video_id": "sea", "comment_id": "c3"},
    {"text": "Will Topuria fight again this year?", "likes": 4, "video_id": "t", "comment_id": "c4"},
    {"text": "another AI voice channel reading headlines", "likes": 1, "video_id": "x",
     "comment_id": "c5"},
    {"text": "The enemy AI in this game is so good", "likes": 3, "video_id": "mw4",
     "comment_id": "c6"},
]  # fmt: skip


class CritiqueTests(unittest.TestCase):
    """#2027: the comments the mailbag already reads, read for what viewers object to."""

    def test_the_comment_is_read_as_a_critique(self):
        from analytics.mailbag import critiques_from_comments

        got = critiques_from_comments(COMMENTS, titles={"steamq": "Steam Review Queue"})
        self.assertEqual([c["comment_id"] for c in got], ["c1", "c5", "c2"])  # most liked first
        first = got[0]
        self.assertEqual(first["kinds"], ["machine-made", "leaving"])
        self.assertEqual(first["likes"], 2)
        self.assertEqual(first["title"], "Steam Review Queue")
        self.assertEqual(got[1]["kinds"], ["machine-made"])
        self.assertEqual(got[2]["kinds"], ["quality"])

    def test_the_mailbag_prints_them(self):
        from analytics.mailbag import critique_lines, critiques_from_comments, mailbag_lines

        data = {"clusters": [], "comments": 6, "videos": 5,
                "critiques": critiques_from_comments(COMMENTS, titles={"steamq": "Steam Q"})}  # fmt: skip
        lines = critique_lines("tapin", data)
        self.assertIn("3 critiques", lines[0])
        self.assertIn("You are part of the problem. Do not reccomend", lines[1])
        self.assertIn("2 likes", lines[1])
        self.assertIn("machine-made, leaving", lines[1])
        self.assertIn("Steam Q", lines[1])
        with patch("analytics.mailbag.answered", return_value={}):
            self.assertIn(lines[1], mailbag_lines("tapin", data))
        self.assertEqual(critique_lines("tapin", {"clusters": []}), [])


def _refusal(status=401, body="quota_exceeded"):
    exc = Exception(f"status_code: {status}, body: {{'detail': {{'status': '{body}'}}}}")
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


class VoiceEndTests(IsolatedQuotaStore, unittest.TestCase):
    """#2029: the paid voice ends once, and the render goes on in the local voice."""

    def setUp(self):
        super().setUp()
        from core import tts

        tts.reset_paid_voice()
        self.addCleanup(tts.reset_paid_voice)
        env = patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs", "PAID_UNTIL": "",
                                      "PAID_VOICE_UNTIL": "", "SIGNAL_BREAKER_PERSIST": "true",
                                      "ELEVEN_API_KEY": "key-one"})  # fmt: skip
        env.start()
        self.addCleanup(env.stop)

    def test_what_a_refusal_is(self):
        from core import tts

        self.assertTrue(tts._is_plan_refusal(_refusal(401, "quota_exceeded")))
        self.assertTrue(tts._is_plan_refusal(_refusal(402, "payment_required")))
        self.assertTrue(tts._is_plan_refusal(_refusal(401, "invalid_api_key")))
        self.assertFalse(tts._is_plan_refusal(_refusal(429, "too_many_concurrent_requests")))
        self.assertFalse(tts._is_plan_refusal(_refusal(400, "voice_not_found")))
        self.assertFalse(tts._is_plan_refusal(TimeoutError("timed out")))

    def test_the_date_ends_it(self):
        from core import tts

        with patch.dict(os.environ, {"PAID_VOICE_UNTIL": "2026-11-30"}):
            self.assertEqual(tts.paid_voice_ended(today=date(2026, 11, 30)), "")
            self.assertIn("Nov 30", tts.paid_voice_ended(today=date(2026, 12, 1)))
        with patch.dict(os.environ, {"PAID_UNTIL": "2026-12-13"}):
            self.assertEqual(tts.paid_voice_ended(today=date(2026, 12, 13)), "")
            self.assertTrue(tts.paid_voice_ended(today=date(2026, 12, 14)))

    def test_a_refused_call_raises_the_end_and_is_remembered(self):
        from core import quota_governor, tts

        client = MagicMock()
        client.text_to_speech.convert.side_effect = _refusal(401, "quota_exceeded")
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(tts, "_try_alt_tts_provider", return_value=None),
            patch.object(tts, "_should_piper_mix", return_value=False),
            patch.object(tts, "_elevenlabs_quota_would_exceed", return_value=False),
            patch.object(tts, "_word_timestamps_enabled", return_value=False),
            patch.object(tts, "resolve_tts_config", return_value=("vid", "mid")),
            patch.object(tts, "_elevenlabs_client", return_value=client),
            self.assertRaises(tts.PaidVoiceEnded),
        ):
            tts.synthesize_to_path("hello", "hello", os.path.join(tmp, "o.mp3"), "tapin", "k")
        ended, why = quota_governor.voice_refused()
        self.assertTrue(ended)
        self.assertIn("quota_exceeded", why)
        self.assertTrue(tts.paid_voice_ended(today=date(2026, 11, 14)))
        with patch.dict(os.environ, {"ELEVEN_API_KEY": "key-two"}):  # a new key is a new plan
            self.assertEqual(quota_governor.voice_refused(), (False, ""))

    def test_the_whole_script_is_voiced_again_in_the_local_voice(self):
        from core import tts

        seen: list[str] = []

        def fake(script, output_path, channel_id=None, segments=None):
            seen.append(tts._resolve_tts_provider())
            if len(seen) == 1:
                raise tts.PaidVoiceEnded("ElevenLabs refused: quota_exceeded")
            return output_path

        with (
            patch.object(tts, "_generate_audio", side_effect=fake),
            patch.object(tts, "_piper_voice_ready", return_value=True),
            patch.object(tts, "_record_spoken_pace"),
        ):
            out = tts.generate_audio("One. Two. Three.", "/tmp/never-written.mp3", "tapin")
            self.assertEqual(os.environ["TTS_PROVIDER"], "piper")
        self.assertEqual(out, "/tmp/never-written.mp3")
        self.assertEqual(seen, ["elevenlabs", "piper"])

    def test_no_local_voice_says_what_to_set(self):
        from core import tts

        with (
            patch.object(tts, "_generate_audio",
                         side_effect=tts.PaidVoiceEnded("ElevenLabs refused: quota_exceeded")),
            patch.object(tts, "_piper_voice_ready", return_value=False),
            patch.object(tts, "_record_spoken_pace"),
            self.assertRaises(RuntimeError) as caught,
        ):  # fmt: skip
            tts.generate_audio("One.", "/tmp/never-written.mp3", "tapin")
        self.assertIn("PIPER_VOICE", str(caught.exception))

    def test_after_the_date_the_first_word_is_local(self):
        from core import tts

        seen: list[str] = []

        def fake(script, output_path, channel_id=None, segments=None):
            seen.append(tts._resolve_tts_provider())
            return output_path

        with (
            patch.dict(os.environ, {"PAID_VOICE_UNTIL": "2020-01-01"}),
            patch.object(tts, "_generate_audio", side_effect=fake),
            patch.object(tts, "_piper_voice_ready", return_value=True),
            patch.object(tts, "_record_spoken_pace"),
        ):
            tts.generate_audio("One.", "/tmp/never-written.mp3", "tapin")
        self.assertEqual(seen, ["piper"])


class CostModeTests(unittest.TestCase):
    """#2030: the cost mode reaches the unattended jobs, and paid mode has a last day."""

    def test_paid_mode_has_a_last_day(self):
        from core import run_mode

        with patch.dict(os.environ, {"PAID_UNTIL": "2026-12-13", "RUN_COST_MODE": "",
                                     "PAID_CALLS": ""}):  # fmt: skip
            with patch.object(run_mode, "_today", return_value=date(2026, 12, 13)):
                self.assertEqual(run_mode.resolve_cost_mode(), "standard")
            with patch.object(run_mode, "_today", return_value=date(2026, 12, 14)):
                self.assertEqual(run_mode.resolve_cost_mode(), "free")

    def test_standard_mode_holds_nothing(self):
        from core import run_mode

        with patch.dict(os.environ, {"PAID_UNTIL": "", "RUN_COST_MODE": "", "PAID_CALLS": ""}):
            self.assertEqual(run_mode.hold_unattended("overnight"), "")
            self.assertFalse(run_mode.free_mode_strict())

    def test_free_mode_with_no_voice_holds_and_says_why(self):
        from core import run_mode

        bare = run_mode.Readiness(tts_provider=None, llm_provider="ollama", llm_model="m",
                                  llm_local=True)  # fmt: skip
        with (
            patch.dict(os.environ, {"RUN_COST_MODE": "free"}),
            patch.object(run_mode, "free_backend_readiness", return_value=bare),
        ):
            why = run_mode.hold_unattended("overnight")
            self.assertTrue(run_mode.free_mode_strict())  # armed even though it cannot run
        self.assertIn("overnight", why)
        self.assertIn("PIPER_VOICE", why)

    def test_overnight_stops_before_it_drafts(self):
        from core import overnight

        names = ("_probe_signals", "_post_publish", "_crosspost", "_score_calls", "_call_week",
                 "_week_compile", "_month_compile", "_sign_in_line")  # fmt: skip
        patches = [patch.object(overnight, name, return_value="") for name in names]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        with (
            patch("core.overnight_pause.is_paused", return_value=False),
            patch("jobs.game_guard.wait_while_gaming", return_value=""),
            patch("analytics.sync_metrics.maybe_sync"),
            patch("core.run_mode.hold_unattended", return_value="Free mode cannot run overnight"),
            patch.object(overnight, "_run_overnight_body") as body,
        ):
            result = overnight.run_overnight("tapin")
        body.assert_not_called()
        self.assertIn("Free mode cannot run", result.pause_line)

    def test_the_fast_lane_and_the_one_pm_step_stop_too(self):
        from jobs import fast_lane, midday

        draft = MagicMock()
        with (
            patch("core.run_mode.hold_unattended", return_value="Free mode cannot run"),
            patch.object(fast_lane, "enabled", return_value=True),
            patch.object(fast_lane, "load_store", return_value={}),
            patch.object(fast_lane, "save_store"),
            patch.object(fast_lane, "blocked", return_value=""),
            patch.object(fast_lane, "next_story",
                         return_value={"key": "k", "why": "w", "topic": "t"}),
        ):  # fmt: skip
            self.assertEqual(fast_lane.run_fast_lane("tapin", draft=draft), [])
        with (
            patch("core.run_mode.hold_unattended", return_value="Free mode cannot run"),
            patch.object(midday, "enabled", return_value=True),
            patch.object(midday, "load_store", return_value={}),
            patch.object(midday, "save_store"),
            patch.object(midday, "blocked", return_value=""),
        ):
            self.assertEqual(midday.run_midday("tapin", draft=draft), [])
        draft.assert_not_called()

    def test_the_worker_arms_the_mode_and_still_uploads(self):
        from jobs import worker

        with (
            patch("core.run_mode.resolve_cost_mode", return_value="free"),
            patch("core.run_mode.apply_cost_mode") as apply,
        ):
            worker._cost_mode()
        apply.assert_called_once_with("free")


WINDOW = (date(2026, 11, 13), date(2026, 12, 13))
START = {"shorts_views_28d": 7000, "subscribers": 200, "long_hours_365d": 10.9}
NOW = {"shorts_views_28d": 9100, "subscribers": 203, "long_hours_365d": 12.4}


class DecisionTests(unittest.TestCase):
    """#2031: the month's test - each number against where it started."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "decision_test_tapin.json")

    def test_the_window_is_in_config(self):
        from core.success import decision

        self.assertEqual(decision.window("tapin"), WINDOW)
        self.assertIsNone(decision.window("no-such-channel"))

    def test_the_start_is_taken_once(self):
        from core.success import decision

        early = decision.capture_baseline("tapin", START, today=date(2026, 11, 12),
                                          entries=[], path=self.path)  # fmt: skip
        self.assertFalse(early)  # before the window
        self.assertTrue(decision.capture_baseline("tapin", START, today=date(2026, 11, 14),
                                                  entries=[], path=self.path))  # fmt: skip
        self.assertFalse(decision.capture_baseline("tapin", NOW, today=date(2026, 11, 20),
                                                   entries=[], path=self.path))  # fmt: skip
        base = decision.load_baseline("tapin", path=self.path)
        self.assertEqual(base["day"], "2026-11-14")
        self.assertEqual(base["shorts_views_28d"], 7000)
        self.assertEqual(base["organic_subscribers"], 200)

    def test_the_line(self):
        from core.success import decision

        waiting = decision.decision_line("tapin", today=date(2026, 11, 13), numbers=START,
                                         baseline={}, entries=[])  # fmt: skip
        self.assertEqual(
            waiting,
            "Decision day Sun Dec 13 (30 days left): the start line is taken at the next "
            "metrics sync",
        )
        decision.capture_baseline("tapin", START, today=date(2026, 11, 14), entries=[],
                                  path=self.path)  # fmt: skip
        base = decision.load_baseline("tapin", path=self.path)
        line = decision.decision_line("tapin", today=date(2026, 11, 20), numbers=NOW,
                                      baseline=base, entries=[])  # fmt: skip
        self.assertEqual(
            line,
            "Decision day Sun Dec 13 (23 days left): organic Shorts views in 28 days 9,100 "
            "(7,000 at the start, +30%); organic subscribers 203 (200, +3); long-form hours "
            "12.4 (10.9, +1.5)",
        )
        after = decision.decision_line("tapin", today=date(2026, 12, 15), numbers=NOW,
                                       baseline=base, entries=[])  # fmt: skip
        self.assertTrue(after.startswith("Decision day was Sun Dec 13:"), after)
        self.assertEqual(decision.decision_line("no-such-channel", today=date(2026, 11, 20)), "")

    def test_status_and_the_weekly_report_carry_it(self):
        from core import status_summary

        self.assertIn("Decision", [label for label, _verb, _fn in status_summary.FAMILIES])
        with patch("core.success.decision.decision_line", return_value=""):
            quiet = status_summary._decision("tapin")
        self.assertEqual(quiet, "")
        families = [("Decision", "ops ypp", lambda _c: "")]
        with patch.object(status_summary, "FAMILIES", families):
            self.assertEqual(status_summary.machine_lines("tapin"), [])  # nothing to say: no line


class CorpusTests(unittest.TestCase):
    def test_the_case_is_filed(self):
        from core.regression_corpus import load_cases

        self.assertIn(2026, {c.get("item") for c in load_cases()})


if __name__ == "__main__":
    unittest.main()
