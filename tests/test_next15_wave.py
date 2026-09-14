"""Next-15 wave: operator-facing honesty, vanished claims, branding, CI.

Every behaviour test below was run against unmodified b9f1354 before the
matching production change. Guards for work already in HEAD were watched
going red with the guarded thing broken (rule 17).
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestWordTimingAliasIsGone(unittest.TestCase):
    """#710. A compatibility alias that production never calls is a trap for
    patch sites. The live name is `load_word_timings`."""

    def test_subtitles_has_no_private_load_alias(self):
        import video.subtitles as subtitles

        self.assertTrue(hasattr(subtitles, "load_word_timings"))
        self.assertFalse(hasattr(subtitles, "_load_word_timings"))

    def test_the_seam_test_patches_the_live_name(self):
        source = Path("tests/test_word_timing_seam.py").read_text(encoding="utf-8")
        self.assertIn('patch("video.subtitles.load_word_timings"', source)
        self.assertNotIn("_load_word_timings", source)


class TestWave6ExtrasIsCollected(unittest.TestCase):
    """#712. A TestCase file named `_wave6_extras.py` is invisible to discover."""

    def test_discover_loads_the_extras_module(self):
        import tests.test_wave6_extras as extras

        suite = unittest.defaultTestLoader.loadTestsFromModule(extras)
        self.assertGreaterEqual(suite.countTestCases(), 4)


class TestChapterMarksFollowWordStarts(unittest.TestCase):
    """#431. Equal-span fallback for three sentences over 60s is also 0:20/0:40,
    so a test that asserts those stamps cannot catch ignored timings.

    Wave 16 (#750): the starts were 0/5/12 s - under YouTube's 10 s minimum, so that
    block is one YouTube discards and chapter_block now emits none for it. Moved to
    0/15/33 s, which still disagree with equal span."""

    def test_marks_use_word_starts_that_disagree_with_equal_span(self):
        from core.chapters import chapter_block

        script = "Opening context. The second point matters. Final consequence."
        words = [
            {"word": "Opening", "start": 0.0, "end": 0.4},
            {"word": "context.", "start": 0.4, "end": 0.8},
            {"word": "The", "start": 15.0, "end": 15.2},
            {"word": "second", "start": 15.2, "end": 15.5},
            {"word": "point", "start": 15.5, "end": 15.8},
            {"word": "matters.", "start": 15.8, "end": 16.1},
            {"word": "Final", "start": 33.0, "end": 33.3},
            {"word": "consequence.", "start": 33.3, "end": 33.8},
        ]
        block = chapter_block(script, duration=60.0, length_choice="4", word_timings=words)
        lines = block.splitlines()
        self.assertTrue(any(line.startswith("0:15") for line in lines), block)
        self.assertTrue(any(line.startswith("0:33") for line in lines), block)
        self.assertFalse(any(line.startswith("0:20") for line in lines), block)
        self.assertFalse(any(line.startswith("0:40") for line in lines), block)


class TestTitleScriptCheckReachesTheOperator(unittest.TestCase):
    """#549. The check is persisted on the package; the fact-engine report
    never printed it, so a wrong-actor title looked clean at Proceed?."""

    def test_a_failed_check_prints_and_needs_review(self):
        from core.ui import display_fact_engine_report

        printed: list[str] = []
        needs = display_fact_engine_report(
            {
                "title_script_check": {
                    "status": "failed",
                    "passed": False,
                    "warnings": [
                        "title contradicts or is not supported by the final "
                        "script: Jones beat Pereira"
                    ],
                    "total": 1,
                }
            },
            print_fn=printed.append,
        )
        blob = " ".join(printed).lower()
        self.assertTrue(needs)
        self.assertIn("title vs script", blob)
        self.assertIn("jones beat pereira", blob)

    def test_unavailable_is_printed_and_is_not_a_pass(self):
        from core.ui import display_fact_engine_report

        printed: list[str] = []
        needs = display_fact_engine_report(
            {
                "title_script_check": {
                    "status": "unavailable",
                    "passed": False,
                    "warnings": [],
                    "total": 0,
                }
            },
            print_fn=printed.append,
        )
        blob = " ".join(printed).lower()
        self.assertTrue(needs)
        self.assertIn("unavailable", blob)
        self.assertIn("title vs script", blob)


