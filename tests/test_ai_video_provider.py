"""AI video-gen provider (Pillar 6, U4) — registration, gating, and fail-open.

No network: ComfyUI HTTP + the workflow file are mocked. Off by default
(AI_VIDEO_PROVIDER unset) the provider must be inert and the manager chain
unchanged; when enabled but unreachable it must fail open to stock/local.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from assets.ai_video_provider import AIVideoProvider
from core import comfy_client as comfy
from core.providers import ProviderResult


class TestProviderGating(unittest.TestCase):
    def test_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(AIVideoProvider().is_configured())
            self.assertIsNone(AIVideoProvider().find_video("topic", "gaming"))

    def test_configured_when_env_set(self):
        with mock.patch.dict(os.environ, {"AI_VIDEO_PROVIDER": "comfyui"}, clear=True):
            self.assertTrue(AIVideoProvider().is_configured())

    def test_find_video_fails_open_when_unreachable(self):
        with mock.patch.dict(os.environ, {"AI_VIDEO_PROVIDER": "comfyui"}, clear=True):
            with mock.patch(
                "core.comfy_client.generate",
                return_value=ProviderResult.fail_open("comfyui", "unreachable"),
            ):
                self.assertIsNone(AIVideoProvider().find_video("topic", "gaming"))


class TestManagerRegistration(unittest.TestCase):
    def test_registered_in_providers(self):
        from assets import manager

        self.assertIn("ai_video", manager._PROVIDERS)

    def test_not_in_chain_when_off(self):
        from assets import manager

        with mock.patch.dict(os.environ, {}, clear=True):
            names = [p.name for p in manager._provider_chain("tapin")]
            self.assertNotIn("ai_video", names)

    def test_prepended_when_configured(self):
        from assets import manager

        with mock.patch.dict(os.environ, {"AI_VIDEO_PROVIDER": "comfyui"}, clear=True):
            names = [p.name for p in manager._provider_chain("tapin")]
            self.assertEqual(names[0], "ai_video")  # preferred, fails open to the rest


class TestComfyGenerate(unittest.TestCase):
    def test_fails_open_without_template(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = comfy.generate("a prompt")
            self.assertFalse(out.ok)

    def test_inject_prompt_replaces_placeholder(self):
        wf = {"3": {"inputs": {"text": "__PROMPT__"}}}
        injected = comfy._inject_prompt(wf, "a red fox")
        self.assertEqual(injected["3"]["inputs"]["text"], "a red fox")

    def test_inject_prompt_handles_quotes_and_backslashes(self):
        # A prompt with JSON-hostile characters must not raise or corrupt the graph.
        wf = {"3": {"inputs": {"text": "__PROMPT__"}}}
        nasty = r'a "quoted" C:\path and a \x escape'
        injected = comfy._inject_prompt(wf, nasty)
        self.assertEqual(injected["3"]["inputs"]["text"], nasty)

    def test_extract_output_file(self):
        outputs = {"9": {"images": [{"filename": "gen.mp4", "subfolder": "s", "type": "output"}]}}
        self.assertEqual(
            comfy._extract_output_file(outputs),
            {"filename": "gen.mp4", "subfolder": "s", "type": "output"},
        )
        self.assertIsNone(comfy._extract_output_file({"9": {}}))

    def test_generate_injects_and_returns_downloaded_path(self):
        template = {"3": {"inputs": {"text": "__PROMPT__"}}}
        outputs = {"9": {"images": [{"filename": "gen.mp4", "subfolder": "", "type": "output"}]}}
        with (
            mock.patch.dict(os.environ, {"COMFYUI_WORKFLOW": "wf.json"}, clear=True),
            mock.patch("os.path.isfile", return_value=True),
            mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(template))),
            mock.patch.object(
                comfy,
                "submit_workflow",
                return_value=ProviderResult.success("comfyui", "comfyui", data="pid"),
            ) as sub,
            mock.patch.object(
                comfy,
                "poll",
                return_value=ProviderResult.success("comfyui", "comfyui", data=outputs),
            ),
            mock.patch.object(comfy, "_download_output", return_value="output/ai_video/gen.mp4"),
        ):
            out = comfy.generate("a cat")
            passed = sub.call_args[0][0]
            self.assertEqual(passed["3"]["inputs"]["text"], "a cat")  # prompt injected
            self.assertTrue(out.ok)
            self.assertEqual(out.data, "output/ai_video/gen.mp4")  # local path, not outputs dict

    def test_generate_fails_open_when_download_fails(self):
        template = {"3": {"inputs": {"text": "__PROMPT__"}}}
        outputs = {"9": {"images": [{"filename": "gen.mp4"}]}}
        with (
            mock.patch.dict(os.environ, {"COMFYUI_WORKFLOW": "wf.json"}, clear=True),
            mock.patch("os.path.isfile", return_value=True),
            mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(template))),
            mock.patch.object(
                comfy,
                "submit_workflow",
                return_value=ProviderResult.success("comfyui", "comfyui", data="pid"),
            ),
            mock.patch.object(
                comfy,
                "poll",
                return_value=ProviderResult.success("comfyui", "comfyui", data=outputs),
            ),
            mock.patch.object(comfy, "_download_output", return_value=None),
        ):
            self.assertFalse(comfy.generate("a cat").ok)


if __name__ == "__main__":
    unittest.main()
