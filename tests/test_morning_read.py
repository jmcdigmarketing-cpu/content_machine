"""Wave 86 (#1164-#1168): what the operator reads each morning, and what #1148 bought.

Read on 2026-10-13 and 10-14:

- What the #1148 checker fix bought on drafts already waiting was never measured; 15 of 31
  waited on unbacked claims checked the old way.
- `ops morning` printed the 300-character sign-in message three times.
- `ops overnight-last` said "already public, or retired" for runs 136 and 139, both pulled
  with a reason on record.
- The overnight task is set for 5:00 AM. It ran at 4:45 PM on 10-13 and did not run on 10-14
  at all. Nothing said either.
- 6 of 32 waiting drafts were past their window and stayed in the count.
"""

from __future__ import annotations

import inspect
import io
import json
import os
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_oauth_revoked import REVOKED, _SignInCase
from tests.test_overnight_renders import _DraftsCase

# ---- #1164: re-check the waiting drafts -------------------------------------------------------

SCORE = "The Cavs beat Orlando 119-105 on October 11."
MELEEK = "Rookie Meleek Thomas averaged 27.3 points in Summer League."
SUMMARY = "Summary: The Cleveland Cavaliers defeated the Orlando Magic 119-105 on October 11."


def _old_verdict():
    return {
        "total": 3,
        "supported": 1,
        "support_rate": 0.333,
        "unsupported": [SCORE, MELEEK],
        "unsupported_types": ["result", "stat"],
        "claims": [
            {
                "claim": "Harden led with 24.",
                "supported": True,
                "citation_line": "x",
                "type": "stat",
            },
            {"claim": SCORE, "supported": False, "citation_line": "", "type": "result"},
            {"claim": MELEEK, "supported": False, "citation_line": "", "type": "stat"},
        ],
    }


def _answer(*claims):
    from core.claim_verifier import ClaimVerification, VerifiedClaim

    return ClaimVerification(
        claims=[
            VerifiedClaim(claim=c, supported=ok, citation_line=SUMMARY if ok else "", claim_type=t)
            for c, ok, t in claims
        ]
    )


class RecheckTests(_DraftsCase):
    def setUp(self):
        super().setUp()
        p = patch("core.runs.recheck._facts_for", return_value=SUMMARY)
        p.start()
        self.addCleanup(p.stop)

    def _lines(self, answer, *, apply=False):
        from core.runs.recheck import recheck_lines

        calls: list[str] = []

        def verify(text, facts, **kwargs):
            calls.append(text)
            return answer

        with patch("core.run_features.merge_features") as merge:
            lines = recheck_lines("tapin", root=self.tmp.name, apply=apply, verify=verify)
        return lines, calls, merge

    def test_the_dry_run_says_what_the_fixed_check_clears(self):
        self._draft(137, claim_verification=_old_verdict())
        answer = _answer((SCORE, True, "result"), (MELEEK, False, "stat"))
        lines, calls, merge = self._lines(answer)
        text = "\n".join(lines)
        self.assertIn("run 137: 2 unbacked -> 1", text)
        self.assertIn("cleared: The Cavs beat Orlando 119-105", text)
        self.assertEqual(len(calls), 1)  # one call per draft, its unbacked claims only
        self.assertIn(SCORE, calls[0])
        self.assertEqual(self._stored(137)["claim_verification"]["unsupported"], [SCORE, MELEEK])
        merge.assert_not_called()

    def test_apply_stores_the_new_verdict_on_the_draft_and_the_run(self):
        self._draft(137, claim_verification=_old_verdict())
        answer = _answer((SCORE, True, "result"), (MELEEK, False, "stat"))
        _lines, _calls, merge = self._lines(answer, apply=True)
        stored = self._stored(137)["claim_verification"]
        self.assertEqual(stored["unsupported"], [MELEEK])
        self.assertEqual(stored["supported"], 2)
        cleared = next(c for c in stored["claims"] if c["claim"] == SCORE)
        self.assertTrue(cleared["supported"])
        self.assertEqual(cleared["by"], "recheck")
        self.assertEqual(cleared["citation_line"], SUMMARY)
        self.assertIn(
            "1 claim(s) the facts do not support", self._stored(137)["script_clean"]["why"]
        )
        self.assertEqual(merge.call_args.args[0], 137)

    def test_a_reworded_claim_is_still_matched(self):
        self._draft(137, claim_verification=_old_verdict())
        answer = _answer(("The Cavaliers beat Orlando 119-105.", True, "result"))
        lines, _calls, _merge = self._lines(answer)
        self.assertIn("run 137: 2 unbacked -> 1", "\n".join(lines))

    def test_a_check_that_does_not_answer_changes_nothing(self):
        self._draft(137, claim_verification=_old_verdict())
        lines, _calls, merge = self._lines(None, apply=True)
        self.assertIn("run 137: the check did not answer", "\n".join(lines))
        self.assertEqual(self._stored(137)["claim_verification"]["unsupported"], [SCORE, MELEEK])
        merge.assert_not_called()

    def test_no_saved_facts_no_call(self):
        self._draft(137, claim_verification=_old_verdict())
        with patch("core.runs.recheck._facts_for", return_value=""):
            lines, calls, _merge = self._lines(_answer())
        self.assertIn("run 137: no saved facts", "\n".join(lines))
        self.assertEqual(calls, [])

    def test_a_draft_past_its_window_is_not_checked(self):
        old = (datetime.now() - timedelta(days=20)).isoformat(timespec="seconds")
        self._draft(137, claim_verification=_old_verdict(), created_at=old)
        _lines, calls, _merge = self._lines(_answer())
        self.assertEqual(calls, [])

    def test_ops_has_the_command(self):
        from scripts import ops

        self.assertIn("recheck-claims", ops.COMMANDS)


