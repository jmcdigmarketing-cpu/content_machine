"""#86 frozen golden prompt-eval in CI — heuristic rubric, no LLM judge."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from core.prompt_evals import score_script

ROOT = Path(__file__).resolve().parent.parent
GOLDENS = ROOT / "config" / "prompt_eval_goldens.json"


class TestPromptEvalCi(unittest.TestCase):
    def _config(self):
        path = ROOT / "config" / "prompt_evals.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["channels"]

    def _goldens(self):
        self.assertTrue(GOLDENS.is_file(), "frozen golden scripts missing")
        return json.loads(GOLDENS.read_text(encoding="utf-8"))

    def test_one_golden_topic_per_shipped_channel_stays_grounded(self):
        channels = self._config()
        goldens = self._goldens()
        for channel_id in ("tapin", "moneywise"):
            self.assertIn(channel_id, channels)
            case = channels[channel_id][0]
            script = goldens[channel_id]["grounded_script"]
            scores = score_script(
                script,
                key_facts=list(case["key_facts"]),
                length_choice=str(case["length_choice"]),
            )
            self.assertEqual(
                scores["ungrounded_count"],
                0,
                f"{channel_id} golden script introduced ungrounded claims: {scores}",
            )

    def test_invented_claim_fails_the_rubric(self):
        channels = self._config()
        goldens = self._goldens()
        for channel_id in ("tapin", "moneywise"):
            case = channels[channel_id][0]
            drifted = goldens[channel_id]["ungrounded_script"]
            scores = score_script(
                drifted,
                key_facts=list(case["key_facts"]),
                length_choice=str(case["length_choice"]),
            )
            self.assertGreater(
                scores["ungrounded_count"],
                0,
                f"{channel_id} drifted script must fail the ungrounded check",
            )


if __name__ == "__main__":
    unittest.main()
