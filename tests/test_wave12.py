"""Wave 12: #630 (ops selftest), #640 (package audit), and the decision branches the
first CI coverage table showed no test executes.

Every test here was observed failing on unmodified db25e26 for the reason named in
its docstring, except the coverage tests at the bottom: those pin behaviour that
already worked but that nothing had ever executed, and say so.
"""

from __future__ import annotations

import io
import json
import os
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

_ALL_GATES = {
    "authenticity",
    "grounding",
    "negative_fact",
    "thin_facts",
    "over_length",
    "metrics",
    "unattended_render",
    "publish_deadman",
}


class TestSelftestRunsEveryGate(unittest.TestCase):
    """#630. Six gates stand between a draft and paid TTS or a publish, and three of
    them default to warn or off. Nothing ran them end to end, so "the gate works" and
    "the gate is armed here" were both taken on trust."""

    def test_every_gate_blocks_its_bad_fixture_and_allows_its_clean_one(self):
        from core.selftest import run_selftest

        results = {r.name: r for r in run_selftest()}
        self.assertEqual(set(results), _ALL_GATES)
        broken = {name: r.detail for name, r in results.items() if not (r.blocks and r.allows)}
        self.assertEqual(broken, {})

    def test_a_broken_gate_is_reported_and_fails_the_verb(self):
        from argparse import Namespace

        from core.selftest import run_selftest
        from scripts import ops

        with patch("core.claim_verifier.gate_blocks", return_value=False):
            results = {r.name: r for r in run_selftest()}
            self.assertFalse(results["grounding"].blocks)
            with redirect_stdout(io.StringIO()) as out:
                code = ops.cmd_selftest(Namespace())
        self.assertEqual(code, 1)
        self.assertIn("grounding", out.getvalue())
        self.assertIn("FAIL", out.getvalue())

    def test_the_verb_passes_when_every_gate_works(self):
        from argparse import Namespace

        from scripts import ops

        self.assertIn("selftest", ops.COMMANDS)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ops.cmd_selftest(Namespace()), 0)
        self.assertIn("armed here", out.getvalue())

    def test_the_operator_environment_is_restored(self):
        from core.selftest import run_selftest

        with patch.dict(os.environ, {"AUTHENTICITY_GATE": "warn"}):
            os.environ.pop("GROUNDING_GATE", None)
            run_selftest()
            self.assertEqual(os.environ.get("AUTHENTICITY_GATE"), "warn")
            self.assertNotIn("GROUNDING_GATE", os.environ)

    def test_armed_here_reads_the_real_environment(self):
        """A gate off by choice is information, not a failure."""
        from core.selftest import run_selftest

        with patch.dict(os.environ, {"METRICS_BEFORE_NEXT": ""}):
            off = {r.name: r for r in run_selftest()}["metrics"]
        with patch.dict(os.environ, {"METRICS_BEFORE_NEXT": "true"}):
            on = {r.name: r for r in run_selftest()}["metrics"]
        self.assertFalse(off.armed_here)
        self.assertTrue(on.armed_here)
        self.assertTrue(off.blocks and off.allows, "armed state must not affect the verdict")

    def test_it_never_reads_a_store(self):
        """Fixtures are passed in, so the result cannot depend on the operator's data."""
        from core.selftest import run_selftest

        def refuse(*_a, **_k):
            raise AssertionError("selftest touched a store")

        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", refuse),
            patch("storage.repositories.content_runs.get_content_run_repository", refuse),
            patch("core.run_quality.load_quality", refuse),
            patch("core.human_presence.last_human_at", refuse),
        ):
            results = run_selftest()
        self.assertTrue(all(r.blocks and r.allows for r in results), [r.detail for r in results])

    def test_authenticity_can_score_against_given_recent_scripts(self):
        from core.authenticity import evaluate_authenticity

        with patch("core.authenticity._recent_scripts", side_effect=AssertionError("store read")):
            report = evaluate_authenticity("a short recap", "tapin", recent=[])
        self.assertIn(report.verdict, ("ok", "review", "block"))

    def test_main_uses_the_same_authenticity_decision(self):
        text = Path("main.py").read_text(encoding="utf-8")
        self.assertIn("blocks_render(auth)", text)


_SECRET = "sk-SENTINEL-640-7a1c9e"
_FAKE_USER = "zqoperator640"


