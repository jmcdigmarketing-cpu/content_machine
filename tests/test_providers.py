"""Pillar 6 provider-slot framework + seam fail-open contract.

Locks the two invariants every seam must keep: (1) the `ProviderResult` shape and the
`run_chain` never-raise / fail-open behavior, and (2) with every gate OFF and no optional
backend installed, each seam returns a non-ok result (so callers keep their current path).
No network, no LLM, no heavy deps.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

from core import (
    avatar,
    caption_align,
    comfy_client,
    grade,
    music,
    reframe,
    run_eval_corpus,
    vault_ingest,
)
from core.providers import (
    STATUS_OK,
    ProviderResult,
    flag_enabled,
    resolve_order,
    run_chain,
    selected_provider,
)


class ProviderResultShape(unittest.TestCase):
    def test_fail_open_defaults(self):
        r = ProviderResult.fail_open("slotx", "why")
        self.assertFalse(r.ok)
        self.assertEqual(r.slot, "slotx")
        self.assertEqual(r.detail, "why")
        self.assertEqual(r.cost_usd, 0.0)

    def test_success(self):
        r = ProviderResult.success("slotx", "prov", data=[1, 2], cost_usd=0.01)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, STATUS_OK)
        self.assertEqual(r.data, [1, 2])
        self.assertEqual(r.provider, "prov")


class EnvHelpers(unittest.TestCase):
    def test_resolve_order(self):
        with mock.patch.dict(os.environ, {"X": "a, B ,c"}, clear=False):
            self.assertEqual(resolve_order("X"), ["a", "b", "c"])
        for off in ("", "none", "off", "0", "false"):
            with mock.patch.dict(os.environ, {"X": off}, clear=False):
                self.assertEqual(resolve_order("X"), [])

    def test_selected_and_flag(self):
        with mock.patch.dict(os.environ, {"P": "ComfyUI", "F": "yes"}, clear=False):
            self.assertEqual(selected_provider("P"), "comfyui")
            self.assertTrue(flag_enabled("F"))
        self.assertEqual(selected_provider("MISSING", "none"), "none")
        self.assertFalse(flag_enabled("MISSING"))


class RunChain(unittest.TestCase):
    def test_empty_chain_fails_open(self):
        r = run_chain("s", [])
        self.assertFalse(r.ok)

    def test_first_ok_wins_and_never_raises(self):
        def boom(**_kw):
            raise RuntimeError("provider blew up")

        def nothing(**_kw):
            return None

        def good(**_kw):
            return ProviderResult.success("s", "good", data="x")

        def unused(**_kw):  # must not be reached once `good` returns ok
            raise AssertionError("should not run after an ok result")

        r = run_chain("s", [boom, nothing, good, unused])
        self.assertTrue(r.ok)
        self.assertEqual(r.provider, "good")

    def test_all_fail_open(self):
        def bad(**_kw):
            return ProviderResult.fail_open("s", "nope")

        r = run_chain("s", [bad, bad])
        self.assertFalse(r.ok)


class SeamsFailOpenWhenOff(unittest.TestCase):
    """With gates unset and no optional backend, every seam is non-ok and never raises."""

    def setUp(self):
        # Ensure gates are unset regardless of the developer's real .env.
        self._patch = mock.patch.dict(
            os.environ,
            {},
            clear=False,
        )
        self._patch.start()
        for var in (
            "TTS_PROVIDER",
            "CAPTION_ALIGN_BACKEND",
            "MUSIC_PROVIDER",
            "AI_VIDEO_PROVIDER",
            "EXPERT_PANEL_ENABLED",
            "AVATAR_PROVIDER",
            "REFRAME_ENABLED",
            "OBSIDIAN_VAULT_PATH",
        ):
            os.environ.pop(var, None)

    def tearDown(self):
        self._patch.stop()

    def test_caption_align(self):
        self.assertFalse(caption_align.transcribe_and_align("x.mp3").ok)

    def test_music(self):
        self.assertFalse(music.generate_bed("calm", 10).ok)

    def test_comfy_generate_without_workflow(self):
        # No workflow ⇒ fail-open with no network call.
        self.assertFalse(comfy_client.generate("a neon street").ok)

    def test_expert_panel_disabled(self):
        self.assertFalse(grade.expert_panel_review("draft text").ok)

    def test_avatar(self):
        self.assertFalse(avatar.lip_sync("p.png", "vo.mp3").ok)

    def test_reframe(self):
        self.assertFalse(reframe.reframe_vertical("clip.mp4").ok)

    def test_vault_ingest_url_shape_and_save_noop(self):
        with mock.patch("core.link_facts.extract_facts_from_url", return_value=["Fact one."]):
            rec = vault_ingest.ingest_url("https://example.com/a")
        self.assertEqual(rec["text"], "Fact one.")
        self.assertEqual(rec["source_url"], "https://example.com/a")
        self.assertIn("retrieved_at", rec)
        # No vault configured ⇒ save is a no-op returning None.
        self.assertIsNone(vault_ingest.save_to_vault(rec, "tapin"))

    def test_eval_corpus_lists_without_llm(self):
        rows = run_eval_corpus.run_corpus()  # README excluded; never raises
        self.assertIsInstance(rows, list)
        self.assertTrue(all(not r["scored"] for r in rows))

    def test_tts_default_is_elevenlabs(self):
        from core import tts

        self.assertEqual(tts._resolve_tts_provider(), "elevenlabs")
        self.assertIsNone(tts._try_alt_tts_provider("hi", "out.mp3", "tapin"))

    def test_tts_unknown_or_uninstalled_provider_falls_back(self):
        from core import tts

        # Selected but the backend isn't installed ⇒ None (ElevenLabs default runs).
        with mock.patch.dict(os.environ, {"TTS_PROVIDER": "kokoro"}, clear=False):
            self.assertNotIn("kokoro_installed", sys.modules)
            self.assertIsNone(tts._try_alt_tts_provider("hi", "out.mp3", "tapin"))


if __name__ == "__main__":
    unittest.main()
