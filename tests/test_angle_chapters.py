"""All angles in one long video, and each angle as its own Short (run 78, 2026-09-13).

The operator liked all five run 78 angles and wanted them as chapters of one long video,
with every chapter also usable as a Short. Before this there was no "all angles" choice,
Extended chapters were labelled from arbitrary sentences ("1:16 That's the whole story"),
and nothing could turn a long render into Shorts. Each test failed on unmodified ae2eab0.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

RUN78_ANGLES = [
    "GTA 6's Hype Train: Will It Crash or Deliver? (Factual read) - An analysis of the "
    "game's development cycle and marketing strategy to determine if it meets player "
    "expectations.",
    "GTA 6: The Antidote to Gaming's Fatigue? (Contrarian counter-take) - A contrarian view "
    "arguing that GTA 6's grand ambitions are exactly what the gaming industry needs to "
    "revitalize its creative spark.",
    "GTA 6's Online Economy: A $1 Billion Opportunity? (Forward prediction) - A prediction "
    "of how GTA 6's online features and monetization model will shape the gaming "
    "industry's business landscape.",
    "GTA 6's Influence on Reality: The Blurred Lines Between Game and Life (Human/stakes "
    "angle) - An exploration of how GTA 6's narrative and gameplay mechanics will reflect "
    "and influence real-world issues and social commentary.",
    "GTA 6's Technical Leap: How Does It Stack Up to Previous Entries? (Analytical "
    "breakdown) - A detailed comparison of GTA 6's technical features, gameplay mechanics, "
    "and graphics with its predecessors to assess its overall quality and impact.",
]
RUN78_HEADLINES = [
    "GTA 6's Hype Train: Will It Crash or Deliver?",
    "GTA 6: The Antidote to Gaming's Fatigue?",
    "GTA 6's Online Economy: A $1 Billion Opportunity?",
    "GTA 6's Influence on Reality: The Blurred Lines Between Game and Life",
    "GTA 6's Technical Leap: How Does It Stack Up to Previous Entries?",
]

PARAGRAPHS = [
    "Twelve years of waiting ends November 19. The hype train for GTA 6 has never been "
    "bigger, and Rockstar has barely spent on marketing. Delivering on that hype is the "
    "real test.",
    "Gaming fatigue is real, and GTA 6 might be the antidote. Contrarian as it sounds, one "
    "ambitious release could remind publishers why big swings matter.",
    "The online economy is where the money lives. GTA Online earned billions, and GTA 6 "
    "Online will decide whether that economy grows or collapses.",
    "Games already shape reality, and GTA 6 will blur the lines between game and real life. "
    "Its satire lands because it feels like tomorrow's headlines.",
    "The technical leap is obvious in every trailer. Stacked against previous entries, the "
    "lighting, crowds and physics look a generation ahead.",
]
SCRIPT = " ".join(PARAGRAPHS)
_WORD = re.compile(r"[A-Za-z0-9']+")


def _expected_word_starts() -> list[int]:
    starts, total = [], 0
    for paragraph in PARAGRAPHS:
        starts.append(total)
        total += len(_WORD.findall(paragraph))
    return starts


def _timings(script: str, step: float = 0.4) -> list[dict]:
    return [
        {"word": w, "start": round(i * step, 3), "end": round(i * step + 0.35, 3)}
        for i, w in enumerate(_WORD.findall(script))
    ]


class TestAngleHeadlines(unittest.TestCase):
    def test_headline_drops_the_lens_label_and_description(self):
        from core.angle_chapters import angle_headline

        for angle, headline in zip(RUN78_ANGLES, RUN78_HEADLINES, strict=True):
            self.assertEqual(angle_headline(angle), headline)

    def test_lens_labels_are_stripped_from_generated_angles(self):
        from apis.topic_variants import _clean_angle_lines

        out = _clean_angle_lines(RUN78_ANGLES[2], ["forward_prediction"])
        self.assertEqual(len(out), 1)
        self.assertNotIn("(Forward prediction)", out[0])
        self.assertTrue(out[0].startswith("GTA 6's Online Economy: A $1 Billion Opportunity?"))


class TestLocateChapters(unittest.TestCase):
    def test_verified_llm_openers_place_each_chapter(self):
        from core.angle_chapters import locate_chapters

        openers = {"starts": [" ".join(p.split()[:7]) for p in PARAGRAPHS]}
        with patch("core.llm_router.complete_json", return_value=openers):
            chapters = locate_chapters(SCRIPT, RUN78_ANGLES)
        self.assertEqual([c.word_start for c in chapters], _expected_word_starts())
        self.assertEqual([c.title for c in chapters], RUN78_HEADLINES)

    def test_openers_out_of_order_fall_back_to_keyword_alignment(self):
        from core.angle_chapters import locate_chapters

        shuffled = {"starts": [" ".join(p.split()[:7]) for p in reversed(PARAGRAPHS)]}
        with patch("core.llm_router.complete_json", return_value=shuffled):
            chapters = locate_chapters(SCRIPT, RUN78_ANGLES)
        self.assertEqual([c.word_start for c in chapters], _expected_word_starts())

    def test_no_llm_still_yields_ordered_chapters(self):
        from core.angle_chapters import locate_chapters

        with patch("core.llm_router.complete_json", side_effect=RuntimeError("extract down")):
            chapters = locate_chapters(SCRIPT, RUN78_ANGLES)
        self.assertEqual([c.word_start for c in chapters], _expected_word_starts())


class TestChapterLines(unittest.TestCase):
    def test_lines_use_headlines_at_real_word_times(self):
        from core.angle_chapters import AngleChapter, chapter_lines

        starts = _expected_word_starts()
        chapters = [
            AngleChapter(index=i, title=RUN78_HEADLINES[i], angle=RUN78_ANGLES[i], word_start=s)
            for i, s in enumerate(starts)
        ]
        lines = chapter_lines(chapters, word_timings=_timings(SCRIPT, step=2.0)).splitlines()
        self.assertEqual(lines[0], f"0:00 {RUN78_HEADLINES[0]}")
        minutes, seconds = divmod(int(starts[2] * 2.0), 60)
        self.assertEqual(lines[2], f"{minutes}:{seconds:02d} {RUN78_HEADLINES[2]}")


class TestAllAnglesPipeline(unittest.TestCase):
    @patch("core.pipeline.write_run_dossier")
    @patch("core.pipeline.write_run_trace")
    @patch("core.pipeline.persist_quality")
    @patch("core.pipeline.build_quality", return_value={})
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=78)
    @patch("core.pipeline.build_research_brief")
    @patch("core.pipeline.generate_content_package")
    def test_all_angles_brief_the_writer_and_become_chapters(
        self, mock_content, _brief, _record, _learn, _bq, _pq, _trace, _doss
    ):
        from core.pipeline import DiscoveryResult, run_pipeline

        _brief.return_value = SimpleNamespace(version="v1", to_prompt_block=lambda: "")
        discovery = DiscoveryResult(
            input_topic="GTA 6",
            base_signals={},
            evaluated=[(angle, 100.0, {}) for angle in RUN78_ANGLES],
            channel_id="tapin",
        )
        mock_content.return_value = {
            "title": "GTA 6 Predictions: Five Big Questions",
            "script": SCRIPT,
            "description": "Five questions about GTA 6.\n\n0:00 Twelve years of waiting",
        }
        with patch("core.llm_router.complete_json", side_effect=RuntimeError("extract down")):
            result = run_pipeline(
                "GTA 6",
                discovery=discovery,
                variant_index=0,
                length_choice="4",
                proceed_video=False,
                channel_id="tapin",
                creative_brief="my thoughts",
                chapter_angles=RUN78_ANGLES,
            )

        kwargs = mock_content.call_args.kwargs
        self.assertEqual(kwargs["topic"], "GTA 6")
        for headline in RUN78_HEADLINES:
            self.assertIn(headline, kwargs["creative_brief"])
        self.assertIn("my thoughts", kwargs["creative_brief"])
        rows = result.features["angle_chapters"]
        self.assertEqual([r["title"] for r in rows], RUN78_HEADLINES)
        self.assertEqual([r["word_start"] for r in rows], _expected_word_starts())
        self.assertIn(f"0:00 {RUN78_HEADLINES[0]}", result.description)
        self.assertIn(RUN78_HEADLINES[4], result.description)
        self.assertNotIn("Twelve years of waiting", result.description.split("\n\n")[-1])


class TestChapterSpans(unittest.TestCase):
    def test_spans_sit_after_the_intro_and_end_at_the_next_chapter(self):
        from core.angle_chapters import AngleChapter
        from core.chapter_shorts import chapter_spans

        starts = _expected_word_starts()
        chapters = [
            AngleChapter(index=i, title=RUN78_HEADLINES[i], angle=RUN78_ANGLES[i], word_start=s)
            for i, s in enumerate(starts)
        ]
        words = _timings(SCRIPT, step=0.4)
        audio_end = words[-1]["end"] + 0.3
        spans = chapter_spans(
            SCRIPT, chapters, word_timings=words, intro_offset=3.0, audio_duration=audio_end
        )
        self.assertEqual(len(spans), 5)
        for i, span in enumerate(spans):
            self.assertAlmostEqual(span.start, 3.0 + words[starts[i]]["start"], delta=0.25)
            if i < 4:
                self.assertAlmostEqual(span.end, 3.0 + words[starts[i + 1]]["start"], delta=0.25)
            self.assertTrue(span.fits_shorts)
            self.assertTrue(span.text.startswith(PARAGRAPHS[i].split()[0]))
        self.assertAlmostEqual(spans[-1].end, 3.0 + audio_end, delta=0.25)

    def test_a_chapter_over_three_minutes_does_not_fit_shorts(self):
        from core.angle_chapters import AngleChapter
        from core.chapter_shorts import chapter_spans

        chapters = [
            AngleChapter(index=0, title="One", angle="One", word_start=0),
            AngleChapter(index=1, title="Two", angle="Two", word_start=10),
        ]
        words = _timings(SCRIPT, step=20.0)
        spans = chapter_spans(
            SCRIPT, chapters, word_timings=words, intro_offset=0.0, audio_duration=2000.0
        )
        self.assertFalse(spans[0].fits_shorts)

    def test_selection_parsing(self):
        from core.chapter_shorts import parse_chapter_selection

        self.assertEqual(parse_chapter_selection("", 5), [0, 1, 2, 3, 4])
        self.assertEqual(parse_chapter_selection("all", 5), [0, 1, 2, 3, 4])
        self.assertEqual(parse_chapter_selection("1, 3,5", 5), [0, 2, 4])
        self.assertEqual(parse_chapter_selection("9, x", 5), [])


class TestCutChapterShorts(unittest.TestCase):
    def test_each_chapter_is_cut_and_recorded_as_its_own_rendered_run(self):
        from core import chapter_shorts

        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "gta_6_all_angles.mp4")
        with open(src, "wb") as handle:
            handle.write(b"0")
        starts = _expected_word_starts()
        features = {
            "length_preset": "4",
            "angle_chapters": [
                {"index": i, "title": RUN78_HEADLINES[i], "angle": RUN78_ANGLES[i], "word_start": s}
                for i, s in enumerate(starts)
            ],
        }
        parent = SimpleNamespace(
            id=78,
            channel_id="tapin",
            input_topic="GTA 6",
            composite_score=100.0,
            title="GTA 6 Predictions",
            tags_json=json.dumps(["GTA6"]),
            script_preview=SCRIPT,
            mp3_path=os.path.join(tmp, "a.mp3"),
            mp4_path=src,
            features_json=json.dumps(features),
        )
        repo = SimpleNamespace(get=lambda run_id: parent)
        calls: list[list[str]] = []

        def _ffmpeg(argv, **kwargs):
            calls.append(list(argv))
            with open(argv[-1], "wb") as handle:
                handle.write(b"clip")
            return SimpleNamespace(returncode=0, stderr="")

        ids = iter(range(100, 110))
        with (
            patch.object(chapter_shorts, "get_content_run_repository", return_value=repo),
            patch.object(chapter_shorts, "load_word_timings", return_value=_timings(SCRIPT)),
            patch.object(chapter_shorts, "_intro_offset", return_value=3.0),
            patch.object(chapter_shorts, "_probe_duration", return_value=60.0),
            patch.object(chapter_shorts.subprocess, "run", side_effect=_ffmpeg),
            patch.object(
                chapter_shorts, "record_content_run", side_effect=lambda **kw: next(ids)
            ) as rec,
        ):
            made = chapter_shorts.cut_chapter_shorts(78, indices=[0, 2])

        self.assertEqual([m.run_id for m in made], [100, 101])
        self.assertEqual(len(calls), 2)
        self.assertIn("-ss", calls[0])
        first = rec.call_args_list[0].kwargs
        self.assertEqual(first["status"], "rendered")
        self.assertEqual(first["title"], RUN78_HEADLINES[0])
        self.assertEqual(first["features"]["parent_run_id"], 78)
        self.assertEqual(rec.call_args_list[1].kwargs["features"]["chapter_index"], 2)
        self.assertTrue(os.path.isfile(made[1].mp4_path))


class TestAngleMenuChoice(unittest.TestCase):
    def test_a_means_all_angles(self):
        import main

        self.assertEqual(main._parse_angle_choice("a", 5, 3, allow_own=False), ("all", 3))
        self.assertEqual(main._parse_angle_choice("A", 5, 3, allow_own=True), ("all", 3))
        self.assertEqual(main._parse_angle_choice("", 5, 3, allow_own=False), ("one", 3))
        self.assertEqual(main._parse_angle_choice("2", 5, 3, allow_own=False), ("one", 1))
        self.assertEqual(main._parse_angle_choice("0", 5, 3, allow_own=True), ("own", -1))
        self.assertEqual(main._parse_angle_choice("a", 1, 0, allow_own=False), ("one", 0))


class TestFreshAngleShorts(unittest.TestCase):
    def _run(self, confirm: bool):
        import main

        drafts = [
            SimpleNamespace(
                run_id=200 + i,
                topic=RUN78_ANGLES[i],
                title=RUN78_HEADLINES[i],
                script="Short script.",
                timings={"word_count": 180},
                features={"projected_cost": {"total": 0.31}},
                aborted=True,
            )
            for i in (1, 3)
        ]
        with (
            patch.object(main, "run_pipeline", side_effect=drafts) as pipe,
            patch.object(main, "run_media_only", return_value=("a.mp3", "v.mp4", "")) as media,
            patch.object(main, "ask_confirm", return_value=confirm),
        ):
            made = main._make_fresh_angle_shorts(
                [1, 3],
                topic="GTA 6",
                discovery=SimpleNamespace(evaluated=[(a, 100.0, {}) for a in RUN78_ANGLES]),
                channel_id="tapin",
                creative_brief="my thoughts",
                key_facts=["fact"],
            )
        return pipe, media, made

    def test_each_angle_is_drafted_at_medium_then_rendered_after_one_confirm(self):
        pipe, media, made = self._run(confirm=True)
        self.assertEqual([c.kwargs["variant_index"] for c in pipe.call_args_list], [1, 3])
        self.assertTrue(all(c.kwargs["length_choice"] == "2" for c in pipe.call_args_list))
        self.assertTrue(all(not c.kwargs.get("chapter_angles") for c in pipe.call_args_list))
        self.assertEqual(media.call_count, 2)
        self.assertEqual(made, [201, 203])

    def test_declining_renders_nothing(self):
        _pipe, media, made = self._run(confirm=False)
        media.assert_not_called()
        self.assertEqual(made, [])


if __name__ == "__main__":
    unittest.main()
