"""Wave 114 (2026-10-18): the next ten.

Measured first: wave 113's unattended sync also tried the generic "default" channel, which has
no sign-in, and keeps retrying it; run 154 was moved on YouTube to 10-21 02:00Z (probably in
Studio) while its record kept the old slot, so the Buffer round sent its TikTok and Instagram
posts for a day before YouTube publishes it, and the privacy sync then wrote "private" over it.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc)
SLOT = "2026-10-21T02:00:00Z"


def _service(statuses):
    """videos.list(part=status) answering {id: (privacyStatus, publishAt or "")}."""
    service = MagicMock()

    def _list(part, id, maxResults):
        call = MagicMock()
        items = []
        for vid in id.split(","):
            if vid in statuses:
                privacy, publish_at = statuses[vid]
                status = {"privacyStatus": privacy}
                if publish_at:
                    status["publishAt"] = publish_at
                items.append({"id": vid, "status": status})
        call.execute.return_value = {"items": items}
        return call

    service.videos.return_value.list.side_effect = _list
    return service


class SyncSignInTests(unittest.TestCase):
    """#1518: the worker's daily sync skips a channel nobody signed in for."""

    def test_a_channel_with_no_sign_in_is_skipped(self):
        from jobs import worker

        with tempfile.TemporaryDirectory() as tmp:
            token = os.path.join(tmp, "tapin.json")
            with open(token, "w", encoding="utf-8") as handle:
                handle.write("{}")
            paths = {"tapin": token, "default": os.path.join(tmp, "default.json")}
            with (
                patch("config.channels.active_channel_ids", return_value=["tapin", "default"]),
                patch(
                    "youtube.oauth.token_path_for_channel", side_effect=lambda cid=None: paths[cid]
                ),
                patch("analytics.sync_metrics.maybe_sync") as sync,
            ):
                worker._sync_metrics()
        sync.assert_called_once_with("tapin")


class ScheduledHoldTests(unittest.TestCase):
    """#1519: a video YouTube still holds for its slot keeps its record, at YouTube's slot."""

    def test_drift_leaves_a_held_video_alone(self):
        from analytics.privacy_sync import drift

        self.assertEqual(drift({"e7G": "public"}, {"e7G": "private"}, held={"e7G"}), {})
        self.assertEqual(
            drift({"e7G": "public"}, {"e7G": "private"}), {"e7G": ["public", "private"]}
        )

    def test_the_status_read_keeps_the_slot(self):
        from analytics.privacy_sync import fetch_status

        with patch("apis.youtube_quota.record_usage"):
            got = fetch_status(
                _service({"e7G": ("private", SLOT), "a": ("public", "")}), ["e7G", "a"]
            )
        self.assertEqual(got["e7G"], {"privacy": "private", "publish_at": SLOT})
        self.assertEqual(got["a"], {"privacy": "public", "publish_at": ""})

    def test_the_sync_moves_the_slot_and_keeps_it_public(self):
        from analytics import privacy_sync

        row = SimpleNamespace(id=7, youtube_video_id="e7G", privacy_status="private", content_run_id=154,
                              published_at=datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc), metrics_json="{}")  # fmt: skip
        updates = []
        log = SimpleNamespace(list_uploaded_for_channel=lambda channel: [row],
                              update=lambda rid, data: updates.append((rid, data)))  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch("apis.youtube_quota.record_usage"),
            patch.object(privacy_sync, "_publish_runs", return_value=[]),
        ):
            report = privacy_sync.sync_privacy(
                "tapin", service=_service({"e7G": ("private", SLOT)})
            )
        self.assertEqual(report["changed"], [])
        self.assertEqual(updates, [(7, {"privacy_status": "public",
                                        "published_at": datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)})])  # fmt: skip
        self.assertEqual(report["rescheduled"][0]["run_id"], 154)

    def test_the_buffer_round_waits_for_youtube(self):
        from publishing import crosspost

        with (
            patch(
                "analytics.privacy_sync._service",
                return_value=_service({"e7G": ("private", SLOT), "b": ("public", "")}),
            ),
            patch("apis.youtube_quota.record_usage"),
            patch("youtube.oauth.live_youtube_forbidden", return_value=False),
        ):
            held = crosspost._held_by_youtube("tapin", {154: "e7G", 155: "b"})
        self.assertEqual(held, {154: SLOT})

    def test_a_failed_read_holds_nothing(self):
        from publishing import crosspost

        with patch("analytics.privacy_sync._service", side_effect=RuntimeError("no sign-in")):
            self.assertEqual(crosspost._held_by_youtube("tapin", {154: "e7G"}), {})

    def test_a_removed_copy_is_hosted_again(self):
        from publishing.crosspost import _needs_hosting

        self.assertTrue(_needs_hosting({}))
        self.assertFalse(_needs_hosting({"object_key": "tapin/run154.mp4", "url": "https://x"}))
        self.assertTrue(
            _needs_hosting({"object_key": "tapin/run154.mp4", "object_removed": "2026-10-19"})
        )


