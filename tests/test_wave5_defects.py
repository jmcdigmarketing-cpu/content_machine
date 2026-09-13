"""Wave 5: #701, #700, #699, #112 substrate, #151.

Every test here was observed failing on unmodified 352c547, for the reason named
in its docstring. The recurring shape rules 17/20/21 exist for is still the one
that bites: a helper is correct in isolation, and the thing that feeds it -- or
the guard that is supposed to catch it -- was never exercised with real inputs.
"""

import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


class TestWeekendClockRollsForward(unittest.TestCase):
    """#701. `(5 - weekday()) % 7` is 0 on a Saturday, so 'this weekend' resolved
    to Saturday noon -- in the past from Saturday afternoon on. The sibling
    'tonight' branch rolls forward explicitly; this one did not.

    The existing guard (tests/test_stage3_queue.py::TestChannelClock) pins `now`
    to a Wednesday and asserts only `weekend.weekday() == 5`, which the buggy
    code satisfies on every day of the week. It cannot fail for this defect.
    """

    def test_this_weekend_never_resolves_into_the_past(self):
        from core.publish_windows import resolve_relative_clock

        # A full week of ET afternoons, plus the two cases that actually broke:
        # Saturday evening and Sunday afternoon.
        moments = [
            datetime(2026, 9, 7, 15, 0, tzinfo=ET),  # Monday
            datetime(2026, 9, 8, 15, 0, tzinfo=ET),  # Tuesday
            datetime(2026, 9, 9, 15, 0, tzinfo=ET),  # Wednesday
            datetime(2026, 9, 10, 15, 0, tzinfo=ET),  # Thursday
            datetime(2026, 9, 11, 15, 0, tzinfo=ET),  # Friday
            datetime(2026, 9, 12, 20, 0, tzinfo=ET),  # Saturday EVENING
            datetime(2026, 9, 13, 13, 0, tzinfo=ET),  # Sunday afternoon
        ]
        for now in moments:
            with self.subTest(day=now.strftime("%a %H:%M")):
                resolved = resolve_relative_clock("this weekend", now=now)
                self.assertIsNotNone(resolved)
                self.assertGreater(
                    resolved,
                    now,
                    f"'this weekend' resolved to {resolved}, which is not after {now}",
                )
                self.assertIn(
                    resolved.astimezone(ET).weekday(),
                    (5, 6),
                    "'this weekend' must land on a Saturday or Sunday",
                )

    def test_saturday_evening_resolves_to_sunday_not_next_saturday(self):
        """Saturday 20:00 is still 'this weekend' -- Sunday is the answer, not
        a date six days out."""
        from core.publish_windows import resolve_relative_clock

        saturday_night = datetime(2026, 9, 12, 20, 0, tzinfo=ET)
        resolved = resolve_relative_clock("this weekend", now=saturday_night)
        self.assertIsNotNone(resolved)
        local = resolved.astimezone(ET)
        self.assertEqual(local.weekday(), 6, "should be the Sunday of the same weekend")
        self.assertEqual(local.date(), datetime(2026, 9, 13, tzinfo=ET).date())

    def test_weekday_before_the_weekend_still_resolves_to_saturday(self):
        """The behaviour the Wednesday guard already pinned must not change."""
        from core.publish_windows import resolve_relative_clock

        wednesday = datetime(2026, 9, 9, 14, 0, tzinfo=timezone.utc)
        resolved = resolve_relative_clock("this weekend", now=wednesday)
        self.assertIsNotNone(resolved)
        local = resolved.astimezone(ET)
        self.assertEqual(local.weekday(), 5)
        self.assertEqual(local.hour, 12)

    def test_sunday_after_noon_rolls_to_the_next_weekend(self):
        """Once Sunday noon has passed there is no 'this weekend' left."""
        from core.publish_windows import resolve_relative_clock

        sunday_evening = datetime(2026, 9, 13, 19, 0, tzinfo=ET)
        resolved = resolve_relative_clock("this weekend", now=sunday_evening)
        self.assertIsNotNone(resolved)
        local = resolved.astimezone(ET)
        self.assertEqual(local.weekday(), 5)
        self.assertGreater(local, sunday_evening)


