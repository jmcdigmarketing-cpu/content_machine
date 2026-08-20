"""Defects from live runs 69-70, each reproduced before fixing.

Run 69 (GTA 6 leaks, Standard) rendered and published fine. Run 70 (Cejudo, Free)
**died after 71 seconds of discovery** because Free mode had just told the operator
`llm=ollama OK (local $0)`.

Both are the decisions §18 shape again: something reported healthy while being broken.

No network: every probe is mocked (tests/CLAUDE.md).
"""

import argparse
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core import run_mode

_OLLAMA_ENV = {"OLLAMA_MODEL": "llama3.1:8b"}


class TestFreeModeOllamaReadiness(unittest.TestCase):
    """Run 70: `Free ready: llm=ollama OK (local $0)` -> 404 model not found -> run dead.

    `_ollama_ready` pinged `/api/tags` and returned `status_code == 200`, i.e. "the
    daemon answered". It never checked that the configured model was among the tags.
    The router already had this right (`llm_router._provider_available`), so the bug was
    a *second*, weaker copy of the same probe.
    """

    def test_daemon_up_but_nothing_pulled_is_not_ready(self):
        with (
            patch.dict(os.environ, _OLLAMA_ENV, clear=True),
            patch("core.llm_router.ollama_installed_models", return_value=[]),
        ):
            ready, model = run_mode._ollama_ready()
        self.assertFalse(ready, "an empty Ollama must not report ready")
        self.assertEqual(model, "llama3.1:8b")

    def test_free_mode_does_not_advertise_an_empty_ollama(self):
        # The operator-facing line is what made run 70 waste a full discovery.
        with (
            patch.dict(os.environ, _OLLAMA_ENV, clear=True),
            patch("core.llm_router.ollama_installed_models", return_value=[]),
        ):
            provider, _model, note = run_mode._free_llm()
        self.assertIsNone(provider, "no free LLM should be claimed")
        self.assertTrue(note, "the operator needs to be told why")
        self.assertIn("pull", note.lower())

    def test_the_pulled_model_is_ready(self):
        with (
            patch.dict(os.environ, _OLLAMA_ENV, clear=True),
            patch("core.llm_router.ollama_installed_models", return_value=["llama3.1:8b"]),
        ):
            self.assertEqual(run_mode._ollama_ready(), (True, "llama3.1:8b"))

    def test_bare_name_matches_a_tagged_install(self):
        # Same rule the router uses: OLLAMA_MODEL=llama3.1 matches an installed llama3.1:8b.
        with (
            patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.1"}, clear=True),
            patch("core.llm_router.ollama_installed_models", return_value=["llama3.1:8b"]),
        ):
            ready, _ = run_mode._ollama_ready()
        self.assertTrue(ready)

    def test_a_different_model_is_not_a_match(self):
        with (
            patch.dict(os.environ, _OLLAMA_ENV, clear=True),
            patch("core.llm_router.ollama_installed_models", return_value=["qwen2.5:7b"]),
        ):
            ready, _ = run_mode._ollama_ready()
        self.assertFalse(ready)

    def test_no_model_configured_never_probes(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("core.llm_router.ollama_installed_models") as probe,
        ):
            self.assertEqual(run_mode._ollama_ready(), (False, ""))
            probe.assert_not_called()

    def test_readiness_and_apply_agree(self):
        """The line the operator reads and the env that gets applied must not disagree."""
        with (
            patch.dict(os.environ, _OLLAMA_ENV, clear=True),
            patch("core.llm_router.ollama_installed_models", return_value=[]),
            patch.object(run_mode, "_local_tts_available", return_value="piper"),
            patch("apis.free_backends.reddit_available", return_value=False),
            patch("apis.free_backends.youtube_available", return_value=False),
        ):
            readiness = run_mode.free_backend_readiness()
            self.assertFalse(readiness.llm_ok)
            self.assertNotIn("ollama OK", run_mode.format_readiness_line(readiness))

            result = run_mode.apply_cost_mode(run_mode.COST_MODE_FREE, readiness=readiness)
        self.assertFalse(result.can_render, "must block rather than route to a dead model")
        self.assertTrue(any(b.startswith("llm:") for b in result.blockers))


class TestFreeDoctorOllamaDiagnosis(unittest.TestCase):
    """After the run-70 probe fix, free-doctor must not call an empty Ollama 'unreachable'."""

    def _run(self, env: dict[str, str], *, probe: tuple[bool, int]) -> str:
        from scripts import ops

        buf = io.StringIO()
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                run_mode, "_ollama_ready", return_value=(False, env.get("OLLAMA_MODEL", ""))
            ),
            patch.object(run_mode, "_local_tts_available", return_value=None),
            patch("apis.free_backends.reddit_available", return_value=False),
            patch("apis.free_backends.youtube_available", return_value=False),
            patch.object(ops, "_ollama_server_probe", return_value=probe),
            redirect_stdout(buf),
        ):
            ops.cmd_free_doctor(argparse.Namespace())
        return buf.getvalue()

    def test_daemon_up_empty_says_pull_not_serve(self):
        text = self._run(_OLLAMA_ENV, probe=(True, 0))
        self.assertIn("pull", text.lower())
        self.assertNotIn("unreachable", text.lower())
        self.assertNotIn("ollama serve", text.lower())

    def test_daemon_down_says_unreachable(self):
        text = self._run(_OLLAMA_ENV, probe=(False, 0))
        self.assertIn("unreachable", text.lower())
        self.assertIn("ollama serve", text.lower())

    def test_openrouter_fallback_named_when_ollama_unusable(self):
        env = {**_OLLAMA_ENV, "OPENROUTER_API_KEY": "sk-or-x"}
        text = self._run(env, probe=(True, 0))
        self.assertIn("openrouter", text.lower())
        self.assertIn("pull", text.lower())


if __name__ == "__main__":
    unittest.main()
