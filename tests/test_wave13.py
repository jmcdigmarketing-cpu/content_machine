"""Wave 13: #736, #734, #737, #735.

Every test here was observed failing on unmodified 99708d9 for the reason named in its
docstring, except the #734 branch tests, which pin working behaviour the coverage table
showed was never executed, and say so.
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_SHIPPED_TOP = (
    "analytics",
    "apis",
    "config",
    "core",
    "desktop",
    "jobs",
    "publishing",
    "sports",
    "storage",
    "video",
    "youtube",
)


def _git(*args: str, cwd: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


class TestPackageBuildIgnoresStaleEggInfo(unittest.TestCase):
    """#736. setuptools builds an sdist from any `*.egg-info/SOURCES.txt` it finds in the
    source tree. A stale one made the sdist 701 members instead of 378. The audit built
    from the live repo, so its answer depended on leftovers nobody could see."""

    def test_stage_tree_copies_tracked_and_untracked_files_but_never_ignored_ones(self):
        from core.package_audit import stage_tree

        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as dest:
            _git("init", "-q", cwd=root)
            Path(root, ".gitignore").write_text("*.egg-info/\nbuild/\n/data/\n", encoding="utf-8")
            Path(root, "core").mkdir()
            Path(root, "core", "tracked.py").write_text("x = 1", encoding="utf-8")
            _git("add", ".gitignore", "core/tracked.py", cwd=root)
            Path(root, "core", "untracked.py").write_text("y = 2", encoding="utf-8")
            Path(root, "content_machine.egg-info").mkdir()
            Path(root, "content_machine.egg-info", "SOURCES.txt").write_text(
                "tests/test_x.py", encoding="utf-8"
            )
            Path(root, "data").mkdir()
            Path(root, "data", "quota_state.json").write_text("{}", encoding="utf-8")

            stage_tree(Path(root), Path(dest))

            staged = sorted(
                str(p.relative_to(dest)).replace("\\", "/")
                for p in Path(dest).rglob("*")
                if p.is_file()
            )
        self.assertEqual(staged, [".gitignore", "core/tracked.py", "core/untracked.py"])

    def test_the_build_runs_outside_the_repo_and_leaves_it_untouched(self):
        from core import package_audit

        seen_cwds: list[str] = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            seen_cwds.append(kwargs.get("cwd", ""))
            Path(kwargs["cwd"], "content_machine.egg-info").mkdir(exist_ok=True)
            name = "x.whl" if "wheel" in cmd else "x.tar.gz"
            Path(out, name).write_bytes(b"")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as out:
            with patch.object(package_audit.subprocess, "run", side_effect=fake_run):
                package_audit.build_archives(Path(out), root=Path(root))
            self.assertTrue(seen_cwds)
            for cwd in seen_cwds:
                self.assertNotEqual(Path(cwd).resolve(), Path(root).resolve())
            self.assertEqual(list(Path(root).iterdir()), [], "the build wrote into the repo")


def _quiet_publish_gates():
    """Every blocker except the one under test returns nothing."""
    return [
        patch("core.thin_facts.thin_facts_abort_reason", return_value=None),
        patch("core.render_gate.block_reason_from_quality", return_value=None),
        patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
        patch("core.cadence.cadence_status", return_value=SimpleNamespace(ok=True)),
        patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value=None),
        patch("core.tts_char_cap.tts_char_cap_reason", return_value=None),
        patch("core.disk_preflight.block_reason", return_value=None),
        patch("core.publish_windows.window_reason", return_value=None),
        patch("core.cross_channel_dup.cross_channel_dup_block_reason", return_value=None),
    ]


class _Quiet(unittest.TestCase):
    def setUp(self):
        self._patches = _quiet_publish_gates()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()


class TestEveryPublishBlockerReachesTheList(_Quiet):
    """#734 coverage: `publish_blockers.py:94-128` never executed. Each component gate was
    tested alone; nothing proved its reason reaches the refusal list. These passed on
    99708d9 - they pin behaviour, they did not find a bug."""

    def test_cadence_over_cap(self):
        from core.publish_blockers import blocking_publish_reasons

        status = SimpleNamespace(ok=False, total=9, cap=7, window_days=7)
        with patch("core.cadence.cadence_status", return_value=status):
            reasons = blocking_publish_reasons(channel_id="tapin")
        self.assertIn("cadence: 9/7 videos in 7d window", reasons)

    def test_rpm_below_cost(self):
        from core.publish_blockers import blocking_publish_reasons

        with patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value="rpm-cost gate: low"):
            self.assertIn("rpm-cost gate: low", blocking_publish_reasons(channel_id="tapin"))

    def test_tts_cap(self):
        from core.publish_blockers import blocking_publish_reasons

        with patch("core.tts_char_cap.tts_char_cap_reason", return_value="TTS character cap"):
            self.assertIn("TTS character cap", blocking_publish_reasons(script="long"))

    def test_disk_preflight(self):
        from core.publish_blockers import blocking_publish_reasons

        with patch("core.disk_preflight.block_reason", return_value="disk: 1 GB free"):
            self.assertIn("disk: 1 GB free", blocking_publish_reasons(mp4_path="x.mp4"))


class TestPublishBlockersReadTheRealRun(_Quiet):
    """#734, found by tracing the fields. `ops blocking` (`scripts/ops.py:1501`) and the
    web `/next` (`core/operator_shell.py:33`) passed only `channel_id`, so the render gate
    graded an empty dict. Measured on this machine: both said "report card F (need >= B)"
    while tapin's last rendered run (72) grades A with authenticity ok."""

    def setUp(self):
        super().setUp()
        self._patches[1].stop()  # this class exercises the real render gate
        self._patches.pop(1)

    def test_no_run_data_is_not_graded_as_an_F(self):
        from core.publish_blockers import blocking_publish_reasons

        reasons = blocking_publish_reasons(channel_id="tapin")
        self.assertFalse([r for r in reasons if "report card" in r], reasons)

    def test_the_last_run_context_is_loaded_from_the_trace_and_record(self):
        from core.publish_blockers import last_run_context

        trace = {"run_id": 72, "status": "rendered", "quality": {"authenticity_verdict": "ok"}}
        record = SimpleNamespace(
            features_json=json.dumps({"key_facts_count": 5}), mp4_path="out.mp4"
        )
        repo = SimpleNamespace(get=lambda run_id: record)
        with (
            patch("core.review_booth.last_reviewable_trace", return_value=trace),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
        ):
            context = last_run_context("tapin")
        self.assertEqual(context["quality"], {"authenticity_verdict": "ok"})
        self.assertEqual(context["fact_count"], 5)
        self.assertEqual(context["mp4_path"], "out.mp4")

    def test_with_no_run_the_sentence_says_so(self):
        from core.publish_blockers import publish_status_sentence

        with patch("core.review_booth.last_reviewable_trace", return_value=None):
            line = publish_status_sentence("tapin")
        self.assertIn("no rendered or drafted run", line.lower())

    def test_ops_blocking_and_next_use_the_real_run(self):
        from argparse import Namespace

        from core import operator_shell
        from scripts import ops

        with patch(
            "core.publish_blockers.publish_status_sentence", return_value="real sentence"
        ) as status:
            self.assertEqual(ops.cmd_blocking(Namespace(channel="tapin", html=False)), 0)
            with (
                patch("core.run_mode.projected_cost_block_reason", return_value=None),
                patch("core.fact_expiry.warning_lines", return_value=[]),
            ):
                self.assertEqual(operator_shell.next_sentence("tapin"), "real sentence")
        self.assertEqual(status.call_count, 2)


