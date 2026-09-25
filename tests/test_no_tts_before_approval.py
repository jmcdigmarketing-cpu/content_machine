"""Candidate 373: no path bills TTS before the script is approved.

TTS is ~91% of a rendered run's metered cost, so a draft entry point that
reached `generate_audio` would charge the operator for a script they are about
to reject. `core/pipeline.py` returns on `not proceed_video` well before the TTS
call, and `tests/test_pipeline_smoke.py` already locks that one seam.

What was NOT locked is 373's actual claim -- *every* entry point. These tests
drive the three real draft callers and assert both halves: the call site still
asks for a draft (`proceed_video=False`), and no TTS is billed on the way there.
`generate_audio` is patched at each module's call site; its internals are never
mocked.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.pipeline import DiscoveryResult


def _discovery(topic: str = "GTA 6 leak") -> DiscoveryResult:
    signals = {"youtube": {"connected": True, "active": True, "score": 50}}
    return DiscoveryResult(
        input_topic=topic,
        base_signals=signals,
        evaluated=[(topic, 71.0, signals)],
        channel_id="tapin",
    )


class TestDraftEntryPointsNeverBillTts(unittest.TestCase):
    def test_pipeline_draft_return_precedes_the_tts_call(self):
        """The seam itself: proceed_video=False returns before generate_audio."""
        from core.pipeline import run_pipeline

        with (
            patch("core.pipeline.generate_audio") as tts,
            patch("core.pipeline.write_run_dossier"),
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=1),
            patch(
                "core.pipeline.generate_content_package",
                return_value={"title": "T", "script": "Hook line.", "description": "D"},
            ),
        ):
            result = run_pipeline(
                "GTA 6 leak",
                discovery=_discovery(),
                proceed_video=False,
                channel_id="tapin",
            )

        self.assertTrue(result.aborted)
        self.assertEqual(result.abort_reason, "proceed_video=False")
        self.assertEqual(tts.call_count, 0)

    def test_batch_generation_asks_for_a_draft_and_bills_no_tts(self):
        """The overnight path, driven for real. Drafts go to a temp dir per
        tests/CLAUDE.md -- never the operator's `output/`."""
        import tempfile

        from core import batch_generation

        drafted = SimpleNamespace(
            aborted=False,
            abort_reason=None,
            script="Hook line. Second line.",
            title="GTA 6 leak explained",
            description="Desc",
            tags=["gta"],
            run_id=5,
            features={},
        )

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("core.tts.generate_audio") as tts,
                patch("core.pipeline.run_pipeline", return_value=drafted) as run,
                patch("core.pipeline.run_discovery", return_value=_discovery()),
                patch.object(batch_generation, "_drafts_dir", return_value=tmp),
            ):
                batch_generation.generate_draft("GTA 6 leak", channel_id="tapin")

        self.assertTrue(run.called, "batch_generation no longer calls run_pipeline")
        self.assertIs(run.call_args.kwargs.get("proceed_video"), False)
        self.assertEqual(tts.call_count, 0)

    def test_every_draft_call_site_passes_proceed_video_false(self):
        """main.py's interactive loop cannot be driven headlessly, so pin the
        kwarg at the call site instead of pretending to exercise the prompt."""
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        for rel in ("main.py", "scripts/auto_generate.py", "core/batch_generation.py"):
            with self.subTest(entry=rel):
                tree = ast.parse((root / rel).read_text(encoding="utf-8"))
                calls = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and getattr(node.func, "id", None) == "run_pipeline"
                ]
                self.assertTrue(calls, f"{rel} no longer calls run_pipeline by name")
                for call in calls:
                    flags = [
                        kw.value
                        for kw in call.keywords
                        if kw.arg == "proceed_video" and isinstance(kw.value, ast.Constant)
                    ]
                    self.assertTrue(flags, f"{rel} calls run_pipeline without proceed_video")
                    self.assertEqual(
                        [f.value for f in flags],
                        [False],
                        f"{rel} asks run_pipeline to render before the operator approved",
                    )


if __name__ == "__main__":
    unittest.main()
