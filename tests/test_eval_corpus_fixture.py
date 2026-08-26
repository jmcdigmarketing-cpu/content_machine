"""Eval-corpus in-repo fixture is listed with EVAL_CORPUS_LLM off."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core import run_eval_corpus


class TestEvalCorpusFixture(unittest.TestCase):
    def test_load_cases_returns_original_fixture(self):
        cases = run_eval_corpus.load_cases()
        names = [name for name, _text in cases]
        self.assertIn("invented_release_date", names)
        body = dict(cases)["invented_release_date"]
        self.assertIn("GTA", body)
        self.assertNotIn("system_prompts_leaks", body)

    def test_runner_lists_fixture_without_llm(self):
        with patch.dict(os.environ, {"EVAL_CORPUS_LLM": ""}, clear=False):
            os.environ.pop("EVAL_CORPUS_LLM", None)
            rows = run_eval_corpus.run_corpus()
        matching = [r for r in rows if r["case"] == "invented_release_date"]
        self.assertEqual(len(matching), 1)
        self.assertFalse(matching[0]["scored"])
        self.assertGreater(matching[0]["chars"], 40)


if __name__ == "__main__":
    unittest.main()
