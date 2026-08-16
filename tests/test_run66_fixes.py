"""Defects surfaced by live run 66 (GTA VI / Netflix), each reproduced before fixing.

The run rendered and published fine, which is the point: none of these announced
themselves as failures. They were a wrong number shown to the operator, a false alarm
from the quality gate, a signal reporting ERROR for a transient hiccup, a junk question,
and two model slugs quietly probing into the void once a day.

No network: every external call is mocked (tests/CLAUDE.md).
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from apis.signal_contract import STATUS_ERROR, STATUS_UNAVAILABLE, classify_exception


class TestDurationEstimate(unittest.TestCase):
    """Run 66: shown "243 words (~101s spoken)", rendered 70.2s of audio."""

    def test_run66_estimate_now_tracks_reality(self):
        from core.script_length import estimate_duration_seconds

        self.assertAlmostEqual(estimate_duration_seconds("word " * 243), 70.2, delta=8.0)

    def test_old_constant_would_still_fail_this(self):
        # Pins WHY the constant changed: 2.4 w/s predicts 101s for the same script.
        from core.script_length import estimate_duration_seconds

        self.assertAlmostEqual(estimate_duration_seconds("word " * 243, wps=2.4), 101.25, delta=1)

    def test_preset_seconds_cannot_drift_from_words(self):
        from core.script_length import PRESETS, WORDS_PER_SECOND

        for preset in PRESETS.values():
            self.assertEqual(preset.min_seconds, round(preset.min_words / WORDS_PER_SECOND))
            self.assertEqual(preset.max_seconds, round(preset.max_words / WORDS_PER_SECOND))

    def test_extended_advertises_an_achievable_duration(self):
        # It used to claim 420-900s while really producing ~300-600s.
        from core.script_length import estimate_duration_seconds, get_length_preset

        preset = get_length_preset("4")
        actual_max = estimate_duration_seconds("word " * preset.max_words)
        self.assertAlmostEqual(preset.max_seconds, actual_max, delta=2)


class TestGroundingFalseAlarm(unittest.TestCase):
    """Run 66 flagged "If Netflix" as a possible hallucination and lost a grade for it."""

    FACTS = "Netflix bags an exclusive GTA VI trailer. Rockstar Games announced August 27."
    SENTENCE = "My prediction? If Netflix's numbers spike on August 27, publishers follow."

    def test_sentence_initial_if_no_longer_flags(self):
        from core.fact_grounding import find_ungrounded_entities

        self.assertEqual(find_ungrounded_entities(self.SENTENCE, self.FACTS), [])

    def test_the_entity_extracted_is_the_real_one(self):
        from core.fact_grounding import extract_entities

        self.assertIn("Netflix", extract_entities(self.SENTENCE))
        self.assertNotIn("If Netflix", extract_entities(self.SENTENCE))

    def test_other_sentence_openers_too(self):
        from core.fact_grounding import extract_entities

        for text, want in (
            ("When Sony responded", "Sony"),
            ("Because Rockstar Games delayed it", "Rockstar Games"),
            ("But Netflix disagreed", "Netflix"),
            ("Although Nintendo waited", "Nintendo"),
        ):
            self.assertIn(want, extract_entities(text), text)

    def test_real_inventions_are_still_caught(self):
        # The gate must not be softened into uselessness.
        from core.fact_grounding import find_ungrounded_entities

        flagged = find_ungrounded_entities(
            "But Shadow Legion joins Emma Frost next week.", self.FACTS
        )
        self.assertIn("Shadow Legion", flagged)
        self.assertIn("Emma Frost", flagged)

    def test_legitimate_names_survive_the_trim(self):
        # A first attempt trimmed on the whole common-word list and destroyed these.
        from core.fact_grounding import extract_entities

        self.assertIn("Black Widow", extract_entities("Emma Frost and Black Widow are in."))
        self.assertIn("Season 8.5", extract_entities("The Season 8.5 update dropped."))

    def test_the_word_the_is_not_trimmed(self):
        # "The Rock", "The Athletic" are real names.
        from core.fact_grounding import extract_entities

        self.assertTrue(any("The" in e for e in extract_entities("The Rock returned.")))


class TestTimeoutClassification(unittest.TestCase):
    """Run 66: `youtube: ERROR - The read operation timed out`."""

    def test_timeout_is_transient_not_an_error(self):
        status, _ = classify_exception(TimeoutError("The read operation timed out"))
        self.assertEqual(status, STATUS_UNAVAILABLE)

    def test_message_only_timeouts_too(self):
        status, _ = classify_exception(OSError("connection timeout after 15s"))
        self.assertEqual(status, STATUS_UNAVAILABLE)

    def test_genuine_errors_still_error(self):
        self.assertEqual(classify_exception(ValueError("bad json"))[0], STATUS_ERROR)

    def test_quota_and_auth_still_win_over_timeout(self):
        # Ordering matters: a quota message must not be downgraded to a timeout.
        self.assertNotEqual(
            classify_exception(RuntimeError("quota exceeded, timed out"))[0], STATUS_UNAVAILABLE
        )

    def test_youtube_client_gets_a_bounded_timeout(self):
        from apis.youtube_api import api_timeout

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(api_timeout(), 15.0)
        with patch.dict(os.environ, {"YOUTUBE_API_TIMEOUT": "5"}, clear=False):
            self.assertEqual(api_timeout(), 5.0)
        with patch.dict(os.environ, {"YOUTUBE_API_TIMEOUT": "junk"}, clear=False):
            self.assertEqual(api_timeout(), 15.0)


class TestQuestionRelevance(unittest.TestCase):
    """Run 66 surfaced only "What about Alaska?" from 25 comments on a GTA VI video."""

    TOPIC = "GTA VI trailer Netflix-only release"

    def test_the_run66_question_is_rejected(self):
        from apis.youtube_comments_signal import _is_useful_question

        self.assertFalse(_is_useful_question("What about Alaska?", self.TOPIC))

    def test_topic_relevant_questions_pass(self):
        from apis.youtube_comments_signal import _is_useful_question

        for q in (
            "Why is Rockstar putting the GTA trailer on Netflix first?",
            "Does the Netflix deal mean no YouTube premiere at all?",
        ):
            self.assertTrue(_is_useful_question(q, self.TOPIC), q)

    def test_first_only_filters_the_bait_form(self):
        # "first" as a substring was throwing away legitimate questions.
        from apis.youtube_comments_signal import _is_useful_question

        self.assertFalse(_is_useful_question("first?", self.TOPIC))
        self.assertFalse(_is_useful_question("im first", self.TOPIC))
        self.assertTrue(
            _is_useful_question("Why does Netflix get the GTA trailer first?", self.TOPIC)
        )

    def test_no_topic_keeps_old_behaviour(self):
        from apis.youtube_comments_signal import _is_useful_question

        self.assertTrue(_is_useful_question("Why did they change the whole ranking system?", ""))


class TestDeadSlugs(unittest.TestCase):
    def test_openrouter_default_is_not_the_retired_slug(self):
        from core.llm_router import _DEFAULT_MODELS

        cheap = _DEFAULT_MODELS["openrouter"]["cheap"]
        self.assertNotEqual(cheap, "meta-llama/llama-3.3-70b-instruct:free")
        self.assertTrue(cheap.endswith(":free"), "cheap tier should stay zero-cost")

    def test_ollama_unavailable_when_nothing_is_pulled(self):
        from core import llm_router

        with (
            patch.object(llm_router, "ollama_installed_models", return_value=[]),
            patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1:8b"}, clear=False),
        ):
            self.assertFalse(llm_router._provider_available("ollama", "cheap"))

    def test_ollama_available_when_the_model_is_pulled(self):
        from core import llm_router

        with (
            patch.object(llm_router, "ollama_installed_models", return_value=["llama3.1:8b"]),
            patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1:8b"}, clear=False),
        ):
            self.assertTrue(llm_router._provider_available("ollama", "cheap"))

    def test_bare_name_matches_a_tagged_install(self):
        from core import llm_router

        with (
            patch.object(llm_router, "ollama_installed_models", return_value=["llama3.1:8b"]),
            patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1"}, clear=False),
        ):
            self.assertTrue(llm_router._provider_available("ollama", "cheap"))

    def test_a_different_model_is_not_a_match(self):
        from core import llm_router

        with (
            patch.object(llm_router, "ollama_installed_models", return_value=["qwen2.5:7b"]),
            patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1:8b"}, clear=False),
        ):
            self.assertFalse(llm_router._provider_available("ollama", "cheap"))

    def test_empty_ollama_is_dropped_from_the_chain(self):
        # The payoff: no request, so no daily 404 and no dead-model record.
        from core import llm_router

        with (
            patch.object(llm_router, "ollama_installed_models", return_value=[]),
            patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1:8b"}, clear=False),
        ):
            providers = [p for p, _ in llm_router._resolve_chain("cheap")]
        self.assertNotIn("ollama", providers)

    def test_daemon_unreachable_is_not_an_exception(self):
        from core import llm_router

        with patch.dict("sys.modules", {"requests": MagicMock(get=MagicMock(side_effect=OSError))}):
            self.assertEqual(llm_router.ollama_installed_models(refresh=True), [])


if __name__ == "__main__":
    unittest.main()
