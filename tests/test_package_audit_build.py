"""#894: `ops package-audit` builds where the system setuptools cannot.

The audit built its wheel with `--no-build-isolation`, so it used the system setuptools.
Debian's patched one raises `AttributeError: install_layout`, and the audit failed before
scanning anything - on unmodified HEAD too. An isolated build (pip fetches its own
setuptools) works. The no-isolation build is still tried first (it needs no network); a
failure retries with isolation, and an sdist failure no longer throws the wheel away.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _proc(code: int, err: str = ""):
    return SimpleNamespace(returncode=code, stderr=err, stdout="")


class BuildFallbackTests(unittest.TestCase):
    def _build(self, results):
        from core import package_audit

        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            proc = results.pop(0)
            if proc.returncode == 0:
                out = Path(command[command.index("-w") + 1]) if "-w" in command else None
                name = "pkg-0.1-py3-none-any.whl" if out else "pkg-0.1.tar.gz"
                target = out or Path(kwargs.get("cwd", "."))
                if out is None:
                    target = Path(self._out)
                (target / name).write_text("x", encoding="utf-8")
            return proc

        with tempfile.TemporaryDirectory() as tmp:
            self._out = tmp
            with (
                patch.object(package_audit, "stage_tree", return_value=0),
                patch.object(package_audit.subprocess, "run", side_effect=fake_run),
            ):
                paths = package_audit.build_archives(Path(tmp))
            names = [p.name for p in paths]
        return names, calls, list(package_audit.last_build_notes())

    def test_a_system_setuptools_failure_retries_with_isolation(self):
        names, calls, notes = self._build(
            [_proc(1, "AttributeError: install_layout"), _proc(0), _proc(0)]
        )
        self.assertIn("--no-build-isolation", calls[0])
        self.assertNotIn("--no-build-isolation", calls[1])
        self.assertIn("pkg-0.1-py3-none-any.whl", names)
        self.assertTrue(any("isolated" in n for n in notes), notes)

    def test_a_working_system_build_makes_one_wheel_call(self):
        _names, calls, notes = self._build([_proc(0), _proc(0)])
        self.assertEqual(sum(1 for c in calls if "wheel" in c), 1)
        self.assertEqual(notes, [])

    def test_both_wheel_builds_failing_raises_with_both_reasons(self):
        from core import package_audit

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(package_audit, "stage_tree", return_value=0),
                patch.object(
                    package_audit.subprocess,
                    "run",
                    side_effect=[_proc(1, "install_layout"), _proc(1, "no network")],
                ),
                self.assertRaises(RuntimeError) as ctx,
            ):
                package_audit.build_archives(Path(tmp))
        self.assertIn("install_layout", str(ctx.exception))
        self.assertIn("no network", str(ctx.exception))

    def test_an_sdist_failure_keeps_the_wheel(self):
        names, _calls, notes = self._build([_proc(0), _proc(1, "sdist broke")])
        self.assertEqual(names, ["pkg-0.1-py3-none-any.whl"])
        self.assertTrue(any("sdist not built" in n for n in notes), notes)

    def test_the_report_prints_the_notes(self):
        from core.package_audit import ArchiveReport, render_audit

        text = render_audit(
            [ArchiveReport(name="pkg.whl", members=3)], notes=["wheel: built in isolation"]
        )
        self.assertIn("wheel: built in isolation", text)


if __name__ == "__main__":
    unittest.main()
