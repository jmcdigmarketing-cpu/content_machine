"""#1053 a chapter Short re-hooks, names the long video, and lands in shorts/.

Enter on the offer cuts the chapters and queues them. ffmpeg is a stub.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.chapter_shorts import ChapterSpan, cut_chapter_shorts


class TestChapterShortPlate(unittest.TestCase):
    def test_the_cut_lands_in_shorts_with_a_rehook_and_an_end_card(self):
        text = "A short line. This sentence is the strongest one in the chapter."
        span = ChapterSpan(
            index=0,
            title="Chapter title",
            angle="the angle",
            start=1.0,
            end=31.0,
            text=text,
        )
        from core.chapter_shorts import strongest_sentence

        self.assertEqual(
            strongest_sentence(text),
            "This sentence is the strongest one in the chapter.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "long.mp4")
            with open(source, "wb") as handle:
                handle.write(b"0")
            record = SimpleNamespace(
                id=9,
                channel_id="tapin",
                input_topic="GTA",
                composite_score=1.0,
                title="The Long Video",
                tags_json="[]",
                mp4_path=source,
                features_json="{}",
            )
            seen: list[list[str]] = []

            def fake_ffmpeg(argv, **kwargs):
                seen.append(list(argv))
                with open(argv[-1], "wb") as handle:
                    handle.write(b"clip")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch(
                    "core.chapter_shorts.get_content_run_repository",
                    return_value=SimpleNamespace(get=lambda run_id: record),
                ),
                patch(
                    "core.chapter_shorts._record_spans",
                    return_value=([object()], [span], text),
                ),
                patch("core.chapter_shorts.subprocess.run", side_effect=fake_ffmpeg),
                patch("core.chapter_shorts.record_content_run", return_value=41),
            ):
                made = cut_chapter_shorts(9, output_root=tmp)

        self.assertEqual(len(made), 1)
        self.assertIn(os.path.join("tapin", "shorts"), made[0].mp4_path)
        command = " ".join(seen[0])
        self.assertIn("This sentence is the strongest one in the chapter.", command)
        self.assertIn("The Long Video", command)
        self.assertEqual(made[0].run_id, 41)


class TestShortsDefaultIsQueue(unittest.TestCase):
    def test_enter_cuts_and_queues(self):
        import main

        result = SimpleNamespace(
            run_id=9,
            script="chapter",
            features={"angle_chapters": [{"index": 0, "title": "T", "angle": "a"}]},
        )
        with (
            patch(
                "core.angle_chapters.chapters_from_features",
                return_value=[SimpleNamespace(index=0, title="T")],
            ),
            patch("core.chapter_shorts.chapter_report", return_value=["1. T"]),
            patch("core.chapter_shorts.parse_chapter_selection", return_value=[0]),
            patch(
                "core.chapter_shorts.cut_chapter_shorts",
                return_value=[SimpleNamespace(run_id=41, title="T", index=0, skipped="")],
            ) as cut,
            patch("main.ask_choice", return_value=""),
            patch("main.ask_text", return_value=""),
            patch("main._offer_spaced_queue") as queue,
            patch("main.subsection"),
        ):
            main._offer_angle_shorts(
                result=result,
                discovery=None,
                topic="GTA",
                channel_id="tapin",
                creative_brief="",
                key_facts=None,
            )
        cut.assert_called_once()
        queue.assert_called_once()

    def test_enter_on_the_queue_prompt_queues(self):
        import main

        with (
            patch("core.ask.ask_text", return_value=""),
            patch("core.spaced_queue.plan_spaced_uploads", return_value=[]),
            patch("core.spaced_queue.queue_spaced_uploads") as queued,
        ):
            main._offer_spaced_queue([41], {41: "T"}, topic="GTA", channel_id="tapin")
        queued.assert_called_once()


if __name__ == "__main__":
    unittest.main()
