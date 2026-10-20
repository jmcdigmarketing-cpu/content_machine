"""Wave 89 (#1185-#1190): TikTok and Instagram through the Buffer API.

The operator added `BUFFER_API_KEY` and set up Cloudflare R2, and chose: a video goes to TikTok
and Instagram once it is public on YouTube, new videos only, automatically. Buffer takes a
video only from a public link (no uploads), so R2 hosts the mp4. `createPost` has no
idempotency key, so a call that got no answer is looked for before it is ever sent again.

No network: `requests.post` and the R2 client are fakes; the crosspost store is a temp file.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

import requests

DUE = datetime(2099, 10, 16, 22, 0, tzinfo=timezone.utc)
# A slot inside the week a hosted link lasts - a post is never scheduled past its link.
SLOT = (datetime.now(timezone.utc) + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
R2 = {
    "R2_ACCOUNT_ID": "acct",
    "R2_ACCESS_KEY_ID": "id",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_BUCKET": "videos",
    "R2_PUBLIC_BASE_URL": "https://pub-test.r2.dev",
}


class _Resp:
    def __init__(self, body=None, status=200, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


# ---- #1185: the Buffer client -------------------------------------------------------------------


class BufferApiTests(unittest.TestCase):
    def test_the_post_body_for_a_reel(self):
        from publishing.buffer_api import post_input

        body = post_input("ch1", text="cap", video_url="https://r2/x.mp4?sig", due_at=DUE,
                          service="instagram", thumbnail_ms=3150)  # fmt: skip
        self.assertEqual(body["channelId"], "ch1")
        self.assertEqual(body["schedulingType"], "automatic")
        self.assertEqual(body["mode"], "customScheduled")
        self.assertEqual(body["dueAt"], "2099-10-16T22:00:00.000Z")
        self.assertTrue(body["aiAssisted"])
        self.assertEqual(
            body["assets"],
            [{"video": {"url": "https://r2/x.mp4?sig", "metadata": {"thumbnailOffset": 3150}}}],
        )
        self.assertEqual(
            body["metadata"],
            {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}},
        )

    def test_the_post_body_for_a_tiktok(self):
        from publishing.buffer_api import post_input

        body = post_input("ch2", text="cap", video_url="u", due_at=DUE, service="tiktok")
        self.assertEqual(body["metadata"], {"tiktok": {"isAiGenerated": True}})
        self.assertNotIn("metadata", body["assets"][0]["video"])

    def test_a_query_carries_the_key_and_returns_data(self):
        from publishing import buffer_api

        sent = {}

        def post(url, **kw):
            sent.update(url=url, **kw)
            return _Resp({"data": {"account": {"organizations": [{"id": "o1", "name": "Me"}]}}})

        with patch.dict(os.environ, {"BUFFER_API_KEY": "k123"}):
            orgs = buffer_api.organizations(post=post)
        self.assertEqual(orgs, [{"id": "o1", "name": "Me"}])
        self.assertEqual(sent["url"], "https://api.buffer.com")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer k123")

    def test_a_rejected_key_is_an_auth_error(self):
        from publishing.buffer_api import BufferError, organizations

        body = {"errors": [{"message": "bad", "extensions": {"code": "UNAUTHORIZED"}}]}
        with (
            patch.dict(os.environ, {"BUFFER_API_KEY": "k123"}),
            self.assertRaises(BufferError) as ctx,
        ):
            organizations(post=lambda url, **kw: _Resp(body))
        self.assertEqual(ctx.exception.kind, "auth")
        self.assertNotIn("k123", str(ctx.exception))

    def test_a_rate_limit_waits_once_then_stops(self):
        from publishing.buffer_api import BufferError, organizations

        waits: list[float] = []
        limited = _Resp({}, status=429, headers={"Retry-After": "2"})
        with patch.dict(os.environ, {"BUFFER_API_KEY": "k"}), self.assertRaises(BufferError) as ctx:
            organizations(post=lambda url, **kw: limited, sleep=waits.append)
        self.assertEqual(waits, [2.0])
        self.assertEqual(ctx.exception.kind, "rate_limited")

    def test_a_mutation_error_is_an_input_error(self):
        from publishing.buffer_api import BufferError, create_video_post

        body = {"data": {"createPost": {"message": "Channel not found"}}}
        with patch.dict(os.environ, {"BUFFER_API_KEY": "k"}), self.assertRaises(BufferError) as ctx:
            create_video_post("ch1", text="t", video_url="u", due_at=DUE, service="tiktok",
                              post=lambda url, **kw: _Resp(body))  # fmt: skip
        self.assertEqual(ctx.exception.kind, "input")
        self.assertIn("Channel not found", str(ctx.exception))


# ---- #1186: the video host ---------------------------------------------------------------------


class VideoHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mp4 = os.path.join(self.tmp.name, "v.mp4")
        with open(self.mp4, "wb") as f:
            f.write(b"mp4")

    def test_the_video_is_put_and_its_public_address_returned(self):
        # Was "a week-long link": a presigned link answers HEAD with 403 and Buffer refused it
        # live on 2026-10-15 ("Video could not be read from its URL").
        from publishing import video_host

        client = MagicMock()
        with patch.dict(os.environ, R2):
            url = video_host.host(self.mp4, "tapin/run5-ab12.mp4", client=client)
        self.assertEqual(url, "https://pub-test.r2.dev/tapin/run5-ab12.mp4")
        args = client.upload_file.call_args
        self.assertEqual(args.args[1:], ("videos", "tapin/run5-ab12.mp4"))
        self.assertEqual(args.kwargs["ExtraArgs"], {"ContentType": "video/mp4"})
        client.generate_presigned_url.assert_not_called()

    def test_what_is_missing_is_named(self):
        from publishing import video_host

        with patch.dict(os.environ, dict.fromkeys(R2, "")):
            self.assertEqual(
                video_host.missing(),
                ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
                 "R2_PUBLIC_BASE_URL"],
            )  # fmt: skip
            self.assertFalse(video_host.configured())

    def test_a_logged_link_has_no_signature(self):
        from publishing.video_host import safe_url

        self.assertEqual(safe_url("https://a.r2/b.mp4?X-Amz-Signature=abc"), "https://a.r2/b.mp4")


# ---- #1187-#1190: sending, syncing, wiring --------------------------------------------------------


def _run(tmp, run_id, title="Ravens face injury crisis ahead of Browns showdown"):
    path = os.path.join(tmp, f"v{run_id}.mp4")
    with open(path, "wb") as f:
        f.write(b"mp4")
    return SimpleNamespace(
        id=run_id, channel_id="tapin", input_topic="Baltimore Ravens at Cleveland Browns",
        selected_topic=title, title=title, mp4_path=path,
        description="A preview of Sunday's game.\n\nMade with AI-assisted narration and editing.",
        tags_json=json.dumps(["NFL", "Ravens", "Browns"]),
    )  # fmt: skip


class CrosspostCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.public: list[tuple[int, str]] = [(100, "old100")]
        self.runs = {n: _run(self.tmp.name, n) for n in (100, 113, 114)}
        self.duration = 40.0
        self.create = MagicMock(side_effect=self._created)
        self.made = 0
        self.host = MagicMock(return_value="https://acct.r2/videos/key.mp4?X-Amz-Signature=s")
        self.remove = MagicMock(return_value=True)
        for p in (
            patch("publishing.crosspost.CROSSPOST_TEMPLATE",
                  os.path.join(self.tmp.name, "crosspost_{channel}.json")),
            patch("publishing.crosspost._public_runs", side_effect=lambda ch: list(self.public)),
            patch("publishing.crosspost._content_run", side_effect=lambda rid: self.runs.get(rid)),
            patch("publishing.crosspost._duration", side_effect=lambda p: self.duration),
            patch("publishing.crosspost._suggested_slot", return_value=SLOT),
            patch("publishing.buffer_api.create_video_post", self.create),
            patch("publishing.buffer_api.configured", return_value=True),
            patch("publishing.video_host.configured", return_value=True),
            patch("publishing.video_host.host", self.host),
            patch("publishing.video_host.remove", self.remove),
            patch.dict(os.environ, {"CROSSPOST_AUTO": "true"}),
        ):  # fmt: skip
            p.start()
            self.addCleanup(p.stop)
        from publishing.crosspost import save_channels

        save_channels("tapin", "org1", {"tiktok": "tt1", "instagram": "ig1"})

    def _created(self, channel_id, **kw):
        self.made += 1
        return {"id": f"post{self.made}", "dueAt": kw["due_at"].isoformat(), "status": "scheduled"}

    def _store(self):
        from publishing.crosspost import _load

        return _load("tapin")

    def _first_then(self, *public):
        from publishing.crosspost import send_due

        send_due("tapin")  # the first call records what was already public
        self.public.extend(public)
        return send_due("tapin")


class SendTests(CrosspostCase):
    def test_a_video_made_public_goes_to_both(self):
        lines = self._first_then((113, "yt113"))
        services = sorted(c.kwargs["service"] for c in self.create.call_args_list)
        self.assertEqual(services, ["instagram", "tiktok"])
        posts = self._store()["posts"]["113"]
        self.assertEqual(posts["tiktok"]["state"], "scheduled")
        self.assertEqual(posts["instagram"]["post_id"], "post2")
        self.assertIn("Made with AI-assisted", self.create.call_args.kwargs["text"])
        self.assertEqual(self.host.call_count, 1)  # hosted once for both
        self.assertIn("run 113", "\n".join(lines))

    def test_videos_public_before_it_was_switched_on_are_left(self):
        self._first_then((113, "yt113"))
        self.assertNotIn("100", self._store()["posts"])

    def test_a_long_video_skips_instagram(self):
        self.duration = 200.0  # decision 64: Reels take up to 180 s
        self._first_then((113, "yt113"))
        self.assertEqual([c.kwargs["service"] for c in self.create.call_args_list], ["tiktok"])
        self.assertEqual(self._store()["posts"]["113"]["instagram"]["state"], "skipped")

    def test_a_dry_run_sends_nothing(self):
        from publishing.crosspost import send_due

        send_due("tapin")
        self.public.append((113, "yt113"))
        lines = send_due("tapin", apply=False)
        self.create.assert_not_called()
        self.host.assert_not_called()
        self.assertIn("would schedule", "\n".join(lines))

    def test_an_unanswered_call_is_found_not_sent_twice(self):
        self.create.side_effect = requests.Timeout("no answer")
        self._first_then((113, "yt113"))
        self.assertEqual(self._store()["posts"]["113"]["tiktok"]["state"], "sending")
        from publishing.buffer_api import due_text

        sent_text = self.create.call_args.kwargs["text"]
        found = [{"id": "found1", "dueAt": due_text(SLOT), "text": sent_text,
                  "status": "scheduled", "channelId": "tt1"}]  # fmt: skip
        with patch("publishing.buffer_api.find_posts", side_effect=lambda org, ch: [
            p for p in found if p["channelId"] == ch
        ]):  # fmt: skip
            from publishing.crosspost import send_due

            send_due("tapin")
        tiktok = [c for c in self.create.call_args_list if c.kwargs["service"] == "tiktok"]
        self.assertEqual(len(tiktok), 1)  # Instagram's first call is the only new one
        self.assertEqual(self._store()["posts"]["113"]["tiktok"]["post_id"], "found1")

    def test_buffers_refusal_is_kept_not_retried(self):
        from publishing.buffer_api import BufferError
        from publishing.crosspost import send_due

        self.create.side_effect = BufferError("input", "Video is too short")
        self._first_then((113, "yt113"))
        calls = self.create.call_count
        send_due("tapin")
        self.assertEqual(self.create.call_count, calls)
        self.assertEqual(self._store()["posts"]["113"]["tiktok"]["error"], "Video is too short")

    def test_a_rejected_key_stops_the_round(self):
        from publishing.buffer_api import BufferError

        self.create.side_effect = BufferError("auth", "UNAUTHORIZED")
        lines = self._first_then((113, "yt113"), (114, "yt114"))
        self.assertEqual(self.create.call_count, 1)
        self.assertIn("Buffer key rejected", "\n".join(lines))

    def test_two_videos_can_go_on_the_same_day(self):
        # Decision 63 (the operator, 2026-10-17): "erase this rule" - no spacing between posts.
        self._first_then((113, "yt113"), (114, "yt114"))
        tiktok = sorted(c.kwargs["due_at"] for c in self.create.call_args_list
                        if c.kwargs["service"] == "tiktok")  # fmt: skip
        self.assertEqual(len(tiktok), 2)
        self.assertLess(tiktok[1] - tiktok[0], timedelta(hours=20))

    def test_a_far_slot_is_still_scheduled(self):
        # Was "a slot past the link's week waits": the address is public now (2026-10-15,
        # Buffer refused a presigned link) and does not expire.
        from publishing.crosspost import send_due

        send_due("tapin")
        self.public.append((113, "yt113"))
        far = datetime.now(timezone.utc) + timedelta(days=9)
        with patch("publishing.crosspost._suggested_slot", return_value=far):
            send_due("tapin")
        self.assertEqual(self.create.call_count, 2)

    def test_missing_setup_is_named_and_nothing_sent(self):
        from publishing.crosspost import step

        with (
            patch("publishing.video_host.configured", return_value=False),
            patch("publishing.video_host.missing", return_value=["R2_BUCKET"]),
        ):
            self.public.append((113, "yt113"))
            lines = step("tapin")
        self.create.assert_not_called()
        self.assertIn("R2_BUCKET", "\n".join(lines))

    def test_switched_off_does_nothing(self):
        from publishing.crosspost import step

        self.public.append((113, "yt113"))
        with patch.dict(os.environ, {"CROSSPOST_AUTO": "false"}):
            self.assertEqual(step("tapin"), [])
        self.create.assert_not_called()


class SyncTests(CrosspostCase):
    def setUp(self):
        super().setUp()
        self._first_then((113, "yt113"))

    def _sync(self, posts):
        from publishing.crosspost import sync_status

        with patch("publishing.buffer_api.get_post", side_effect=lambda pid: posts[pid]):
            return sync_status("tapin")

    def test_sent_is_recorded_and_the_copy_removed(self):
        self._sync({
            "post1": {"id": "post1", "status": "sent", "sentAt": "2026-10-16T22:01:00Z",
                      "externalLink": "https://www.tiktok.com/@tapin/video/1"},
            "post2": {"id": "post2", "status": "sent", "sentAt": "2026-10-17T22:01:00Z",
                      "externalLink": "https://www.instagram.com/reel/abc"},
        })  # fmt: skip
        posts = self._store()["posts"]["113"]
        self.assertEqual(posts["tiktok"]["state"], "sent")
        self.assertEqual(posts["instagram"]["link"], "https://www.instagram.com/reel/abc")
        self.remove.assert_called_once()

    def test_buffers_error_message_is_kept(self):
        from publishing.crosspost import status_lines

        self._sync({
            "post1": {"id": "post1", "status": "error", "error": {"message": "Video too short"}},
            "post2": {"id": "post2", "status": "scheduled"},
        })  # fmt: skip
        # #1400 (wave 116): the first failure is sent once more; the message stays.
        self.assertEqual(self._store()["posts"]["113"]["tiktok"]["state"], "retry")
        self.assertIn("Video too short", "\n".join(status_lines("tapin")))
        self.remove.assert_not_called()  # Instagram still needs the link

    def test_a_video_taken_down_on_youtube_cancels_its_posts(self):
        self.public[:] = [(100, "old100")]
        with patch("publishing.buffer_api.delete_post", return_value=True) as delete:
            self._sync({"post1": {"id": "post1", "status": "scheduled"},
                        "post2": {"id": "post2", "status": "scheduled"}})  # fmt: skip
        self.assertEqual(delete.call_count, 2)
        self.assertEqual(self._store()["posts"]["113"]["tiktok"]["state"], "cancelled")

    def test_cancel_by_hand(self):
        from publishing.crosspost import cancel

        with patch("publishing.buffer_api.delete_post", return_value=True) as delete:
            lines = cancel("tapin", 113)
        self.assertEqual(delete.call_count, 2)
        self.assertIn("cancelled", "\n".join(lines))


class ChannelsTests(unittest.TestCase):
    CHANNELS: ClassVar[list[dict]] = [
        {"id": "tt1", "name": "tapinmedia", "service": "tiktok", "type": "business",
         "isDisconnected": False, "isLocked": False, "isQueuePaused": False},
        {"id": "ig1", "name": "tapin.media", "service": "instagram", "type": "business",
         "isDisconnected": False, "isLocked": False, "isQueuePaused": False},
        {"id": "yt1", "name": "TapIn", "service": "youtube", "type": "channel",
         "isDisconnected": False, "isLocked": False, "isQueuePaused": False},
    ]  # fmt: skip

    def test_one_of_each_is_picked(self):
        from publishing.crosspost import choose_channels

        picked, notes = choose_channels(self.CHANNELS)
        self.assertEqual(picked, {"tiktok": "tt1", "instagram": "ig1"})
        self.assertEqual(notes, [])

    def test_a_disconnected_channel_is_not_picked(self):
        from publishing.crosspost import choose_channels

        rows = [dict(c) for c in self.CHANNELS]
        rows[1]["isDisconnected"] = True
        picked, notes = choose_channels(rows)
        self.assertNotIn("instagram", picked)
        self.assertIn("disconnected", " ".join(notes))

    def test_the_command_saves_them(self):
        from scripts.ops import cmd_crosspost

        with tempfile.TemporaryDirectory() as tmp, (
            patch("publishing.crosspost.CROSSPOST_TEMPLATE",
                  os.path.join(tmp, "crosspost_{channel}.json"))
        ), patch("publishing.buffer_api.organizations", return_value=[{"id": "o1", "name": "Me"}]), (
            patch("publishing.buffer_api.channels", return_value=self.CHANNELS)
        ):  # fmt: skip
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmd_crosspost(Namespace(channel="tapin", target="channels", apply=True,
                                               run_id=0))  # fmt: skip
            from publishing.crosspost import buffer_channel_ids

            self.assertEqual(buffer_channel_ids("tapin"), {"tiktok": "tt1", "instagram": "ig1"})
        self.assertEqual(code, 0)
        self.assertIn("tapinmedia", buf.getvalue())


class WiringTests(unittest.TestCase):
    def test_the_morning_sends_after_the_sync(self):
        from scripts import ops

        steps = list(ops.BATCHES["morning"][1])
        self.assertIn("crosspost-send", ops.COMMANDS)
        self.assertGreater(steps.index("crosspost-send"), steps.index("sync-metrics"))

    def test_making_one_public_sends_it(self):
        from publishing.go_public import apply_go_public

        row = SimpleNamespace(id=7, youtube_video_id="abc", content_run_id=5,
                              privacy_status="unlisted", status="uploaded")  # fmt: skip
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [row]
        with (
            patch("publishing.go_public.load_features", return_value={}),
            patch("youtube.oauth.get_youtube_service", return_value=MagicMock()),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("publishing.crosspost.step", return_value=["Crosspost: run 5 scheduled"]) as step,
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo, dry_run=False)
        self.assertEqual(result.status, "updated", result.detail)
        step.assert_called_once_with("tapin")
        self.assertEqual(result.crosspost, ["Crosspost: run 5 scheduled"])

    def test_overnight_reports_it(self):
        from core import overnight

        result = overnight.OvernightResult(channel_id="tapin")
        with patch("publishing.crosspost.step", return_value=["Crosspost: 1 scheduled"]):
            overnight._crosspost(result)
        self.assertEqual(result.crosspost_line, "Crosspost: 1 scheduled")
        self.assertIn("Crosspost: 1 scheduled", overnight.render_overnight(result))


if __name__ == "__main__":
    unittest.main()
