"""#1113: a video is named by its title, not by the note its upload left.

2026-10-10: `ops growth` printed "best 968 (~8,400 units remaining today (1,600/10,000 used ..."
and the scoreboard printed 'best: "YouTube scheduled publish at 2026-10-08T02:00:00.000Z ..."'.
The publish log's `detail` holds the upload's note for every real upload (45 of 45 rows); only
a seeded row keeps a title there. Seven readers used it as the title.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

QUOTA = "~8,400 units remaining today (1,600/10,000 used; ~101 per search; ~5 uploads left)"
SCHEDULED = (
    "YouTube scheduled publish at 2026-10-08T02:00:00.000Z (target visibility: unlisted) "
    "| thumbnails.set OK"
)


def _row(detail, run_id=120, video_id="vid1", metrics=None):
    return SimpleNamespace(
        id=1,
        content_run_id=run_id,
        channel_id="tapin",
        youtube_video_id=video_id,
        detail=detail,
        metrics_json=json.dumps(metrics or {"views": 968}),
        published_at=None,
        status="uploaded",
        privacy_status="public",
        idempotency_key="",
    )


def _runs(titles):
    return SimpleNamespace(get=lambda rid: titles.get(int(rid)))


RUN = SimpleNamespace(title="People are blending Minecraft inside Elden Ring", selected_topic="x")


class VideoTitleTests(unittest.TestCase):
    def _title(self, row, titles=None):
        from storage.repositories import publish_log

        known = {120: RUN} if titles is None else titles
        with patch.object(publish_log, "_run_repo", return_value=_runs(known)):
            return publish_log.video_title(row)

    def test_an_upload_note_is_not_a_title(self):
        from storage.repositories.publish_log import is_upload_note

        for note in (QUOTA, SCHEDULED, "videos.insert complete", "thumbnails.set OK"):
            self.assertTrue(is_upload_note(note), note)
        self.assertFalse(is_upload_note("GTA 6 trailer 3 breakdown"))

    def test_the_runs_title_is_the_videos_title(self):
        self.assertEqual(self._title(_row(QUOTA)), RUN.title)
        self.assertEqual(self._title(_row(SCHEDULED)), RUN.title)

    def test_a_seeded_row_keeps_the_title_in_its_detail(self):
        row = _row("Wemby is already the best defender alive", run_id=None)
        self.assertEqual(self._title(row), "Wemby is already the best defender alive")

    def test_a_run_without_a_title_falls_back_to_its_topic(self):
        run = SimpleNamespace(title="", selected_topic="Chargers at 0-4")
        self.assertEqual(self._title(_row(QUOTA), {120: run}), "Chargers at 0-4")

    def test_nothing_known_is_untitled_never_the_note(self):
        self.assertEqual(self._title(_row(QUOTA, run_id=None)), "(untitled)")
        self.assertEqual(self._title(_row(QUOTA), {}), "(untitled)")

    def test_growth_names_the_best_video(self):
        from analytics import growth
        from storage.repositories import publish_log

        repo = SimpleNamespace(list_uploaded_for_channel=lambda cid: [_row(QUOTA)])
        with (
            patch.object(growth, "_repo", return_value=repo),
            patch.object(publish_log, "_run_repo", return_value=_runs({120: RUN})),
        ):
            rows = growth._rows("tapin")
        self.assertEqual(rows[0]["title"], RUN.title[:60])

    def test_the_post_time_domain_is_read_from_the_title(self):
        """The fallback domain was inferred from the quota note."""
        from analytics import post_timing
        from storage.repositories import publish_log

        run = SimpleNamespace(title="UFC 320 main card preview", selected_topic="")
        with patch.object(publish_log, "_run_repo", return_value=_runs({120: run})):
            domain = post_timing._domain_from_metrics(
                "{}", publish_log.video_title(_row(QUOTA)), "x"
            )
        self.assertEqual(domain, "ufc")


class NoReaderUsesTheNoteTests(unittest.TestCase):
    def test_no_module_reads_detail_as_a_title(self):
        """Seven readers did. A new one should call `video_title`."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        pattern = re.compile(r"title\s*=\s*[^\n]*\bdetail\b|\"title\":\s*[^\n]*\bdetail\b")
        hits = []
        for folder in ("analytics", "core"):
            for path in (root / folder).rglob("*.py"):
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line) and "video_title" not in line:
                        hits.append(f"{path.relative_to(root)}:{n}: {line.strip()}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