# ---- #1165: the sign-in, once and short ------------------------------------------------------

LONG = (
    "YouTube sign-in for tapin has expired or been revoked - run: py -m youtube.oauth_setup "
    "--channel tapin. If it expires again in about a week, the Google Cloud OAuth consent "
    "screen is in Testing: publish it (In production) with the policy site's home page and "
    "privacy links (docs/platform_publish_setup.md)."
)


class SignInLogTests(_SignInCase):
    def test_the_log_line_is_one_short_line(self):
        from youtube import oauth

        self._creds(REVOKED)
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR") as logs:
            oauth.load_credentials("tapin")
        (line,) = [r.getMessage() for r in logs.records]
        self.assertLess(len(line), 120)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)
        self.assertIn("expired or been revoked", oauth.sign_in_problem("tapin"))


class SignInOnceTests(unittest.TestCase):
    def test_the_short_line(self):
        from youtube.oauth import short_sign_in

        self.assertEqual(
            short_sign_in("tapin"),
            "YouTube sign-in for tapin has ended - sign in again: "
            "py -m youtube.oauth_setup --channel tapin",
        )

    def test_the_morning_says_it_once(self):
        from scripts import ops

        def step(_args):
            return 0

        commands = {name: (help_, step) for name, (help_, _fn) in ops.COMMANDS.items()}
        buf = io.StringIO()
        with (
            patch.dict(ops.COMMANDS, commands),
            patch.object(ops, "_batch_sign_in", return_value=LONG),
            redirect_stdout(buf),
        ):
            ops._run_batch("morning", Namespace(channel="tapin"))
        out = buf.getvalue()
        self.assertEqual(out.count("expired or been revoked"), 1)
        self.assertIn("skipped sync-metrics - YouTube sign-in for tapin has ended", out)

    def test_the_status_machine_line_is_short(self):
        from core import status_summary

        with (
            patch("youtube.oauth.sign_in_status", return_value=LONG),
            patch("youtube.oauth.resolve_channel_id", side_effect=lambda c=None: c or "tapin"),
        ):
            line = status_summary._sign_in("tapin")
        self.assertEqual(
            line,
            "Sign-in: YouTube sign-in for tapin has ended - sign in again: "
            "py -m youtube.oauth_setup --channel tapin",
        )

    def test_a_short_problem_is_said_as_it_is(self):
        from core import status_summary

        problem = "No YouTube sign-in for tapin - run: py -m youtube.oauth_setup --channel tapin"
        with patch("youtube.oauth.sign_in_status", return_value=problem):
            self.assertEqual(status_summary._sign_in("tapin"), f"Sign-in: {problem}")


