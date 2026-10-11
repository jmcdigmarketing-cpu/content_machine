"""#1034: sentences that are hard to say are rewritten before they are voiced.

A script is read once and heard once. Three shapes trip a voice (and the listener): a string
of numbers ("18-0-0 with 8 KO and 10 SUB"), a parenthetical, and three or more names in a row.
The detector is free and always reports; the rewrite is one cheap call, only on a hit, and a
rewritten sentence is kept only if it still carries every number and name and no new one.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

SCRIPT = (
    "Shavkat Rakhmonov is 18-0-0 with 8 KO and 10 SUB. "
    "The welterweight belt (vacant since March) is the prize. "
    "He beat Garry. "
    "Next come Usman, Edwards, Covington and Muhammad."
)


class HardToSayTests(unittest.TestCase):
    def _why(self, script):
        from core.script_craft import hard_to_say

        return {row["sentence"]: row["why"] for row in hard_to_say(script)}

    def test_a_number_string_is_flagged(self):
        found = self._why(SCRIPT)
        self.assertEqual(found["Shavkat Rakhmonov is 18-0-0 with 8 KO and 10 SUB."], "numbers")

    def test_a_parenthetical_is_flagged(self):
        found = self._why(SCRIPT)
        self.assertEqual(
            found["The welterweight belt (vacant since March) is the prize."], "parenthetical"
        )

    def test_stacked_names_are_flagged(self):
        found = self._why(SCRIPT)
        self.assertEqual(found["Next come Usman, Edwards, Covington and Muhammad."], "names")

    def test_a_plain_sentence_is_not(self):
        self.assertNotIn("He beat Garry.", self._why(SCRIPT))
        self.assertEqual(self._why("He won 19 fights. Two were decisions."), {})

    def test_one_score_is_not_a_number_string(self):
        self.assertEqual(self._why("The Chargers lost 27-10 on Sunday."), {})


class RewriteTests(unittest.TestCase):
    def _run(self, replies, script=SCRIPT, enabled="true"):
        from core import script_craft

        def call(system, user):
            return {"rewrites": replies}

        with patch.dict(os.environ, {"READ_ALOUD_REWRITE": enabled}):
            return script_craft.read_aloud_pass(script, call)

    def test_a_rewrite_that_keeps_everything_is_taken(self):
        old = "The welterweight belt (vacant since March) is the prize."
        new = "The welterweight belt has been vacant since March. It is the prize."
        script, report = self._run([{"old": old, "new": new}])
        self.assertIn(new, script)
        self.assertNotIn("(", script)
        self.assertEqual(report["rewritten"], 1)
        self.assertEqual(report["flagged"], 3)

    def test_a_rewrite_that_drops_a_number_is_refused(self):
        old = "Shavkat Rakhmonov is 18-0-0 with 8 KO and 10 SUB."
        new = "Shavkat Rakhmonov is unbeaten, with eight knockouts."
        script, report = self._run([{"old": old, "new": new}])
        self.assertIn(old, script)
        self.assertEqual(report["rewritten"], 0)

    def test_a_rewrite_that_adds_a_name_is_refused(self):
        old = "Next come Usman, Edwards, Covington and Muhammad."
        new = "Next come Usman and Edwards. Then Covington, Muhammad and Chimaev."
        script, _report = self._run([{"old": old, "new": new}])
        self.assertIn(old, script)

    def test_a_rewrite_that_is_still_hard_is_refused(self):
        old = "The welterweight belt (vacant since March) is the prize."
        new = "The welterweight belt (it has been vacant since March) is the prize."
        script, _report = self._run([{"old": old, "new": new}])
        self.assertIn(old, script)

    def test_off_reports_and_changes_nothing(self):
        calls = []
        from core import script_craft

        with patch.dict(os.environ, {"READ_ALOUD_REWRITE": "false"}):
            script, report = script_craft.read_aloud_pass(SCRIPT, lambda s, u: calls.append(1))
        self.assertEqual((script, calls), (SCRIPT, []))
        self.assertEqual(report["flagged"], 3)

    def test_nothing_flagged_makes_no_call(self):
        calls = []
        from core import script_craft

        with patch.dict(os.environ, {"READ_ALOUD_REWRITE": "true"}):
            script, report = script_craft.read_aloud_pass(
                "He won 19 fights.", lambda s, u: calls.append(1)
            )
        self.assertEqual((script, calls, report["flagged"]), ("He won 19 fights.", [], 0))

    def test_a_failed_call_keeps_the_script(self):
        from core import script_craft

        def boom(system, user):
            raise RuntimeError("no model")

        with patch.dict(os.environ, {"READ_ALOUD_REWRITE": "true"}):
            script, report = script_craft.read_aloud_pass(SCRIPT, boom)
        self.assertEqual(script, SCRIPT)
        self.assertEqual(report["rewritten"], 0)

    def test_the_suite_runs_with_it_off(self):
        self.assertEqual(os.environ.get("READ_ALOUD_REWRITE"), "false")


if __name__ == "__main__":
    unittest.main()
