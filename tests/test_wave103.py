"""Wave 103, the small items. Each test calls the function that was wrong.

#1257 roadmap-index printed every open item. #1250 explain treated word_count as
seconds. #1256 the seven-day opening window never saw a date. #1260 an award
said "on the board this week". #1258 a boxing weigh-in took the MMA feed's
domain. #1259 a UFC follow-up repeated its last topic.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

DUBOIS = "Daniel Dubois vs. Fabio Wardley 2 weigh-in"


class RoadmapListTests(unittest.TestCase):
    def test_the_default_index_is_the_counts(self):
        from core.roadmap_index import render

        text = render()
        self.assertIn("numbered", text)
        self.assertNotIn("Open numbered", text)
        self.assertNotIn("#1248", text)

    def test_list_prints_the_open_numbers(self):
        # Wave 104: a backlog of its own - pinned to the live file, this test changed verdict
        # whenever an item was ticked (#1255, then #1248 in a separate commit).
        from core import roadmap_index

        real = roadmap_index._lines
        backlog = ["- [ ] 42. **An open item** `[S]`", "- [x] 43. **A done item** `[S]`"]

        def lines(name):
            return backlog if name == "backlog.md" else real(name)

        with patch.object(roadmap_index, "_lines", side_effect=lines):
            text = roadmap_index.render(list_open=True)
        self.assertIn("Open numbered", text)
        self.assertIn("  #42 An open item", text)
        self.assertNotIn("#43", text)


class ExplainWordCountTests(unittest.TestCase):
    def test_word_count_is_not_printed_as_a_timing(self):
        from core.run_trace import explain_trace

        text = explain_trace(
            {
                "run_id": 158,
                "status": "drafted",
                "timings": {"tts": 4.2, "word_count": 160},
            }
        )
        timings = next(line for line in text.splitlines() if line.startswith("Timings:"))
        self.assertIn("tts", timings)
        self.assertNotIn("word_count", timings)
        self.assertIn("Words: 160", text)


class OpeningWeekTests(unittest.TestCase):
    def _record(self, run_id: int, script: str, when):
        from storage.repositories.content_runs import PostgresContentRunRepository

        row = SimpleNamespace(
            id=run_id,
            channel_id="tapin",
            input_topic="t",
            selected_topic="t",
            status="drafted",
            composite_score=1.0,
            signals_json="{}",
            variants_json="[]",
            title="",
            description="",
            tags_json="[]",
            brief_version="",
            prompt_version="",
            script_preview=script,
            mp3_path="",
            mp4_path="",
            timings_json="{}",
            abort_reason="",
            features_json="{}",
            quality_json="{}",
            created_at=when,
        )
        return PostgresContentRunRepository()._row_to_record(row)

    def test_a_script_from_eight_days_ago_is_outside_the_week(self):
        from core.authenticity import scripts_this_week

        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        old = self._record(1, "The old opening from last week stays.", now - timedelta(days=8))
        fresh = self._record(2, "Herbert threw for three hundred yards.", now - timedelta(days=2))
        repo = SimpleNamespace(list_for_channel=lambda *_a, **_k: [fresh, old])
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=repo,
        ):
            kept = scripts_this_week("tapin", now=now)
        self.assertEqual(kept, ["Herbert threw for three hundred yards."])

    def test_fourteen_scripts_from_this_week_all_count(self):
        from core.authenticity import scripts_this_week

        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        runs = [
            self._record(i, f"Opening number {i} is its own sentence.", now - timedelta(days=1))
            for i in range(1, 15)
        ]
        repo = SimpleNamespace(list_for_channel=lambda *_a, **_k: list(reversed(runs)))
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=repo,
        ):
            kept = scripts_this_week("tapin", now=now)
        self.assertEqual(len(kept), 14)

    def test_a_row_with_no_timestamp_no_longer_counts(self):
        """A JSON row written before created_at was stored has no date. #1261 (wave 104): it
        is not "this week" - stamping create() dates every new row."""
        from core.authenticity import scripts_this_week

        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        undated = self._record(1, "An undated opening still counts.", None)
        repo = SimpleNamespace(list_for_channel=lambda *_a, **_k: [undated])
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=repo,
        ):
            kept = scripts_this_week("tapin", now=now)
        self.assertEqual(kept, [])

    def test_a_new_json_row_is_stamped(self):
        from storage.repositories import content_runs

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "runs.json")
            with patch.object(content_runs, "RUNS_FILE", path):
                content_runs.JsonContentRunRepository().create(
                    {
                        "channel_id": "tapin",
                        "input_topic": "t",
                        "selected_topic": "t",
                        "status": "drafted",
                        "composite_score": 1,
                    }
                )
            with open(path, encoding="utf-8") as handle:
                row = json.loads(handle.read())[0]
        self.assertTrue(row.get("created_at"))


class AwardDateTests(unittest.TestCase):
    def test_ballon_dor_says_its_date(self):
        from datetime import datetime as dt

        from core.best_bet import suggested_games

        bets = suggested_games(
            [("Ballon d'Or 2026", "soccer")],
            covered_topics=[],
            now=dt(2026, 10, 17, tzinfo=timezone.utc),
        )
        self.assertEqual(len(bets), 1)
        self.assertNotEqual(bets[0].rationale, "on the board this week")
        self.assertIn("Oct 28", bets[0].rationale)


class BoxingHeadlineTests(unittest.TestCase):
    def test_the_weigh_in_is_boxing_not_the_feeds_ufc(self):
        from apis.topic_scorer import infer_topic_domain
        from core.best_bet import _consider_candidate, _domain_for_feed

        self.assertEqual(infer_topic_domain(DUBOIS), "boxing")
        self.assertEqual(_domain_for_feed("boxing", ["ufc", "mma"]), "boxing")
        cand = _consider_candidate(
            DUBOIS,
            "MMA Fighting",
            allowed={"gaming", "ufc", "nba", "nfl", "soccer"},
            exclude=set(),
            seen_local=set(),
            feed_domains=["ufc", "mma"],
        )
        self.assertTrue(cand is None or cand["domain"] != "ufc")

    def test_a_ufc_weigh_in_stays_ufc(self):
        from apis.topic_scorer import infer_topic_domain
        from core.best_bet import _domain_for_feed

        self.assertEqual(infer_topic_domain("UFC 320 weigh-ins"), "ufc")
        self.assertEqual(_domain_for_feed("ufc", ["ufc", "mma"]), "ufc")


class NeutralSignalTests(unittest.TestCase):
    def test_a_neutral_topic_on_tapin_skips_finance_and_music(self):
        # Wave 104: odds runs - TapIn covers sports (extra_domains), and a player-only NBA
        # topic reads neutral too.
        from apis.register_signals import _gated_signal_names
        from apis.topic_scorer import infer_topic_domain

        topic = "Pokemon at 5 PM"
        self.assertEqual(infer_topic_domain(topic), "neutral")
        gated = _gated_signal_names(topic, "tapin")
        for name in ("fred", "coingecko", "lastfm", "sec_edgar"):
            self.assertIn(name, gated)
        self.assertNotIn("odds", gated)
        self.assertNotIn("rawg", gated)
        self.assertEqual(_gated_signal_names(topic), set())
        self.assertEqual(_gated_signal_names(topic, "default"), set())

    def test_a_football_topic_still_runs_sports_signals(self):
        from apis.register_signals import _gated_signal_names

        gated = _gated_signal_names(
            "Manchester City ofund guilty, what does this mean for the prem", "tapin"
        )
        self.assertNotIn("odds", gated)
        self.assertIn("rawg", gated)


class RateLimitCoolTests(unittest.TestCase):
    def setUp(self):
        from core import llm_router

        # Wave 104: the cooldown outlived this test and reached the next one in the process.
        self.addCleanup(llm_router._llm_cool_until.clear)

    def test_a_429_cools_the_provider_and_does_not_disable_it(self):
        from core import llm_router

        exc = SimpleNamespace(
            status_code=429, response=SimpleNamespace(headers={"Retry-After": "30"})
        )
        llm_router.cool_provider("openrouter", exc)
        self.assertNotIn("openrouter", llm_router.disabled_providers())
        with patch.object(llm_router, "_provider_available", return_value=True):
            names = [provider for provider, _model in llm_router._resolve_chain("cheap")]
        # Wave 104: it waits at the end of the chain instead of leaving it.
        self.assertEqual(names[-1], "openrouter")
        later = llm_router.time.monotonic() + 31
        with (
            patch.object(llm_router.time, "monotonic", return_value=later),
            patch.object(llm_router, "_provider_available", return_value=True),
        ):
            names = [provider for provider, _model in llm_router._resolve_chain("cheap")]
        self.assertIn("openrouter", names)

    def test_a_huge_retry_after_is_capped(self):
        from core import llm_router

        exc = SimpleNamespace(
            status_code=429, response=SimpleNamespace(headers={"Retry-After": "99999"})
        )
        seconds = llm_router.cool_provider("openrouter", exc)
        self.assertLessEqual(seconds, 60)


class StaleReadOnceTests(unittest.TestCase):
    def test_three_loads_judge_each_stale_line_once(self):
        from datetime import date

        from core.facts.recency import stale_preview
        from core.obsidian_facts import load_fact_records
        from core.vault import index as vault_index

        preview = "Topuria vs Holloway is set for Oct 4 in Abu Dhabi."
        with tempfile.TemporaryDirectory() as tmp:
            vault = os.path.join(tmp, "vault")
            note = os.path.join(vault, "tapin")
            os.makedirs(note)
            with open(os.path.join(note, "topuria.md"), "w", encoding="utf-8") as handle:
                handle.write(
                    "---\nchannel: tapin\ndate: 2026-09-20\n---\n# Topuria\n"
                    f"- {preview}\n- Topuria is the featherweight champion.\n"
                )
            vault_index.clear_cache()
            calls: list[str] = []

            def counting(bullet, verified, today):
                calls.append(bullet)
                return stale_preview(bullet, verified, today)

            with (
                patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}),
                patch("core.obsidian_facts.stale_preview", counting),
            ):
                for _ in range(3):
                    claims = [
                        record.claim
                        for record in load_fact_records(
                            "Topuria", "tapin", today=date(2026, 10, 10)
                        )
                    ]
                self.assertNotIn(preview, claims)
                self.assertEqual(calls.count(preview), 1)
                load_fact_records("Topuria", "tapin", today=date(2026, 10, 11))
            vault_index.clear_cache()
        self.assertEqual(calls.count(preview), 2)


class OvernightDraftTests(unittest.TestCase):
    def test_twenty_two_waiting_drafts_none_and_says_so(self):
        from core.overnight import OvernightResult, _run_overnight_body, render_overnight

        result = OvernightResult(channel_id="tapin")
        with (
            patch("core.batch_review.pending_drafts", return_value=[object()] * 22),
            patch("core.overnight_quota.adjust_count", return_value=(3, "")),
            patch("core.batch_generation.collect_topics") as collect,
        ):
            _run_overnight_body("tapin", result, count=3, topics=None, file=None, facts_file=None)
        collect.assert_not_called()
        self.assertEqual(result.requested, 0)
        self.assertIn("22", result.draft_line)
        text = render_overnight(result)
        self.assertIn("22", text)
        self.assertNotIn("best bets unavailable", text)

    def test_no_waiting_drafts_keeps_the_request(self):
        from core.overnight import draft_count

        self.assertEqual(draft_count(0, 3), (3, ""))


class WatchPublishTests(unittest.TestCase):
    def _row(self, video_id, run_id):
        return SimpleNamespace(
            id=run_id,
            content_run_id=run_id,
            youtube_video_id=video_id,
            privacy_status="unlisted",
            channel_id="tapin",
        )

    def _run(self, run_id, title):
        return SimpleNamespace(
            id=run_id,
            title=title,
            mp4_path=f"output/tapin/{run_id}.mp4",
            quality_json='{"grade": "B"}',
            features_json='{"technical_qc": {"video_duration": 42}}',
        )

    def test_option_7_is_watch_and_publish(self):
        from core.ui import prompt_startup_mode

        said: list[str] = []
        prompts: list[str] = []
        with patch("core.intelligence_report.intelligence_mode_enabled", return_value=False):
            mode = prompt_startup_mode(
                print_fn=lambda *args: said.append(" ".join(str(x) for x in args)),
                input_fn=lambda prompt: prompts.append(prompt) or "7",
            )
        self.assertEqual(mode, "watch_publish")
        self.assertTrue(any("7)" in line and "Watch and publish" in line for line in said))
        self.assertTrue(any("1-7" in prompt for prompt in prompts))

    def test_one_pass_publishes_only_the_one_chosen_now(self):
        from publishing.go_public import watch_and_publish

        rows = [self._row("aaa", 10), self._row("bbb", 11)]
        runs = {10: self._run(10, "Chargers"), 11: self._run(11, "Ballon")}
        answers = iter(["n", "s"])
        said: list[str] = []
        calls: list[tuple] = []

        def apply(video_id, **kwargs):
            calls.append((video_id, kwargs.get("dry_run")))
            return SimpleNamespace(status="dry_run", detail="planned")

        with (
            patch("publishing.go_public.unlisted_holds", return_value=rows),
            patch("publishing.go_public._run_for_hold", side_effect=lambda rid: runs[rid]),
            patch("publishing.go_public.load_features", return_value={}),
            patch("core.facts.claim_confirm.run_flagged_claims", return_value=[]),
            patch("publishing.go_public.apply_go_public", side_effect=apply),
        ):
            decisions = watch_and_publish(
                "tapin", ask=lambda _prompt: next(answers), print_fn=said.append
            )
        text = "\n".join(said)
        self.assertIn("output/tapin/10.mp4", text)
        self.assertIn("42s", text)
        self.assertIn("grade B", text)
        self.assertEqual(calls, [("aaa", False)])
        self.assertEqual(decisions, ["now", "keep"])  # wave 104: "s" is not a choice

    def test_a_flagged_claim_is_not_published(self):
        from publishing.go_public import watch_and_publish

        claim = SimpleNamespace(text="the score was 3-0")
        with (
            patch("publishing.go_public.unlisted_holds", return_value=[self._row("aaa", 10)]),
            patch("publishing.go_public._run_for_hold", return_value=self._run(10, "Chargers")),
            patch("publishing.go_public.load_features", return_value={}),
            patch("core.facts.claim_confirm.run_flagged_claims", return_value=[claim]),
            patch("publishing.go_public.apply_go_public") as apply,
        ):
            decisions = watch_and_publish(
                "tapin", ask=lambda _prompt: "n", print_fn=lambda _line: None
            )
        apply.assert_not_called()
        self.assertEqual(decisions, ["refused"])

    def test_set_aside_is_not_offered_again(self):
        from publishing.go_public import watch_and_publish

        stored: dict[int, dict] = {}

        def merge(run_id, updates):
            stored.setdefault(int(run_id), {}).update(updates)

        def load(run_id):
            return dict(stored.get(int(run_id or 0), {}))

        row = self._row("aaa", 10)
        with (
            patch("publishing.go_public.unlisted_holds", return_value=[row]),
            patch("publishing.go_public._run_for_hold", return_value=self._run(10, "Chargers")),
            patch("publishing.go_public.load_features", side_effect=load),
            patch("publishing.go_public.merge_features", side_effect=merge),
            patch("core.facts.claim_confirm.run_flagged_claims", return_value=[]),
            patch("publishing.go_public.apply_go_public") as apply,
        ):
            first = watch_and_publish("tapin", ask=lambda _prompt: "a", print_fn=lambda _l: None)
            second = watch_and_publish("tapin", ask=lambda _prompt: "n", print_fn=lambda _l: None)
        apply.assert_not_called()
        self.assertEqual(first, ["aside"])
        self.assertEqual(second, [])
        self.assertTrue(stored[10].get("watch_aside"))

    def test_now_still_refuses_a_grounding_hold(self):
        from publishing.go_public import watch_and_publish

        row = self._row("aaa", 10)
        written: list = []

        class Repo:
            def list_uploaded_for_channel(self, _channel):
                return [row]

            def update(self, *args, **kwargs):
                written.append(args)

        said: list[str] = []
        with (
            patch("publishing.go_public.unlisted_holds", return_value=[row]),
            patch("publishing.go_public._run_for_hold", return_value=self._run(10, "Chargers")),
            patch("publishing.go_public.load_features", return_value={}),
            patch("core.facts.claim_confirm.run_flagged_claims", return_value=[]),
            patch("publishing.go_public.override_held", return_value=True),
            patch("publishing.go_public._run_title", return_value="Chargers"),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=Repo(),
            ),
        ):
            watch_and_publish("tapin", ask=lambda _prompt: "n", print_fn=said.append)
        text = "\n".join(said)
        self.assertIn("refused", text)
        self.assertIn("grounding", text)
        self.assertEqual(written, [])


_CLAIM = "the score was 3-0 in the first half"
_SOURCE = "ESPN reported the score was 3-0 in the first half"


def _claim_features() -> dict:
    return {
        "claim_verification": {
            "unsupported": [_CLAIM],
            "unsupported_types": ["score"],
            "supported": 0,
            "total": 1,
        },
        "auto_research": {"kept_lines": [_SOURCE]},
        "grounding_override": True,
        "grounding_override_claims": [_CLAIM],
    }


class ReviewClaimTests(unittest.TestCase):
    def test_the_room_lists_the_claim_and_its_source_line(self):
        from core.review_bind import claim_rows

        with (
            patch("core.facts.claim_confirm.load_features", return_value=_claim_features()),
            patch("core.facts.claim_confirm._snapshot_lines", return_value=[]),
        ):
            rows = claim_rows(10)
        self.assertEqual(rows[0]["claim"], _CLAIM)
        self.assertIn("ESPN", rows[0]["source_line"])

    def test_an_empty_source_does_not_confirm(self):
        from core.review_bind import confirm_from_room

        with patch("core.facts.claim_confirm.merge_features") as merge:
            result = confirm_from_room(10, 1, "")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("source", result["detail"])
        merge.assert_not_called()

    def test_go_public_stays_off_while_a_claim_is_open(self):
        from core.review_bind import go_public_from_room

        with (
            patch("core.facts.claim_confirm.load_features", return_value=_claim_features()),
            patch("core.facts.claim_confirm._snapshot_lines", return_value=[]),
            patch("publishing.go_public.apply_go_public") as apply,
        ):
            result = go_public_from_room(10, "abc123", channel_id="tapin")
        apply.assert_not_called()
        self.assertEqual(result["status"], "refused")
        self.assertIn("flagged", result["detail"])

    def test_cut_names_the_sentence(self):
        from core.review_bind import reject_from_room

        script = "Intro. The score was 3-0 in the first half. Outro."
        with (
            patch("core.facts.claim_confirm.load_features", return_value=_claim_features()),
            patch("core.facts.claim_confirm._snapshot_lines", return_value=[]),
            patch("core.facts.claim_confirm.full_script", return_value=script),
            patch("core.facts.claim_confirm.merge_features"),
        ):
            result = reject_from_room(10, 1)
        self.assertEqual(result["status"], "rejected")
        self.assertTrue(any("3-0" in line for line in result["sentences"]))


try:
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]
    QLabel = QLineEdit = QPushButton = None  # type: ignore[misc, assignment]

from tests.qt_support import requires_qt


@requires_qt
class ReviewRoomClaimTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def _window(self):
        from desktop.review import ReviewWindow

        with (
            patch("core.facts.claim_confirm.load_features", return_value=_claim_features()),
            patch("core.facts.claim_confirm._snapshot_lines", return_value=[]),
        ):
            return ReviewWindow(
                context={
                    "mp4_path": "",
                    "run_id": 10,
                    "channel_id": "tapin",
                    "unlisted_url": "https://youtu.be/abc123",
                    "grade": "B",
                }
            )

    def test_the_window_lists_the_claim_and_keeps_go_public_off(self):
        window = self._window()
        labels = [w.text() for w in window.findChildren(QLabel)]
        self.assertTrue(any(_CLAIM in text for text in labels))
        self.assertTrue(any("ESPN" in text for text in labels))
        buttons = {w.text(): w for w in window.findChildren(QPushButton)}
        self.assertFalse(buttons["Go public"].isEnabled())
        window.findChildren(QLineEdit)[0].setText("")
        buttons["Confirm"].click()
        self.assertFalse(buttons["Go public"].isEnabled())
        labels = [w.text() for w in window.findChildren(QLabel)]
        self.assertTrue(any(_CLAIM in text for text in labels))
        window.close()

    def test_a_source_clears_the_claim_and_go_public_turns_on(self):
        from desktop.review import ReviewWindow

        store = {"features": _claim_features()}

        def load(_run_id):
            return store["features"]

        def merge(_run_id, updates):
            store["features"] = {**store["features"], **updates}

        with (
            patch("core.facts.claim_confirm.load_features", side_effect=load),
            patch("core.facts.claim_confirm._snapshot_lines", return_value=[]),
            patch("core.facts.claim_confirm.merge_features", side_effect=merge),
            patch("core.facts.claim_confirm.merge_quality"),
            patch("core.facts.claim_confirm._save_confirmed_fact"),
        ):
            window = ReviewWindow(
                context={
                    "mp4_path": "",
                    "run_id": 10,
                    "channel_id": "tapin",
                    "unlisted_url": "https://youtu.be/abc123",
                }
            )
            buttons = {w.text(): w for w in window.findChildren(QPushButton)}
            self.assertFalse(buttons["Go public"].isEnabled())
            window.findChildren(QLineEdit)[0].setText("https://espn.com/score")
            buttons["Confirm"].click()
            buttons = {w.text(): w for w in window.findChildren(QPushButton)}
            self.assertTrue(buttons["Go public"].isEnabled())
            self.assertNotIn("Confirm", buttons)
            labels = [w.text() for w in window.findChildren(QLabel)]
            self.assertFalse(any(text.startswith("1. ") for text in labels))
        window.close()


class FollowUpRepeatTests(unittest.TestCase):
    def test_the_ufc_follow_up_does_not_repeat_its_topic(self):
        from core.topic_graph import follow_up_seed, record_published_topic

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "topic_graph.json")
            with patch("config.paths.TOPIC_GRAPH_FILE", path):
                record_published_topic("tapin", "UFC Illia Islam")
                seed = follow_up_seed("tapin")
        self.assertTrue(seed is None or seed.topic.strip().lower() != "ufc illia islam")
        if seed is not None:
            self.assertNotIn("continue UFC Illia Islam (", seed.rationale)
