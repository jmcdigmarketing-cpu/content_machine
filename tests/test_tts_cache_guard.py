"""#830: a test run never writes the real data/tts_cache.

`tests/__init__.py` pins TTS_CACHE=false, but it only loads under `-t .`; a bare
`python -m unittest discover -s tests` skips it, and a test that synthesised audio then
filled the operator's real cache. The guard now lives in the write path: under a
detected test runner, the store refuses the default directory. An explicit
TTS_CACHE_DIR - which every cache test sets - is still honoured.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from core import tts


class TtsCacheGuardTests(unittest.TestCase):
    def _src(self, tmp):
        src = os.path.join(tmp, "src.mp3")
        with open(src, "wb") as f:
            f.write(b"mp3")
        return src

    def test_default_dir_refused_under_a_test_runner(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data:
            env = {k: v for k, v in os.environ.items() if k != "TTS_CACHE_DIR"}
            env["TTS_CACHE"] = "true"
            with (
                patch.dict(os.environ, env, clear=True),
                patch("config.paths.DATA_DIR", data),
                patch.object(sys, "argv", ["python -m unittest", "discover"]),
            ):
                tts.tts_cache_store("k1", self._src(tmp))
            self.assertFalse(os.path.exists(os.path.join(data, "tts_cache", "k1.mp3")))

    def test_default_dir_written_outside_a_test_runner(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data:
            env = {k: v for k, v in os.environ.items() if k != "TTS_CACHE_DIR"}
            env["TTS_CACHE"] = "true"
            with (
                patch.dict(os.environ, env, clear=True),
                patch("config.paths.DATA_DIR", data),
                patch.object(sys, "argv", ["main.py"]),
                patch("core.tts._under_test_runner", return_value=False),
            ):
                tts.tts_cache_store("k2", self._src(tmp))
            self.assertTrue(os.path.exists(os.path.join(data, "tts_cache", "k2.mp3")))

    def test_explicit_dir_still_written_under_a_test_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "cache")
            with (
                patch.dict(os.environ, {"TTS_CACHE": "true", "TTS_CACHE_DIR": cache}),
                patch.object(sys, "argv", ["python -m unittest"]),
            ):
                tts.tts_cache_store("k3", self._src(tmp))
            self.assertTrue(os.path.exists(os.path.join(cache, "k3.mp3")))

    def test_runner_detection(self):
        with patch.object(sys, "argv", ["python -m unittest", "discover"]):
            self.assertTrue(tts._under_test_runner())
        with (
            patch.object(sys, "argv", ["main.py"]),
            patch.dict(sys.modules, {"pytest": object()}),
        ):
            self.assertTrue(tts._under_test_runner())


if __name__ == "__main__":
    unittest.main()
