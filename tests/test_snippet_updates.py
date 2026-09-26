"""#865 / #873: a snippet update always sends the whole writable snippet.

`rollback-publish --apply` sent `videos.update(part="status,snippet")` with a snippet
holding only `description`. YouTube requires `title` and `categoryId` whenever
`snippet` is in `part`, so the live call fails - or clears what it was not sent. No test
exercised it: every one was a dry run. #873 needs the same call to move already-uploaded
football videos from Gaming (20) to Sports (17), so both go through one helper.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord

LIVE = {
    "title": "City's 115 charges: what the verdict means",
    "description": "Original description.\n#football",
    "tags": ["premier league"],
    "categoryId": "20",
    "defaultLanguage": "en",
    "channelTitle": "TapIn",
    "publishedAt": "2026-09-26T10:00:00Z",
    "thumbnails": {"default": {"url": "x"}},
}


def _service(snippets):
    """A fake YouTube client that answers videos.list and records videos.update."""
    service = MagicMock()
    videos = service.videos.return_value

    def _list(part, id, **_kw):
        ids = id.split(",")
        req = MagicMock()
        req.execute.return_value = {
            "items": [{"id": i, "snippet": dict(snippets[i])} for i in ids if i in snippets]
        }
        return req

    videos.list.side_effect = _list
    return service


class WritableSnippetTests(unittest.TestCase):
    def test_keeps_only_writable_keys_and_applies_changes(self):
        from publishing.snippet_update import writable_snippet

        out = writable_snippet(LIVE, categoryId="17")
        self.assertEqual(out["categoryId"], "17")
        self.assertEqual(out["title"], LIVE["title"])
        self.assertEqual(out["description"], LIVE["description"])
        for read_only in ("channelTitle", "publishedAt", "thumbnails"):
            self.assertNotIn(read_only, out)

    def test_refuses_without_title_or_category(self):
        from publishing.snippet_update import writable_snippet

        with self.assertRaises(ValueError):
            writable_snippet({"description": "only this"})

    def test_fetch_batches_ids(self):
        from publishing.snippet_update import fetch_snippets

        ids = [f"v{i}" for i in range(120)]
        service = _service({i: LIVE for i in ids})
        got = fetch_snippets(service, ids)
        self.assertEqual(len(got), 120)
        self.assertEqual(service.videos.return_value.list.call_count, 3)


class RollbackApplyTests(unittest.TestCase):
    def test_apply_sends_the_whole_snippet_and_keeps_the_description(self):
        from publishing.rollback import apply_rollback

        service = _service({"abc": LIVE})
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true", "OBSIDIAN_VAULT_PATH": ""}),
            patch("youtube.oauth.get_youtube_service", return_value=service),
        ):
            result = apply_rollback("abc", correction="Source walked this back.", dry_run=False)
        self.assertEqual(result.status, "updated", result.detail)
        kwargs = service.videos.return_value.update.call_args.kwargs
        snippet = kwargs["body"]["snippet"]
        self.assertEqual(snippet["title"], LIVE["title"])
        self.assertEqual(snippet["categoryId"], "20")
        self.assertTrue(snippet["description"].startswith("Correction: Source walked this back."))
        self.assertIn("Original description.", snippet["description"])
        self.assertEqual(kwargs["body"]["status"]["privacyStatus"], "unlisted")

    def test_a_missing_video_is_refused_without_an_update(self):
        from publishing.rollback import apply_rollback

        service = _service({})
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true", "OBSIDIAN_VAULT_PATH": ""}),
            patch("youtube.oauth.get_youtube_service", return_value=service),
        ):
            result = apply_rollback("gone", correction="x", dry_run=False)
        self.assertEqual(result.status, "error")
        service.videos.return_value.update.assert_not_called()


def _row(rid, vid, run_id):
    return PublishLogRecord(
        id=rid,
        content_run_id=run_id,
        channel_id="tapin",
        youtube_video_id=vid,
        privacy_status="public",
        status="uploaded",
    )


class RecategorizeTests(unittest.TestCase):
    def _plan(self, rows, domains, titles=None):
        from publishing.recategorize import plan_recategorize

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        with (
            patch(
                "publishing.recategorize.run_domain", side_effect=lambda rid: domains.get(rid, "")
            ),
            patch(
                "publishing.recategorize._run_title",
                side_effect=lambda rid: (titles or {}).get(rid, ""),
            ),
        ):
            return plan_recategorize("tapin", repo=repo)

    def test_a_soccer_run_is_planned_for_sports(self):
        plan = self._plan([_row(1, "v98", 98)], {98: "soccer"})
        self.assertEqual([(p.video_id, p.category_id) for p in plan], [("v98", "17")])

    def test_old_runs_fall_back_to_the_title(self):
        plan = self._plan(
            [_row(1, "v50", 50)],
            {},
            titles={50: "Arsenal vs Chelsea: what the Premier League table says"},
        )
        self.assertEqual([p.category_id for p in plan], ["17"])

    def test_unknown_domain_is_left_alone(self):
        self.assertEqual(self._plan([_row(1, "v1", 1)], {1: "neutral"}), [])

    def test_dry_run_never_builds_a_client(self):
        from publishing.recategorize import apply_recategorize

        with patch("youtube.oauth.get_youtube_service") as svc:
            result = apply_recategorize("tapin", plan=[], dry_run=True)
        svc.assert_not_called()
        self.assertEqual(result["updated"], 0)

    def test_apply_updates_only_the_ones_that_differ(self):
        from publishing.recategorize import Recategorize, apply_recategorize

        service = _service({"a": LIVE, "b": {**LIVE, "categoryId": "17"}})
        plan = [Recategorize("a", 1, "soccer", "17"), Recategorize("b", 2, "soccer", "17")]
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("youtube.oauth.get_youtube_service", return_value=service),
        ):
            result = apply_recategorize("tapin", plan=plan, dry_run=False)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["already"], 1)
        body = service.videos.return_value.update.call_args.kwargs["body"]
        self.assertEqual(body["snippet"]["categoryId"], "17")
        self.assertEqual(body["snippet"]["title"], LIVE["title"])
        json.dumps(result)

    def test_ops_verb_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("recategorize", COMMANDS)


if __name__ == "__main__":
    unittest.main()