class FormatTests(unittest.TestCase):
    """B: #1491 Shorts against Shorts, #1323 which content converts, #1314 compilation hours."""

    def test_a_long_video_is_read_apart(self):
        from core import channel_health

        rates = {98: 0.31, 99: 0.33, 109: 0.30, 110: 0.32, 111: 0.29, 120: 0.11}
        info = {rid: {"seconds": 406.0 if rid == 120 else 40.0} for rid in rates}
        with (
            patch("core.engagement_predictor.run_engagement_map", return_value=rates),
            patch.object(channel_health, "_engagement_info", return_value=info),
            patch.object(channel_health, "_unmeasured_recent", return_value=[]),
        ):
            sub = channel_health._engagement_sub("tapin")
        self.assertEqual(sub.status, channel_health.GREEN, sub.detail)
        self.assertIn("(runs 98-111)", sub.detail)
        self.assertIn("1 long video read apart (median 11%", sub.detail)

    def test_subscribers_per_1000_by_domain_and_format(self):
        from analytics import growth

        rows = [{"run_id": 1, "subs": 1, "views": 500, "paid": 0}, {"run_id": 2, "subs": 0, "views": 300, "paid": 0},
                {"run_id": 3, "subs": 1, "views": 250, "paid": 0}, {"run_id": 4, "subs": 0, "views": 50, "paid": 0}]  # fmt: skip
        kinds = {
            1: ("gaming", "Shorts"),
            2: ("gaming", "Shorts"),
            3: ("nfl", "Shorts"),
            4: ("ufc", "long"),
        }
        with patch.object(growth, "_kind", side_effect=lambda rid: kinds[rid]):
            got = growth.conversion(rows)
        self.assertEqual([(g["domain"], g["format"], g["per_1k"]) for g in got],
                         [("gaming", "Shorts", 1.25), ("nfl", "Shorts", 4.0)])  # fmt: skip
        line = growth.conversion_line({"subscribers": {"by": got}})
        self.assertTrue(
            line.startswith("subscribers per 1,000 organic views: gaming Shorts 1.2"), line
        )

    def _compilations(self, runs, logs):
        from core import ypp_readiness

        with (
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=SimpleNamespace(list_for_channel=lambda c: runs)),
            patch("storage.repositories.publish_log.get_publish_log_repository",
                  return_value=SimpleNamespace(list_uploaded_for_channel=lambda c: logs)),
        ):  # fmt: skip
            return ypp_readiness.compilation_line("tapin")

    def test_what_the_compilations_add(self):
        week = SimpleNamespace(
            id=200, features_json=json.dumps({"compilation": {"week": "2026-10-19"}})
        )
        short = SimpleNamespace(id=150, features_json="{}")
        log = SimpleNamespace(
            content_run_id=200, metrics_json=json.dumps({"estimated_minutes_watched": 120})
        )
        self.assertIn("none made yet", self._compilations([short], []))
        self.assertIn("1 made, none measured yet", self._compilations([week, short], []))
        line = self._compilations([week, short], [log])
        self.assertIn("1 made, 2.0 long-form hours from 1 measured", line)
        self.assertIn("4,000 hours is", line)


