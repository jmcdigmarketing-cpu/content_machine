"""Thin-facts abort before TTS — drafts stay free; the $0.31 voice line does not."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.thin_facts import thin_facts_abort_reason


class TestThinFactsAbort(unittest.TestCase):
    def test_well_grounded_does_not_abort(self):
        with patch.dict(os.environ, {"THIN_FACTS_TTS_ABORT": "true"}, clear=False):
            reason = thin_facts_abort_reason(
                fact_count=8,
                features={"claim_verification": {"support_rate": 0.92, "total": 12}},
            )
        self.assertIsNone(reason)

    def test_few_fact_lines_aborts(self):
        with patch.dict(os.environ, {"THIN_FACTS_TTS_ABORT": "true", "THIN_FACTS_MIN_LINES": "3"}):
            reason = thin_facts_abort_reason(fact_count=1, features={"claim_support_rate": 1.0})
        self.assertIsNotNone(reason)
        self.assertIn("1 verified", reason)

    def test_low_claim_support_aborts(self):
        with patch.dict(
            os.environ,
            {
                "THIN_FACTS_TTS_ABORT": "true",
                "THIN_FACTS_MIN_LINES": "3",
                "THIN_FACTS_MIN_SUPPORT": "0.5",
            },
            clear=False,
        ):
            reason = thin_facts_abort_reason(fact_count=6, features={"claim_support_rate": 0.2})
        self.assertIsNotNone(reason)
        self.assertIn("20%", reason)

    def test_missing_verifier_fail_opens_on_support_bar(self):
        # Verifier skipped/failed — do not invent a support rate and block a 6-line draft.
        with patch.dict(os.environ, {"THIN_FACTS_TTS_ABORT": "true"}, clear=False):
            reason = thin_facts_abort_reason(fact_count=6, features={})
        self.assertIsNone(reason)

    def test_env_off_never_aborts(self):
        with patch.dict(os.environ, {"THIN_FACTS_TTS_ABORT": "off"}, clear=False):
            reason = thin_facts_abort_reason(fact_count=0, features={"claim_support_rate": 0.0})
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
