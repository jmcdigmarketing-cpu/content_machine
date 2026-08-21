"""ops doctor — nested optional imports, no extra HTTP."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core.ops_doctor import gather, render


def _stack() -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("core.run_mode._ollama_ready", return_value=(False, None)))
    stack.enter_context(
        patch(
            "core.run_mode.free_backend_readiness",
            return_value=SimpleNamespace(tts_provider=None, youtube_free=True),
        )
    )
    stack.enter_context(patch("core.feed_health.cached_warnings", return_value=["feed stale"]))
    stack.enter_context(
        patch("youtube.oauth.token_path_for_channel", return_value="Z:/no-token.json")
    )
    stack.enter_context(patch("youtube.oauth.token_has_scope", return_value=False))
    stack.enter_context(patch("os.path.isfile", return_value=False))
    stack.enter_context(
        patch("apis.youtube_quota.get_usage_summary", return_value={"remaining": 10000})
    )
    stack.enter_context(patch("apis.youtube_quota.format_uploads_left", return_value="~6 uploads"))
    stack.enter_context(patch("core.cuda_probe.probe", return_value={"torch_version": None}))
    stack.enter_context(
        patch("core.cuda_probe.render", return_value="CUDA\n  torch : not installed")
    )
    stack.enter_context(
        patch(
            "core.ram_preflight.snapshot",
            return_value={"ram_gb": 16.0, "vram_gb": 12.0, "ram_min_gb": None, "vram_min_gb": None},
        )
    )
    stack.enter_context(patch("core.ram_preflight.render", return_value="RAM 16.00 GB free"))
    stack.enter_context(
        patch(
            "core.secrets_doctor.gather",
            return_value={"present": 2, "missing": 1, "placeholder": 0},
        )
    )
    stack.enter_context(
        patch("core.workspace_hazards.gather", return_value={"hazards": [], "onedrive": False})
    )
    stack.enter_context(patch("core.workspace_hazards.render", return_value="workspace: ok"))
    return stack


class TestOpsDoctor(unittest.TestCase):
    def test_gather_lists_checks(self):
        with _stack():
            data = gather("tapin")
        names = {c["name"] for c in data["checks"]}
        self.assertIn("oauth", names)
        self.assertIn("feeds", names)
        self.assertIn("cuda", names)
        self.assertIn("nvenc", names)
        self.assertIn("ram", names)
        self.assertIn("secrets", names)
        self.assertIn("workspace", names)
        blob = render(data, channel_id="tapin")
        self.assertIn("ops doctor", blob)

    def test_cuda_import_failure_does_not_wipe_other_checks(self):
        with _stack():
            with patch("core.cuda_probe.probe", side_effect=RuntimeError("cuda")):
                data = gather("tapin")
        names = {c["name"] for c in data["checks"]}
        self.assertIn("oauth", names)
        cuda = next(c for c in data["checks"] if c["name"] == "cuda")
        self.assertTrue(cuda["ok"])
        self.assertIn("RuntimeError", cuda["detail"])


if __name__ == "__main__":
    unittest.main()
