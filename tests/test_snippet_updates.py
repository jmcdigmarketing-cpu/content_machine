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
        service = _service(dict.fromkeys(ids, LIVE))
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
    def _plan(self, rows, resolved, titles=None, legacy=None):
        from publishing.recategorize import plan_recategorize

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        with (
            patch(
                "publishing.recategorize.resolved_run_domain",
                side_effect=lambda rid: resolved.get(rid, ""),
            ),
            patch(
                "publishing.recategorize.run_domain",
                side_effect=lambda rid: (legacy or {}).get(rid, ""),
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

    def test_a_stale_stored_domain_loses_to_the_title(self):
        """Run 98 was made before soccer existed: it stored `domain: gaming`, and the
        operator's dry run planned the Manchester City video for Gaming (20)."""
        plan = self._plan(
            [_row(1, "VHGnKSGODzU", 98)],
            {},
            titles={
                98: "Manchester City guilty on 114 charges - what it means for the Premier League"
            },
            legacy={98: "gaming"},
        )
        self.assertEqual([(p.domain, p.category_id) for p in plan], [("soccer", "17")])

    def test_keywordless_title_keeps_the_stored_domain(self):
        plan = self._plan(
            [_row(1, "v7", 7)], {}, titles={7: "Is this the best one yet?"}, legacy={7: "gaming"}
        )
        self.assertEqual([p.category_id for p in plan], ["20"])

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


class ManageScopeTests(unittest.TestCase):
    """The operator's saved login could upload but not edit: go-public and recategorize
    --apply both died on YouTube's 403 "insufficient authentication scopes" (the second
    with a traceback). An edit now checks the token first and says how to fix it."""

    def test_missing_manage_scope_is_detected_from_the_token(self):
        from publishing.snippet_update import manage_scope_problem

        with (
            patch("youtube.oauth.token_path_for_channel", return_value=__file__),
            patch(
                "youtube.oauth._scopes_from_token_file",
                return_value=["https://www.googleapis.com/auth/youtube.upload"],
            ),
        ):
            msg = manage_scope_problem("tapin")
        self.assertIn("py -m youtube.oauth_setup --channel tapin", msg)

    def test_a_full_token_or_no_token_is_not_blocked_here(self):
        from publishing.snippet_update import manage_scope_problem

        with (
            patch("youtube.oauth.token_path_for_channel", return_value=__file__),
            patch(
                "youtube.oauth._scopes_from_token_file",
                return_value=["https://www.googleapis.com/auth/youtube"],
            ),
        ):
            self.assertEqual(manage_scope_problem("tapin"), "")
        with patch("youtube.oauth.token_path_for_channel", return_value="/no/such/token.json"):
            self.assertEqual(manage_scope_problem("tapin"), "")

    def _blocked(self):
        return patch(
            "publishing.snippet_update.manage_scope_problem",
            return_value="re-consent needed: py -m youtube.oauth_setup --channel tapin",
        )

    def test_go_public_stops_before_building_a_client(self):
        from publishing.go_public import apply_go_public

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = []
        with (
            self._blocked(),
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo, dry_run=False)
        self.assertEqual(result.status, "blocked")
        self.assertIn("oauth_setup", result.detail)
        svc.assert_not_called()

    def test_recategorize_stops_before_building_a_client(self):
        from publishing.recategorize import Recategorize, apply_recategorize

        with (
            self._blocked(),
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = apply_recategorize(
                "tapin", plan=[Recategorize("a", 1, "soccer", "17")], dry_run=False
            )
        self.assertTrue(result["mode"].startswith("blocked"))
        self.assertIn("oauth_setup", result["mode"])
        svc.assert_not_called()

    def test_rollback_stops_before_building_a_client(self):
        from publishing.rollback import apply_rollback

        with (
            self._blocked(),
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true", "OBSIDIAN_VAULT_PATH": ""}),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = apply_rollback("abc", correction="x", dry_run=False)
        self.assertEqual(result.status, "blocked")
        svc.assert_not_called()

    def test_one_failed_update_does_not_crash_the_batch(self):
        from publishing.recategorize import Recategorize, apply_recategorize

        service = _service({"a": LIVE, "b": LIVE})
        calls = {"n": 0}

        def _update(**_kw):
            calls["n"] += 1
            req = MagicMock()
            if calls["n"] == 1:
                req.execute.side_effect = RuntimeError("HttpError 500 backend error")
            return req

        service.videos.return_value.update.side_effect = _update
        plan = [Recategorize("a", 1, "soccer", "17"), Recategorize("b", 2, "soccer", "17")]
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("youtube.oauth.get_youtube_service", return_value=service),
        ):
            result = apply_recategorize("tapin", plan=plan, dry_run=False)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertIn("500", result["errors"][0])

    def test_youtube_scope_error_becomes_the_fix(self):
        from publishing.snippet_update import edit_error_text

        err = RuntimeError('<HttpError 403 "Request had insufficient authentication scopes.">')
        self.assertIn("py -m youtube.oauth_setup --channel tapin", edit_error_text(err, "tapin"))
        self.assertIn("500", edit_error_text(RuntimeError("HttpError 500"), "tapin"))


if __name__ == "__main__":
    unittest.main()
