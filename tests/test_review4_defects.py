"""Defects found reviewing Cursor's 0e1c73e..93e5feb waves (review 4).

Every test here failed on unmodified 93e5feb. The shape is the one rules 17 and 20
were written for: a helper is unit-tested in isolation, so the suite stays green
while nothing in production ever calls it with real inputs.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from storage.repositories.content_runs import ContentRunRecord
from storage.repositories.publish_log import PublishLogRecord


def _run(run_id: int, topic: str) -> ContentRunRecord:
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic=topic,
        selected_topic=topic,
        status="completed",
        composite_score=60.0,
    )


def _log(run_id: int, rate: float, age_days: float) -> PublishLogRecord:
    return PublishLogRecord(
        id=run_id,
        content_run_id=run_id,
        channel_id="tapin",
        status="uploaded",
        metrics_json=json.dumps({"engaged_rate": rate}),
        published_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )


class TestRecencyDecayReachesTheRecommendation(unittest.TestCase):
    """#365 shipped `recency_weight` and `weighted_engaged_mean` and wired them into
    `get_best_bet` - but `_build_entries` never sets `age_days`, so every weight is
    `recency_weight(None) == 1.0` and the weighted mean equals the arithmetic mean it
    replaced. The only test drove the two helpers in isolation."""

    def test_a_stale_win_no_longer_outvotes_a_recent_one(self):
        from core.best_bet import get_best_bet

        runs = [_run(1, "UFC title fight fallout"), _run(2, "UFC main event fallout")]
        logs = [_log(1, 0.10, 400.0), _log(2, 0.40, 2.0)]
        run_repo, log_repo = MagicMock(), MagicMock()
        run_repo.list_for_channel.return_value = runs
        log_repo.list_timed_outcomes.return_value = logs

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bet = get_best_bet("tapin")

        self.assertIsNotNone(bet)
        assert bet is not None
        # Unweighted this is exactly 0.25. A 400-day-old sample carries 0.046 of the
        # weight of a 2-day-old one, so the honest number sits near the recent 0.40.
        self.assertGreater(
            bet.avg_engaged_rate,
            0.35,
            f"age_days never reached the weighting; got the arithmetic mean "
            f"{bet.avg_engaged_rate:.4f}",
        )

    def test_entries_carry_the_age_the_weighting_needs(self):
        from core.best_bet import _build_entries

        run_repo, log_repo = MagicMock(), MagicMock()
        run_repo.list_for_channel.return_value = [_run(1, "UFC title fight fallout")]
        log_repo.list_timed_outcomes.return_value = [_log(1, 0.10, 30.0)]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
        ):
            entries = _build_entries("tapin")
        self.assertAlmostEqual(float(entries[0]["age_days"] or -1), 30.0, places=0)


class TestNewQualityKeysHaveAReader(unittest.TestCase):
    """#302 plausibility, #596 competitor-title duplicate and #367 relative clock all
    write into the persisted `quality` dict. Nothing read any of them - not the
    dossier, not the booth, not the report card. `ungrounded_numeric`, written two
    lines above them in the same function, has a reader; these three were write-only."""

    def _dossier(self, quality: dict) -> str:
        from core.run_ledger import render_dossier

        record = _run(7, "UFC title fight fallout")
        record.quality_json = json.dumps(quality)
        repo = MagicMock()
        repo.get.return_value = record
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch("core.run_ledger._publish_for_run", return_value=None),
        ):
            return render_dossier(7)

    def test_the_dossier_names_a_ten_times_purse(self):
        text = self._dossier({"numeric_outliers": ["$50 million purse"]})
        self.assertIn("$50 million purse", text)

    def test_the_dossier_names_a_verbatim_competitor_title(self):
        text = self._dossier({"competitor_title_duplicate": "Title matches SportsCentre"})
        self.assertIn("SportsCentre", text)

    def test_the_dossier_resolves_tonight_to_a_date(self):
        text = self._dossier({"clock_tonight": "2026-09-08T21:00:00-04:00"})
        self.assertIn("2026-09-08T21:00", text)


class TestRetractionThrottleRunsBeforeTheNetwork(unittest.TestCase):
    """#686 throttles the *toast* to once per 24h, but the stamp is only consulted
    inside `maybe_toast_retractions` - after `watch_urls` has already fetched up to
    12 URLs at an 8s timeout each. `ops tray` calls this, so an interactive command
    can block for over a minute to decide it toasted this morning already."""

    def test_a_fresh_stamp_skips_the_fetch_entirely(self):
        from core.retraction_watch import notify_retractions_if_due

        fetched: list[str] = []

        def _fetch(url: str) -> str:
            fetched.append(url)
            return "body"

        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "stamp.json")
            with open(stamp, "w", encoding="utf-8") as fh:
                json.dump({"last": datetime.now(timezone.utc).isoformat()}, fh)
            trace = {"selected_topic": "UFC", "sources": ["https://example.com/a"]}
            with patch("core.review_booth.last_trace", return_value=trace):
                sent = notify_retractions_if_due(
                    "tapin", fetch=_fetch, stamp_path=stamp, toaster=lambda *a, **k: True
                )
        self.assertFalse(sent)
        self.assertEqual(fetched, [], "the 24h throttle fetched before checking the stamp")

    def test_the_urls_it_watches_are_not_carrying_json_punctuation(self):
        """`pairs_from_trace` scrapes URLs out of `json.dumps(trace)`, and the shared
        `_URL` pattern only stops at whitespace / `]` / `>` / `)` - so every URL comes
        back with the closing quote (and often a comma) attached. Every fetch 404s,
        the exception is swallowed by the blanket handler, and #341's trace path has
        never watched anything."""
        from core.retraction_watch import pairs_from_trace

        trace = {"selected_topic": "UFC", "sources": ["https://example.com/a", "http://b.io/x"]}
        urls = [url for url, _claim in pairs_from_trace(trace)]
        self.assertEqual(urls, ["https://example.com/a", "http://b.io/x"], urls)


class TestHudProbeCleansUpAfterItself(unittest.TestCase):
    """`detect_hud` mkdtemps a directory for the extracted frame and never removes it.
    `assign_owned_clips` calls it from `try_owned_beat_background`, which
    `render_video` calls on every render, for every clip whose index entry predates
    #683 - so each render leaks one temp directory per such clip, and re-probes them
    next time because the answer is never written back."""

    def test_no_temp_directory_survives_a_probe(self):
        import core.hud_detect as hud

        made: list[str] = []
        real_mkdtemp = tempfile.mkdtemp

        def _spy(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            made.append(path)
            return path

        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.mp4"
            clip.write_bytes(b"not really a video")
            with patch.object(tempfile, "mkdtemp", _spy):
                hud.detect_hud(str(clip))

        self.assertTrue(made, "detect_hud no longer extracts a frame; retarget this test")
        leaked = [p for p in made if os.path.isdir(p)]
        self.assertEqual(leaked, [], f"detect_hud leaked {len(leaked)} temp dir(s)")

    def test_the_same_clip_is_not_re_probed_within_a_process(self):
        """An overnight batch renders many drafts in one interpreter, and
        assign_owned_clips re-probes every legacy clip for each of them."""
        import core.hud_detect as hud

        calls: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.mp4"
            clip.write_bytes(b"not really a video")
            with patch.object(
                hud,
                "_load_frame",
                lambda path: calls.append(path) or None,  # type: ignore[func-returns-value]
            ):
                hud.detect_hud(str(clip))
                hud.detect_hud(str(clip))
        self.assertEqual(len(calls), 1, f"probed the same unchanged clip {len(calls)} times")


class TestPreCommitConfigDocumentsSomethingThatWorks(unittest.TestCase):
    """`.pre-commit-config.yaml` opens by telling the operator to run
    `pre-commit install`. This repo sets `core.hooksPath = .githooks`, so git never
    looks in `.git/hooks` and pre-commit refuses to install there - the documented
    command cannot produce a working hook on the one machine this repo runs on."""

    def test_it_does_not_tell_the_operator_to_run_pre_commit_install(self):
        text = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")
        mentions = [ln for ln in text.splitlines() if "pre-commit install" in ln]
        for line in mentions:
            self.assertIn(
                "Do NOT",
                line,
                f"core.hooksPath is .githooks, so this cannot take effect: {line.strip()}",
            )
        self.assertIn("hooksPath", text, "say why the install path is different here")


if __name__ == "__main__":
    unittest.main()
