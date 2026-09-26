"""Edge TTS (TTS_PROVIDER=edge) — cloud $0, SSML lexicon, WordBoundary sidecar.

Never hits Microsoft: Communicate.stream is mocked. Captions keep the caller script.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from core import tts


class _FakeCommunicate:
    """Stand-in for edge_tts.Communicate. Records the text Edge would speak."""

    last_text = ""
    last_voice = ""
    last_boundary = ""
    fail = False
    events: ClassVar[list[dict]] = []

    # Mirrors the real edge_tts 7.x signature, which defaults `boundary` to
    # "SentenceBoundary" -- a fake that only accepts (text, voice) would happily
    # pin the caller's omission instead of catching it.
    def __init__(self, text: str, voice: str, *, boundary: str = "SentenceBoundary"):
        type(self).last_text = text
        type(self).last_voice = voice
        type(self).last_boundary = boundary

    async def stream(self):
        if self.fail:
            raise RuntimeError("edge endpoint gone")
        for event in self.events:
            yield event


def _edge_module():
    class _Mod:
        Communicate = _FakeCommunicate

    return _Mod()


class _EdgeCase(unittest.TestCase):
    """Every test starts from a disarmed, empty fake.

    `_FakeCommunicate` is one class with mutable class attributes, and one test arms
    `fail = True` to prove the fallback. Nothing reset it, so under `ops test --order
    shuffle --seed 1` the endpoint test that ran next saw "edge endpoint gone" (#828).
    """

    def setUp(self):
        _FakeCommunicate.fail = False
        _FakeCommunicate.events = []
        _FakeCommunicate.last_text = ""
        _FakeCommunicate.last_voice = ""
        _FakeCommunicate.last_boundary = ""


def _boundary(text: str, offset_ticks: int, duration_ticks: int) -> dict:
    return {
        "type": "WordBoundary",
        "offset": offset_ticks,
        "duration": duration_ticks,
        "text": text,
    }


class TestEdgeRequestsWordTimings(_EdgeCase):
    """edge_tts 7.x defaults to SentenceBoundary, so a Communicate() built without
    `boundary=` yields no WordBoundary events at all and the .words.json branch is
    silently skipped. decisions SS23 (captions are timed by the ASR) then has nothing
    to time with on the $0 path."""

    def test_synth_asks_for_word_boundaries(self):
        _FakeCommunicate.events = [_boundary("Hello", 0, 5_000_000)]
        _FakeCommunicate.last_boundary = ""
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "vo.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "edge"}, clear=False),
                patch.dict("sys.modules", {"edge_tts": _edge_module()}),
            ):
                tts._edge_synth("Hello", out, "tapin")
        self.assertEqual(_FakeCommunicate.last_boundary, "WordBoundary")


class TestEdgeIsSentSpeakableText(_EdgeCase):
    """`edge_tts.Communicate` ESCAPES its input -- it is not an SSML endpoint. Handing
    it `<speak>...</speak>` makes the voice read the markup aloud: measured against
    the live endpoint, one sentence went from 3.94s to 23.76s of "speak version
    equals one point zero xmlns equals http colon...". Pronunciation must ride the
    same plain-text respelling the local providers use."""

    def test_no_markup_reaches_the_endpoint(self):
        _FakeCommunicate.events = []
        _FakeCommunicate.last_text = ""
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "vo.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "edge"}, clear=False),
                patch.dict("sys.modules", {"edge_tts": _edge_module()}),
            ):
                tts._edge_synth("Topuria defends the title.", out, "tapin")
        sent = _FakeCommunicate.last_text
        self.assertNotIn("<", sent, sent)
        self.assertNotIn("xmlns", sent, sent)

    def test_the_lexicon_still_changes_what_is_spoken(self):
        _FakeCommunicate.events = []
        _FakeCommunicate.last_text = ""
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "vo.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "edge"}, clear=False),
                patch.dict("sys.modules", {"edge_tts": _edge_module()}),
            ):
                tts._edge_synth("Topuria defends the title.", out, "tapin")
        sent = _FakeCommunicate.last_text
        self.assertIn("toh-POO-ree-ah", sent)
        self.assertNotIn("Topuria", sent)


class TestEdgeProviderNotLocal(_EdgeCase):
    def test_edge_is_not_a_local_provider(self):
        with patch.dict(os.environ, {"TTS_PROVIDER": "edge"}, clear=False):
            self.assertFalse(tts.is_local_tts_provider())


class TestEdgeSynth(_EdgeCase):
    def setUp(self):
        _FakeCommunicate.last_text = ""
        _FakeCommunicate.last_voice = ""
        _FakeCommunicate.fail = False
        _FakeCommunicate.events = [
            {"type": "audio", "data": b"ID3fake-mp3"},
            _boundary("hello", 0, 5_000_000),
            _boundary("world", 5_000_000, 4_000_000),
        ]

    def test_writes_mp3_and_word_sidecar_without_saying_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "edge", "EDGE_VOICE": "en-US-JennyNeural"}),
                patch.dict("sys.modules", {"edge_tts": _edge_module()}),
            ):
                with patch("builtins.print") as printed:
                    result = tts._try_alt_tts_provider("hello world", mp3, "tapin")
            self.assertEqual(result, mp3)
            self.assertTrue(os.path.isfile(mp3))
            self.assertGreater(os.path.getsize(mp3), 0)
            sidecar = Path(mp3 + ".words.json")
            self.assertTrue(sidecar.is_file())
            words = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(words[0]["word"], "hello")
            self.assertAlmostEqual(words[0]["start"], 0.0)
            self.assertAlmostEqual(words[0]["end"], 0.5)
            self.assertEqual(words[1]["word"], "world")
            self.assertAlmostEqual(words[1]["start"], 0.5)
            self.assertAlmostEqual(words[1]["end"], 0.9)
            blob = " ".join(str(c.args[0]) for c in printed.call_args_list if c.args)
            self.assertIn("cloud, $0", blob)
            self.assertNotIn("(local, $0)", blob)

    def test_stream_failure_returns_none_after_calling_communicate(self):
        _FakeCommunicate.fail = True
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "edge"}),
                patch.dict("sys.modules", {"edge_tts": _edge_module()}),
            ):
                result = tts._try_alt_tts_provider("hello", mp3, "tapin")
        self.assertIsNone(result)
        self.assertEqual(_FakeCommunicate.last_text, "hello")
        self.assertFalse(os.path.isfile(mp3))

    def test_lexicon_respells_the_spoken_copy_and_does_not_mutate_script(self):
        script = "Salkilld wins."
        _FakeCommunicate.events = [{"type": "audio", "data": b"x"}]
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "edge"}),
                patch.dict("sys.modules", {"edge_tts": _edge_module()}),
                patch.object(tts, "_lexicon_for_channel", return_value={"Salkilld": "Sal-killed"}),
                patch.object(
                    tts,
                    "ElevenLabs",
                    side_effect=AssertionError("ElevenLabs must not run for edge"),
                ),
            ):
                tts.generate_audio(script, mp3, channel_id="tapin")
        self.assertEqual(script, "Salkilld wins.")
        sent = _FakeCommunicate.last_text
        # Respelled for the voice, never marked up: Communicate escapes its input,
        # so any tag here would be read aloud verbatim.
        self.assertEqual(sent, "Sal-killed wins.")
        self.assertNotIn("<", sent)

    def test_unmodified_edge_tts_is_declared_in_the_free_extra(self):
        # LGPL-3.0: installed dependency, never vendored. The pin lives in [free].
        from config.paths import ROOT_DIR

        text = Path(ROOT_DIR, "pyproject.toml").read_text(encoding="utf-8")
        start = text.index("free = [")
        end = text.index("]", start)
        block = text[start:end]
        self.assertIn("edge-tts", block)


class TestEdgeVoiceMix(_EdgeCase):
    def test_edge_is_its_own_family_not_local(self):
        from core.voice_consistency import voice_mix_warning

        with patch.dict(
            os.environ,
            {"TTS_PROVIDER": "edge", "INTRO_TTS_PROVIDER": "piper"},
            clear=False,
        ):
            msg = voice_mix_warning()
        self.assertIsNotNone(msg)
        self.assertIn("edge", msg)
        self.assertIn("local", msg)