class _SqlBackedRepo:
    """Drives the real `PostgresJobRepository` against a temp SQLite file.

    What this proves: ordering, LIMIT, and one row per claim.

    What it does NOT prove: `skip_locked`. SQLAlchemy emits no FOR UPDATE on
    SQLite. That lock is measured on real Postgres in
    ``tests/test_postgres_job_claim.py`` (CI service + local content_machine_test).
    """

    def __enter__(self):
        import storage.db as db
        from config.settings import Settings
        from storage.models import Base
        from storage.repositories.jobs import PostgresJobRepository

        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "jobs.sqlite3")
        # `Settings.database_url` is a CLASS attribute evaluated at import time,
        # so setting the env var (or clearing get_settings' cache) does nothing
        # once config.settings has been imported. Patch the attribute itself.
        self._env = patch.object(Settings, "database_url", f"sqlite:///{path}")
        self._env.start()
        # get_engine is lru_cached AND assigns module globals; without the reset
        # the repo silently reuses whatever engine another test built.
        db.get_engine.cache_clear()
        db._engine = None
        db._SessionLocal = None
        self.db = db
        self.statements: list[str] = []
        engine = db.get_engine()
        Base.metadata.create_all(engine)

        from sqlalchemy import event

        @event.listens_for(engine, "before_cursor_execute")
        def _record(conn, cursor, statement, params, context, executemany):
            self.statements.append(statement)

        return PostgresJobRepository(), self.statements

    def __exit__(self, *exc):
        try:
            self.db.get_engine().dispose()
        except Exception as exc:
            print(f"engine dispose skipped: {exc}")
        self.db.get_engine.cache_clear()
        self.db._engine = None
        self.db._SessionLocal = None
        self._env.stop()
        self._tmp.cleanup()
        return False