class TestNoDataVsDataSaysDefault(unittest.TestCase):
    """#562. Zero samples and 'not enough samples, use the default' must not
    share a sentence."""

    def test_length_zero_samples_is_not_the_thin_default_line(self):
        from core.length_recommender import get_recommended_length

        with patch("core.length_recommender._collect_length_samples", return_value=[]):
            none = get_recommended_length("tapin", "Marvel Rivals update")
        thin_samples = [{"length_choice": "2", "engaged_rate": 0.3} for _ in range(4)]
        with patch("core.length_recommender._collect_length_samples", return_value=thin_samples):
            thin = get_recommended_length("tapin", "Marvel Rivals update")

        self.assertEqual(none.source, "default")
        self.assertEqual(thin.source, "default")
        self.assertIn("no engagement analytics yet", none.rationale)
        self.assertNotIn("no engagement analytics yet", thin.rationale)
        self.assertIn("more measured", thin.rationale)
        self.assertNotEqual(none.rationale, thin.rationale)

    def test_post_time_empty_slot_is_not_the_no_analytics_line(self):
        from analytics.post_timing import PostScheduleConfig, PostSlot, get_recommended_time

        learned = PostScheduleConfig(timezone="UTC", slots=(PostSlot(0, 12, 0),))
        when = datetime(2026, 9, 9, 16, 0, tzinfo=timezone.utc)
        with (
            patch("analytics.post_timing._use_learned_post_slots", return_value=True),
            patch("analytics.post_timing.learn_slots_from_analytics", return_value=learned),
            patch("analytics.post_timing.next_optimal_post_time", return_value=when),
            patch("analytics.post_timing.format_scheduled_local", return_value="Wed 12:00"),
            patch("analytics.post_timing._slot_engagement", return_value=(0.0, 0, [])),
        ):
            learned_empty = get_recommended_time("tapin", "Marvel Rivals update")
        with (
            patch("analytics.post_timing._use_learned_post_slots", return_value=True),
            patch("analytics.post_timing.learn_slots_from_analytics", return_value=None),
            patch("analytics.post_timing.next_optimal_post_time", return_value=when),
            patch("analytics.post_timing.format_scheduled_local", return_value="Wed 12:00"),
            patch("analytics.post_timing._collect_timed_samples", return_value=[]),
        ):
            none = get_recommended_time("tapin", "Marvel Rivals update")

        self.assertIn("no engagement analytics yet", none.rationale)
        self.assertNotIn("no engagement analytics yet", learned_empty.rationale)
        self.assertNotEqual(none.rationale, learned_empty.rationale)


class TestConfidenceNoteAlwaysNamesN(unittest.TestCase):
    """#569. High-confidence used to return empty, so the operator never saw n."""

    def test_high_confidence_still_names_the_sample_count(self):
        from core.recommender_confidence import SOLID_SAMPLES, confidence_note

        note = confidence_note(SOLID_SAMPLES)
        self.assertIn(f"{SOLID_SAMPLES} sample", note)
        self.assertNotEqual(note, "")


class TestWeekFlipIsPrinted(unittest.TestCase):
    """#568. A pick that disagrees with last week's stamped pick is news."""

    def test_a_new_week_that_disagrees_names_both_picks(self):
        from core.recommender_history import note_week_flip

        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "recommend_pick.json")
            last_week = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
            this_week = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
            first = note_week_flip("tapin", "length", "2", now=last_week, stamp_file=stamp)
            flipped = note_week_flip("tapin", "length", "3", now=this_week, stamp_file=stamp)

        self.assertEqual(first, "")
        self.assertIn("last week", flipped.lower())
        self.assertIn("2", flipped)
        self.assertIn("3", flipped)

    def test_same_week_does_not_claim_a_flip(self):
        from core.recommender_history import note_week_flip

        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "recommend_pick.json")
            now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
            note_week_flip("tapin", "length", "2", now=now, stamp_file=stamp)
            again = note_week_flip("tapin", "length", "3", now=now, stamp_file=stamp)

        self.assertEqual(again, "")

    def test_an_unreadable_stamp_is_visible_not_silent(self):
        from core.recommender_history import note_week_flip

        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "recommend_pick.json")
            Path(stamp).write_text("{not json", encoding="utf-8")
            note = note_week_flip(
                "tapin",
                "length",
                "2",
                now=datetime(2026, 9, 9, tzinfo=timezone.utc),
                stamp_file=stamp,
            )

        self.assertIn("could not compare", note.lower())

    def test_display_length_prints_the_flip(self):
        from core.length_recommender import LengthRecommendation, display_recommended_length

        rec = LengthRecommendation(
            length_choice="3",
            label="Long",
            source="analytics",
            avg_engaged_rate=0.4,
            supporting_runs=8,
            rationale="Long averages 40%",
            channel_id="tapin",
        )
        buf = io.StringIO()
        with (
            patch(
                "core.recommender_history.note_week_flip",
                return_value="last week recommended 2; this week 3",
            ),
            redirect_stdout(buf),
        ):
            display_recommended_length(rec)
        self.assertIn("last week recommended 2", buf.getvalue())


