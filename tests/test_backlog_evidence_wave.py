"""Fail-first coverage for backlog evidence items #424, #453, #552 and #582."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

_ASCII = st.characters(min_codepoint=32, max_codepoint=126)


class FootageLicenseLedgerTests(unittest.TestCase):
    def test_ledger_links_expired_clip_license_to_the_run_that_used_it(self):
        from assets.license_ledger import license_ledger_rows

        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp, "chargers.mp4")
            clip.write_bytes(b"clip")
            sidecar = clip.with_suffix(".license.yaml")
            sidecar.write_text(
                json.dumps(
                    {
                        "license": "CC BY 4.0",
                        "commercial_use": True,
                        "expires_on": "2026-01-01",
                    }
                ),
                encoding="utf-8",
            )
            index = Path(tmp, "clip_index.json")
            index.write_text(
                json.dumps({"clips": {str(clip): {"game": "Madden 26"}}}),
                encoding="utf-8",
            )
            runs = [
                SimpleNamespace(
                    id=124,
                    channel_id="tapin",
                    quality_json=json.dumps({"footage_clips": [str(clip)]}),
                )
            ]

            rows = license_ledger_rows(
                index_path=str(index),
                runs=runs,
                today=date(2026, 10, 16),
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["license"], "CC BY 4.0")
        self.assertTrue(rows[0]["commercial_use"])
        self.assertEqual(rows[0]["expiry_status"], "EXPIRED")
        self.assertEqual(rows[0]["run_ids"], [124])


class SignalContractPropertyTests(unittest.TestCase):
    @settings(
        max_examples=40,
        deadline=None,
        suppress_health_check=(HealthCheck.too_slow,),
    )
    @given(
        connected=st.booleans(),
        active=st.one_of(st.none(), st.booleans()),
        score=st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False)),
        data=st.one_of(
            st.none(),
            st.dictionaries(
                st.text(alphabet=_ASCII, max_size=8),
                st.integers(),
                max_size=4,
            ),
        ),
        detail=st.one_of(st.none(), st.text(alphabet=_ASCII, max_size=30)),
    )
    def test_normalization_always_returns_the_complete_signal_contract(
        self,
        connected,
        active,
        score,
        data,
        detail,
    ):
        from apis.signal_contract import normalize_signal

        raw = {"connected": connected}
        if active is not None:
            raw["active"] = active
        if score is not None:
            raw["score"] = score
        if data is not None:
            raw["data"] = data
        if detail is not None:
            raw["status_detail"] = detail
        normalized = normalize_signal(raw)

        required = {
            "connected",
            "active",
            "score",
            "confidence",
            "data",
            "status",
            "status_detail",
        }
        self.assertTrue(required.issubset(normalized), normalized)
        self.assertIs(normalized["connected"], connected)
        if data is not None:
            self.assertEqual(normalized["data"], data)

    def test_none_normalizes_to_the_same_complete_contract(self):
        from apis.signal_contract import normalize_signal

        normalized = normalize_signal(None)
        self.assertEqual(
            set(normalized),
            {
                "connected",
                "active",
                "score",
                "confidence",
                "data",
                "status",
                "status_detail",
            },
        )


class NumberUnitSanityTests(unittest.TestCase):
    def test_wrong_unit_is_flagged_but_an_equivalent_conversion_is_not(self):
        from core.facts.unit_sanity import find_unit_mismatches

        facts = "The campaign video ran for 80 minutes before the final segment."
        wrong = find_unit_mismatches(
            "The campaign video ran for 80 hours before the final segment.",
            facts,
        )
        equivalent = find_unit_mismatches(
            "The campaign video ran for 1.33 hours before the final segment.",
            facts,
        )
        unrelated = find_unit_mismatches(
            "The battery lasted 80 hours.",
            facts,
        )

        self.assertEqual(len(wrong), 1)
        self.assertIn("80 hours", wrong[0])
        self.assertEqual(equivalent, [])
        self.assertEqual(unrelated, [])


class ProviderLatencyBudgetTests(unittest.TestCase):
    def test_successful_call_records_measured_latency(self):
        from core import llm_router

        llm_router.reset_usage()
        with (
            patch.object(llm_router, "_resolve_chain", return_value=[("deepseek", "model")]),
            patch.object(llm_router, "_openai_complete", return_value=("ok", 2, 1)),
            patch.object(llm_router.time, "perf_counter", side_effect=[10.0, 12.5]),
        ):
            self.assertEqual(llm_router.complete("hello"), "ok")
        self.assertEqual(llm_router.get_usage()[0]["elapsed_seconds"], 2.5)

    def test_reliability_flags_latest_provider_latency_against_trailing_budget(self):
        from core.reliability import provider_latency_rows

        traces = [
            {
                "llm_calls": [
                    {"provider": "deepseek", "elapsed_seconds": seconds}
                    for seconds in (2.0, 2.2, 1.8, 12.0)
                ]
            }
        ]
        rows = provider_latency_rows(traces)
        self.assertEqual(rows[0]["provider"], "deepseek")
        self.assertEqual(rows[0]["budget_seconds"], 10.0)
        self.assertEqual(rows[0]["latest_seconds"], 12.0)
        self.assertTrue(rows[0]["over_budget"])


if __name__ == "__main__":
    unittest.main()