# ---- #1166: a pulled run is called pulled -----------------------------------------------------

PULLED = "Pulled 2026-10-13: states a result for a game not yet played (operator's call)"


class PulledRunTests(unittest.TestCase):
    def test_overnight_last_says_pulled_and_why(self):
        from core import batch_review

        row = {"run_id": 139, "title": "Oklahoma City's young core", "at": datetime.now()}
        with (
            patch.object(batch_review, "overnight_rendered", return_value=[row]),
            patch("core.stale_renders.shelf_rows", return_value=[]),
            patch("core.stale_renders.gone_reason", return_value=f"pulled - {PULLED}"),
        ):
            text = "\n".join(batch_review.overnight_rendered_lines("tapin"))
        self.assertIn(f"pulled - {PULLED}", text)
        self.assertNotIn("already public, or retired", text)

    def test_the_cancelled_job_is_the_reason(self):
        from core.stale_renders import gone_reason

        job = SimpleNamespace(
            job_type="upload", status="failed", channel_id="tapin", content_run_id=139,
            last_error=PULLED,
        )  # fmt: skip
        with patch("core.job_queue.list_active_jobs", return_value=[job]):
            self.assertEqual(gone_reason(139, "tapin"), f"pulled - {PULLED}")

    def test_the_retire_stamp_is_next(self):
        from core.stale_renders import gone_reason

        run = SimpleNamespace(
            id=114, features_json=json.dumps({"retired_at": "2026-10-13T20:01:00"})
        )
        repo = SimpleNamespace(get=lambda run_id: run)
        with (
            patch("core.job_queue.list_active_jobs", return_value=[]),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
        ):
            self.assertEqual(gone_reason(114, "tapin"), "retired on 2026-10-13")

    def test_the_recent_runs_list_says_retired(self):
        from core.status import run_state

        retired = SimpleNamespace(status="rendered", features_json='{"retired_at": "2026-10-13"}')
        self.assertEqual(run_state(retired), "retired")
        self.assertEqual(
            run_state(SimpleNamespace(status="drafted", features_json="{}")), "drafted"
        )


# ---- #1167: when overnight ran, against when it was due ---------------------------------------

QUERY = """Folder: \\ContentMachine
TaskName:                             \\ContentMachine\\OvernightDrafts
Next Run Time:                        10/15/2026 5:00:00 AM
Status:                               Ready
Last Run Time:                        10/13/2026 4:45:39 PM
Last Result:                          0
Start Time:                           5:00:00 AM
"""


