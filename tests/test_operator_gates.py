"""Trace redaction + unlisted-before-public + intelligence SKU."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core import run_trace
from core.intelligence_report import IntelligenceReport, sku_authenticity_notes, to_sku_markdown
from publishing.youtube_publisher import apply_unlisted_review, build_video_status
from youtube.upload import UploadRequest


class TestTraceRedact(unittest.TestCase):
    def test_strips_api_bodies_keeps_tokens(self):
        blob = {
            "provider": "openrouter",
            "input_tokens": 12,
            "body": {"choices": [{"text": "secret payload"}]},
            "messages": [{"role": "user", "content": "do not store"}],
        }
        out = run_trace.redact_trace_value(blob)
        self.assertEqual(out["input_tokens"], 12)
        self.assertEqual(out["body"], "[redacted]")
        self.assertEqual(out["messages"], "[redacted]")

    def test_write_run_trace_redacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(run_trace, "TRACES_DIR", tmp),
                patch.object(
                    run_trace,
                    "_llm_calls",
                    return_value=([{"provider": "x", "body": "402 html"}], 0.0),
                ),
            ):
                path = run_trace.write_run_trace(
                    run_id=99,
                    channel_id="tapin",
                    input_topic="t",
                    selected_topic="t",
                    status="drafted",
                    quality={"prompt": "system leak"},
                )
                self.assertIsNotNone(path)
                with open(path, encoding="utf-8") as fh:
                    data = json.loads(fh.read())
        self.assertEqual(data["llm_calls"][0]["body"], "[redacted]")
        self.assertEqual(data["quality"]["prompt"], "[redacted]")


class TestUnlistedReview(unittest.TestCase):
    def test_public_becomes_unlisted_when_immediate(self):
        with patch.dict(os.environ, {"YOUTUBE_UNLISTED_REVIEW": "true"}):
            privacy, held = apply_unlisted_review("public")
        self.assertEqual(privacy, "unlisted")
        self.assertTrue(held)

    def test_scheduled_public_is_untouched_by_hold(self):
        from datetime import datetime, timedelta, timezone

        future = datetime.now(timezone.utc) + timedelta(hours=24)
        with patch.dict(os.environ, {"YOUTUBE_UNLISTED_REVIEW": "true"}):
            privacy, held = apply_unlisted_review("public", publish_at=future)
            status = build_video_status(
                UploadRequest(
                    file_path="x.mp4",
                    title="T",
                    description="D",
                    privacy_status="public",
                    publish_at=future,
                )
            )
        self.assertFalse(held)
        self.assertEqual(privacy, "public")
        self.assertEqual(status["privacyStatus"], "private")

    def test_env_off_keeps_public(self):
        with patch.dict(os.environ, {"YOUTUBE_UNLISTED_REVIEW": "false"}):
            privacy, held = apply_unlisted_review("public")
        self.assertEqual(privacy, "public")
        self.assertFalse(held)


class TestIntelligenceSku(unittest.TestCase):
    def test_sku_markdown_has_authenticity_and_no_tts(self):
        report = IntelligenceReport(
            generated_at="2026-08-21T12:00:00+00:00",
            channel_id="tapin",
            channel_name="TapIn",
            input_topic="UFC 250",
            selected_variant="Topuria preview",
            composite_score=70.0,
            domain="ufc",
            corroboration={"confidence": 0.2, "source_count": 1, "label": "thin"},
        )
        report.authenticity_notes = sku_authenticity_notes(report)
        md = to_sku_markdown(report)
        self.assertIn("Intelligence-report SKU", md)
        self.assertIn("No TTS", md)
        self.assertIn("Authenticity notes", md)
        self.assertIn("research-only", md)
        self.assertIn("Corroboration is thin", md)


if __name__ == "__main__":
    unittest.main()
