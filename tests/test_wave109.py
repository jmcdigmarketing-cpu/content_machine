"""Wave 109 (2026-10-18): volume blockers.

- Takes (the operator: "calls + what to watch"): overnight's 3 drafts of 2026-10-18 all waited on
  "no take found", and 5-6 of the 8 held since Oct 14 closed on a call the detector did not know.
  Drafts already waiting are read again, so tonight can render them.
- "vs.": `extract_hook` cut "Jets vs. Patriots in London..." to "Jets vs." - the hook score, hook
  learning and the default-on hook rewrite all read that "sentence".
- Deadlines: run 165, the Chargers at Chiefs preview, kicked off 20:25Z; the noon slot needed it
  queued by 10:30 AM EDT and nothing said so.
- #1291: health's "recent five" were runs 109-133, and four newer videos had no rate yet.
- #450: facts from a phone voice note.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# The scripts' own closing lines, 2026-10-14..18 (runs 164, 161, 160, 150, 165).
CALLS = [
    "Watch who the UFC pairs him with next - that's the real test.",
    "Watch for the first community clears on the harshest ruleset.",
    "If Malott wins, I'll eat it - but the odds are mispriced on the underdogs.",
    "If they win, the hope is real.",
    "The mechanism is simple: if the Bolts can't get off the field on third down, Herbert's "
    '"be better" plea is irrelevant.',
]
# Runs 159 and 166 close on a stake and a verdict, with no call or watch shape - still held.
RECAPS = [
    "New England is 3-2 and can go 3-0 at home. A Jets win flips the AFC East race and ends a "
    "Foxborough drought.",
    "The devs answered the fanart on day one. That's a feedback loop working exactly as designed.",
]
OPENING = "Cristian Perez knocked out Kyle Nelson in 27 seconds at UFC Edmonton. "


def _draft(meta, script):
    from core.batch_review import PendingDraft

    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
        f.write("# Draft\n\n## Script\n\n" + script + "\n")
    base = {"run_id": 165, "topic": "x", "title": "A fine title",
            "claim_verification": {"unsupported": [], "claims": []}}  # fmt: skip
    return PendingDraft(folder=folder, meta={**base, **meta}, script=script)


# ---- 1. takes -------------------------------------------------------------------------------------


class TakeTests(unittest.TestCase):
    def test_the_closing_calls_the_detector_missed(self):
        from core.authenticity import has_insight

        for line in CALLS:
            self.assertTrue(has_insight(OPENING + line), line)

    def test_a_plain_recap_still_has_no_take(self):
        from core.authenticity import has_insight

        for script in RECAPS:
            self.assertFalse(has_insight(script), script[:40])

    def test_a_draft_held_only_for_no_take_is_read_again(self):
        from core.batch_review import authenticity_now, unattended_block_reason

        draft = _draft({"authenticity_verdict": "review",
                        "authenticity_failed": ["original_insight"]}, OPENING + CALLS[1])  # fmt: skip
        self.assertEqual(authenticity_now(draft), ("ok", ""))
        self.assertFalse(unattended_block_reason(draft).startswith("authenticity"))

    def test_another_failure_or_a_recap_still_holds(self):
        from core.batch_review import authenticity_now, unattended_block_reason

        two = _draft({"authenticity_verdict": "review",
                      "authenticity_failed": ["original_insight", "substance"]},
                     OPENING + CALLS[1])  # fmt: skip
        self.assertEqual(authenticity_now(two)[0], "review")
        recap = _draft({"authenticity_verdict": "review",
                        "authenticity_failed": ["original_insight"]}, RECAPS[0])  # fmt: skip
        self.assertEqual(authenticity_now(recap), ("review", "no take found"))
        self.assertIn("no take found", unattended_block_reason(recap))


# ---- 2. "vs." ---------------------------------------------------------------------------------------


class FirstSentenceTests(unittest.TestCase):
    def test_vs_and_jr_do_not_end_the_hook(self):
        from core.hook_score import extract_hook

        self.assertEqual(extract_hook("Jets vs. Patriots in London is a trap game. Then more."),
                         "Jets vs. Patriots in London is a trap game.")  # fmt: skip
        self.assertEqual(extract_hook("Darius Acuff Jr. is a name to know. More."),
                         "Darius Acuff Jr. is a name to know.")  # fmt: skip

    def test_a_short_opener_is_still_its_own_sentence(self):
        from core.hook_score import extract_hook

        self.assertEqual(extract_hook("Seven days. Twenty hours. IGN admitted it."), "Seven days.")
        self.assertEqual(extract_hook("LeBron to Cleveland? Rival execs agree."),
                         "LeBron to Cleveland?")  # fmt: skip

    def test_the_splitter_is_public(self):
        from core.operator_facts import sentences

        self.assertEqual(sentences("Jets vs. Pats. Done."), ["Jets vs. Pats.", "Done."])


# ---- 3. a game draft's deadline -----------------------------------------------------------------

KICKOFF = "2026-10-18T20:25Z"
NINE_EDT = datetime(2026, 10, 18, 13, 0, tzinfo=timezone.utc)


class DeadlineTests(unittest.TestCase):
    def _line(self, now, *, taken=frozenset()):
        from core import batch_review

        chargers = _draft({"event_at": KICKOFF,
                           "title": "Chargers' Pass Defense vs Chiefs' Offense"}, "x")  # fmt: skip
        old = _draft({"run_id": 162, "title": "Pistons bench"}, "y")
        with (
            patch.object(batch_review, "pending_drafts", return_value=[old, chargers]),
            patch("core.spaced_queue._taken_slots", return_value=set(taken)),
        ):
            return batch_review.deadline_line("tapin", now=now)

    def test_it_says_when_to_decide_for_the_last_slot_before_kickoff(self):
        line = self._line(NINE_EDT)
        self.assertIn("Decide first: Chargers' Pass Defense vs Chiefs' Offense", line)
        self.assertIn("kicks off Sun Oct 18 4:25 PM EDT", line)
        self.assertIn("review it by 10:30 AM EDT for the 12:00 PM EDT slot", line)

    def test_past_the_last_slot_it_says_none_is_left(self):
        line = self._line(NINE_EDT + timedelta(hours=2))  # 11 AM EDT: noon is under 90 minutes
        self.assertIn("no upload slot is left before kickoff", line)

    def test_nothing_when_no_game_waits(self):
        from core import batch_review

        with patch.object(batch_review, "pending_drafts", return_value=[_draft({}, "y")]):
            self.assertEqual(batch_review.deadline_line("tapin", now=NINE_EDT), "")

    def test_the_review_takes_the_game_first(self):
        from core import batch_review

        chargers = _draft({"event_at": KICKOFF, "title": "Chargers"}, "x")
        old = _draft({"run_id": 162, "title": "Pistons"}, "y")
        self.assertEqual(batch_review.review_order([old, chargers], now=NINE_EDT),
                         [chargers, old])  # fmt: skip


# ---- 4. #1291: health names what it reads -------------------------------------------------------


class HealthRunsTests(unittest.TestCase):
    def test_the_recent_runs_and_the_newer_unmeasured_ones_are_named(self):
        from core import channel_health

        rates = dict.fromkeys((60, 72, 98, 99, 109, 120, 131, 132, 133), 0.3)
        everything = {**rates, 11: 0.1}
        now = datetime.now(timezone.utc)
        rows = [SimpleNamespace(content_run_id=r, published_at=now - timedelta(days=d))
                for r, d in ((93, 22), (126, 2), (132, 3), (155, 1), (157, 1), (159, 0.6))]  # fmt: skip
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        with (
            patch("core.engagement_predictor.run_engagement_map",
                  side_effect=lambda c, min_views=0: rates if min_views else everything),
            patch("storage.repositories.publish_log.get_publish_log_repository",
                  return_value=repo),
        ):  # fmt: skip
            sub = channel_health._engagement_sub("tapin")
        self.assertIn("(runs 109-133)", sub.detail)
        self.assertIn("4 newer videos not measured yet (runs 126, 155, 157, 159)", sub.detail)


# ---- 5. #450: facts from a voice note ------------------------------------------------------------


class VoiceFactsTests(unittest.TestCase):
    def _words(self, text):
        from core.providers import ProviderResult

        words = [{"word": w, "start": 0.0, "end": 0.1} for w in text.split()]
        return ProviderResult.success("caption_align", "faster_whisper", data=words)

    def test_a_memo_becomes_fact_lines(self):
        from core.facts import voice_notes

        said = "Malott is 11 and 2. Buckley has won 3 straight. The card starts at 8 PM."
        with patch("core.caption_align.transcribe_and_align", return_value=self._words(said)):
            lines, why = voice_notes.transcript_lines("memo.m4a")
        self.assertEqual(why, "")
        self.assertEqual(lines, ["Malott is 11 and 2.", "Buckley has won 3 straight.",
                                 "The card starts at 8 PM."])  # fmt: skip

    def test_punctuation_the_aligner_split_off_joins_back(self):
        # Live, a test memo: "The main card starts at 8 p .m." - the aligner strips each word.
        from core.facts import voice_notes
        from core.providers import ProviderResult

        words = [{"word": w} for w in ["The", "card", "starts", "at", "8", "p", ".m."]]
        done = ProviderResult.success("caption_align", "faster_whisper", data=words)
        with patch("core.caption_align.transcribe_and_align", return_value=done):
            lines, _why = voice_notes.transcript_lines("memo.m4a")
        self.assertEqual(lines, ["The card starts at 8 p.m."])

    def test_no_transcriber_says_why(self):
        from core.facts import voice_notes
        from core.providers import ProviderResult

        failed = ProviderResult.fail_open("caption_align", "faster_whisper not installed")
        with patch("core.caption_align.transcribe_and_align", return_value=failed):
            self.assertEqual(voice_notes.transcript_lines("memo.m4a"),
                             ([], "faster_whisper not installed"))  # fmt: skip

    def test_ops_is_a_dry_run_until_apply(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            memo = os.path.join(tmp, "memo.m4a")
            open(memo, "wb").close()
            args = Namespace(path=memo, run_id=165, topic="", channel="tapin", apply=False)
            out = io.StringIO()
            with (
                patch("core.facts.voice_notes.transcript_lines",
                      return_value=(["Malott is 11 and 2."], "")),
                patch("core.review_booth.apply_booth_facts") as save,
                redirect_stdout(out),
            ):  # fmt: skip
                code = COMMANDS["voice-facts"][1](args)
            self.assertEqual(code, 0)
            save.assert_not_called()
            self.assertIn("Malott is 11 and 2.", out.getvalue())
            self.assertIn("--apply", out.getvalue())
            with (
                patch("core.facts.voice_notes.transcript_lines",
                      return_value=(["Malott is 11 and 2."], "")),
                patch("core.review_booth.apply_booth_facts", return_value=1) as save,
                redirect_stdout(io.StringIO()),
            ):  # fmt: skip
                code = COMMANDS["voice-facts"][1](Namespace(**{**vars(args), "apply": True}))
        self.assertEqual(code, 0)
        self.assertEqual(save.call_args.kwargs.get("origin"), "voice")


if __name__ == "__main__":
    unittest.main()
