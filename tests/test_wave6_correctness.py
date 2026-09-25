"""#702 and #703 connected-path regressions.

The production defect in #702 was green because its tests invented a trace
shape that ``write_run_trace`` never emits. These cases start at the real
writer and keep every persisted store inside a temporary directory.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch


class TestRetractionTraceRoundTrip(unittest.TestCase):
    def test_production_feature_and_trace_writers_feed_the_retraction_reader(self):
        from core import run_trace
        from core.retraction_watch import pairs_from_trace
        from core.run_features import build_features

        urls = ["https://example.com/report", "https://ufc.example/results"]
        features = build_features(
            topic="UFC result",
            channel_id="tapin",
            content_package={
                "title": "UFC result",
                "script": "A result changed.",
                "source_urls": urls,
            },
        )

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_trace, "TRACES_DIR", tmp),
            patch.object(run_trace, "_llm_calls", return_value=([], 0.0)),
        ):
            written = run_trace.write_run_trace(
                run_id=702,
                channel_id="tapin",
                input_topic="UFC result",
                selected_topic="Why the result changed",
                status="drafted",
                features=features,
            )
            self.assertIsNotNone(written)
            trace = run_trace.read_trace(702)

        self.assertEqual(trace["source_urls"], urls)
        self.assertEqual(
            pairs_from_trace(trace),
            [(urls[0], "Why the result changed"), (urls[1], "Why the result changed")],
        )


def _published_correction_fixture():
    row = SimpleNamespace(
        content_run_id=71,
        youtube_video_id="yt-71",
        published_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
    )
    run = SimpleNamespace(
        features_json=json.dumps(
            {
                "source_urls": ["https://example.com/source"],
                "claim_verification": {
                    "claims": [
                        {
                            "claim": "The event happened.",
                            "supported": True,
                            "citation_line": "The event happened.",
                        }
                    ]
                },
            }
        )
    )
    return row, run


class TestCorrectionScanThrottle(unittest.TestCase):
    def test_fresh_stamp_skips_before_the_fetch(self):
        from core.correction_dossier import scan_published_for_corrections

        row, run = _published_correction_fixture()
        now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
        fetched: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "correction.json")
            with open(stamp, "w", encoding="utf-8") as fh:
                json.dump({"last": now.isoformat()}, fh)
            found = scan_published_for_corrections(
                "tapin",
                published=[row],
                run_lookup={71: run},
                fetch=lambda url: fetched.append(url) or "The event happened. Nothing has changed.",
                negative_store=lambda *_args: None,
                stamp_path=stamp,
                now=now,
            )

        self.assertEqual(found, [])
        self.assertEqual(fetched, [])

    def test_stale_stamp_fetches_and_records_completion(self):
        from core.correction_dossier import scan_published_for_corrections

        row, run = _published_correction_fixture()
        now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
        fetched: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "correction.json")
            with open(stamp, "w", encoding="utf-8") as fh:
                json.dump({"last": (now - timedelta(hours=25)).isoformat()}, fh)
            found = scan_published_for_corrections(
                "tapin",
                published=[row],
                run_lookup={71: run},
                fetch=lambda url: fetched.append(url) or "The event happened. Nothing has changed.",
                negative_store=lambda *_args: None,
                stamp_path=stamp,
                now=now,
            )
            with open(stamp, encoding="utf-8") as fh:
                saved = json.load(fh)

        self.assertEqual(found, [])
        self.assertEqual(fetched, ["https://example.com/source"])
        self.assertEqual(saved["last"], now.isoformat())

    def test_manual_force_bypasses_a_fresh_stamp(self):
        from core.correction_dossier import scan_published_for_corrections

        row, run = _published_correction_fixture()
        now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
        fetched: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "correction.json")
            with open(stamp, "w", encoding="utf-8") as fh:
                json.dump({"last": now.isoformat()}, fh)
            scan_published_for_corrections(
                "tapin",
                published=[row],
                run_lookup={71: run},
                fetch=lambda url: fetched.append(url) or "The event happened. Nothing has changed.",
                negative_store=lambda *_args: None,
                stamp_path=stamp,
                now=now,
                force=True,
            )

        self.assertEqual(fetched, ["https://example.com/source"])


if __name__ == "__main__":
    unittest.main()
