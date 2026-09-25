"""Config-driven voice catalog: registry loading, parked categories, dead-voice guard.

Adding a voice must be a config edit, and a bad id must never kill a render (it surfaces
at the TTS step, after the whole script + grounding pipeline has already succeeded).
No network â€” the ElevenLabs client is mocked. Per tests/CLAUDE.md.
"""

import json
import os
import tempfile
import unittest
from typing import ClassVar
from unittest.mock import patch

from core import tts


class _CatalogCase(unittest.TestCase):
    """Points core.tts at a temp voices.json and clears its caches around each test."""

    catalog: ClassVar[dict] = {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "voices.json")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.catalog, f)
        self._patch = patch.object(tts, "VOICES_FILE", self.path)
        self._patch.start()
        tts._voice_catalog_cache = None
        tts.reset_dead_voices()

    def tearDown(self):
        self._patch.stop()
        tts._voice_catalog_cache = None
        tts.reset_dead_voices()


class TestRegistryFromConfig(_CatalogCase):
    catalog: ClassVar[dict] = {
        "elevenlabs": {
            "male": [{"id": "aaa", "weight": 3}, {"id": "bbb", "weight": 1}],
            "female": [{"id": "ccc", "weight": 2}],
            "_parked": [{"id": "zzz", "weight": 9}],
        },
        "local": {"piper": [{"id": "voices/a.onnx", "weight": 2}], "kokoro": ["af_heart"]},
    }

    def test_categories_and_weights_load(self):
        registry = tts.load_voice_registry()
        self.assertEqual(registry["male"], {"aaa": 3, "bbb": 1})
        self.assertEqual(registry["female"], {"ccc": 2})

    def test_underscore_category_is_parked(self):
        registry = tts.load_voice_registry()
        self.assertNotIn("_parked", registry)
        self.assertNotIn("zzz", {v for pool in registry.values() for v in pool})

    def test_global_pick_only_uses_active_voices(self):
        picks = {tts.weighted_random_voice() for _ in range(60)}
        self.assertTrue(picks.issubset({"aaa", "bbb", "ccc"}))

    def test_local_pool_reads_both_shapes(self):
        self.assertEqual(tts.load_local_voice_pool("piper"), {"voices/a.onnx": 2})
        self.assertEqual(tts.load_local_voice_pool("kokoro"), {"af_heart": 1})  # bare string
        self.assertEqual(tts.load_local_voice_pool("xtts"), {})


class TestRegistryFallback(_CatalogCase):
    catalog: ClassVar[dict] = {"elevenlabs": {}}  # present but defines nothing usable

    def test_empty_catalog_falls_back_to_builtin(self):
        self.assertEqual(tts.load_voice_registry(), tts._BUILTIN_VOICE_REGISTRY)

    def test_missing_file_falls_back_to_builtin(self):
        os.remove(self.path)
        tts._voice_catalog_cache = None
        self.assertEqual(tts.load_voice_registry(), tts._BUILTIN_VOICE_REGISTRY)

    def test_malformed_file_falls_back_to_builtin(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")
        tts._voice_catalog_cache = None
        self.assertEqual(tts.load_voice_registry(), tts._BUILTIN_VOICE_REGISTRY)


class TestDeadVoiceGuard(_CatalogCase):
    catalog: ClassVar[dict] = {
        "elevenlabs": {"male": [{"id": "good", "weight": 1}, {"id": "bad", "weight": 1}]}
    }

    def test_unusable_voice_detection(self):
        self.assertTrue(tts._is_unusable_voice(Exception("voice_not_found")))
        self.assertTrue(tts._is_unusable_voice(Exception("A voice with ID 'x' was not found.")))
        self.assertFalse(tts._is_unusable_voice(Exception("rate limited")))

    def test_dead_voice_is_skipped(self):
        tts._mark_voice_dead("bad", "voice_not_found")
        picks = {tts.weighted_random_voice() for _ in range(40)}
        self.assertEqual(picks, {"good"})

    def test_all_dead_still_returns_a_voice(self):
        # Never leave the caller with an empty pool â€” retry beats crashing.
        tts._mark_voice_dead("good", "voice_not_found")
        tts._mark_voice_dead("bad", "voice_not_found")
        self.assertIn(tts.weighted_random_voice(), {"good", "bad"})

    def test_pinned_pool_respects_dead_voices(self):
        tts._mark_voice_dead("bad", "voice_not_found")
        picks = {tts.weighted_random_voice({"good": 1, "bad": 5}) for _ in range(40)}
        self.assertEqual(picks, {"good"})


class TestEntriesToPool(unittest.TestCase):
    def test_skips_blanks_and_floors_weight(self):
        entries = [
            {"id": "a", "weight": 5},
            {"id": "", "weight": 3},  # blank id dropped
            {"id": "b", "weight": 0},  # floors to 1
            {"id": "c", "weight": "x"},  # unparseable -> 1
            "d",  # bare string -> weight 1
            42,  # wrong type dropped
        ]
        self.assertEqual(tts._entries_to_pool(entries), {"a": 5, "b": 1, "c": 1, "d": 1})

    def test_non_list_is_empty(self):
        self.assertEqual(tts._entries_to_pool({"id": "a"}), {})
        self.assertEqual(tts._entries_to_pool(None), {})


class TestLocalVoicePrecedence(_CatalogCase):
    catalog: ClassVar[dict] = {"local": {"piper": [{"id": "catalog.onnx", "weight": 1}]}}

    def test_catalog_beats_env_pool(self):
        with patch("core.tts.get_channel_profile", side_effect=RuntimeError("no profile")):
            with patch.dict(os.environ, {"PIPER_VOICES": "env.onnx"}, clear=False):
                self.assertEqual(tts.resolve_local_voice("piper", "tapin"), "catalog.onnx")

    def test_env_used_when_catalog_empty(self):
        # kokoro has no catalog entry here, so its own env pool wins.
        with patch("core.tts.get_channel_profile", side_effect=RuntimeError("no profile")):
            with patch.dict(os.environ, {"KOKORO_VOICES": "af_bella"}, clear=False):
                self.assertEqual(tts.resolve_local_voice("kokoro", "tapin"), "af_bella")


_OPERATOR_ELEVENLABS_INTAKE = (
    "3TPKV1kjDlVtZbl4Ksh",
    "ksryVoNAGZT8GxWCTiVm",
    "VhxAIIZM8IRmnl5fyeyk",
    "si0svtk05vPEuvwAW93c",
    "fBD19tfE58bkETeiwUoC",
    "GorLj2SsI4u2JqL58gAA",
    "PoqlHoqJoAfdQ0g8bLK3",
)


class TestShippedVoicesJson(unittest.TestCase):
    def _catalog(self) -> dict:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "config", "voices.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_operator_elevenlabs_ids_are_listed(self):
        blob = json.dumps(self._catalog())
        for vid in _OPERATOR_ELEVENLABS_INTAKE:
            self.assertIn(vid, blob)

    def test_piper_catalog_has_four_equal_weight_onnx(self):
        piper = self._catalog().get("local", {}).get("piper") or []
        self.assertEqual(len(piper), 4)
        weights = {int(row.get("weight") or 1) for row in piper}
        self.assertEqual(weights, {1})
        for row in piper:
            path = str(row.get("id") or "")
            self.assertTrue(path.lower().endswith(".onnx"), path)
            self.assertIn("video/voices/", path.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
