"""#888: the run dossier is rewritten once the render has run.

The operator's path saves the run (and writes its dossier) before it renders. The render
then records the voices, the pace and the render assets on the run - and nothing
rewrote the note, so the dossier showed none of it until the overnight rewrite.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch


def _render(content_run_id):
    from core import pipeline

    calls = MagicMock()
    with tempfile.TemporaryDirectory() as tmp:
        with (
            patch.dict(os.environ, {"THUMBNAIL_MODE": "off", "CONTENT_RENDER_PROGRESS": "0"}),
            patch.object(pipeline, "update_content_run_media"),
            patch.object(pipeline, "record_render_assets"),
            patch("core.run_trace.update_trace"),
            patch.object(
                pipeline,
                "media_paths_for_topic",
                return_value=(os.path.join(tmp, "a.mp3"), "a.mp4", os.path.join(tmp, "a.mp4")),
            ),
            patch("core.tts_char_cap.tts_char_cap_reason", return_value=""),
            patch.object(pipeline, "generate_audio"),
            patch.object(pipeline, "render_vertical_video", return_value=(None, None)),
            patch("core.voice.plan.plan_for_run", return_value=({"narrator": "vA"}, None)),
            patch("core.tts.last_run_voices", return_value={"narrator": "vA"}),
            patch("core.run_features.load_features", return_value={}),
            patch(
                "core.run_features.merge_features",
                side_effect=lambda rid, upd: calls.merge(rid, dict(upd)),
            ),
            patch(
                "core.vault.dossiers.write_run_dossier",
                side_effect=lambda rid: calls.dossier(rid),
            ),
        ):
            pipeline.run_media_only(
                "topic", "script", channel_id="tapin", content_run_id=content_run_id
            )
    return calls


class DossierAfterRenderTests(unittest.TestCase):
    def test_a_saved_run_gets_its_dossier_rewritten_after_the_voices(self):
        calls = _render(7)
        names = [c[0] for c in calls.mock_calls]
        self.assertIn("dossier", names)
        voices_at = next(
            i for i, c in enumerate(calls.mock_calls) if c[0] == "merge" and "voices" in c.args[1]
        )
        self.assertGreater(names.index("dossier"), voices_at)

    def test_the_pace_is_stored_with_the_voices(self):
        calls = _render(7)
        merged = next(
            c.args[1] for c in calls.mock_calls if c[0] == "merge" and "voices" in c.args[1]
        )
        self.assertEqual(merged.get("tts_speed"), 0.95)

    def test_an_unsaved_render_writes_no_dossier(self):
        calls = _render(None)
        self.assertNotIn("dossier", [c[0] for c in calls.mock_calls])

    def test_the_audit_line_shows_the_pace(self):
        from core.vault.dossiers import audit_lines

        text = "\n".join(
            audit_lines(
                {"voice_mode": "debate", "voices": {"narrator": "vA"}, "tts_speed": 0.95}, {}
            )
        )
        self.assertIn("Voices (debate, 0.95x)", text)


if __name__ == "__main__":
    unittest.main()
