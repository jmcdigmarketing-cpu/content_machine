"""SkillOpt-Sleep (Pillar 7 C2) — the gate/winner orchestration + frozen aggregate.

Generation + rubric scoring are covered by prompt_evals' own tests; here we patch the
per-directive scorer to exercise run_skillopt's baseline-vs-candidate gate, proposal write,
and fail-open paths without any LLM calls.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from core import skillopt


class TestAggregate(unittest.TestCase):
    def test_frozen_scalar(self):
        # 80 hook - 10*1 ungrounded - 5*2 filler + 10 length_fit = 70
        s = {"hook_score": 80, "ungrounded_count": 1, "filler_count": 2, "length_fit": True}
        self.assertEqual(skillopt._aggregate(s), 70.0)

    def test_handles_missing_metrics(self):
        self.assertEqual(skillopt._aggregate({}), 0.0)
        self.assertEqual(skillopt._aggregate({"hook_score": 50}), 50.0)


class TestRunSkillopt(unittest.TestCase):
    def _scores(self, mapping):
        # side_effect for _score_directive(channel, directive) -> (mean_aggregate, n)
        return lambda _ch, d: mapping[d]

    def test_winner_written_when_beats_gate(self):
        mapping = {"": (10.0, 2), "D1": (25.0, 2), "D2": (11.0, 2)}
        with (
            tempfile.TemporaryDirectory() as vault,
            patch("core.skillopt._score_directive", side_effect=self._scores(mapping)),
            patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}, clear=False),
            patch("core.events.emit_event"),
        ):
            res = skillopt.run_skillopt("tapin", directives=("D1", "D2"))
            self.assertTrue(res.improved)
            self.assertEqual(res.best_directive, "D1")
            self.assertEqual(res.best_score, 25.0)
            self.assertTrue(os.path.isfile(res.proposal_path))
            with open(res.proposal_path, encoding="utf-8") as f:
                self.assertIn("D1", f.read())

    def test_no_winner_when_below_margin(self):
        mapping = {"": (10.0, 2), "D1": (10.5, 2)}
        with (
            patch("core.skillopt._score_directive", side_effect=self._scores(mapping)),
            patch.dict(os.environ, {"SKILLOPT_MIN_MARGIN": "1.0"}, clear=False),
        ):
            res = skillopt.run_skillopt("tapin", directives=("D1",))
        self.assertFalse(res.improved)
        self.assertEqual(res.proposal_path, "")

    def test_no_golden_topics_is_noop(self):
        with patch("core.skillopt._score_directive", return_value=(0.0, 0)):
            res = skillopt.run_skillopt("tapin", directives=("D1",))
        self.assertEqual(res.n_topics, 0)
        self.assertFalse(res.improved)

    def test_proposal_skipped_without_vault(self):
        mapping = {"": (10.0, 2), "D1": (99.0, 2)}
        with (
            patch("core.skillopt._score_directive", side_effect=self._scores(mapping)),
            patch.dict(os.environ, {}, clear=False),
            patch("core.events.emit_event"),
        ):
            os.environ.pop("OBSIDIAN_VAULT_PATH", None)
            res = skillopt.run_skillopt("tapin", directives=("D1",))
        self.assertTrue(res.improved)  # still a winner
        self.assertEqual(res.proposal_path, "")  # just no record written


if __name__ == "__main__":
    unittest.main()