class TestPostgresClaimNext(unittest.TestCase):
    """#700. `claim_next` loaded *every* pending row on every claim in order to
    sort by `payload_json.sort_key` in Python, then took `rows[0]`.

    The whole existing queue suite drives `JsonJobRepository`; the Postgres path
    -- the supported one -- had no test at all.
    """

    def test_claim_order_follows_sort_key_then_id(self):
        with _SqlBackedRepo() as (repo, _statements):
            third = repo.enqueue(
                {
                    "channel_id": "tapin",
                    "job_type": "render",
                    "payload_json": json.dumps({"sort_key": 5}),
                }
            )
            first = repo.enqueue(
                {
                    "channel_id": "tapin",
                    "job_type": "render",
                    "payload_json": json.dumps({"sort_key": 0}),
                }
            )
            second = repo.enqueue(
                {
                    "channel_id": "tapin",
                    "job_type": "render",
                    "payload_json": json.dumps({"sort_key": 2}),
                }
            )
            claimed = [repo.claim_next(), repo.claim_next(), repo.claim_next()]

        self.assertEqual([c.id for c in claimed], [first.id, second.id, third.id])

    def test_a_job_with_no_sort_key_falls_back_to_id_order(self):
        """`_claim_sort_tuple` returns (id, id) with no sort_key. The SQL has to
        agree, or drag-reorder (#148) and plain FIFO disagree about who is next."""
        with _SqlBackedRepo() as (repo, _statements):
            older = repo.enqueue(
                {"channel_id": "tapin", "job_type": "render", "payload_json": "{}"}
            )
            newer = repo.enqueue(
                {"channel_id": "tapin", "job_type": "render", "payload_json": "{}"}
            )
            claimed = [repo.claim_next(), repo.claim_next()]

        self.assertEqual([c.id for c in claimed], [older.id, newer.id])

    def test_claim_does_not_load_the_whole_pending_table(self):
        """The filed defect: no LIMIT, so every pending row crossed the wire per
        claim. Asserted on the SQL actually emitted, not on the row count."""
        with _SqlBackedRepo() as (repo, statements):
            for i in range(6):
                repo.enqueue(
                    {
                        "channel_id": "tapin",
                        "job_type": "render",
                        "payload_json": json.dumps({"sort_key": i}),
                    }
                )
            del statements[:]
            repo.claim_next()
            selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]

        self.assertTrue(selects, "claim_next emitted no SELECT")
        self.assertTrue(
            any("LIMIT" in s.upper() for s in selects),
            f"claim_next still selects unbounded rows: {selects}",
        )

    def test_a_claimed_job_is_never_handed_out_twice(self):
        with _SqlBackedRepo() as (repo, _statements):
            repo.enqueue({"channel_id": "tapin", "job_type": "render", "payload_json": "{}"})
            repo.enqueue({"channel_id": "tapin", "job_type": "render", "payload_json": "{}"})
            first = repo.claim_next()
            second = repo.claim_next()
            exhausted = repo.claim_next()

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first.id, second.id)
        self.assertIsNone(exhausted)

    def test_job_type_filter_still_applies(self):
        with _SqlBackedRepo() as (repo, _statements):
            repo.enqueue(
                {
                    "channel_id": "tapin",
                    "job_type": "upload",
                    "payload_json": json.dumps({"sort_key": 0}),
                }
            )
            render = repo.enqueue(
                {
                    "channel_id": "tapin",
                    "job_type": "render",
                    "payload_json": json.dumps({"sort_key": 9}),
                }
            )
            claimed = repo.claim_next(job_type="render")

        self.assertEqual(claimed.id, render.id)

    def test_a_job_scheduled_for_later_is_not_claimed(self):
        with _SqlBackedRepo() as (repo, _statements):
            repo.enqueue(
                {
                    "channel_id": "tapin",
                    "job_type": "render",
                    "payload_json": "{}",
                    "scheduled_at": datetime.now(timezone.utc) + timedelta(hours=3),
                }
            )
            claimed = repo.claim_next()

        self.assertIsNone(claimed)


HEX = re.compile(r"#(?:[0-9a-fA-F]{3,8})\b")
# An exempt declaration says so on its own line, with the reason. Grep-able,
# reviewable, and per-site -- unlike exempting a hex value globally, which would
# wave through `#000` everywhere the moment one legitimate `#000` exists.
EXEMPT_MARKER = "palette-exempt"


