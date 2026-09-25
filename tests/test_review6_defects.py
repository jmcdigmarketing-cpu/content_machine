"""Defects found auditing Cursor's 18ba62c (review 6).

Every test here was observed failing on unmodified 18ba62c for the reason named
in its docstring.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _published(run_id: int = 75, video_id: str = "vid123"):
    return SimpleNamespace(content_run_id=run_id, youtube_video_id=video_id, channel_id="tapin")


def _run(run_id: int = 75):
    from storage.repositories.content_runs import ContentRunRecord

    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="UFC 320",
        selected_topic="UFC 320",
        status="completed",
        composite_score=1.0,
        features_json=json.dumps(
            {
                "source_urls": ["https://tapology.com/fight/1"],
                "claim_verification": {
                    "claims": [{"claim": "Jones beat Pereira at UFC 320", "supported": True}]
                },
            }
        ),
    )


def _scan(vault: str, body: str, **kwargs):
    from core.correction_dossier import scan_published_for_corrections

    return scan_published_for_corrections(
        "tapin",
        published=[_published()],
        run_lookup={75: _run()},
        fetch=lambda url: body,
        negative_store=None,
        stamp_path=os.path.join(vault, "correction_scan.json"),
        force=True,
        **kwargs,
    )


class TestUnreadableSourceIsNotAVanishedClaim(unittest.TestCase):
    """#705's coverage check treats *any* low-overlap body as a vanished claim.

    An empty response, a whitespace body, a JS shell that renders client-side, or
    a page truncated by the 8000-byte read cap all score near-zero coverage --
    and each filed a correction dossier claiming the source had changed.

    That is the module's own rule run backwards. `scan_published_for_corrections`
    already refuses to report an unreachable source as clean; an *unreadable* one
    must not be reported as changed either. Both are "the check did not run".
    """

    def test_an_empty_body_does_not_file_a_correction(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(vault, "")
        self.assertEqual(found, [], "an empty fetch was reported as a vanished claim")

    def test_a_whitespace_body_does_not_file_a_correction(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(vault, "   \n\t  ")
        self.assertEqual(found, [])

    def test_a_client_rendered_shell_does_not_file_a_correction(self):
        """A SPA returns markup with no article text. The claim is not gone; the
        text was never in the response."""
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(vault, "<html><head></head><body><div id='root'></div></body></html>")
        self.assertEqual(found, [])

    def test_an_unreadable_body_says_so_rather_than_going_quiet(self):
        """Skipping silently would make it look clean, which is the same defect
        in the other direction."""
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                with self.assertLogs(
                    "content_machine.core.correction_dossier", level="WARNING"
                ) as logs:
                    _scan(vault, "")
        self.assertTrue(
            any("unreadable" in line.lower() for line in logs.output),
            f"no WARNING explained the skipped check: {logs.output}",
        )

    def test_a_truncated_page_does_not_file_on_coverage_alone(self):
        """`_default_fetch` reads only `_MAX_BODY_CHARS`. A long article whose
        claim sits past the cap scores low coverage for a purely mechanical
        reason."""
        from core.correction_dossier import _MAX_BODY_CHARS

        filler = "Navigation home login subscribe newsletter advertisement footer "
        body = (filler * ((_MAX_BODY_CHARS // len(filler)) + 2))[:_MAX_BODY_CHARS]
        self.assertGreaterEqual(len(body), _MAX_BODY_CHARS)
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(vault, body)
        self.assertEqual(found, [], "a truncated read was reported as a vanished claim")

    def test_a_truncated_page_still_files_on_explicit_retraction(self):
        """Truncation suppresses the weak signal only. Retraction language that
        did make it into the read is still real evidence."""
        from core.correction_dossier import _MAX_BODY_CHARS

        filler = "Navigation home login subscribe newsletter advertisement footer "
        body = ("This story has been RETRACTED. " + filler * 200)[:_MAX_BODY_CHARS]
        self.assertGreaterEqual(len(body), _MAX_BODY_CHARS)
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(vault, body)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, "high")

    def test_a_real_page_that_dropped_the_claim_still_files(self):
        """The guard must not disarm the feature it protects."""
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(
                    vault,
                    "Tonight's card is postponed after a weather delay in Las Vegas. "
                    "Officials confirmed the venue would reopen tomorrow morning and "
                    "that ticket holders will be contacted directly by the promoter "
                    "with rescheduling details for every affected bout on the card. "
                    "Further updates will follow once the commission has reviewed "
                    "the revised schedule and the broadcast window is confirmed.",
                )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, "medium")

    def test_ordinary_rewording_still_does_not_file(self):
        """Guard the guard: this must pass because the claim is PRESENT, not
        because the body was rejected as unreadable. Without the first assertion
        a too-high readable floor would make this test vacuous."""
        from core.correction_dossier import _MIN_READABLE_TOKENS, _content_tokens

        body = (
            "Jon Jones defeated Alex Pereira during UFC 320 in a decision "
            "that closed out a card the promotion had built around the "
            "heavyweight title picture for most of the year."
        )
        self.assertGreaterEqual(
            len(_content_tokens(body)),
            _MIN_READABLE_TOKENS,
            "this body is below the readable floor, so the test proves nothing",
        )
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = _scan(vault, body)
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
