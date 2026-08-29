"""ops doctor — nested optional imports, no extra HTTP."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core.ops_doctor import gather, render


def _stack(*, mock_secrets: bool = True) -> ExitStack:
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
    if mock_secrets:
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
        self.assertIn("paid_calls", names)
        blob = render(data, channel_id="tapin")
        self.assertIn("ops doctor", blob)

    def test_paid_calls_off_without_strict_fails_the_doctor_check(self):
        with _stack():
            with patch.dict(
                "os.environ", {"PAID_CALLS": "off", "FREE_MODE_STRICT": ""}, clear=False
            ):
                data = gather("tapin")
        paid = next(c for c in data["checks"] if c["name"] == "paid_calls")
        self.assertFalse(paid["ok"])
        self.assertIn("PAID_CALLS=off", paid["detail"])

    def test_paid_calls_off_with_strict_passes(self):
        with _stack():
            with patch.dict(
                "os.environ",
                {"PAID_CALLS": "off", "FREE_MODE_STRICT": "1"},
                clear=False,
            ):
                data = gather("tapin")
        paid = next(c for c in data["checks"] if c["name"] == "paid_calls")
        self.assertTrue(paid["ok"])

    def test_cuda_import_failure_does_not_wipe_other_checks(self):
        with _stack():
            with patch("core.cuda_probe.probe", side_effect=RuntimeError("cuda")):
                data = gather("tapin")
        names = {c["name"] for c in data["checks"]}
        self.assertIn("oauth", names)
        cuda = next(c for c in data["checks"] if c["name"] == "cuda")
        self.assertTrue(cuda["ok"])
        self.assertIn("RuntimeError", cuda["detail"])

    def test_cuda_fails_when_nvidia_smi_but_cpu_torch(self):
        """GPU in the box + 2.8.0+cpu is the green-and-inert hole, not a PASS."""
        with _stack():
            with patch(
                "core.cuda_probe.probe",
                return_value={
                    "torch_version": "2.8.0+cpu",
                    "cuda_available": False,
                    "cuda_built": False,
                    "nvidia_smi": True,
                    "nvenc_capable": True,
                },
            ):
                data = gather("tapin")
        cuda = next(c for c in data["checks"] if c["name"] == "cuda")
        self.assertFalse(cuda["ok"])
        self.assertIn("cpu", cuda["detail"].lower())
        nvenc = next(c for c in data["checks"] if c["name"] == "nvenc")
        self.assertTrue(nvenc["ok"])

    def test_cuda_does_not_fail_laptops_without_a_gpu(self):
        with _stack():
            with patch(
                "core.cuda_probe.probe",
                return_value={
                    "torch_version": "2.8.0+cpu",
                    "cuda_available": False,
                    "nvidia_smi": False,
                    "nvenc_capable": False,
                },
            ):
                data = gather("tapin")
        cuda = next(c for c in data["checks"] if c["name"] == "cuda")
        self.assertTrue(cuda["ok"])

    def test_cuda_passes_when_torch_sees_cuda(self):
        with _stack():
            with patch(
                "core.cuda_probe.probe",
                return_value={
                    "torch_version": "2.8.0+cu124",
                    "cuda_available": True,
                    "nvidia_smi": True,
                    "nvenc_capable": True,
                },
            ):
                data = gather("tapin")
        cuda = next(c for c in data["checks"] if c["name"] == "cuda")
        self.assertTrue(cuda["ok"])


_REQUIRED_KEYS = (
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
    "ELEVEN_API_KEY",
    "APIFY_CONTENT_MACHINE_KEY",
    "YOUTUBE_API_KEY",
)
_OPTIONAL_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "NEWS_API_KEY",
)
_DUMMY = "sk-test-not-a-real-secret"


def _secrets_env(*, blank_required: str | None = None) -> dict[str, str]:
    env = {name: _DUMMY for name in _REQUIRED_KEYS}
    env.update({name: "" for name in _OPTIONAL_KEYS})
    if blank_required:
        env[blank_required] = ""
    return env


class TestDoctorSecretsRequiredVsOptional(unittest.TestCase):
    """Never mock secrets_doctor.gather — that is the call doctor depends on."""

    def test_optional_keys_blank_do_not_fail_doctor(self):
        with _stack(mock_secrets=False):
            with patch.dict("os.environ", _secrets_env(), clear=False):
                data = gather("tapin")
        secrets = next(c for c in data["checks"] if c["name"] == "secrets")
        self.assertTrue(secrets["ok"], secrets["detail"])
        self.assertIn("missing", secrets["detail"])

    def test_required_key_blank_fails_doctor(self):
        with _stack(mock_secrets=False):
            with patch.dict(
                "os.environ", _secrets_env(blank_required="DEEPSEEK_API_KEY"), clear=False
            ):
                data = gather("tapin")
        secrets = next(c for c in data["checks"] if c["name"] == "secrets")
        self.assertFalse(secrets["ok"], secrets["detail"])


if __name__ == "__main__":
    unittest.main()
