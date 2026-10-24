"""Wave 125 (2026-10-23 night): the next ten - UFC 333 first.

Measured first, at 20:10 CDT on Fri 10-23: the operator had signed in at about 7:42 PM and run a
review. Run 184, "Yan's resilience vs. Dvalishvili's pressure at UFC 333", sat in the queue for
Sun noon - the day after the card - because a title that names the card by its number matched no
event, and nothing re-checked a queued job's slot against its event. Run 179 was scheduled for Sat
noon with last season's "clinched the No. 1 seed"; the operator asked for it off the schedule, and
no command did that. Three caption files took 1,200 units while three uploads were queued, so run
184 waited for the reset. The sign-in line read "lapses Fri 8:42 PM EDT" on a Friday, a week out.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 24, 1, 30, tzinfo=timezone.utc)  # Fri 9:30 PM EDT
CARD = "UFC 333: Volkanovski vs. Evloev"
CARD_AT = "2026-10-24T17:00Z"
RUN184 = "Yan's resilience vs. Dvalishvili's pressure at UFC 333"


class NumberedCardTests(unittest.TestCase):
    """#1551: a title that names the card by its number finds the card."""

    EVENTS: ClassVar[dict[str, str]] = {
        CARD: CARD_AT,
        "UFC Fight Night: Moicano vs. Nolan": "2026-11-01T00:00Z",
        "Kansas City Chiefs at Seattle Seahawks": "2026-10-26T00:20Z",
    }

    def test_run_184_finds_ufc_333(self):
        from core.seasonal_calendar import event_for

        self.assertEqual(event_for(RUN184, events=self.EVENTS), (CARD, CARD_AT))
        self.assertEqual(
            event_for("Petr Yan wins UFC 333 poll", events=self.EVENTS), (CARD, CARD_AT)
        )

    def test_another_number_is_another_card(self):
        from core.seasonal_calendar import event_for

        self.assertEqual(event_for("What UFC 33 got right", events=self.EVENTS), ("", ""))
        self.assertEqual(event_for("UFC 3330 is a typo", events=self.EVENTS), ("", ""))

    def test_the_two_sides_rule_still_works(self):
        from core.seasonal_calendar import event_for

        got = event_for("Can the Chiefs beat the Seahawks?", events=self.EVENTS)
        self.assertEqual(got[0], "Kansas City Chiefs at Seattle Seahawks")


class BeforeItsEventTests(unittest.TestCase):
    """#1552: a queued job whose slot is at or after its event takes a slot before it."""

    def _upload(self, publish_at, event, slot):
        from jobs import worker

        payload = {"file_path": "v.mp4", "title": RUN184, "privacy_status": "public",
                   "youtube_publish_at": publish_at.isoformat()}  # fmt: skip
        job = SimpleNamespace(id=80, content_run_id=184, channel_id="tapin", job_type="upload",
                              status="running", attempts=0, last_error="",
                              payload_json=json.dumps(payload))  # fmt: skip
        repo, runs, publisher = MagicMock(), MagicMock(), MagicMock()
        runs.get.return_value = SimpleNamespace(id=184, title=RUN184, mp4_path="")
        publisher.publish.return_value = SimpleNamespace(status="scheduled", detail="")
        with (
            patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value=None),
            patch.object(worker, "get_publisher", return_value=publisher),
            patch.object(worker, "get_job_repository", return_value=repo),
            patch.object(worker, "get_content_run_repository", return_value=runs),
            patch.object(worker, "_finalize_upload_job"),
            patch("core.stale_renders.run_event", return_value=event),
            patch("core.stale_renders._now", return_value=NOW),
            patch("core.spaced_queue.slot_for_run", return_value=(slot, "")) as slotted,
            patch("builtins.print") as said,
        ):
            worker._process_upload(job)
        return publisher.publish.call_args.args[0], repo, slotted, said

    def test_run_184_moves_before_the_card(self):
        sunday = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)
        card = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
        noon = datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)
        request, repo, _slotted, said = self._upload(sunday, card, noon)
        self.assertEqual(request.publish_at, noon)
        stored = json.loads(repo.update.call_args.args[1]["payload_json"])
        self.assertEqual(stored["youtube_publish_at"], noon.isoformat())
        self.assertIn("before its event", said.call_args.args[0])

    def test_a_slot_before_its_event_is_kept(self):
        noon = datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)
        card = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
        request, _repo, slotted, _said = self._upload(noon, card, None)
        self.assertEqual(request.publish_at, noon)
        slotted.assert_not_called()

    def test_no_event_keeps_the_slot(self):
        sunday = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)
        request, _repo, slotted, _said = self._upload(sunday, None, None)
        self.assertEqual(request.publish_at, sunday)
        slotted.assert_not_called()


