"""Wave 88 (#1174-#1178): what the operator sees in the morning.

Read on 2026-10-14:

- The nightly correction scan pairs every claim of a run with every source page of the run.
  Run 119's note checks "Shavkat Rakhmonov posted '19-0 VS 19-0' on his TikTok" against an
  article about a former UFC security guard. 10 notes on 5 videos since Oct 9, the same four
  refiled each scan, each saying the claim was "blocked from future scripts" when nothing was -
  and none of it on the morning screen.
- The sign-in has been dead two days; `ops morning` prints the command and moves on.
- The operator's own three drafts wait one or two named sentences from clean, and the review
  can only render them as they are or reject them.
- 4 of the last 8 thumbnails went out without their title: one sampled pixel was too light
  for white text, so no text was drawn at all.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from tests.test_overnight_renders import _DraftsCase

CLAIM = "Shavkat Rakhmonov posted '19-0 VS 19-0' on his TikTok."
GUARD = (
    "Former UFC security guard reacts to Dana White's admitted bias ahead of the DWCS bout. "
    "It is completely blocked out, the guard said, describing fight week at the Apex."
)

# ---- #1174: a claim is checked only against a page about it ----------------------------------


class CorrectionSubjectTests(unittest.TestCase):
    def _scan(self, body, claim=CLAIM):
        from core.correction_dossier import scan_published_for_corrections

        row = SimpleNamespace(content_run_id=119, youtube_video_id="q6_QBAUrtiQ")
        run = SimpleNamespace(
            features_json=json.dumps(
                {
                    "claim_verification": {"claims": [{"claim": claim, "supported": True}]},
                    "source_urls": ["https://www.mmafighting.com/ufc/514292/security-guard"],
                }
            )
        )
        with tempfile.TemporaryDirectory() as tmp, patch("core.correction_dossier._write_note"):
            return scan_published_for_corrections(
                "tapin",
                published=[row],
                run_lookup={119: run},
                fetch=lambda url: body,
                negative_store=lambda *a: None,
                stamp_path=os.path.join(tmp, "stamp.json"),
                force=True,
            )

    def test_run119_a_page_about_something_else_files_nothing(self):
        self.assertEqual(self._scan(GUARD), [])

    def test_a_page_about_the_claim_that_no_longer_says_it_still_files(self):
        # A claim of two names and two words is still "carried" by any page that names both
        # (coverage 0.5, the old rule's line), so this one says more.
        claim = "Shavkat Rakhmonov withdrew from the title fight with a knee injury from sparring."
        body = (
            "Shavkat Rakhmonov returns to training camp in Dubai ahead of his next bout, "
            "his coach said this week, with no date set for a return."
        )
        (dossier,) = self._scan(body, claim)
        self.assertEqual(dossier.severity, "medium")

    def test_a_retraction_on_a_page_about_something_else_files_nothing(self):
        self.assertEqual(self._scan("Correction: an earlier version misnamed him. " + GUARD), [])

    def test_the_note_says_a_fact_was_blocked_only_when_it_was(self):
        from core.correction_dossier import CorrectionDossier

        base = {
            "channel_id": "tapin",
            "video_id": "q6_QBAUrtiQ",
            "run_id": 119,
            "claim": CLAIM,
            "source_url": "https://example.com/a",
            "changed_evidence": "source no longer carries the claim",
            "severity": "medium",
            "suggested_correction": "x",
        }
        self.assertNotIn("blocked from future scripts", CorrectionDossier(**base).render())
        recorded = CorrectionDossier(**base, negative_recorded=True).render()
        self.assertIn("blocked from future scripts", recorded)

    def test_new_notes_say_how_the_page_was_chosen(self):
        from core.correction_dossier import CHECKED_LINE, CorrectionDossier

        note = CorrectionDossier(
            channel_id="tapin", video_id="v", run_id=1, claim=CLAIM, source_url="u",
            changed_evidence="e", severity="medium", suggested_correction="s",
        ).render()  # fmt: skip
        self.assertIn(CHECKED_LINE, note)


# ---- #1175: open corrections on the morning screen ---------------------------------------------


def _note(folder, name, video, claim, *, checked=True, status="open"):
    lines = [
        f"# Correction needed: {video} - 2026-10-15",
        "",
        f"## {claim}",
        "",
        f"- **Video:** {video}",
        "- **Source:** https://www.example.com/story",
        f"- **Status:** {status}",
    ]
    if checked:
        from core.correction_dossier import CHECKED_LINE

        lines.append(CHECKED_LINE)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class OpenCorrectionTests(unittest.TestCase):
    def test_the_morning_lists_open_ones_once_each(self):
        from core.correction_dossier import open_correction_lines

        with tempfile.TemporaryDirectory() as tmp:
            _note(tmp, "2026-10-15_correction-aaa.md", "aaa", "Claim one about a fighter.")
            _note(tmp, "2026-10-16_correction-aaa.md", "aaa", "Claim one about a fighter.")
            _note(tmp, "2026-10-16_correction-bbb.md", "bbb", "Claim two.", status="closed")
            _note(tmp, "2026-10-13_correction-ccc.md", "ccc", "An old pairing.", checked=False)
            _note(tmp, "2026-10-16_weekly.md", "zzz", "Not a correction.")
            text = "\n".join(open_correction_lines("tapin", reports_dir=tmp))
        self.assertIn("Open corrections - tapin: 1", text)
        self.assertEqual(text.count("Claim one about a fighter."), 1)
        self.assertIn("example.com", text)
        self.assertNotIn("Claim two.", text)
        self.assertIn("1 older note", text)

    def test_no_vault_says_nothing(self):
        from core.correction_dossier import open_correction_lines

        self.assertEqual(open_correction_lines("tapin", reports_dir=""), [])

    def test_the_morning_runs_it(self):
        from scripts import ops

        self.assertIn("corrections-open", ops.BATCHES["morning"][1])
        self.assertIn("corrections-open", ops.COMMANDS)


# ---- #1176: the morning offers to sign in -----------------------------------------------------

LONG = (
    "YouTube sign-in for tapin has expired or been revoked - run: py -m youtube.oauth_setup --channel tapin. "
    * 2
)


class MorningSignInTests(unittest.TestCase):
    def _morning(self, *, console, answer, states):
        from scripts import ops

        ran: list[str] = []

        def fake(name):
            def step(_args):
                ran.append(name)
                return 0

            return step

        commands = {name: (help_, fake(name)) for name, (help_, _fn) in ops.COMMANDS.items()}
        asked: list[str] = []

        def ask(prompt):
            asked.append(prompt)
            return answer

        buf = io.StringIO()
        with (
            patch.dict(ops.COMMANDS, commands),
            patch.object(ops, "_batch_sign_in", side_effect=states),
            patch.object(ops, "_has_console", return_value=console),
            patch("builtins.input", side_effect=ask),
            patch("youtube.oauth.run_interactive_oauth") as oauth,
            redirect_stdout(buf),
        ):
            ops._run_batch("morning", Namespace(channel="tapin"))
        return ran, asked, oauth

    def test_a_yes_signs_in_and_the_sync_runs(self):
        ran, asked, oauth = self._morning(console=True, answer="y", states=[LONG, ""])
        self.assertEqual(len(asked), 1)
        self.assertIn("Sign in to YouTube now", asked[0])
        oauth.assert_called_once_with("tapin")
        self.assertIn("sync-metrics", ran)

    def test_a_no_skips_the_sync_as_before(self):
        ran, _asked, oauth = self._morning(console=True, answer="n", states=[LONG])
        oauth.assert_not_called()
        self.assertNotIn("sync-metrics", ran)

    def test_without_a_console_it_does_not_ask(self):
        _ran, asked, oauth = self._morning(console=False, answer="y", states=[LONG])
        self.assertEqual(asked, [])
        oauth.assert_not_called()

    def test_the_overnight_report_uses_the_short_line(self):
        from core import overnight
        from youtube import oauth

        with (
            patch.object(oauth, "live_youtube_forbidden", return_value=False),
            patch.object(oauth, "sign_in_status", return_value=LONG),
        ):
            line = overnight._sign_in_line("tapin")
        self.assertLess(len(line), 120)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)


# ---- #1177: the review can cut a draft's flagged sentences ------------------------------------

SCRIPT = (
    "The Chargers are 0-5 this year. He has 40 knockouts in the UFC. The line held up well "
    "again on Sunday afternoon and the defense was fine."
)


def _flagged():
    return {
        "total": 2,
        "supported": 1,
        "unsupported": ["Topuria has 40 knockouts in the UFC."],
        "unsupported_types": ["stat"],
        "claims": [
            {"claim": "The Chargers are 0-5.", "supported": True, "citation_line": "x", "type": "result"},
            {"claim": "Topuria has 40 knockouts in the UFC.", "supported": False, "citation_line": "", "type": "stat"},
        ],
    }  # fmt: skip


class ReviewCutTests(_DraftsCase):
    def _review(self, answers, min_words=10):
        from core.batch_review import review_drafts

        folder = self._draft(7, claim_verification=_flagged())
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
            f.write(f"# Draft\n\n## Script\n\n{SCRIPT}\n\n## Description\n\nd\n")
        said: list[str] = []
        replies = iter(answers)
        with (
            patch("core.batch_review._draft_min_words", return_value=min_words),
            patch("core.run_features.merge_features") as merge,
        ):
            review_drafts(
                "tapin",
                root=self.tmp.name,
                ask=lambda prompt: said.append(prompt) or next(replies),
                print_fn=lambda *a: said.append(" ".join(str(x) for x in a)),
            )
        return folder, said, merge

    def test_c_cuts_the_flagged_sentence_and_asks_again(self):
        from core.batch_review import draft_script

        folder, said, merge = self._review(["c", ""])
        self.assertNotIn("40 knockouts", draft_script(folder))
        self.assertIn("The Chargers are 0-5 this year.", draft_script(folder))
        stored = self._stored(7)
        self.assertEqual(stored["claim_verification"]["unsupported"], [])
        self.assertEqual(stored["script_clean"]["cut"], ["He has 40 knockouts in the UFC."])
        text = "\n".join(said)
        self.assertIn("cut: He has 40 knockouts in the UFC.", text)
        self.assertEqual(sum(1 for line in said if "Render it?" in line), 2)
        merge.assert_called()

    def test_the_prompt_offers_it_only_when_something_is_flagged(self):
        _folder, said, _merge = self._review([""])
        self.assertIn("c = cut the flagged sentences", next(s for s in said if "Render it?" in s))

    def test_nothing_to_cut_says_so(self):
        from core.batch_review import draft_script

        folder, said, _merge = self._review(["c", ""], min_words=500)
        self.assertIn("40 knockouts", draft_script(folder))
        self.assertTrue(any("nothing was cut: the cut would leave it under 425" in s for s in said))
        self.assertEqual(sum(1 for s in said if "c = cut" in s), 1)  # offered once

    def test_run145_a_claim_in_the_first_sentence_says_so(self):
        from core.batch_review import why_not_cut

        script = "Wemby has +200 odds for MVP. He is the pick. The Spurs win 60 games this year."
        why = why_not_cut(script, ["Wemby has +200 odds for MVP."], 5)
        self.assertIn("first sentence", why)
        self.assertIn("not found", why_not_cut(script, ["Jokic retired in June."], 5))


# ---- #1178: the thumbnail keeps its title -------------------------------------------------------


class ThumbnailPlateTests(unittest.TestCase):
    def test_a_light_picture_gets_a_plate_not_a_blank(self):
        from assets.thumbnail_compose import MIN_CONTRAST, compose_thumbnail

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "t.jpg")
            plate = compose_thumbnail(
                Image.new("RGB", (1280, 720), "white"), "Ben Affleck vs Fortnite", dest
            )
            self.assertEqual(plate.refused, "")
            self.assertTrue(plate.backed)
            self.assertTrue(os.path.exists(dest))
            self.assertGreaterEqual(plate.contrast, MIN_CONTRAST)

    def test_a_dark_picture_needs_no_plate(self):
        from assets.thumbnail_compose import compose_thumbnail

        with tempfile.TemporaryDirectory() as tmp:
            plate = compose_thumbnail(
                Image.new("RGB", (1280, 720), (20, 20, 30)), "UFC 332", os.path.join(tmp, "t.jpg")
            )
        self.assertFalse(plate.backed)


# ---- #1179 / #1180: the proof drafts' openers ----------------------------------------------------

HEAT = "So today we talk about the Heat. They went 11 and 1, 11 of 12 games, and Bam looks new."
RUN149 = (
    "Zero and five, and the Chargers still believe. Los Angeles lost 23-17 to Denver in Week 5, "
    "and Harbaugh stood up and took the blame himself. Jim Harbaugh has won everywhere he's "
    "coached."
)


class OpenerTests(unittest.TestCase):
    def _variants(self, script, openers):
        from core import content_engine

        with (
            patch.dict("os.environ", {"HOOK_REGEN_ENABLED": "true", "HOOK_VARIANTS": "3"}),
            patch.object(content_engine, "_call_content_llm", return_value={"openers": openers}),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
        ):
            return content_engine._hook_variants(script)

    def test_run150_an_opener_without_a_full_stop_gets_one(self):
        out, extra = self._variants(HEAT, ["The Heat won 11 of 12 preseason games"])
        self.assertEqual(extra["picked"], "The Heat won 11 of 12 preseason games.")
        self.assertTrue(out.startswith("The Heat won 11 of 12 preseason games. They went"), out)

    def test_an_opener_that_ends_a_question_keeps_it(self):
        out, _extra = self._variants(HEAT, ["Can the Heat win 11 of 12 preseason games again?"])
        self.assertNotIn("?.", out)

    def test_run149_an_opener_that_says_the_next_sentence_is_refused(self):
        opener = "Jim Harbaugh took the blame personally after a 23-17 loss to Denver."
        out, extra = self._variants(RUN149, [opener])
        self.assertEqual(out, RUN149)
        self.assertIn("next sentence", extra["variants"][0].get("refused", ""))


if __name__ == "__main__":
    unittest.main()