class TestCommunityPostDraft(unittest.TestCase):
    """#430. A YouTube Community post draft from the weekly-report paragraph.
    Nothing is posted."""

    def test_draft_carries_the_next_actions_and_says_it_is_a_draft(self):
        from analytics.weekly_report import community_post_draft

        report = {
            "channel_id": "tapin",
            "ready": True,
            "n": 12,
            "baseline": 0.25,
            "next_actions": ["Lead with the 'fraud' angle again (45% vs 25% baseline, n=3)"],
        }
        draft = community_post_draft(report)
        self.assertIn("fraud", draft.lower())
        self.assertIn("draft", draft.lower())
        self.assertNotIn("youtube.com", draft.lower())

    def test_writing_the_draft_does_not_construct_the_youtube_client(self):
        from analytics.weekly_report import write_community_post_draft

        report = {
            "channel_id": "tapin",
            "ready": True,
            "next_actions": ["Make more ufc videos (40% vs 25% baseline, n=4)"],
        }
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                with patch("youtube.oauth.get_youtube_service") as svc:
                    path = write_community_post_draft("tapin", report)
            self.assertIsNotNone(path)
            assert path is not None
            text = path.read_text(encoding="utf-8")
        self.assertIn("ufc", text.lower())
        self.assertIn("community", path.name)
        svc.assert_not_called()


class TestMetricSnapshotsAreSticky(unittest.TestCase):
    """#440. A later sync must not erase the 24h/7d curve."""

    def test_a_second_sync_keeps_the_first_24h_snapshot(self):
        from analytics.youtube_metrics import merge_metric_snapshots

        published = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
        first_at = published + timedelta(hours=20)
        later_at = published + timedelta(days=8)
        first = merge_metric_snapshots(
            {},
            {"views": 100, "engaged_rate": 0.40, "likes": 10},
            published_at=published,
            now=first_at,
        )
        second = merge_metric_snapshots(
            first,
            {"views": 900, "engaged_rate": 0.22, "likes": 40},
            published_at=published,
            now=later_at,
        )
        self.assertEqual(second["snapshots"]["24h"]["views"], 100)
        self.assertEqual(second["snapshots"]["24h"]["engaged_rate"], 0.40)
        self.assertEqual(second["views"], 900)
        self.assertEqual(second["snapshots"]["7d"]["views"], 900)

    def test_dossier_prints_the_snapshots(self):
        from core.run_ledger import render_dossier

        run = SimpleNamespace(
            id=440,
            channel_id="tapin",
            status="published",
            selected_topic="UFC 320",
            input_topic="UFC 320",
            title="Jones vs Pereira",
            composite_score=80.0,
            abort_reason=None,
            features_json="{}",
            quality_json="{}",
            timings_json="{}",
        )
        repo = MagicMock()
        repo.get.return_value = run
        publish = {
            "youtube_video_id": "vid440",
            "status": "uploaded",
            "metrics": {
                "views": 900,
                "engaged_rate": 0.22,
                "likes": 40,
                "snapshots": {
                    "24h": {"views": 100, "engaged_rate": 0.40, "likes": 10},
                    "7d": {"views": 500, "engaged_rate": 0.30, "likes": 20},
                },
            },
        }
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch("core.run_ledger._publish_for_run", return_value=publish),
            patch("core.run_trace.read_trace", return_value=None),
            patch("core.experiments.assignment_for_run", return_value=None),
        ):
            text = render_dossier(440)
        self.assertIn("24h snapshot", text)
        self.assertIn("views 100", text)
        self.assertIn("7d snapshot", text)


