"""_ollama_server_probe — free-doctor's "is Ollama up (even before a model is chosen)?"

Delegates to llm_router.ollama_probe (single /api/tags helper). Reachable-and-empty
is distinct from unreachable so free-doctor can say "pull" rather than "serve".
"""

import unittest
from unittest.mock import MagicMock, patch

from core import llm_router
from scripts.ops import _ollama_server_probe


class TestOllamaServerProbe(unittest.TestCase):
    def setUp(self):
        llm_router._ollama_probe_cache = None

    def tearDown(self):
        llm_router._ollama_probe_cache = None

    def test_up_with_models_strips_v1(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"name": "llama3.1:8b"}, {"name": "qwen2.5"}]}
        with patch.object(llm_router.requests, "get", return_value=resp) as g:
            self.assertEqual(_ollama_server_probe(), (True, 2))
        url = g.call_args.args[0]
        self.assertTrue(url.endswith("/api/tags"))
        self.assertNotIn("/v1", url)  # the OpenAI-compat /v1 suffix is stripped

    def test_up_no_models(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": []}
        with patch.object(llm_router.requests, "get", return_value=resp):
            self.assertEqual(_ollama_server_probe(), (True, 0))

    def test_non_200_is_down(self):
        with patch.object(llm_router.requests, "get", return_value=MagicMock(status_code=500)):
            self.assertEqual(_ollama_server_probe(), (False, 0))

    def test_unreachable_is_down(self):
        with patch.object(llm_router.requests, "get", side_effect=OSError("connection refused")):
            self.assertEqual(_ollama_server_probe(), (False, 0))


if __name__ == "__main__":
    unittest.main()
