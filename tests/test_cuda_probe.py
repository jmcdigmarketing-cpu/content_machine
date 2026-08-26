"""CUDA probe — no install, no download, nested import failure is fine."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.cuda_probe import probe, render


class TestCudaProbe(unittest.TestCase):
    def test_probe_keys_without_raising(self):
        data = probe()
        for key in (
            "torch_version",
            "cuda_available",
            "nvidia_smi",
            "gpu_hour_usd",
            "nvenc_capable",
        ):
            self.assertIn(key, data)
        self.assertIsInstance(data["cuda_available"], bool)
        self.assertIsInstance(data["nvenc_capable"], bool)
        blob = render(data)
        self.assertIn("CUDA", blob)
        self.assertIn("nvenc", blob.lower())
        self.assertNotIn("pip install", blob.lower())

    def test_missing_torch_is_nested_fail_open(self):
        import builtins

        real_import = builtins.__import__

        def boom(name, *args, **kwargs):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("no torch")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=boom):
            data = probe()
        self.assertFalse(data["cuda_available"])
        self.assertEqual(data.get("torch_error"), "ImportError")


if __name__ == "__main__":
    unittest.main()