class StopRuleTests(unittest.TestCase):
    """C: #354 a test that ends, #1423 the intro read with it, #1507 the hook line."""

    def test_ten_each_without_a_winner_is_no_difference(self):
        from core.experiment_stats import evaluate

        mixed = [0.30, 0.34, 0.28, 0.36, 0.31, 0.33, 0.29, 0.35, 0.32, 0.30]
        self.assertEqual(
            evaluate({"a": mixed, "b": list(reversed(mixed))})["status"], "no_difference"
        )
        self.assertEqual(evaluate({"a": mixed[:6], "b": mixed[:6]})["status"], "no_clear_winner")
        self.assertEqual(evaluate({"a": mixed[:5], "b": mixed[:6]})["status"], "collecting")
        clear = evaluate({"a": [0.6] * 10, "b": [0.2] * 10})
        self.assertEqual((clear["status"], clear["winner"]), ("winner", "a"))

    def test_the_intro_verdict(self):
        from analytics.growth import intro_verdict

        self.assertEqual(intro_verdict([0.3] * 5, [0.4] * 4), "reads at 6 each")
        self.assertTrue(
            intro_verdict([0.2] * 8, [0.6] * 8).startswith("no intro holds more viewers - ")
        )
        mixed = [0.30, 0.34, 0.28, 0.36, 0.31, 0.33, 0.29, 0.35, 0.32, 0.30]
        self.assertTrue(
            intro_verdict(mixed, list(reversed(mixed))).startswith("no real difference")
        )

    def test_the_experiment_report_says_stop(self):
        from core import experiments

        report = {"lever": "intro", "assigned": {"on": 10, "off": 10},
                  "evaluation": {"status": "no_difference", "winner": None, "arms": {}}}  # fmt: skip
        lines: list[str] = []
        experiments._display_one(report, print_fn=lines.append)
        self.assertTrue(any("Settled: no real difference at 10 each" in ln for ln in lines), lines)

    def test_the_hook_line_says_the_retune_waits(self):
        from analytics import hook_learning

        got = {"ready": True, "n": 14, "r": -0.42, "needs": 21, "traits": [], "min": 8}
        with (
            patch.object(hook_learning, "learn", return_value=got),
            patch.object(hook_learning, "_against_rules", return_value=[]),
        ):
            line = hook_learning.render_line("tapin")
        self.assertIn("settles at n=21", line)
        self.assertIn("retune waits for about 85", line)


class EmptyDayTests(unittest.TestCase):
    """D: #1428 (the operator: it renders and waits) - one more render for an empty day."""

    def _limit(self, entries, *, base=2):
        from core import batch_review

        with (
            patch.object(batch_review, "unattended_limit", return_value=base),
            patch("analytics.upload_queue.list_queue_entries", **entries),
        ):
            return batch_review.overnight_render_limit("tapin", now=NOW)

    def test_one_more_only_when_the_next_day_is_empty(self):
        soon = SimpleNamespace(publish_at=NOW + timedelta(hours=10))
        later = SimpleNamespace(publish_at=NOW + timedelta(hours=40))
        self.assertEqual(self._limit({"return_value": [later]})[0], 3)
        self.assertEqual(self._limit({"return_value": [soon, later]}), (2, ""))
        self.assertEqual(self._limit({"return_value": []}, base=0), (0, ""))
        self.assertEqual(self._limit({"side_effect": RuntimeError("db")}), (2, ""))

    def test_the_morning_says_why(self):
        from core.overnight import OvernightResult, render_lines

        result = OvernightResult(channel_id="tapin")
        result.renders = {"rendered": [170], "queued": [170], "failed": [], "waiting": [],
                          "empty_day": "nothing is scheduled for the next 24 hours - one more render"}  # fmt: skip
        self.assertTrue(
            any(ln.startswith("One more render tonight") for ln in render_lines(result))
        )


