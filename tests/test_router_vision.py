"""Router vision path: image content-blocks, skip text-only providers, Free-mode block.

Thumbnail scoring used to require OPENAI_API_KEY and call core.llm_client (deleted).
No network: complete / openai client mocked (tests/CLAUDE.md).
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from core import llm_router
from core.llm_router import LLMUnavailableError
from tests.optional_deps import requires_pillow


def _image_messages() -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "score this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }
    ]


class TestRouterVision(unittest.TestCase):
    def test_image_payload_reaches_openai_compat_client(self):
        with (
            patch.dict(os.environ, {"FREE_MODE_STRICT": ""}, clear=False),
            patch.object(
                llm_router,
                "_resolve_chain",
                return_value=[("anthropic", "claude"), ("openai", "gpt-4o")],
            ),
            patch.object(llm_router, "_model_is_dead", return_value=False),
            patch.object(llm_router, "_over_llm_budget", return_value=False),
            patch.object(llm_router, "_anthropic_complete") as anth,
            patch.object(
                llm_router, "_openai_complete", return_value=('{"overall": 70}', 10, 4)
            ) as oai,
            patch.object(llm_router, "_record_usage"),
            patch.object(llm_router, "_llm_daily_budget", return_value=None),
        ):
            text = llm_router.complete(_image_messages(), tier="extract")
        self.assertIn("overall", text)
        anth.assert_not_called()
        oai.assert_called_once()
        sent = oai.call_args[0][2]
        content = sent[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[1]["type"], "image_url")

    def test_pinned_anthropic_does_not_flatten_the_image(self):
        with (
            patch.dict(os.environ, {"FREE_MODE_STRICT": ""}, clear=False),
            self.assertRaises(LLMUnavailableError) as ctx,
        ):
            llm_router.complete(_image_messages(), provider="anthropic", model="claude")
        self.assertIn("cannot take image", str(ctx.exception))

    def test_free_mode_blocks_vision(self):
        with (
            patch.dict(os.environ, {"FREE_MODE_STRICT": "1"}, clear=False),
            self.assertRaises(LLMUnavailableError) as ctx,
        ):
            llm_router.complete(_image_messages(), tier="extract")
        self.assertIn("Free mode", str(ctx.exception))


class TestThumbnailVisionViaRouter(unittest.TestCase):
    def _jpeg(self) -> str:
        from PIL import Image  # callers carry @requires_pillow (tests/optional_deps.py)

        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        Image.new("RGB", (1080, 1920), color=(20, 20, 180)).save(path, "JPEG")
        return path

    @requires_pillow
    def test_no_openai_key_still_scores_via_router(self):
        from assets.thumbnail_scorer import score_thumbnail

        path = self._jpeg()
        payload = (
            '{"curiosity": 80, "clarity": 70, "contrast": 60, '
            '"emotion": 50, "overall": 66, "suggestions": ["tighter crop"]}'
        )
        try:
            with (
                patch.dict(
                    os.environ,
                    {
                        "THUMBNAIL_SCORER_ENABLED": "true",
                        "OPENAI_API_KEY": "",
                        "FREE_MODE_STRICT": "",
                    },
                    clear=False,
                ),
                patch("core.llm_router.complete", return_value=payload) as complete,
            ):
                result = score_thumbnail(path, "GTA 6 leaks", channel_id="tapin", persist=False)
            self.assertIsNotNone(result)
            self.assertEqual(result.source, "llm")
            self.assertEqual(result.overall, 66)
            complete.assert_called_once()
            msgs = complete.call_args[0][0]
            self.assertEqual(msgs[0]["content"][1]["type"], "image_url")
        finally:
            os.unlink(path)

    @requires_pillow
    def test_free_mode_falls_back_to_heuristic_without_calling_complete(self):
        from assets.thumbnail_scorer import score_thumbnail

        path = self._jpeg()
        try:
            with (
                patch.dict(
                    os.environ,
                    {"THUMBNAIL_SCORER_ENABLED": "true", "FREE_MODE_STRICT": "1"},
                    clear=False,
                ),
                patch("core.llm_router.complete") as complete,
            ):
                result = score_thumbnail(path, "GTA 6 leaks", channel_id="tapin", persist=False)
            complete.assert_not_called()
            self.assertIsNotNone(result)
            self.assertEqual(result.source, "heuristic")
        finally:
            os.unlink(path)

    @requires_pillow
    def test_router_failure_falls_back_to_heuristic(self):
        from assets.thumbnail_scorer import score_thumbnail

        path = self._jpeg()
        try:
            with (
                patch.dict(
                    os.environ,
                    {"THUMBNAIL_SCORER_ENABLED": "true", "FREE_MODE_STRICT": ""},
                    clear=False,
                ),
                patch(
                    "core.llm_router.complete",
                    side_effect=LLMUnavailableError("no vision-capable LLM provider"),
                ),
            ):
                result = score_thumbnail(path, "GTA 6 leaks", channel_id="tapin", persist=False)
            self.assertIsNotNone(result)
            self.assertEqual(result.source, "heuristic")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
