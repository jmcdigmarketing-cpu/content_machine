"""Stage 0 ask() / emit() seams: scripted answers and a module-level print sink."""

from __future__ import annotations

import unittest

from core import ask
from core import emit as emit_mod


class TestAskScriptedBackend(unittest.TestCase):
    def tearDown(self):
        ask.reset_backend()

    def test_gate_prompts_keep_their_strings_and_yn_default(self):
        """Same prompt text the terminal shows today; empty Enter is No."""
        auth = "  Authenticity gate flagged this video. Render anyway? [y/N]: "
        ground = "  Grounding gate flagged unsupported claims. Render anyway? [y/N]: "
        thin = "  Thin facts — render anyway and pay TTS? [y/N]: "
        over = "  Over length for TTS — render anyway? [y/N]: "
        metrics = "  Start the next video anyway? [y/N]: "
        ask.set_backend(ask.ScriptedBackend(["y", "n", "", "yes", "N"]))
        seen: list[str] = []

        class Recording(ask.ScriptedBackend):
            def ask_text(self, prompt: str = "") -> str:
                seen.append(prompt)
                return super().ask_text(prompt)

        ask.set_backend(Recording(["y", "n", "", "yes", "N"]))
        self.assertTrue(ask.ask_confirm(auth, default=False))
        self.assertFalse(ask.ask_confirm(ground, default=False))
        self.assertFalse(ask.ask_confirm(thin, default=False))
        self.assertTrue(ask.ask_confirm(over, default=False))
        self.assertFalse(ask.ask_confirm(metrics, default=False))
        self.assertEqual(seen, [auth, ground, thin, over, metrics])


class TestEmitSink(unittest.TestCase):
    def tearDown(self):
        emit_mod.reset_emit()

    def test_set_emit_captures_a_real_display_helper(self):
        from core.ui import display_database_status

        lines: list[str] = []

        def sink(*args, **_kwargs):
            lines.append(" ".join(str(a) for a in args))

        emit_mod.set_emit(sink)
        display_database_status()
        self.assertTrue(any("Database:" in line for line in lines))