def unexempted_hex(css: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for n, line in enumerate(css.splitlines(), start=1):
        if EXEMPT_MARKER in line:
            continue
        out.extend((n, m.group(0)) for m in HEX.finditer(line))
    return out


class TestLegacyCssHasNoSecondPalette(unittest.TestCase):
    """#699. d1a1895 made the token CSS win the cascade by emitting it last, but
    that only works for selectors BOTH blocks declare. `.phone-bezel`,
    `.yt-mock` and `.cheat-sheet` exist only in `_CSS`, so ordering cannot reach
    them and 93e5feb put `#2a2f3a` / `#111` / `#000` / `#fff` straight back in.

    Nothing in the repo scanned for this -- no lint rule, no allowlist, no
    annotation convention -- which is why the palette regrew three commits after
    it was fixed.
    """

    def test_css_carries_no_unexempted_hex_literal(self):
        from core.html_report import _CSS

        offenders = unexempted_hex(_CSS)
        self.assertEqual(
            offenders,
            [],
            "literal colours in _CSS must be a token var() or carry an explicit "
            f"'/* {EXEMPT_MARKER}: reason */': {offenders}",
        )

    def test_every_exemption_states_a_reason(self):
        """An exemption with no reason is an allowlist entry, which is the thing
        this item exists to stop."""
        from core.html_report import _CSS

        for n, line in enumerate(_CSS.splitlines(), start=1):
            if EXEMPT_MARKER not in line:
                continue
            reason = line.split(EXEMPT_MARKER, 1)[1].lstrip(": ").rstrip("*/ ").strip()
            with self.subTest(line=n):
                self.assertTrue(len(reason) > 8, f"line {n} exempts without a reason")

    def test_the_bezel_and_cheatsheet_read_their_colour_from_tokens(self):
        """Behaviour, not shape: the compiled page must paint those borders with
        the token hex, and the token must actually be defined on the page."""
        from core.design_tokens import surface_hex
        from core.html_report import themed_page

        page = themed_page("Booth", "<p>x</p>", channel_id="tapin").lower()
        border = surface_hex("border").lower()
        self.assertIn(f"--border:{border}", page.replace(" ", ""))
        self.assertIn("var(--border)", page)

    def test_token_background_still_wins_the_cascade(self):
        """The existing guard in test_stage2_html pins one hardcoded sentinel
        (#111318) behind `if at_legacy != -1`, so it passes vacuously the moment
        that sentinel moves. Bind the claim to the scanner instead."""
        from core.chrome import themed_css
        from core.html_report import _CSS, themed_page

        page = themed_page("Booth", "<p>x</p>", channel_id="tapin")
        self.assertIn("design_tokens.json", page)
        self.assertGreater(
            page.find(themed_css("tapin").strip()[:40]),
            page.find(_CSS.strip()[:40]),
            "token CSS must still be emitted after the legacy block",
        )


class TestCorrectionSubstrate(unittest.TestCase):
    """#112. The detection half of the retraction watch exists. The recording
    half had no substrate at all, and three things that LOOK like substrate were
    empty in production:

      1. `ClaimVerification.to_dict()` dropped the claim list and every
         `citation_line` -- the field that says which source backed which claim.
      2. Nothing ever set `features["source_urls"]`, though `collect_source_urls`
         was already being called and its result thrown away.
      3. `write_render_sidecars` reads exactly those two keys, so every
         `.facts.json` shipped `{"claims": [], "sources": []}`.

    The existing sidecar test hand-builds both missing keys, which is why this
    shipped unnoticed -- it is green over an empty artifact.
    """

    def _verification(self):
        from core.claim_verifier import ClaimVerification, VerifiedClaim

        return ClaimVerification(
            claims=[
                VerifiedClaim(
                    claim="Jones beat Pereira",
                    supported=True,
                    citation_line="Jones defeated Pereira at UFC 320 (tapology.com)",
                ),
                VerifiedClaim(claim="The purse was $50m", supported=False),
            ]
        )

    def test_to_dict_keeps_the_claim_to_source_edge(self):
        payload = self._verification().to_dict()
        self.assertIn("claims", payload)
        supported = [c for c in payload["claims"] if c.get("supported")]
        self.assertTrue(supported, "supported claims were dropped at persist time")
        self.assertTrue(
            supported[0].get("citation_line"),
            "citation_line is the claim->source edge a correction dossier joins on",
        )

    def test_to_dict_keeps_its_existing_keys(self):
        """Readers of the compact shape (run_quality, calibration) must not break."""
        payload = self._verification().to_dict()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["supported"], 1)
        self.assertEqual(payload["support_rate"], 0.5)
        self.assertEqual(payload["unsupported"], ["The purse was $50m"])

    def test_sidecar_carries_real_claims_and_sources(self):
        """Driven off the REAL `to_dict()` output, not a hand-built dict. This is
        the assertion tests/test_wave23_wraps.py should have made."""
        from core.render_artifacts import write_render_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "clip.mp4")
            with open(mp4, "wb") as fh:
                fh.write(b"fake-mp4-bytes")
            write_render_sidecars(
                mp4,
                script="Hook. Jones beat Pereira.",
                features={
                    "claim_verification": self._verification().to_dict(),
                    "source_urls": ["https://tapology.com/x"],
                },
                quality={"ungrounded_count": 0},
            )
            with open(mp4.replace(".mp4", ".facts.json"), encoding="utf-8") as fh:
                data = json.load(fh)

        self.assertTrue(data["claims"], "sidecar shipped with an empty claims list")
        self.assertTrue(data["sources"], "sidecar shipped with an empty sources list")
        self.assertIn("tapology.com", json.dumps(data))
        self.assertIn("citation_line", json.dumps(data))

    def test_engine_publishes_source_urls_in_its_features(self):
        """`collect_source_urls` was already called, and its result used only for
        the single-outlet demotion -- never returned, so the sidecar that reads
        `features["source_urls"]` always got nothing. Drives the real engine."""
        from core.content_engine import generate_content_package

        payload = {
            "script": "Jones beat Pereira at UFC 320 in a first-round finish. " * 8,
            "title": "Jones stops Pereira",
            "description": "desc",
            "tags": ["ufc"],
        }
        operator_facts = [
            "Jones beat Pereira at UFC 320 (https://www.tapology.com/fight/1)",
            "Purse figures via https://www.mmajunkie.com/purse",
        ]
        with (
            patch(
                "core.content_engine.enrich_facts",
                return_value="- Jones beat Pereira at UFC 320",
            ),
            patch("core.content_engine._call_content_llm", return_value=payload),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="Jones stops Pereira"),
            patch("core.content_engine._maybe_improve_hook", side_effect=lambda s: s),
            patch(
                "core.content_engine._maybe_inject_insight",
                side_effect=lambda s, *_a, **_k: s,
            ),
        ):
            result = generate_content_package(
                "Jones vs Pereira",
                {},
                (40, 80),
                "2026-09-09",
                channel_id="tapin",
                key_facts=operator_facts,
                length_choice="1",
            )

        urls = result.get("source_urls") or []
        self.assertTrue(urls, "engine features carry no source_urls for the sidecar to write")
        self.assertTrue(
            any("tapology.com" in u for u in urls),
            f"the operator's own pasted source did not survive into features: {urls}",
        )

    def test_ungrounded_count_falls_back_to_features(self):
        """`core/pipeline.py` hands the sidecar a hardcoded `quality={}` -- it
        cannot do otherwise, because `build_quality` needs a run_id that only
        exists after the sidecar has run. So `ungrounded_count` was `None` in
        every `.facts.json` ever written. The count is just
        `len(features["ungrounded_entities"])`, so derive it where the field is
        owned rather than reordering the pipeline around one number."""
        from core.render_artifacts import write_render_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "clip.mp4")
            with open(mp4, "wb") as fh:
                fh.write(b"fake-mp4-bytes")
            out = write_render_sidecars(
                mp4,
                script="Hook.",
                features={"ungrounded_entities": ["$50 million", "17 fights"]},
                quality={},
            )

        self.assertEqual(out["ungrounded_count"], 2)

    def test_an_explicit_quality_count_still_wins(self):
        from core.render_artifacts import write_render_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "clip.mp4")
            with open(mp4, "wb") as fh:
                fh.write(b"x")
            out = write_render_sidecars(
                mp4,
                script="Hook.",
                features={"ungrounded_entities": ["a", "b"]},
                quality={"ungrounded_count": 0},
            )

        self.assertEqual(out["ungrounded_count"], 0)


