"""Pillar 3 (Fact Engine) — claim-level LLM verifier: parsing, citations,
fail-open behavior, env switches, and the GROUNDING_GATE."""

import unittest
from unittest.mock import patch

from core import claim_verifier as cv

_FACTS = (
    "Tapology bout: Justin Gaethje vs Ilia Topuria\n"
    "- Gaethje won by TKO in round 2 at UFC 350\n"
    "- The event took place on 2026-07-04 in Las Vegas"
)
_SCRIPT = (
    "Gaethje stopped Topuria in round 2. He is now the undisputed champion. "
    "Expect a rematch by December."
)


def _llm_payload():
    return {
        "claims": [
            {"claim": "Gaethje stopped Topuria in round 2", "supported": True, "citation": 2},
            {"claim": "Gaethje is the undisputed champion", "supported": False, "citation": None},
        ]
    }


class TestVerifyClaims(unittest.TestCase):
    def setUp(self):
        # Credential/flag env leaks between tests (tests/CLAUDE.md) — pin the
        # verifier on for this class regardless of the ambient environment.
        self._env = patch.dict("os.environ", {"CLAIM_VERIFIER_ENABLED": "true"}, clear=False)
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_parses_claims_and_resolves_citations(self):
        with patch("core.llm_router.complete_json", return_value=_llm_payload()):
            result = cv.verify_claims(_SCRIPT, _FACTS, topic="UFC 350")
        self.assertIsNotNone(result)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.supported_count, 1)
        self.assertEqual(len(result.unsupported), 1)
        self.assertIn("undisputed champion", result.unsupported[0].claim)
        supported = next(c for c in result.claims if c.supported)
        self.assertIn("TKO in round 2", supported.citation_line)
        self.assertEqual(result.support_rate, 0.5)

    def test_to_dict_shape(self):
        with patch("core.llm_router.complete_json", return_value=_llm_payload()):
            d = cv.verify_claims(_SCRIPT, _FACTS).to_dict()
        self.assertEqual(d["total"], 2)
        self.assertEqual(d["supported"], 1)
        self.assertEqual(d["support_rate"], 0.5)
        self.assertEqual(len(d["unsupported"]), 1)

    def test_disabled_returns_none_without_llm_call(self):
        with patch.dict("os.environ", {"CLAIM_VERIFIER_ENABLED": "false"}, clear=False):
            with patch("core.llm_router.complete_json") as mock_llm:
                self.assertIsNone(cv.verify_claims(_SCRIPT, _FACTS))
                mock_llm.assert_not_called()

    def test_empty_inputs_return_none(self):
        self.assertIsNone(cv.verify_claims("", _FACTS))
        self.assertIsNone(cv.verify_claims(_SCRIPT, "  "))

    def test_llm_failure_is_fail_open(self):
        with patch("core.llm_router.complete_json", side_effect=RuntimeError("providers down")):
            self.assertIsNone(cv.verify_claims(_SCRIPT, _FACTS))

    def test_garbage_payload_returns_none(self):
        for payload in (None, "not json", {"claims": "nope"}, {"claims": []}):
            with patch("core.llm_router.complete_json", return_value=payload):
                self.assertIsNone(cv.verify_claims(_SCRIPT, _FACTS))

    def test_out_of_range_citation_ignored(self):
        payload = {"claims": [{"claim": "c", "supported": True, "citation": 99}]}
        with patch("core.llm_router.complete_json", return_value=payload):
            result = cv.verify_claims(_SCRIPT, _FACTS)
        self.assertEqual(result.claims[0].citation_line, "")

    def test_priority_facts_survive_char_budget_truncation(self):
        """Operator key facts must be numbered first — signal corpus can't crowd them out."""
        noise = "\n".join(f"Signal line {i} with filler padding text" for i in range(200))
        priority = ["The Lakers reportedly wanted James to take a pay cut."]
        facts = cv._numbered_facts(noise, priority_facts=priority)
        self.assertGreaterEqual(len(facts), 1)
        self.assertIn("pay cut", facts[0])


class TestGroundingGate(unittest.TestCase):
    def test_default_mode_is_block(self):
        """Was warn; armed by default since #735 (operator call 2026-09-13)."""
        with patch.dict("os.environ", {"GROUNDING_GATE": ""}, clear=False):
            self.assertEqual(cv.grounding_gate_mode(), "block")

    def test_gate_blocks_only_in_block_mode_with_unsupported(self):
        verification = {"total": 2, "supported": 1, "unsupported": ["bad claim"]}
        with patch.dict("os.environ", {"GROUNDING_GATE": "warn"}, clear=False):
            self.assertFalse(cv.gate_blocks(verification))
        with patch.dict("os.environ", {"GROUNDING_GATE": "block"}, clear=False):
            self.assertTrue(cv.gate_blocks(verification))
            self.assertFalse(cv.gate_blocks({"total": 2, "supported": 2, "unsupported": []}))
            self.assertFalse(cv.gate_blocks(None))


class TestDisplay(unittest.TestCase):
    def test_unsupported_claims_need_review(self):
        out: list[str] = []
        needs = cv.display_claim_verification(
            {"total": 3, "supported": 1, "unsupported": ["claim a", "claim b"]},
            print_fn=lambda *a: out.append(" ".join(str(x) for x in a)),
        )
        self.assertTrue(needs)
        joined = "\n".join(out)
        self.assertIn("2 of 3", joined)
        self.assertIn("claim a", joined)

    def test_all_supported_is_clean(self):
        out: list[str] = []
        needs = cv.display_claim_verification(
            {"total": 3, "supported": 3, "unsupported": []},
            print_fn=lambda *a: out.append(" ".join(str(x) for x in a)),
        )
        self.assertFalse(needs)
        self.assertIn("3/3", "\n".join(out))

    def test_none_shows_nothing(self):
        out: list[str] = []
        self.assertFalse(cv.display_claim_verification(None, print_fn=out.append))
        self.assertEqual(out, [])


class TestVerifierSeesWholeFacts(unittest.TestCase):
    def test_a_negation_past_the_old_400_char_slice_reaches_the_prompt(self):
        """#649. Facts used to be sliced at 400 chars. The drones / K9 /
        hurricane-weather claims sat in the tail. The verifier prompt must
        carry the whole sentence, including the negation.
        """
        pad = "Take-Two confirmed in a statement that " + ("the studio " * 40)
        tail = "will not use drones, K9 units, or hurricane-weather systems."
        full = pad + tail
        self.assertGreater(len(full), 400)
        captured: list[str] = []

        def fake_complete(user, **kwargs):
            captured.append(user)
            return {"claims": []}

        with (
            patch.dict("os.environ", {"CLAIM_VERIFIER_ENABLED": "true"}, clear=False),
            patch("core.llm_router.complete_json", side_effect=fake_complete),
        ):
            cv.verify_claims("GTA 6 uses drones in missions.", full, topic="GTA 6")
        self.assertTrue(captured)
        self.assertIn("hurricane-weather systems", captured[0])
        self.assertIn("will not use drones", captured[0])
        self.assertIn(full, captured[0])

    def test_known_gap_run_74_script_strings_are_not_in_the_repo(self):
        """The backlog named run 74's drones / K9 / hurricane-weather *script*.
        Operator traces are empty and those strings are not checked in. Closing
        that half needs the real script frozen beside this test.
        """
        from pathlib import Path

        repo = Path(__file__).resolve().parents[1]
        hits = []
        for path in (repo / "tests").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "hurricane-weather" in text and path.name != Path(__file__).name:
                hits.append(path.name)
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