def _curve(bump_from=0.5, bump_to=0.75):
    """A falling curve (1.3 -> 0.2) with retention held well above it between two fractions."""
    out = []
    for i in range(1, 101):
        x = i / 100.0
        y = 1.3 - 1.1 * x + (0.25 if bump_from <= x <= bump_to else 0.0)
        out.append([round(x, 2), round(y, 3)])
    return out


def _words(n=40, gap=1.5):
    """Sentences of three words, one every `gap` seconds of audio."""
    words = []
    for k in range(n):
        t = k * gap
        words += [{"word": f"S{k}", "start": t, "end": t + 0.4}, {"word": "says", "start": t + 0.45, "end": t + 0.8},
                  {"word": "this.", "start": t + 0.85, "end": t + 1.2}]  # fmt: skip
    return words


class RecutTests(unittest.TestCase):
    """D: #1057 (the operator: the best-held window, a draft that waits)."""

    def test_the_window_is_where_retention_beats_the_trend(self):
        from video.recut import best_window

        start, end = best_window(_curve(), 60.0, start_after=2.65)  # held from 30 s to 45 s
        self.assertLessEqual(start, 30.6)
        self.assertGreaterEqual(end, 44.4)
        self.assertTrue(20.0 <= end - start <= 40.0)

    def test_it_never_starts_inside_the_intro_or_runs_into_the_end(self):
        from video.recut import best_window

        start, _end = best_window(_curve(0.0, 0.3), 60.0, start_after=2.65)
        self.assertGreaterEqual(start, 2.65)
        self.assertIsNone(best_window(_curve(), 20.0, start_after=2.65))
        self.assertLessEqual(best_window(_curve(0.7, 1.0), 60.0, start_after=2.65)[1], 56.0)

    def test_it_snaps_to_whole_sentences(self):
        from video.recut import snap

        start, end, sentence = snap((30.2, 52.0), _words(), 2.15)
        self.assertEqual(sentence, "S18 says this.")  # 30.2 s falls inside S18 (29.15-30.35)
        self.assertAlmostEqual(start, 18 * 1.5 + 2.15)
        self.assertTrue(20.0 <= end - start <= 40.5)

    def test_the_cut_seeks_and_shows_the_card_first(self):
        from video.recut import CARD_SECONDS, recut_argv

        argv = recut_argv("in.mp4", "out.mp4", start=30.0, end=55.0, card="card.png")
        self.assertLess(argv.index("-ss"), argv.index("-i"))
        self.assertEqual(argv[argv.index("-t") + 1], "25.00")
        graph = argv[argv.index("-filter_complex") + 1]
        self.assertIn(f"between(t,0,{CARD_SECONDS})", graph)

    def test_the_title_is_the_sentence_when_it_reads_as_one(self):
        from video.recut import recut_title

        self.assertEqual(recut_title("Pereira never fought a wrestler this good.", "Old"),
                         "Pereira never fought a wrestler this good")  # fmt: skip
        self.assertEqual(
            recut_title("Short.", "UFC 310 preview"), "UFC 310 preview - the moment that held"
        )

    def test_apply_records_a_run_that_waits(self):
        from video import recut

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "v.mp4")
            with open(src, "wb") as handle:
                handle.write(b"x")
            source = SimpleNamespace(id=99, mp4_path=src, title="Old", description="Desc", tags_json="[]",
                                     input_topic="topic")  # fmt: skip
            plan = {"run_id": 99, "start": 30.0, "end": 55.0, "sentence": "S19 says this.",
                    "title": "S19 says this", "stayed": 0.52, "video_id": "JX8"}  # fmt: skip

            def cut(argv, **_kw):
                with open(argv[-1], "wb") as out:
                    out.write(b"y")
                return SimpleNamespace(returncode=0)

            with (
                patch("storage.repositories.content_runs.get_content_run_repository",
                      return_value=SimpleNamespace(get=lambda rid: source)),
                patch("core.run_recorder.record_content_run", return_value=201) as record,
            ):  # fmt: skip
                made, where = recut.make_recut("tapin", plan, run=cut)
        self.assertEqual(made, 201)
        self.assertTrue(where.endswith("v.recut.mp4"))
        kwargs = record.call_args.kwargs
        self.assertEqual(kwargs["status"], "rendered")
        self.assertEqual(kwargs["features"]["recut_of"]["run_id"], 99)

    def test_the_teaser_starts_after_the_runs_own_intro(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "run164.mp4")
            open(mp4, "wb").close()
            run = SimpleNamespace(id=164, channel_id="tapin", mp4_path=mp4,
                                  quality_json=json.dumps({"opening": {"intro": False, "intro_seconds": 0.0}}))  # fmt: skip
            with (
                patch("storage.repositories.content_runs.get_content_run_repository",
                      return_value=SimpleNamespace(get=lambda rid: run)),
                patch("video.teaser.create_teaser", return_value="t.mp4") as make,
                patch("builtins.print"),
            ):  # fmt: skip
                COMMANDS["teaser"][1](SimpleNamespace(run_id=164))
        self.assertEqual(make.call_args.kwargs.get("start"), 0.0)