def _zip(dest: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(dest, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return dest


def _tar(dest: Path, members: dict[str, str]) -> Path:
    with tarfile.open(dest, "w:gz") as archive:
        for name, text in members.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return dest


class TestPackageAudit(unittest.TestCase):
    """#640. Nothing had ever looked inside a built package. `config/secrets/` holds
    real OAuth files on disk, `config` is a shipped package, and the only check that
    they stay out was that nobody had noticed them in."""

    def test_forbidden_paths_are_flagged(self):
        from core.package_audit import scan_archive

        with tempfile.TemporaryDirectory() as tmp:
            whl = _zip(
                Path(tmp, "pkg.whl"),
                {
                    "core/ok.py": "x = 1",
                    "config/secrets/youtube_token.json": "{}",
                    "config/secrets/README.md": "fine",
                    ".env": "A=1",
                    ".env.example": "A=",
                    "data/traces/1.json": "{}",
                },
            )
            report = scan_archive(whl, secrets=[])
        self.assertEqual(
            sorted(report.path_hits),
            [".env", "config/secrets/youtube_token.json", "data/traces/1.json"],
        )

    def test_a_secret_value_inside_a_member_is_flagged_by_name_only(self):
        from core.package_audit import render_audit, scan_archive

        with tempfile.TemporaryDirectory() as tmp:
            sdist = _tar(
                Path(tmp, "pkg.tar.gz"),
                {"pkg-0.1/core/leak.py": f'KEY = "{_SECRET}"', "pkg-0.1/core/ok.py": "x = 1"},
            )
            report = scan_archive(sdist, secrets=[_SECRET])
        self.assertEqual(report.secret_hits, ["pkg-0.1/core/leak.py"])
        text = render_audit([report])
        self.assertIn("leak.py", text)
        self.assertNotIn(_SECRET, text)

    def test_an_operator_path_inside_a_member_is_flagged(self):
        from core.package_audit import scan_archive

        with tempfile.TemporaryDirectory() as tmp:
            whl = _zip(
                Path(tmp, "pkg.whl"),
                {"core/where.py": f'VAULT = r"C:\\Users\\{_FAKE_USER}\\Documents\\x"'},
            )
            with patch.dict(os.environ, {"USERNAME": _FAKE_USER, "USER": _FAKE_USER}):
                report = scan_archive(whl, secrets=[])
        self.assertEqual(report.operator_path_hits, ["core/where.py"])

    def test_a_clean_archive_passes(self):
        from core.package_audit import scan_archive

        with tempfile.TemporaryDirectory() as tmp:
            whl = _zip(Path(tmp, "pkg.whl"), {"core/ok.py": "x = 1", ".env.example": "A="})
            report = scan_archive(whl, secrets=[_SECRET])
        self.assertFalse(report.path_hits or report.secret_hits or report.operator_path_hits)
        self.assertEqual(report.members, 2)

    def test_the_verb_fails_only_on_a_hit(self):
        from argparse import Namespace

        from scripts import ops

        self.assertIn("package-audit", ops.COMMANDS)
        with tempfile.TemporaryDirectory() as tmp:
            clean = _zip(Path(tmp, "clean.whl"), {"core/ok.py": "x = 1"})
            dirty = _zip(Path(tmp, "dirty.whl"), {"config/secrets/client_secrets.json": "{}"})
            with (
                patch("core.package_audit.build_archives", return_value=[clean]),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(ops.cmd_package_audit(Namespace()), 0)
            with (
                patch("core.package_audit.build_archives", return_value=[clean, dirty]),
                redirect_stdout(io.StringIO()) as out,
            ):
                self.assertEqual(ops.cmd_package_audit(Namespace()), 1)
        self.assertIn("client_secrets.json", out.getvalue())

    def test_a_build_leaves_no_new_directories_in_the_repo(self):
        """Found building by hand: `pip wheel .` left `build/` and
        `content_machine.egg-info/` in the repo root. The audit must clean up what it
        created, and only what it created."""
        from core import package_audit

        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as out:
            Path(root, "build").mkdir()  # pre-existing: must survive

            def fake_run(cmd, **_kwargs):
                Path(root, "content_machine.egg-info").mkdir(exist_ok=True)
                Path(root, "build", "lib").mkdir(parents=True, exist_ok=True)
                name = "x.whl" if "wheel" in cmd else "x.tar.gz"
                Path(out, name).write_bytes(b"")

                class _Done:
                    returncode = 0
                    stdout = stderr = ""

                return _Done()

            with patch.object(package_audit.subprocess, "run", side_effect=fake_run):
                package_audit.build_archives(Path(out), root=Path(root))
            self.assertFalse(Path(root, "content_machine.egg-info").exists())
            self.assertTrue(
                Path(root, "build").exists(), "a directory the operator had was removed"
            )


class TestUntestedGateDecisionsFromTheCoverageTable(unittest.TestCase):
    """The first CI coverage table (run 34744476819) showed these decision branches
    never executed: `render_gate.py:84-97` and `publish_deadman.py:43,50`. They
    already behaved correctly -- these pass on db25e26 -- but a green suite had never
    once run them, which is the thing #631 was meant to expose."""

    def test_a_missing_run_fails_closed(self):
        from core.render_gate import block_reason_for_run

        with patch.dict(os.environ, {"OVERNIGHT_RENDER_GATE": "true"}):
            self.assertIsNotNone(block_reason_for_run(None))
            with patch("core.run_quality.load_quality", return_value={}):
                self.assertIsNotNone(block_reason_for_run(42))

    def test_an_unreadable_quality_store_fails_open(self):
        from core.render_gate import block_reason_for_run

        with (
            patch.dict(os.environ, {"OVERNIGHT_RENDER_GATE": "true"}),
            patch("core.run_quality.load_quality", side_effect=OSError("locked")),
        ):
            self.assertIsNone(block_reason_for_run(42))

    def test_the_deadman_blocks_with_no_heartbeat_and_allows_a_fresh_one(self):
        from core.publish_deadman import deadman_block_reason

        now = 1_000_000.0
        with patch.dict(os.environ, {"PUBLISH_DEADMAN_DAYS": "3"}):
            with patch("core.human_presence.last_human_at", return_value=None):
                self.assertIn("no operator heartbeat", deadman_block_reason(now=now) or "")
            self.assertIsNone(deadman_block_reason(last_human_at=now - 3600, now=now))
            self.assertIsNotNone(deadman_block_reason(last_human_at=now - 5 * 86400, now=now))


if __name__ == "__main__":
    unittest.main()