class TestVanishedClaimSimilarity(unittest.TestCase):
    """#705. Substring-missing fires on ordinary rewording. Similarity must not."""

    def _scan(self, vault: str, body: str):
        from core.correction_dossier import scan_published_for_corrections
        from storage.repositories.content_runs import ContentRunRecord

        published = SimpleNamespace(
            content_run_id=75, youtube_video_id="vid123", channel_id="tapin"
        )
        run = ContentRunRecord(
            id=75,
            channel_id="tapin",
            input_topic="UFC 320",
            selected_topic="UFC 320",
            status="completed",
            composite_score=1.0,
            features_json=json.dumps(
                {
                    "source_urls": ["https://tapology.com/fight/1"],
                    "claim_verification": {
                        "claims": [
                            {
                                "claim": "Jones beat Pereira at UFC 320",
                                "supported": True,
                            }
                        ]
                    },
                }
            ),
        )
        return scan_published_for_corrections(
            "tapin",
            published=[published],
            run_lookup={75: run},
            fetch=lambda url: body,
            negative_store=None,
            stamp_path=os.path.join(vault, "correction_scan.json"),
            force=True,
        )

    def test_ordinary_rewording_does_not_file(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = self._scan(
                    vault,
                    "Jon Jones defeated Alex Pereira during UFC 320 in a decision.",
                )
        self.assertEqual(found, [])

    def test_a_vanished_claim_files_weaker_than_an_explicit_retraction(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                vanished = self._scan(
                    vault,
                    "Tonight's card is postponed. Weather delay in Las Vegas.",
                )
                retracted = self._scan(
                    vault,
                    "We regret this retraction: the earlier report was wrong.",
                )
        self.assertEqual(len(vanished), 1)
        self.assertEqual(vanished[0].severity, "medium")
        self.assertEqual(len(retracted), 1)
        self.assertEqual(retracted[0].severity, "high")

    def test_a_clean_scan_still_writes_the_stamp_when_unforced(self):
        from core.correction_dossier import scan_published_for_corrections

        with tempfile.TemporaryDirectory() as vault:
            stamp = os.path.join(vault, "correction_scan.json")
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = scan_published_for_corrections(
                    "tapin",
                    published=[],
                    run_lookup={},
                    fetch=lambda url: "",
                    negative_store=None,
                    stamp_path=stamp,
                    force=False,
                    now=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
                )
            self.assertEqual(found, [])
            self.assertTrue(os.path.isfile(stamp), "overnight stamp was not written")


class TestTapInBrandAssets(unittest.TestCase):
    """#708. compile_kit('tapin').missing used to name logo.svg and banner.svg."""

    def test_tapin_logo_and_banner_are_on_disk(self):
        from core.brand_kit import compile_kit

        kit = compile_kit("tapin")
        missing = " ".join(kit.missing).lower()
        self.assertNotIn("logo.svg", missing)
        self.assertNotIn("banner.svg", missing)
        self.assertTrue(kit.logo_path)
        self.assertTrue(kit.banner_path)
        self.assertTrue(Path(kit.logo_path).is_file())
        self.assertTrue(Path(kit.banner_path).is_file())

    def test_tapin_geometry_is_not_a_copy_of_moneywise(self):
        tapin = Path("assets/branding/tapin/logo.svg").read_text(encoding="utf-8")
        money = Path("assets/branding/moneywise/logo.svg").read_text(encoding="utf-8")
        self.assertNotEqual(tapin, money)
        self.assertIn("#E53935", tapin)
        self.assertNotIn("polyline", tapin)


class TestCIStartsPostgresOffMain(unittest.TestCase):
    """#711. on.push limited to main/master never starts postgres:16 here."""

    def test_workflow_runs_on_push_and_manual_dispatch(self):
        text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotRegex(
            text,
            r"(?s)on:\s*\n\s*push:\s*\n\s*branches:\s*\[main, master\]",
        )


if __name__ == "__main__":
    unittest.main()