class LockTests(unittest.TestCase):
    """E: #457 (the operator: a lock and a check, CI unchanged)."""

    def test_drift_names_each_package_that_differs(self):
        from core.ops_doctor import lock_drift

        lock = {"packages": [{"name": "content-machine", "directory": {"path": "."}},
                             {"name": "Anyio", "version": "4.13.0"}, {"name": "certifi", "version": "2026.4.22"},
                             {"name": "rich", "version": "14.0.0"}]}  # fmt: skip
        installed = {"anyio": "4.13.0", "Certifi": "2026.10.18"}
        self.assertEqual(lock_drift(lock, installed),
                         ["certifi lock 2026.4.22, installed 2026.10.18", "rich lock 14.0.0, not installed"])  # fmt: skip

    def test_the_lock_covers_every_direct_dependency(self):
        import re
        import tomllib

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "pyproject.toml"), "rb") as handle:
            project = tomllib.load(handle)["project"]
        with open(os.path.join(root, "pylock.toml"), "rb") as handle:
            locked = {p["name"].lower().replace("_", "-") for p in tomllib.load(handle)["packages"]}
        wanted = [
            *project.get("dependencies", []),
            *project.get("optional-dependencies", {}).get("app", []),
        ]
        missing = []
        for requirement in wanted:
            if ";" in requirement:  # a platform marker: locked on Windows only when it applies
                continue
            name = re.match(r"[A-Za-z0-9_.-]+", requirement).group(0).lower().replace("_", "-")
            if name not in locked:
                missing.append(name)
        self.assertEqual(missing, [])

    def test_no_lock_is_not_a_failure(self):
        from core import ops_doctor

        with patch.object(
            ops_doctor, "LOCK_FILE", os.path.join(tempfile.gettempdir(), "no-such-pylock.toml")
        ):
            ok, detail = ops_doctor.lock_check()
        self.assertTrue(ok)
        self.assertIn("pip lock", detail)


class CompilationDisclosureTests(unittest.TestCase):
    """#1522 (live 2026-10-19 05:23): the first compilation was scheduled public with no AI
    disclosure line - week_compile wrote its own description; the pre-publish check only warned."""

    def test_the_compilation_says_it_is_ai_assisted(self):
        from video import week_compile

        when = datetime(2026, 10, 15, tzinfo=timezone.utc)
        shorts = [{"run_id": i, "title": f"t{i}", "path": f"p{i}.mp4", "offset": 2.15,
                   "published_at": when + timedelta(hours=i)} for i in range(1, 6)]  # fmt: skip
        with (
            patch.object(week_compile, "week_shorts", return_value=shorts),
            patch.object(week_compile, "_duration", return_value=40.0),
            patch(
                "core.description_extras.ai_disclosure_line",
                return_value="Made with AI-assisted narration.",
            ),
        ):
            plan = week_compile.plan_week("tapin", now=NOW)
        self.assertTrue(plan.description.rstrip().endswith("Made with AI-assisted narration."))


if __name__ == "__main__":
    unittest.main()