class OvernightTimingTests(unittest.TestCase):
    def test_the_task_query_is_read(self):
        from core.nightly_task import task_times

        times = task_times(QUERY)
        self.assertEqual(times["last"], datetime(2026, 10, 13, 16, 45, 39))
        self.assertEqual(times["start"], (5, 0))

    def test_a_day_with_no_run_is_said(self):
        """Live, 2026-10-14 at 5:51 PM: the 5:00 AM run never happened."""
        from core.nightly_task import missed_line, task_times

        line = missed_line(task_times(QUERY), now=datetime(2026, 10, 14, 17, 51))
        self.assertIn("did not run at 5:00 AM on Oct 14", line)
        self.assertIn("last ran Oct 13 4:45 PM", line)
        self.assertIn("schedule-drafts --wake", line)

    def test_a_late_run_is_said(self):
        from core.nightly_task import missed_line, task_times

        line = missed_line(task_times(QUERY), now=datetime(2026, 10, 13, 21, 0))
        self.assertIn("ran at 4:45 PM on Oct 13, 12 hours after its 5:00 AM start", line)

    def test_a_run_on_time_says_nothing(self):
        from core.nightly_task import missed_line, task_times

        on_time = QUERY.replace("10/13/2026 4:45:39 PM", "10/14/2026 5:00:12 AM")
        self.assertEqual(missed_line(task_times(on_time), now=datetime(2026, 10, 14, 9, 0)), "")

    def test_the_suite_never_queries_the_task(self):
        from core import nightly_task

        self.assertEqual(os.environ.get("NIGHTLY_TASK_QUERY"), "false")
        with patch.object(nightly_task, "run_schtasks", side_effect=AssertionError("queried")):
            self.assertEqual(nightly_task.overnight_timing_line(), "")

    def test_overnight_last_prints_it(self):
        from core import batch_review

        self.assertIn("_timing_lines()", inspect.getsource(batch_review.overnight_rendered_lines))
        with patch("core.nightly_task.overnight_timing_line", return_value="Overnight did not run"):
            self.assertEqual(batch_review._timing_lines(), ["  Overnight did not run"])

    def test_wake_prints_the_line_and_changes_nothing(self):
        from core import nightly_task
        from scripts import ops

        buf = io.StringIO()
        with (
            patch.object(nightly_task, "run_schtasks", side_effect=AssertionError("ran")),
            redirect_stdout(buf),
        ):
            code = ops.main(["schedule-drafts", "--wake"])
        self.assertEqual(code, 0)
        self.assertIn("WakeToRun", buf.getvalue())
        self.assertIn("ContentMachine", buf.getvalue())


# ---- #1168: old drafts are set aside -----------------------------------------------------------


def _days_ago(days):
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")


class OldDraftTests(_DraftsCase):
    def _three(self):
        self._draft(1, created_at=_days_ago(20))  # past twice its window
        self._draft(2, created_at=_days_ago(10))  # past its window, not twice
        self._draft(3)

    def test_a_dry_run_lists_and_writes_nothing(self):
        from core.batch_review import expire_old_drafts

        self._three()
        found = expire_old_drafts("tapin", root=self.tmp.name, apply=False)
        self.assertEqual([d.run_id for d in found], [1])
        self.assertNotIn("review", self._stored(1))

    def test_apply_sets_it_aside_and_out_of_the_count(self):
        from core.batch_review import expire_old_drafts, expired_lines, pending_drafts

        self._three()
        expire_old_drafts("tapin", root=self.tmp.name)
        review = self._stored(1)["review"]
        self.assertEqual((review["decision"], review["by"]), ("expired", "overnight"))
        self.assertEqual([d.run_id for d in pending_drafts("tapin", root=self.tmp.name)], [2, 3])
        text = "\n".join(expired_lines("tapin", root=self.tmp.name))
        self.assertIn("run 1", text)
        self.assertIn("Title 1", text)

    def test_overnight_does_it_before_rendering(self):
        from core import overnight

        source = inspect.getsource(overnight._run_overnight_body)
        self.assertLess(source.index("expire_old_drafts("), source.index("render_unattended("))
        result = overnight.OvernightResult(channel_id="tapin", requested=3)
        result.expired = 2
        self.assertIn("Set aside 2 drafts", "\n".join(overnight.render_lines(result)))

    def test_the_plan_says_what_tonight_sets_aside(self):
        from core import batch_review

        self._three()
        with (
            patch.object(batch_review, "unattended_limit", return_value=2),
            patch.dict(os.environ, {"OVERNIGHT_EXPIRE_DRAFTS": "true"}),
        ):
            text = "\n".join(batch_review.unattended_plan_lines("tapin", root=self.tmp.name))
        self.assertIn("Tonight sets aside 1 draft past twice its window", text)

    def test_batch_review_lists_them(self):
        from scripts import ops

        buf = io.StringIO()
        with (
            patch("core.batch_review.expired_lines", return_value=["Set aside - tapin: 1"]),
            redirect_stdout(buf),
        ):
            code = ops.main(["batch-review", "--channel", "tapin", "--expired"])
        self.assertEqual(code, 0)
        self.assertIn("Set aside - tapin: 1", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
