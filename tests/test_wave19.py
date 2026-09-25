"""Wave 19: headless all-angles, draft freshness, the weekly target, nightly drafts, wrong
actors named in the script, and gates that are proven to be tested.

Operator calls 2026-09-16 (second round): Claude runs the first live all-angles render itself
(render only); news drafts re-ask after 2 days, others after 7; nightly drafts through a
scheduler verb the operator installs; #739 swapped for #748's wrong-actor gap. Each test
here failed on unmodified cf7c62b unless its docstring says it guards existing behaviour.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


class _StopAtPipeline(Exception):
    pass


def _drive_auto_generate(argv: list[str]):
    """Run scripts.auto_generate.main up to run_pipeline and return that call."""
    from core.cadence import CadenceStatus
    from scripts import auto_generate

    evaluated = [
        ("GTA 6 angle zero", 40.0, {"a": 1}),
        ("GTA 6 angle one", 90.0, {"b": 2}),
        ("GTA 6 angle two", 60.0, {"c": 3}),
    ]
    discovery = SimpleNamespace(
        evaluated=evaluated, raw_scores=[], angle_scores=[], base_signals={}, timings={}
    )
    spinner = MagicMock()
    spinner.__enter__ = MagicMock(return_value=SimpleNamespace(report=None))
    spinner.__exit__ = MagicMock(return_value=False)
    with (
        patch.object(auto_generate, "_pick_topic", return_value="GTA 6"),
        patch(
            "core.cadence.cadence_status",
            return_value=CadenceStatus(recent=0, upcoming=0, cap=5, window_days=7),
        ),
        patch("core.cadence.display_cadence"),
        patch("core.metrics_gate.metrics_gate_reason", return_value=None),
        patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value=None),
        patch("core.run_mode.apply_and_guard"),
        patch("core.ui.DiscoverySpinner", return_value=spinner),
        patch("core.pipeline.run_discovery", return_value=discovery),
        patch("core.pipeline.best_variant_index", return_value=1),
        patch("core.outlier.get_competitor_outlier", return_value=None),
        patch("core.outlier.display_outlier"),
        patch("core.vault_relevance.build_relevance_corpus", return_value=None),
        patch("core.pipeline.run_pipeline", side_effect=_StopAtPipeline) as run_pipeline,
        patch("builtins.print"),
    ):
        try:
            auto_generate.main(argv)
        except _StopAtPipeline:
            pass
    return run_pipeline.call_args


# --- #765 + #755 headless ------------------------------------------------------------


class TestHeadlessPicksWhatItPrints(unittest.TestCase):
    def test_the_script_is_written_for_the_ranked_variant(self):
        call = _drive_auto_generate(["--channel", "tapin", "--topic", "GTA 6", "--length", "2"])
        self.assertIsNotNone(call)
        self.assertEqual(call.kwargs["variant_index"], 1)

    def test_all_angles_passes_every_variant_as_chapters_at_extended(self):
        call = _drive_auto_generate(["--channel", "tapin", "--topic", "GTA 6", "--all-angles"])
        self.assertIsNotNone(call)
        self.assertEqual(
            call.kwargs["chapter_angles"],
            ["GTA 6 angle zero", "GTA 6 angle one", "GTA 6 angle two"],
        )
        self.assertEqual(call.kwargs["length_choice"], "4")

    def test_no_queue_and_cut_shorts_flags_exist(self):
        text = (ROOT / "scripts" / "auto_generate.py").read_text(encoding="utf-8")
        for flag in ("--all-angles", "--no-queue", "--cut-shorts"):
            with self.subTest(flag=flag):
                self.assertIn(f'"{flag}"', text)
        self.assertIn("cut_chapter_shorts(", text)
        self.assertIn("chapter_report(", text)


# --- #748 wrong actor ----------------------------------------------------------------


class TestReversedRelations(unittest.TestCase):
    FACTS = "Tom Aspinall defeated Jon Jones at UFC 321.\nThe card sold out in Abu Dhabi."

    def test_a_reversed_result_is_found(self):
        from core.relational_check import reversed_relations

        found = reversed_relations(
            "It was a huge night. Jon Jones defeated Tom Aspinall in the second round.",
            self.FACTS,
        )
        self.assertEqual(len(found), 1)
        self.assertIn("Jon Jones defeated Tom Aspinall", found[0])

    def test_the_right_direction_is_clean(self):
        from core.relational_check import reversed_relations

        self.assertEqual(
            reversed_relations("Tom Aspinall defeated Jon Jones in round two.", self.FACTS), []
        )

    def test_a_reversal_blocks_the_grounding_gate_even_after_the_verifier_passed(self):
        from core.claim_verifier import gate_blocks
        from core.relational_check import merge_reversals

        passed = {"total": 2, "supported": 2, "support_rate": 1.0, "unsupported": [], "claims": []}
        merged = merge_reversals(passed, "Jon Jones defeated Tom Aspinall.", self.FACTS)
        self.assertTrue(gate_blocks(merged))
        self.assertEqual(merged["unsupported_types"], ["result"])
        self.assertEqual(merged["total"], 3)
        self.assertAlmostEqual(merged["support_rate"], 2 / 3, places=3)

    def test_a_missing_verdict_still_gets_the_reversal(self):
        from core.relational_check import merge_reversals

        merged = merge_reversals(None, "Jon Jones defeated Tom Aspinall.", self.FACTS)
        self.assertIsNotNone(merged)
        self.assertEqual(len(merged["unsupported"]), 1)
        self.assertIsNone(merge_reversals(None, "A clean script.", self.FACTS))

    def test_content_engine_merges_it(self):
        text = (ROOT / "core" / "content_engine.py").read_text(encoding="utf-8")
        self.assertIn("merge_reversals(", text)

    def test_title_fallback_fails_a_reversed_title(self):
        from core.youtube_meta import _heuristic_title_script_check

        verdict = _heuristic_title_script_check(
            "Jon Jones Defeated Tom Aspinall", "Tom Aspinall defeated Jon Jones in round two."
        )
        self.assertFalse(verdict["passed"], verdict)


# --- #763 draft freshness ------------------------------------------------------------


class TestDraftFreshness(unittest.TestCase):
    def _meta(self, topic: str, days_old: float) -> dict:
        made = datetime.now() - timedelta(days=days_old)
        return {"topic": topic, "variant": topic, "created_at": made.isoformat(timespec="seconds")}

    def test_news_drafts_get_two_days_and_others_seven(self):
        from core.batch_review import freshness_window_days

        self.assertEqual(freshness_window_days(self._meta("UFC 321 main card results", 0)), 2)
        self.assertEqual(freshness_window_days(self._meta("GTA 6 trailer 3 leak", 0)), 2)
        self.assertEqual(
            freshness_window_days(self._meta("How GTA Online's economy actually works", 0)), 7
        )

    def test_age_is_read_from_created_at(self):
        from core.batch_review import draft_age_days

        self.assertAlmostEqual(draft_age_days(self._meta("x", 3)), 3.0, places=1)
        self.assertIsNone(draft_age_days({"topic": "x"}))

    def test_an_old_news_draft_asks_before_the_render_question(self):
        from core.batch_review import review_drafts

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp, "a")
            folder.mkdir()
            (folder / "draft.md").write_text("## Script\n\nLine one.\n", encoding="utf-8")
            meta = self._meta("UFC 321 main card results", 4)
            meta.update({"run_id": 5, "title": "UFC 321", "channel_id": "tapin"})
            (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            prompts: list[str] = []
            lines: list[str] = []

            def ask(prompt):
                prompts.append(prompt)
                return ""

            with patch("core.batch_review._render") as render:
                summary = review_drafts(
                    "tapin",
                    root=tmp,
                    ask=ask,
                    print_fn=lambda *a: lines.append(" ".join(map(str, a))),
                )
            saved = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(len(prompts), 1, prompts)
        self.assertIn("still current", prompts[0])
        self.assertIn("4d", "\n".join(lines))
        render.assert_not_called()
        self.assertEqual(summary.later, [5])
        self.assertNotIn("review", saved)


# --- #764 under-target line ----------------------------------------------------------


class TestWeeklyTarget(unittest.TestCase):
    def _status(self, recent: int, upcoming: int):
        from core.cadence import CadenceStatus

        return CadenceStatus(recent=recent, upcoming=upcoming, cap=5, window_days=7)

    def test_under_target_names_the_gap(self):
        from core.cadence import target_line

        with patch.dict(os.environ, {"UPLOADS_PER_WEEK_TARGET": "3"}):
            line = target_line(self._status(1, 0))
        self.assertIn("1 of 3-5", line)
        self.assertIn("short 2", line)
        self.assertIn("batch-review", line)

    def test_on_target_is_silent(self):
        from core.cadence import target_line

        with patch.dict(os.environ, {"UPLOADS_PER_WEEK_TARGET": "3"}):
            self.assertEqual(target_line(self._status(2, 1)), "")

    def test_display_cadence_and_status_print_it(self):
        from core.cadence import display_cadence

        lines: list[str] = []
        with patch.dict(os.environ, {"UPLOADS_PER_WEEK_TARGET": "3"}):
            display_cadence(self._status(0, 0), print_fn=lambda *a: lines.append(str(a[0])))
        self.assertTrue(any("short 3" in line for line in lines), lines)
        for name in ("core/status.py", "core/overnight.py"):
            with self.subTest(caller=name):
                self.assertIn("target_line(", (ROOT / name).read_text(encoding="utf-8"))
        self.assertIn("UPLOADS_PER_WEEK_TARGET", (ROOT / ".env.example").read_text("utf-8"))


# --- nightly drafts ------------------------------------------------------------------


class TestNightlyTask(unittest.TestCase):
    def test_install_argv_schedules_overnight_daily(self):
        from core.nightly_task import TASK_NAME, install_argv

        argv = install_argv("tapin", python=r"C:\Py\python.exe", repo=r"C:\dev\content_machine")
        self.assertEqual(argv[:6], ["schtasks", "/Create", "/SC", "DAILY", "/ST", "05:00"])
        self.assertEqual(argv[argv.index("/TN") + 1], TASK_NAME)
        command = argv[argv.index("/TR") + 1]
        self.assertIn(r'cd /d "C:\dev\content_machine"', command)
        self.assertIn("-m scripts.ops overnight --channel tapin --count 3", command)
        self.assertEqual(argv[-1], "/F")

    def test_run_reports_a_missing_schtasks_instead_of_raising(self):
        from core.nightly_task import run_schtasks

        with patch("core.nightly_task.subprocess.run", side_effect=FileNotFoundError):
            code, out = run_schtasks(["schtasks", "/Query"])
        self.assertNotEqual(code, 0)
        self.assertIn("schtasks", out)

    def test_ops_verb_defaults_to_query_and_never_installs_unasked(self):
        from scripts import ops

        self.assertIn("schedule-drafts", ops.COMMANDS)
        args = SimpleNamespace(channel="tapin", install=False, remove=False)
        with (
            patch("core.nightly_task.run_schtasks", return_value=(1, "not found")) as run,
            patch("builtins.print"),
        ):
            ops.COMMANDS["schedule-drafts"][1](args)
        argv = run.call_args.args[0]
        self.assertIn("/Query", argv)
        self.assertNotIn("/Create", argv)


# --- #627 gate mutation --------------------------------------------------------------


class TestGateMutation(unittest.TestCase):
    def test_mutants_flip_one_site_at_a_time(self):
        from scripts.mutate_gates import apply_mutant, count_mutants

        source = "def f(x, y):\n    return x > 3 and not y\n"
        self.assertEqual(count_mutants(source), 3)  # >, and, not
        namespace: dict = {}
        exec(compile(apply_mutant(source, 0), "<m>", "exec"), namespace)
        self.assertTrue(namespace["f"](1, False))  # x <= 3 and not y

    @unittest.skipIf(os.environ.get("MUTATION_CHILD"), "no mutation runs inside a mutant")
    def test_a_real_mutant_is_killed_by_the_suite(self):
        from scripts.mutate_gates import count_mutants, function_source, run_mutant

        source = function_source("core.claim_types", "claim_blocks")
        self.assertGreater(count_mutants(source), 0)
        killed = run_mutant(
            "core.claim_types",
            "claim_blocks",
            0,
            ["tests.test_wave18.TestClaimTypes"],
        )
        self.assertTrue(killed)

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("mutate-gates", ops.COMMANDS)


class TestVoiceCostFollowsTheLengthPolicy(unittest.TestCase):
    """#768, live run 2026-09-17: the Extended render resolved to piper ($0) but the
    projection printed `tts $1.2692` - the cost meter read TTS_PROVIDER alone.

    #775 reversed the piper default, so the policy now only diverts long-form when the
    operator sets TTS_PROVIDER_LONG. The meter must follow it either way, which is what
    these pin."""

    SCRIPT = "x" * 5700

    def _env(self, **extra):
        env = {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": "piper"}
        env.update(extra)
        return patch.dict(os.environ, env)

    def test_extended_costs_nothing_when_the_policy_sends_it_to_piper(self):
        from core.cost_meter import estimate_run_cost, render_cost_lines

        with self._env():
            self.assertEqual(render_cost_lines(self.SCRIPT, length_choice="4")["tts"], 0.0)
            self.assertEqual(
                estimate_run_cost(script=self.SCRIPT, rendered=True, length_choice="4")["tts"],
                0.0,
            )
            self.assertGreater(render_cost_lines(self.SCRIPT, length_choice="2")["tts"], 0.0)

    def test_an_explicit_paid_provider_still_costs(self):
        from core.cost_meter import render_cost_lines

        with self._env(TTS_PROVIDER="elevenlabs"):
            self.assertGreater(render_cost_lines(self.SCRIPT, length_choice="4")["tts"], 0.0)

    def test_every_cost_caller_passes_the_length(self):
        pipeline = (ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
        for needle in ("rendered=True, length_choice=", "merge_render_cost("):
            with self.subTest(needle=needle):
                self.assertIn(needle, pipeline)
        self.assertIn(
            "length_choice=length_choice", pipeline.split("merge_render_cost(", 1)[1][:400]
        )
        review = (ROOT / "core" / "batch_review.py").read_text(encoding="utf-8")
        self.assertIn("render_cost_lines(draft.script, length_choice=", review)


class TestVoiceStageNamesTheRealProvider(unittest.TestCase):
    """#772, live run 79: the progress line said "ElevenLabs TTS..." and the next line
    said "Provider: piper (local, $0)"."""

    def test_the_label_follows_the_length_policy(self):
        from core.tts import voice_stage_label

        with patch.dict(os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": "piper"}):
            self.assertIn("piper", voice_stage_label("4"))
            self.assertIn("elevenlabs", voice_stage_label("2").lower())

    def test_the_render_uses_it(self):
        pipeline = (ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn('progress.stage("ElevenLabs TTS...")', pipeline)
        self.assertIn("voice_stage_label(", pipeline)


class TestMutationSurvivorsNowKilled(unittest.TestCase):
    """The first `ops mutate-gates` run (2026-09-17) left 7 of 45 mutants alive. Each test
    below kills one; they passed on the real code and fail on the named mutant."""

    RUMOR = "GTA 6 is reportedly getting a second trailer."
    GOTY = "GTA 5 didn't win Game of the Year in 2013."

    def test_types_without_claim_rows_are_read(self):
        # typed_unsupported #2: `len(types) == len(claims)` flipped.
        from core.claim_types import blocking_unsupported

        verification = {"unsupported": [self.RUMOR], "unsupported_types": ["rumor"]}
        self.assertEqual(blocking_unsupported(verification), [])

    def test_claim_rows_alone_carry_the_type(self):
        # typed_unsupported #5 / #7: `not supported` removed, `or ""` turned into `and ""`.
        from core.claim_types import typed_unsupported

        verification = {
            "unsupported": [self.RUMOR],
            "claims": [{"claim": self.RUMOR, "supported": False, "type": "rumor"}],
        }
        self.assertEqual(typed_unsupported(verification), [(self.RUMOR, "rumor")])

    def test_a_junk_claim_row_is_skipped_not_raised(self):
        # typed_unsupported #6: `isinstance(row, dict) and ...` turned into `or`.
        from core.claim_types import typed_unsupported

        verification = {
            "unsupported": [self.RUMOR],
            "claims": ["not a row", {"claim": self.RUMOR, "supported": False, "type": "rumor"}],
        }
        self.assertEqual(typed_unsupported(verification), [(self.RUMOR, "rumor")])

    def test_merging_a_reversal_keeps_the_existing_types(self):
        # merge_reversals #4: the alignment check flipped wiped a typed award claim.
        from core.relational_check import merge_reversals

        typed = {
            "total": 1,
            "supported": 0,
            "unsupported": [self.GOTY],
            "unsupported_types": ["award"],
            "claims": [],
        }
        merged = merge_reversals(
            typed, "Jon Jones defeated Tom Aspinall.", "Tom Aspinall defeated Jon Jones."
        )
        self.assertEqual(merged["unsupported_types"], ["award", "result"])

    def test_unreadable_features_do_not_hold_a_run_unlisted(self):
        # _override_held #2: `return False` for non-dict features inverted.
        from core.spaced_queue import slot_privacy

        self.assertEqual(slot_privacy(None, features_json="[]"), "public")

    def test_support_rate_is_read_from_the_verification_block(self):
        # thin_facts_abort_reason #3: `features.get("claim_verification") or {}` -> `and {}`.
        from core.thin_facts import thin_facts_abort_reason

        with patch.dict(
            os.environ, {"THIN_FACTS_TTS_ABORT": "true", "THIN_FACTS_MIN_SUPPORT": "0.5"}
        ):
            reason = thin_facts_abort_reason(
                fact_count=10, features={"claim_verification": {"support_rate": 0.2}}
            )
        self.assertIsNotNone(reason)
        self.assertIn("20%", reason)


# --- #767 headless output under a redirected console ---------------------------------


class TestRedirectedConsole(unittest.TestCase):
    """Live run 2026-09-17: `auto_generate > log.txt` died on the cadence check mark -
    a redirected Windows stdout is cp1252, which is exactly how Task Scheduler runs it."""

    def test_a_check_mark_survives_a_cp1252_pipe(self):
        import subprocess
        import sys

        code = (
            "from core.console_encoding import ensure_utf8_stdout; ensure_utf8_stdout(); "
            "print('Cadence ' + chr(0x2713))"
        )
        env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, timeout=120
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])

    def test_headless_entry_points_call_it(self):
        for name in (
            "scripts/auto_generate.py",
            "scripts/ops.py",
            "core/overnight.py",
            "core/batch_generation.py",
            "jobs/worker.py",
        ):
            with self.subTest(entry=name):
                self.assertIn("ensure_utf8_stdout()", (ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
