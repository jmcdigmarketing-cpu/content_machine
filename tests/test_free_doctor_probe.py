"""_ollama_server_probe — free-doctor's "is Ollama up (even before a model is chosen)?"

Fail-open network probe: a reachable server reports its model count; anything else
(non-200, connection refused, bad JSON) reads as down. Lets free-doctor distinguish
"Ollama running, just pick a model" from "no free LLM installed".
"""

import unittest
from unittest.mock import MagicMock, patch

from scripts.ops import _ollama_server_probe


class TestOllamaServerProbe(unittest.TestCase):
    def test_up_with_models_strips_v1(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"name": "llama3.1:8b"}, {"name": "qwen2.5"}]}
        with patch("requests.get", return_value=resp) as g:
            self.assertEqual(_ollama_server_probe(), (True, 2))
        url = g.call_args.args[0]
        self.assertTrue(url.endswith("/api/tags"))
        self.assertNotIn("/v1", url)  # the OpenAI-compat /v1 suffix is stripped

    def test_up_no_models(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": []}
        with patch("requests.get", return_value=resp):
            self.assertEqual(_ollama_server_probe(), (True, 0))

    def test_non_200_is_down(self):
        with patch("requests.get", return_value=MagicMock(status_code=500)):
            self.assertEqual(_ollama_server_probe(), (False, 0))

    def test_unreachable_is_down(self):
        with patch("requests.get", side_effect=OSError("connection refused")):
            self.assertEqual(_ollama_server_probe(), (False, 0))


if __name__ == "__main__":
    unittest.main()