def _pyproject() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def _glob_match(rel: str, pattern: str) -> bool:
    """setuptools package-data semantics: `*` never crosses `/` (fnmatch's does)."""
    parts, pattern_parts = rel.split("/"), pattern.split("/")
    return len(parts) == len(pattern_parts) and all(
        fnmatch.fnmatch(part, want) for part, want in zip(parts, pattern_parts, strict=True)
    )


class TestTheWheelShipsWhatItNeeds(unittest.TestCase):
    """#737. `[tool.setuptools] packages` listed top-level packages only, so the only
    subpackage, `storage.repositories`, was absent from the wheel, and no `package-data`
    was declared, so `config/channels.json` and every other runtime file were too."""

    def test_every_subpackage_is_listed(self):
        packages = set(_pyproject()["tool"]["setuptools"]["packages"])
        tracked = subprocess.run(
            ["git", "ls-files", *[f"{top}/*__init__.py" for top in _SHIPPED_TOP]],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        needed = {str(Path(p).parent).replace("\\", "/").replace("/", ".") for p in tracked}
        self.assertEqual(sorted(needed - packages), [])

    def test_runtime_data_files_are_declared(self):
        globs = _pyproject()["tool"]["setuptools"].get("package-data", {})
        tracked = subprocess.run(
            ["git", "ls-files", "config/*.json", "core/data/*", "analytics/*.json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        # windows-terminal/profiles.json is a manual install fragment no code reads.
        runtime = [
            p for p in tracked if not p.startswith(("config/secrets/", "config/windows-terminal/"))
        ]
        missing = []
        for path in runtime:
            package, _, rel = path.partition("/")
            if not any(_glob_match(rel, g) for g in globs.get(package, [])):
                missing.append(path)
        self.assertEqual(missing, [])

    def test_no_glob_can_reach_the_secrets_folder(self):
        globs = _pyproject()["tool"]["setuptools"].get("package-data", {}).get("config", [])
        self.assertTrue(globs, "no config package-data declared")
        for secret in ("secrets/client_secrets.json", "secrets/youtube_token.json"):
            self.assertFalse([g for g in globs if _glob_match(secret, g)], f"{secret} would ship")

    def test_the_glob_matcher_does_not_cross_directories(self):
        """The first draft used fnmatch, whose `*` crosses `/`: it said `*.json`
        would ship `secrets/client_secrets.json`, which setuptools does not do."""
        self.assertTrue(fnmatch.fnmatch("secrets/client_secrets.json", "*.json"))
        self.assertFalse(_glob_match("secrets/client_secrets.json", "*.json"))
        self.assertTrue(_glob_match("seo/tapin.json", "seo/*.json"))

    def test_the_audit_flags_real_tokens_but_not_design_tokens(self):
        """Found by the #737 proof build: once `config/*.json` shipped, `ops package-audit`
        flagged `config/design_tokens.json` as a token file, because the rule matched any
        JSON name containing "token". A clean package would have failed its own audit."""
        import zipfile

        from core.package_audit import scan_archive

        with tempfile.TemporaryDirectory() as tmp:
            whl = Path(tmp, "pkg.whl")
            with zipfile.ZipFile(whl, "w") as archive:
                for name in (
                    "config/design_tokens.json",
                    "config/youtube_token.json",
                    "config/youtube_token_tapin.json",
                    "token.json",
                    "config/client_secrets.json",
                ):
                    archive.writestr(name, "{}")
            report = scan_archive(whl, secrets=[])
        self.assertEqual(
            sorted(report.path_hits),
            [
                "config/client_secrets.json",
                "config/youtube_token.json",
                "config/youtube_token_tapin.json",
                "token.json",
            ],
        )


class TestAuthenticityAndGroundingAreArmedByDefault(_Quiet):
    """#735. Operator call 2026-09-13: arm AUTHENTICITY_GATE and GROUNDING_GATE by code
    default (both defaulted to warn, and `ops selftest` showed neither armed here), and
    refuse publishing for a *block* verdict only - under block the publish list refused
    any verdict other than ok, so a 'review' video could not publish."""

    def test_unset_means_block(self):
        from core.authenticity import gate_mode
        from core.claim_verifier import grounding_gate_mode

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUTHENTICITY_GATE", None)
            os.environ.pop("GROUNDING_GATE", None)
            self.assertEqual(gate_mode(), "block")
            self.assertEqual(grounding_gate_mode(), "block")

    def test_warn_still_opts_out(self):
        from core.authenticity import gate_mode
        from core.claim_verifier import gate_blocks, grounding_gate_mode

        with patch.dict(os.environ, {"AUTHENTICITY_GATE": "warn", "GROUNDING_GATE": "warn"}):
            self.assertEqual(gate_mode(), "warn")
            self.assertEqual(grounding_gate_mode(), "warn")
            self.assertFalse(gate_blocks({"unsupported": ["x"]}))

    def test_publish_refuses_a_block_verdict_but_not_a_review(self):
        from core.publish_blockers import blocking_publish_reasons

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUTHENTICITY_GATE", None)
            review = blocking_publish_reasons(quality={"authenticity_verdict": "review"})
            block = blocking_publish_reasons(quality={"authenticity_verdict": "block"})
        self.assertFalse([r for r in review if "authenticity" in r], review)
        self.assertTrue([r for r in block if "authenticity" in r], block)

    def test_unattended_generation_uses_the_shared_rule(self):
        text = Path("scripts/auto_generate.py").read_text(encoding="utf-8")
        self.assertIn("blocks_render(auth)", text)
        self.assertNotIn('gate_mode() == "block" and auth.verdict == "block"', text)


if __name__ == "__main__":
    unittest.main()
