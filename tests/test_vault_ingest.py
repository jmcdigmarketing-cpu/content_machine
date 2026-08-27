"""Multi-source vault importer (core/vault_ingest) — PDF / YouTube / URL ingest + ops wiring.

Heavy backends (pypdf, youtube-transcript-api) are lazy and optional; these tests inject
fakes via sys.modules and mock the extractors, so nothing installs or hits the network.
"""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from core import vault_ingest as vi


def _fake_pypdf(pages_text: list[str]) -> dict:
    class _Page:
        def __init__(self, t):
            self._t = t

        def extract_text(self):
            return self._t

    class PdfReader:
        def __init__(self, path):
            self.pages = [_Page(t) for t in pages_text]

    mod = types.ModuleType("pypdf")
    mod.PdfReader = PdfReader
    return {"pypdf": mod}


def _fake_transcript_api(snippets: list[str]) -> dict:
    class YouTubeTranscriptApi:
        @staticmethod
        def get_transcript(vid):
            return [{"text": s} for s in snippets]

    mod = types.ModuleType("youtube_transcript_api")
    mod.YouTubeTranscriptApi = YouTubeTranscriptApi
    return {"youtube_transcript_api": mod}


class TestIngestPdf(unittest.TestCase):
    def test_extracts_text_with_pypdf(self):
        with mock.patch.dict(sys.modules, _fake_pypdf(["Page one facts.", "Page two facts."])):
            rec = vi.ingest_pdf("doc.pdf")
        self.assertEqual(rec["kind"], "pdf")
        self.assertEqual(rec["confidence"], "high")
        self.assertIn("Page one facts.", rec["text"])
        self.assertIn("Page two facts.", rec["text"])

    def test_real_pdf_fixture_extracts_text(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "ingest_sample.pdf"
        rec = vi.ingest_pdf(str(fixture))
        try:
            import pypdf
        except ImportError:
            self.assertEqual(rec["text"], "")
            self.assertEqual(rec["confidence"], "low")
            return
        self.assertEqual(rec["kind"], "pdf")
        self.assertIn("Take-Two", rec["text"])
        self.assertEqual(rec["confidence"], "high")

    def test_missing_pypdf_fails_open(self):
        # No pypdf in sys.modules and not installed → empty record, never raises.
        with mock.patch.dict(sys.modules, {"pypdf": None}):
            rec = vi.ingest_pdf("doc.pdf")
        self.assertEqual(rec["text"], "")
        self.assertEqual(rec["confidence"], "low")


class TestIngestYouTube(unittest.TestCase):
    def test_uses_transcript_when_available(self):
        fake = _fake_transcript_api(["hello world", "second line"])
        with (
            mock.patch.dict(sys.modules, fake),
            mock.patch("apis.youtube_api.extract_youtube_video_id", return_value="vid123"),
        ):
            rec = vi.ingest_youtube_transcript("https://youtu.be/vid123")
        self.assertEqual(rec["kind"], "youtube")
        self.assertEqual(rec["confidence"], "high")
        self.assertIn("hello world", rec["text"])

    def test_falls_back_to_link_extractor_without_transcript(self):
        with (
            mock.patch("apis.youtube_api.extract_youtube_video_id", return_value=None),
            mock.patch("core.link_facts.extract_facts_from_url", return_value=["Title line"]),
        ):
            rec = vi.ingest_youtube_transcript("https://youtu.be/x")
        self.assertIn("Title line", rec["text"])


class TestIngestDispatch(unittest.TestCase):
    def test_routes_by_kind(self):
        with (
            mock.patch.object(vi, "ingest_pdf", return_value={"kind": "pdf"}) as p,
            mock.patch.object(
                vi, "ingest_youtube_transcript", return_value={"kind": "youtube"}
            ) as y,
            mock.patch.object(vi, "ingest_url", return_value={"kind": "url"}) as u,
        ):
            self.assertEqual(vi.ingest("C:/tmp/report.pdf")["kind"], "pdf")
            self.assertEqual(vi.ingest("https://www.youtube.com/watch?v=abc")["kind"], "youtube")
            self.assertEqual(vi.ingest("https://www.bbc.com/news")["kind"], "url")
        p.assert_called_once()
        y.assert_called_once()
        u.assert_called_once()

    def test_empty_source_is_safe(self):
        self.assertEqual(vi.ingest("")["kind"], "unknown")


class TestSaveToVault(unittest.TestCase):
    def test_writes_provenance_note(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False):
                rec = vi._record("Palworld 1.0 shipped.", "https://x/news", kind="url")
                path = vi.save_to_vault(rec, "tapin")
            self.assertIsNotNone(path)
            body = Path(path).read_text(encoding="utf-8")
            self.assertIn("tier: link", body)
            self.assertIn("source: https://x/news", body)
            self.assertIn("Palworld 1.0 shipped.", body)

    def test_unset_vault_returns_none(self):
        with mock.patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            self.assertIsNone(vi.save_to_vault(vi._record("t", "u", kind="url"), "tapin"))


class TestOpsIngestCommand(unittest.TestCase):
    def test_ops_ingest_saves_note(self):
        from scripts.ops import main

        with tempfile.TemporaryDirectory() as d:
            with (
                mock.patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": d}, clear=False),
                mock.patch(
                    "core.vault_ingest.ingest",
                    return_value=vi._record("A verified fact line.", "https://x", kind="url"),
                ),
            ):
                rc = main(["ingest", "https://x", "--channel", "tapin"])
            self.assertEqual(rc, 0)
            notes = list(Path(d, "tapin", "_ingest").glob("*.md"))
            self.assertEqual(len(notes), 1)

    def test_ops_ingest_without_source_returns_usage(self):
        from scripts.ops import main

        self.assertEqual(main(["ingest"]), 2)


if __name__ == "__main__":
    unittest.main()