class UnscheduleTests(unittest.TestCase):
    """#1555: a scheduled video back to private with no publish time (run 179, the operator)."""

    LIVE: ClassVar[dict[str, Any]] = {"privacyStatus": "private", "publishAt": "2026-10-24T16:00:00Z",
                                      "embeddable": True, "publicStatsViewable": True,
                                      "selfDeclaredMadeForKids": False}  # fmt: skip

    def _row(self, status="scheduled", privacy="public"):
        from storage.repositories.publish_log import PublishLogRecord

        return PublishLogRecord(id=1656, content_run_id=179, channel_id="tapin",
                                youtube_video_id="lS5dluGdRlI", privacy_status=privacy,
                                status=status)  # fmt: skip

    def _apply(self, row, after, *, dry_run=False):
        from publishing import go_public

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [row]
        service = MagicMock()
        with (
            patch.dict("os.environ", {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=service),
            patch(
                "publishing.snippet_update.live_status", side_effect=[dict(self.LIVE)] + [after] * 4
            ),
            patch.object(
                go_public, "_run_title", return_value="Detroit Pistons bench delivers 23-0"
            ),
            patch("publishing.go_public.merge_features") as marked,
            patch("time.sleep"),
        ):
            result = go_public.apply_unschedule(
                "lS5dluGdRlI",
                channel_id="tapin",
                repo=repo,
                dry_run=dry_run,
                why="last season's seed",
            )
        return result, service, repo, marked

    def test_it_goes_private_with_no_publish_time(self):
        after = {k: v for k, v in self.LIVE.items() if k != "publishAt"}
        result, service, repo, marked = self._apply(self._row(), after)
        self.assertEqual(result.status, "updated", result.detail)
        body = service.videos.return_value.update.call_args.kwargs["body"]
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertNotIn("publishAt", body["status"])
        self.assertTrue(body["status"]["embeddable"])  # #1306: the whole status
        fields = repo.update.call_args.args[1]
        self.assertEqual((fields["privacy_status"], fields["status"]), ("private", "uploaded"))
        self.assertIn("unscheduled", marked.call_args.args[1])

    def test_a_publish_time_still_shown_is_said(self):
        result, _service, _repo, _marked = self._apply(self._row(), dict(self.LIVE))
        self.assertEqual(result.status, "error")
        self.assertIn("still", result.detail)

    def test_the_dry_run_sends_nothing(self):
        result, service, repo, _marked = self._apply(self._row(), {}, dry_run=True)
        self.assertEqual(result.status, "dry_run")
        service.videos.return_value.update.assert_not_called()
        repo.update.assert_not_called()

    def test_a_public_video_is_refused(self):
        result, service, _repo, _marked = self._apply(self._row("uploaded", "public"), {})
        self.assertEqual(result.status, "invalid")
        service.videos.return_value.update.assert_not_called()

    def test_ops_unschedule_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("unschedule", COMMANDS)


class CaptionReserveTests(unittest.TestCase):
    """#1553: a caption file keeps one upload's units for each upload still queued."""

    def test_the_reserve_grows_with_the_queue(self):
        from youtube.captions import caption_quota_ok

        self.assertTrue(caption_quota_ok(3500))  # nothing queued: one upload's worth kept
        self.assertFalse(caption_quota_ok(3500, waiting=2))
        self.assertTrue(caption_quota_ok(3700, waiting=2))

    def test_the_upload_reads_the_queue(self):
        import tempfile

        from youtube import captions

        pending = [SimpleNamespace(job_type="upload", status="pending") for _ in range(3)]
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            f.write(b"1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        with (
            patch("apis.youtube_quota.get_usage_summary", return_value={"remaining": 4000}),
            patch("core.job_queue.list_active_jobs", return_value=pending),
        ):
            got = captions.maybe_upload_captions(MagicMock(), video_id="v", caption_path=f.name)
        self.assertEqual(got.status, "skipped")
        self.assertIn("3 queued", got.detail)


class WeakHookTests(unittest.TestCase):
    """#1549 (the operator, 2026-10-23: lift the hold) - decision 72."""

    def test_a_weak_hook_no_longer_holds_an_overnight_render(self):
        from core import batch_review
        from core.batch_review import PendingDraft

        meta = {"run_id": 1, "hook_verdict": "weak", "created_at": datetime.now().isoformat()}
        draft = PendingDraft("f", meta, "A clean script.")
        with patch.object(batch_review, "authenticity_now", return_value=("ok", "")):
            reason = batch_review.unattended_block_reason(draft)
        self.assertNotIn("weak hook", reason)


class SignInDateTests(unittest.TestCase):
    """#1554: a lapse more than a day away names its date."""

    def _line(self, expiry, now):
        from youtube import oauth

        with (
            patch.object(oauth, "_reminder_days", return_value=7),
            patch.object(oauth, "sign_in_expiry", return_value=expiry),
        ):
            return oauth.sign_in_expiry_line("tapin", now=now)

    def test_a_week_out_has_its_date(self):
        expiry = datetime(2026, 10, 31, 0, 42, tzinfo=timezone.utc)  # Fri Oct 30 8:42 PM EDT
        line = self._line(expiry, datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(line, "lapses Fri Oct 30 8:42 PM EDT unless the app is published")

    def test_within_a_day_the_weekday_is_enough(self):
        expiry = datetime(2026, 10, 31, 0, 42, tzinfo=timezone.utc)
        line = self._line(expiry, expiry - timedelta(hours=5))
        self.assertEqual(line, "lapses Fri 8:42 PM EDT unless the app is published")


SCRIPT = (
    "The Chiefs are 5-0 and favored by three in Seattle. Seattle ruled out three starters. "
    "Kansas City has covered four straight. The line moved twice this week. Tap in for more."
)


def _prompt_for(guidance=None, rule="most viewers decide in the first seconds"):
    from core import content_engine

    seen: dict[str, str] = {}

    def llm(system_prompt, user_prompt, **_kw):
        seen["system"] = system_prompt
        return {"openers": ["The Chiefs will lose in Seattle, and the spread already says so."]}

    with (
        patch.object(content_engine, "_call_content_llm", side_effect=llm),
        patch.object(content_engine, "_first_line_rule", return_value=rule),
        patch("analytics.hook_learning.regen_guidance", return_value=guidance or {}),
        patch("core.hook_score.hook_regen_enabled", return_value=True),  # the suite turns it off
    ):
        new, extra = content_engine._hook_variants(SCRIPT, channel_id="")
    return seen.get("system", ""), new, extra


class CallFormTests(unittest.TestCase):
    """#1557: since 10-19, 17 of 18 runs refused every hook variant for "no call or take" - the
    prompt said why a call matters and never what one looks like."""

    def test_the_prompt_names_the_form(self):
        system, _new, _extra = _prompt_for()
        self.assertIn("will", system)
        self.assertIn("in so many words", system)

    def test_an_opener_in_that_form_passes_the_rule(self):
        from core.authenticity import first_line_take

        self.assertTrue(
            first_line_take("The Chiefs will lose in Seattle, and the spread already says so.")
        )
        # the live refusals of run 185 stay refused
        self.assertFalse(
            first_line_take(
                "The 5-0 Chiefs are underdogs in Seattle, and the spread says the league already knows why."
            )
        )

    def test_the_variant_is_kept(self):
        _system, new, extra = _prompt_for()
        self.assertTrue(new.startswith("The Chiefs will lose in Seattle"), extra)


class TenExamplesTests(unittest.TestCase):
    """#1504: the ten best-held openers as the rewrite's examples, and decision 67's settled notes
    in place of the fixed rules they contradict."""

    def test_learn_keeps_ten(self):
        from analytics import hook_learning

        rows = [{"hook": f"Opener {i} names Detroit.", "score": 50.0, "traits": set(), "stayed": i / 100}
                for i in range(22)]  # fmt: skip
        with patch.object(hook_learning, "_rows", return_value=rows):
            got = hook_learning.learn("tapin")
        self.assertEqual(len(got["best_hooks"]), 10)
        self.assertEqual(got["best_hooks"][0][0], "Opener 21 names Detroit.")

    def test_the_examples_carry_their_share(self):
        from analytics.hook_learning import guidance_from

        got = {"ready": True, "n": 22, "needs": 16, "traits": [],
               "best_hooks": [("Is Jalen Hurts the best?", 0.45)]}  # fmt: skip
        guidance = guidance_from(got)
        self.assertEqual(guidance["examples"], ["Is Jalen Hurts the best? (45% stayed)"])
        self.assertTrue(guidance["settled"])

    def test_settled_notes_replace_the_rules_they_contradict(self):
        guidance = {
            "examples": [f"Example {i}" for i in range(10)],
            "prefer": [{"trait": "a question", "with": 0.42, "without": 0.21, "gap": 0.21}],
            "avoid": [{"trait": "12 words or fewer", "with": 0.22, "without": 0.31, "gap": -0.09}],
            "settled": True,
        }
        system, _new, _extra = _prompt_for(guidance)
        self.assertNotIn("under 12 words", system)
        self.assertNotIn("or a question", system)
        self.assertIn("Example 9", system)

    def test_unsettled_the_rules_stand(self):
        guidance = {"examples": ["Example 0"], "prefer": [], "avoid": [], "settled": False}
        system, _new, _extra = _prompt_for(guidance)
        self.assertIn("under 12 words", system)


class HookOptionsTests(unittest.TestCase):
    """#1503: at review, one of three hooks; the pick is recorded."""

    PASSES: ClassVar[list[dict[str, Any]]] = [
        {"name": "improve_hook", "picked": "",
         "variants": [{"opener": "Kansas City will cover in Seattle.", "score": 80},
                      {"opener": "Seattle's three starters out will decide it.", "score": 78,
                       "refused": "no better than the current opener (90)"},
                      {"opener": "Bad one with new numbers 99.", "score": 70,
                       "refused": "new specifics (a name or number the script does not have)"}]},
    ]  # fmt: skip

    def test_the_options(self):
        from core.batch_generation import hook_options

        got = hook_options(SCRIPT, self.PASSES)
        self.assertEqual(got[0], "The Chiefs are 5-0 and favored by three in Seattle.")
        self.assertEqual(
            got[1:],
            ["Kansas City will cover in Seattle.", "Seattle's three starters out will decide it."],
        )

    def test_a_stored_repr_is_read(self):
        from core.batch_generation import hook_options

        passes = [dict(self.PASSES[0], variants=repr(self.PASSES[0]["variants"]))]
        self.assertEqual(len(hook_options(SCRIPT, passes)), 3)

    def test_review_swaps_the_first_sentence_and_records_the_pick(self):
        import os
        import shutil
        import tempfile

        from core import batch_review

        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        folder = os.path.join(root, "185")
        os.makedirs(folder)
        options = [
            "The Chiefs are 5-0 and favored by three in Seattle.",
            "Kansas City will cover in Seattle.",
        ]
        meta = {"run_id": 185, "title": "Chiefs at Seahawks", "topic": "Chiefs at Seahawks",
                "created_at": datetime.now().isoformat(), "hook_options": options}  # fmt: skip
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
            f.write(f"# Chiefs\n\n## Script\n\n{SCRIPT}\n\n## Description\n\nd\n")
        answers = iter(["h", "2", ""])
        with (
            patch.object(batch_review, "_show", return_value=[]),
            patch.object(batch_review, "deadline_line", return_value=""),
            patch("builtins.print"),
        ):
            batch_review.review_drafts(
                "tapin", root=root, ask=lambda _p: next(answers), print_fn=lambda *a: None
            )
        script = batch_review.draft_script(folder)
        self.assertTrue(script.startswith("Kansas City will cover in Seattle."), script)
        self.assertIn("Seattle ruled out three starters.", script)
        with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["hook_pick"]["picked"], 2)
        self.assertEqual(stored["hook_pick"]["options"], options)


class RenderProcessTests(unittest.TestCase):
    """#1464: each overnight render in its own process - one crash costs one draft."""

    def test_a_crash_costs_one_draft(self):
        from core import batch_review
        from core.batch_review import PendingDraft

        drafts = [PendingDraft(f"folder{i}", {"run_id": i, "created_at": datetime.now().isoformat()}, "s")
                  for i in (1, 2)]  # fmt: skip
        codes = iter([3221225477, 0])
        with (
            patch.object(batch_review, "unattended_candidates", return_value=(drafts, [])),
            patch.object(batch_review, "shelf_max", return_value=0),
            patch.object(batch_review, "second_read", return_value=""),
            patch.object(batch_review, "_smoke_failure", return_value=""),
            patch.object(batch_review, "_memory_short", return_value=""),
            patch.object(batch_review, "_disk_short", return_value=""),
            patch.object(batch_review, "_write_review"),
            patch("core.nightly_task.beat_step"),
            patch(
                "subprocess.run",
                side_effect=lambda *a, **k: SimpleNamespace(returncode=next(codes)),
            ) as run,
        ):
            out = batch_review.render_unattended("tapin", 2, queue=lambda r, c: 1)
        self.assertEqual(out["rendered"], [2])
        self.assertEqual(out["failed"][0][0], 1)
        self.assertIn("exit 3221225477", out["failed"][0][1])
        argv = run.call_args_list[0].args[0]
        self.assertEqual(argv[1:4], ["-m", "core.batch_review", "--render-draft"])

    def test_the_child_renders_the_folder(self):
        import os
        import shutil
        import tempfile

        from core import batch_review

        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        with open(os.path.join(root, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"run_id": 7, "title": "T", "topic": "T"}, f)
        with open(os.path.join(root, "draft.md"), "w", encoding="utf-8") as f:
            f.write("# T\n\n## Script\n\nThe script.\n")
        with patch.object(batch_review, "_render", return_value=True) as render:
            code = batch_review.main(["--render-draft", root])
        self.assertEqual(code, 0)
        self.assertEqual(render.call_args.args[0].run_id, 7)


class ShortfallsTests(unittest.TestCase):
    """#1517: each shortfall's exit command, from the plan, in the weekly review."""

    def test_every_section_has_a_done_when(self):
        from core.roadmap_index import sections

        found = sections()
        self.assertEqual(len(found), 22)
        self.assertTrue(
            all(s["done_when"] for s in found), [s["key"] for s in found if not s["done_when"]]
        )

    def test_every_named_command_exists(self):
        from core.roadmap_index import sections
        from scripts.ops import COMMANDS

        named = {c for s in sections() for c in s["commands"]}
        self.assertTrue(named)
        self.assertEqual(sorted(named - set(COMMANDS)), [])

    def test_ops_shortfalls_in_the_weekly_review(self):
        from scripts import ops

        self.assertIn("shortfalls", ops.COMMANDS)
        group = (
            next(v for k, v in ops.GROUPS.items() if k == "all-review")
            if hasattr(ops, "GROUPS")
            else None
        )
        source = __import__("inspect").getsource(ops)
        self.assertIn(
            '"shortfalls"',
            source[source.index('"all-review": (') :][:600] if group is None else str(group),
        )


class UnscheduleReadBackTests(UnscheduleTests):
    """#1555's first live run read YouTube back before the change had taken: it said "still
    shows a publish time", and a second read seconds later showed none."""

    def test_a_late_read_back_is_waited_for(self):
        from publishing import go_public

        clean = {k: v for k, v in self.LIVE.items() if k != "publishAt"}
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [self._row()]
        with (
            patch.dict("os.environ", {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=MagicMock()),
            patch(
                "publishing.snippet_update.live_status",
                side_effect=[dict(self.LIVE), dict(self.LIVE), clean],
            ),  # fmt: skip
            patch.object(go_public, "_run_title", return_value="t"),
            patch("publishing.go_public.merge_features"),
            patch("time.sleep") as slept,
        ):
            result = go_public.apply_unschedule(
                "lS5dluGdRlI", channel_id="tapin", repo=repo, dry_run=False
            )
        self.assertEqual(result.status, "updated", result.detail)
        slept.assert_called()


if __name__ == "__main__":
    unittest.main()