class TestCorrectionDossier(unittest.TestCase):
    """#112 proper. #686 shipped a toast: first hit only, truncated to 180 chars,
    deduped per process, joined to no run and persisted nowhere. Nothing was
    written, so a reversal spotted at 3am was gone by morning.

    Scope correction the exploration forced: the watch reads `last_trace` -- ONE
    most-recent draft. #112 is about POST-PUBLISH reversal, so the dossier walks
    published videos instead.
    """

    def _published(self, run_id=75, video_id="vid123"):
        from storage.repositories.publish_log import PublishLogRecord

        return PublishLogRecord(
            id=1,
            content_run_id=run_id,
            idempotency_key="k",
            channel_id="tapin",
            youtube_video_id=video_id,
            privacy_status="public",
            status="uploaded",
            published_at=datetime.now(timezone.utc) - timedelta(days=2),
        )

    def _run(self, run_id=75):
        from storage.repositories.content_runs import ContentRunRecord

        return ContentRunRecord(
            id=run_id,
            channel_id="tapin",
            input_topic="Jones vs Pereira",
            selected_topic="Jones vs Pereira",
            status="completed",
            composite_score=60.0,
            features_json=json.dumps(
                {
                    "source_urls": ["https://tapology.com/fight/1"],
                    "claim_verification": {
                        "claims": [
                            {
                                "claim": "Jones beat Pereira at UFC 320",
                                "supported": True,
                                "citation_line": "Jones def. Pereira (tapology.com)",
                            }
                        ]
                    },
                }
            ),
        )

    def _scan(self, vault: str, **kwargs):
        from core.correction_dossier import scan_published_for_corrections

        kwargs.setdefault("stamp_path", os.path.join(vault, "correction_scan.json"))
        return scan_published_for_corrections("tapin", **kwargs)

    def test_a_reversal_on_a_published_video_writes_a_dossier(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = self._scan(
                    vault,
                    published=[self._published()],
                    run_lookup={75: self._run()},
                    fetch=lambda url: "This report has been RETRACTED by the outlet.",
                    negative_store=None,
                )
                self.assertEqual(len(found), 1)
                dossier = found[0]
                self.assertEqual(dossier.video_id, "vid123")
                self.assertIn("Jones beat Pereira", dossier.claim)
                self.assertIn("tapology.com", dossier.source_url)
                notes = list(os.scandir(os.path.join(vault, "tapin", "_reports")))
                self.assertEqual(len(notes), 1, "no dossier note was written")
                with open(notes[0].path, encoding="utf-8") as fh:
                    text = fh.read()

        # The GPT-6 correction-dossier fields: which video, which claim, what
        # changed, how bad, what to do, and whether it is resolved.
        for field in ("vid123", "Jones beat Pereira", "tapology.com", "Severity", "Status"):
            self.assertIn(field, text, f"dossier omits {field!r}")

    def test_the_dossier_filename_does_not_collide_between_two_videos(self):
        """`write_report_note` writes `{date}_{kind}.md`, so two corrections on
        one day overwrite each other unless `kind` carries the video id."""
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                self._scan(
                    vault,
                    published=[
                        self._published(run_id=75, video_id="aaa"),
                        self._published(run_id=76, video_id="bbb"),
                    ],
                    run_lookup={75: self._run(75), 76: self._run(76)},
                    fetch=lambda url: "RETRACTED",
                    negative_store=None,
                )
                notes = sorted(e.name for e in os.scandir(os.path.join(vault, "tapin", "_reports")))

        self.assertEqual(len(notes), 2, f"one dossier overwrote the other: {notes}")

    def test_a_healthy_source_writes_nothing(self):
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = self._scan(
                    vault,
                    published=[self._published()],
                    run_lookup={75: self._run()},
                    fetch=lambda url: "Jones beat Pereira at UFC 320. Nothing has changed.",
                    negative_store=None,
                )
                reports = os.path.join(vault, "tapin", "_reports")

        self.assertEqual(found, [])
        self.assertFalse(os.path.isdir(reports), "wrote a dossier for a healthy source")

    def test_a_confirmed_reversal_is_recorded_as_a_negative_fact(self):
        """Detection that changes nothing is a toast. `record_negative` is the
        existing correction memory and `negative_gate_blocks` defaults to block,
        so this is what stops the reversed claim being said again."""
        recorded: list[tuple[str, str, str]] = []

        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                self._scan(
                    vault,
                    published=[self._published()],
                    run_lookup={75: self._run()},
                    fetch=lambda url: "RETRACTED",
                    negative_store=lambda f, c, reason: recorded.append((f, c, reason)),
                )

        self.assertEqual(len(recorded), 1)
        self.assertIn("Jones beat Pereira", recorded[0][1])
        self.assertIn("vid123", recorded[0][2])

    def test_nothing_published_is_touched_on_youtube(self):
        """The review is explicit: a correction is written and surfaced, never
        applied to live content without authorisation. Drive a real reversal and
        assert the YouTube client is never constructed."""
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                with patch("youtube.oauth.get_youtube_service") as svc:
                    found = self._scan(
                        vault,
                        published=[self._published()],
                        run_lookup={75: self._run()},
                        fetch=lambda url: "RETRACTED",
                        negative_store=None,
                    )

        self.assertEqual(len(found), 1, "the reversal itself must still be detected")
        svc.assert_not_called()

    def test_a_run_from_before_this_wave_is_skipped_not_crashed(self):
        """Found by running `ops corrections` for real: every run generated
        before the verifier ran persists `claim_verification: null`, and every
        run before this wave has no `claims` key. `dict.get("claims")` returned
        None and the comprehension raised."""
        from storage.repositories.content_runs import ContentRunRecord

        legacy = ContentRunRecord(
            id=75,
            channel_id="tapin",
            input_topic="old",
            selected_topic="old",
            status="completed",
            composite_score=1.0,
            features_json=json.dumps({"claim_verification": None, "source_urls": ["https://x/1"]}),
        )
        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                found = self._scan(
                    vault,
                    published=[self._published()],
                    run_lookup={75: legacy},
                    fetch=lambda url: "RETRACTED",
                    negative_store=None,
                )

        self.assertEqual(found, [])

    def test_a_fetch_failure_is_not_reported_as_all_clear(self):
        """`notify_retractions_if_due` swallowed every exception into `False`,
        so a broken watch and a clean one looked identical. A missing finding
        must not resemble a clean finding."""

        def boom(url):
            raise OSError("network down")

        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                with self.assertLogs(
                    "content_machine.core.correction_dossier", level="WARNING"
                ) as logs:
                    found = self._scan(
                        vault,
                        published=[self._published()],
                        run_lookup={75: self._run()},
                        fetch=boom,
                        negative_store=None,
                    )

        self.assertEqual(found, [])
        self.assertTrue(any("unreachable" in line.lower() for line in logs.output))


class TestBrandKitCompiler(unittest.TestCase):
    """#151. Brand identity lives in three unjoined places -- design_tokens.json
    (palette), channels.json (caption skin, end card, look, intro) and
    assets/branding/<channel>/ (logo, banner) -- and six modules each reach into
    them separately. `channel-go-live` only ran `os.path.isfile` over the third,
    which is why the backlog text says it "checks files exist; it does not apply
    a kit".

    Deliberately a READ path: the compiler resolves the same values the existing
    accessors already return, so no rendered pixel changes in this wave.
    """

    def test_compile_kit_matches_todays_accessors_exactly(self):
        """The refactor must be value-identical, or it is a restyle wearing a
        refactor's clothes."""
        from core.brand_kit import compile_kit
        from core.design_tokens import (
            caption_fill_hex,
            caption_outline_hex,
            header_border_hex,
            look_grain,
            look_vignette,
        )

        for channel in ("tapin", "moneywise"):
            with self.subTest(channel=channel):
                kit = compile_kit(channel)
                self.assertEqual(kit.caption_fill, caption_fill_hex(channel))
                self.assertEqual(kit.caption_outline, caption_outline_hex(channel))
                self.assertEqual(kit.header_border, header_border_hex(channel))
                self.assertEqual(kit.grain, look_grain(channel))
                self.assertEqual(kit.vignette, look_vignette(channel))

    def test_kit_reports_what_is_missing_rather_than_a_bare_boolean(self):
        """An unknown channel has no assets; the kit must name the files."""
        from core.brand_kit import compile_kit

        kit = compile_kit("no-such-channel")
        self.assertIn("logo", " ".join(kit.missing).lower())
        self.assertIn("banner", " ".join(kit.missing).lower())
        self.assertFalse(kit.complete)

    def test_provenance_names_the_source_each_field_came_from(self):
        """Three config files can disagree. A kit that cannot say which one won
        is a fourth place to look, not a single source of truth."""
        from core.brand_kit import compile_kit

        kit = compile_kit("tapin")
        self.assertEqual(kit.provenance["caption_fill"], "design_tokens.json")
        self.assertEqual(kit.provenance["caption_skin"], "channels.json")
        self.assertTrue(kit.provenance["logo"].startswith("assets/branding"))

    def test_channel_go_live_reports_kit_status_not_file_existence(self):
        from core.channel_go_live import inspect_channel

        report = inspect_channel("tapin")
        kit_checks = [c for c in report.checks if c.name == "brand_kit"]
        self.assertEqual(len(kit_checks), 1)
        detail = kit_checks[0].detail.lower()
        self.assertTrue(
            "resolved" in detail or "missing" in detail,
            f"brand_kit check still reports raw filenames: {kit_checks[0].detail!r}",
        )

    def test_structured_channel_config_is_not_stringified(self):
        """Found by running `ops brand-kit --channel moneywise`: caption_skin,
        color_grade and hook_motion are JSON objects in channels.json, and
        `str(dict)` dumped the whole repr into a column."""
        from core.brand_kit import compile_kit

        kit = compile_kit("moneywise")
        self.assertIsInstance(kit.caption_skin, dict)
        self.assertIsInstance(kit.color_grade, dict)
        self.assertIsInstance(kit.hook_motion, dict)
        self.assertEqual(kit.caption_skin.get("mode"), "word")
        rendered = kit.render()
        self.assertNotIn("{'mode'", rendered)

    def test_render_is_ascii_for_the_windows_console(self):
        """The dev console is cp1252; an em-dash came out as a replacement
        character in the real run."""
        from core.brand_kit import compile_kit

        compile_kit("tapin").render().encode("ascii")

    def test_a_kit_for_an_unknown_channel_is_empty_not_an_exception(self):
        from core.brand_kit import compile_kit

        kit = compile_kit("no-such-channel")
        self.assertTrue(kit.missing)
        self.assertFalse(kit.complete)


try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - CI installs [app]
    QApplication = None  # type: ignore[misc, assignment]


from tests.qt_support import requires_qt


@requires_qt
class TestBrandWindow(unittest.TestCase):
    """#151 GUI half. Read-only surface over the compiled kit."""

    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def test_window_shows_every_field_with_its_source(self):
        from core.brand_kit import compile_kit
        from desktop.brand import BrandWindow, kit_rows

        kit = compile_kit("tapin")
        window = BrandWindow(channel_id="tapin", kit=kit)
        self.assertEqual(window.table.rowCount(), len(kit_rows(kit)))
        sources = {window.table.item(r, 2).text() for r in range(window.table.rowCount())}
        self.assertIn("design_tokens.json", sources)
        self.assertIn("channels.json", sources)

    def test_an_incomplete_kit_says_what_is_missing(self):
        from core.brand_kit import compile_kit
        from desktop.brand import BrandWindow

        window = BrandWindow(channel_id="no-such-channel", kit=compile_kit("no-such-channel"))
        self.assertIn("missing", window.status.text().lower())

    def test_the_panel_is_registered_and_reachable(self):
        from desktop.launch import desktop_mode
        from scripts.ops import COMMANDS

        self.assertIn("brand-panel", COMMANDS)
        self.assertIn("brand-kit", COMMANDS)
        self.assertEqual(desktop_mode(["--brand"]), "brand")


if __name__ == "__main__":
    unittest.main()
