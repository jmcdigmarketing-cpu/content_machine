"""Wave 123 (2026-10-22 evening): the console pop-ups, and the cloud's next five.

Measured first: the operator saw System32 windows pop up. The overnight task ran `cmd /c ...
python.exe` - a console window for the whole run, which today started at 16:52 because the PC
was not awake at 5:00 - and the 15-minute worker runs under `pythonw`, where every console tool
it starts (`schtasks`, `wevtutil`, `powercfg`, PowerShell, ffmpeg) opens a window of its own;
four of the tools in `nightly_task` were started with no `CREATE_NO_WINDOW`.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
NO_WINDOW = 0x08000000


def _load_pyw(name: str):
    path = ROOT / "scripts" / f"{name}.pyw"
    loader = importlib.machinery.SourceFileLoader(f"_test_{name}", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class _Recorder:
    """A stand-in for `subprocess.Popen` that records the flags it was given."""

    seen: list = []  # noqa: RUF012 - reset per test

    def __init__(self, *args, **kwargs):
        type(self).seen.append(int(kwargs.get("creationflags") or 0))


class HideChildWindowsTests(unittest.TestCase):
    """A process with no console starts its console tools without a window."""

    def setUp(self):
        _Recorder.seen = []

    def test_a_windowless_process_hides_every_child(self):
        from core import win_shell

        with patch.object(subprocess, "Popen", _Recorder):
            self.assertTrue(win_shell.hide_child_windows(has_console=False, platform="nt"))
            subprocess.Popen(["schtasks", "/Query"])
            subprocess.Popen(["cmd"], creationflags=0x10)  # asked for a console of its own
            wrapped = subprocess.Popen
            self.assertTrue(win_shell.hide_child_windows(has_console=False, platform="nt"))
            self.assertIs(subprocess.Popen, wrapped)  # once, not twice
        self.assertEqual(_Recorder.seen, [NO_WINDOW, 0x10])

    def test_a_child_with_no_output_of_its_own_writes_to_ours(self):
        from core import win_shell

        given: list = []

        class _Std(_Recorder):
            def __init__(self, *args, **kwargs):
                given.append((kwargs.get("stdout"), kwargs.get("stderr")))

        with patch.object(subprocess, "Popen", _Std):
            self.assertTrue(
                win_shell.hide_child_windows(has_console=False, platform="nt", share_std=True)
            )
            subprocess.Popen(["python", "-m", "core.overnight"])  # the draft subprocess
            subprocess.Popen(["schtasks"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(given, [(1, 2), (subprocess.PIPE, subprocess.PIPE)])

    def test_a_console_or_another_system_changes_nothing(self):
        from core import win_shell

        with patch.object(subprocess, "Popen", _Recorder):
            self.assertFalse(win_shell.hide_child_windows(has_console=True, platform="nt"))
            self.assertFalse(win_shell.hide_child_windows(has_console=False, platform="posix"))
            self.assertIs(subprocess.Popen, _Recorder)


class System32CallsTests(unittest.TestCase):
    """The four console tools `nightly_task` starts carry the flag themselves."""

    def test_each_call_passes_no_window(self):
        from core import nightly_task

        done = SimpleNamespace(returncode=0, stdout="", stderr="")
        env = {"NIGHTLY_TASK_QUERY": "true", "CONTENT_SUITE": "0"}
        with (
            patch.dict(os.environ, env),
            patch("core.win_shell.no_window", return_value=NO_WINDOW),
            patch.object(nightly_task.subprocess, "run", return_value=done) as run,
        ):
            nightly_task.run_schtasks(["schtasks", "/Query"])
            nightly_task.power_events()
            nightly_task.wake_timers()
            nightly_task._powershell("Get-Date")
        tools = [call.args[0][0] for call in run.call_args_list]
        self.assertEqual(tools, ["schtasks", "wevtutil", "powercfg", "powershell"])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs.get("creationflags"), NO_WINDOW, call.args[0][0])


class LaunchersTests(unittest.TestCase):
    """Both scheduled launchers hide their children before anything runs."""

    def test_the_worker_launcher(self):
        module = _load_pyw("worker_task")
        order: list[str] = []
        out, err, cwd = sys.stdout, sys.stderr, os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with (
                    patch.object(module, "LOG", os.path.join(tmp, "worker_task.log")),
                    patch(
                        "core.win_shell.hide_child_windows",
                        # after the log redirect: core.logging binds its handler to
                        # sys.stderr, which pythonw leaves None (the 20:52 pass logged errors)
                        side_effect=lambda: order.append(
                            "hide"
                            if str(getattr(sys.stderr, "name", "")).endswith("worker_task.log")
                            else "hide before the log"
                        ),
                    ),
                    patch("core.nightly_task.enable_crash_traceback", return_value=True),
                    patch("runpy.run_module", side_effect=lambda *a, **k: order.append("run")),
                ):
                    module.main()
            finally:
                sys.stdout, sys.stderr = out, err
                os.chdir(cwd)
        self.assertEqual(order, ["hide", "run"])

    def test_the_overnight_launcher(self):
        module = _load_pyw("ops_task")
        order: list[str] = []
        argv_seen: list[list[str]] = []

        def run(*_a, **_k):
            order.append("run")
            argv_seen.append(list(sys.argv))
            raise SystemExit(2)

        out, err, argv, cwd = sys.stdout, sys.stderr, list(sys.argv), os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with (
                    patch.dict(os.environ),  # main() sets PYTHONIOENCODING for the process
                    patch.object(
                        module, "_point_std_at", side_effect=lambda f: order.append("log")
                    ),
                    patch(
                        "core.win_shell.hide_child_windows",
                        side_effect=lambda **k: order.append("hide" if k.get("share_std") else "?"),
                    ),
                    patch("runpy.run_module", side_effect=run),
                ):
                    code = module.main(["--log", os.path.join(tmp, "o.log"), "overnight",
                                        "--channel", "tapin", "--count", "3"])  # fmt: skip
            finally:
                sys.stdout, sys.stderr, sys.argv = out, err, argv
                os.chdir(cwd)
        self.assertEqual(code, 2)
        self.assertEqual(order, ["log", "hide", "run"])
        self.assertEqual(
            argv_seen[0], ["scripts.ops", "overnight", "--channel", "tapin", "--count", "3"]
        )

    def test_the_overnight_log_by_default(self):
        module = _load_pyw("ops_task")
        self.assertEqual(module.default_log(["overnight", "--channel", "tapin"]),
                         os.path.join("output", "logs", "overnight-last.log"))  # fmt: skip


class OvernightTaskTests(unittest.TestCase):
    """The overnight task runs the windowless launcher, changed in place."""

    def test_the_command_has_no_console(self):
        from core import nightly_task

        line = nightly_task.task_command(
            "tapin", count=3, python=r"C:\Py\python.exe", repo=r"C:\repo"
        )
        self.assertNotIn("cmd", line.split()[0].lower())
        self.assertIn("ops_task.pyw", line)
        self.assertTrue(line.endswith("overnight --channel tapin --count 3"))

    def test_the_change_in_place(self):
        from core import nightly_task

        ps = nightly_task.windowless_command(
            "tapin", count=3, python=r"C:\Py\pythonw.exe", repo=r"C:\repo"
        )
        for part in ("Get-ScheduledTask -TaskPath '\\ContentMachine\\' -TaskName 'OvernightDrafts'",
                     "Execute = 'C:\\Py\\pythonw.exe'", "ops_task.pyw", "Set-ScheduledTask"):  # fmt: skip
            self.assertIn(part, ps)

    def test_the_action_is_read_back(self):
        from core import nightly_task

        xml = ("<Task><Actions><Exec><Command>C:\\Py\\pythonw.exe</Command>"
               "<Arguments>\"C:\\repo\\scripts\\ops_task.pyw\" overnight</Arguments></Exec></Actions></Task>")  # fmt: skip
        self.assertEqual(nightly_task.task_action(xml),
                         ("C:\\Py\\pythonw.exe", '"C:\\repo\\scripts\\ops_task.pyw" overnight'))  # fmt: skip


class PaintedHeadlineTests(unittest.TestCase):
    """#1544: the thumbnail test records the words painted, not the ones asked for."""

    def test_the_full_arm_records_what_it_painted(self):
        from assets import flux_thumbnail

        title = "Ben Affleck Gets Destroyed by 12-Year-Olds in Fortnite, Then Argues Back"
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(
                flux_thumbnail,
                "_pillow_thumbnail",
                return_value=SimpleNamespace(path="x.png", provider="pillow"),
            ),  # fmt: skip
        ):
            rows = flux_thumbnail.generate_dual_thumbnails(
                "Affleck", title, tmp, content_run_id=1, channel_id="tapin", text_variants=True
            )
        by_arm = {row["arm"]: row["features"] for row in rows}
        self.assertEqual(by_arm["text_full"]["headline_text"], "Ben Affleck Gets Destroyed")
        self.assertEqual(by_arm["text_full"]["headline_asked"], title)
        self.assertEqual(by_arm["text_short"]["headline_text"], "Ben Affleck Gets")

    def test_the_lever_says_what_text_full_paints(self):
        from pathlib import Path as _P

        text = (_P(__file__).resolve().parent.parent / "core" / "experiment_levers.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("paint the full title", text)


class TeamNamesWholeTests(unittest.TestCase):
    """#1485: a city shared by several teams keeps the team's own name."""

    def test_the_three_that_broke(self):
        from apis.topic_tokens import search_query, title_phrases

        self.assertIn("Philadelphia 76ers", title_phrases("Philadelphia 76ers beat the Knicks"))
        self.assertIn("San Francisco 49ers", title_phrases("San Francisco 49ers beat the Rams"))
        self.assertIn(
            "Brighton & Hove Albion", title_phrases("Brighton & Hove Albion beat Arsenal")
        )
        self.assertIn(
            "San Francisco 49ers",
            search_query("Why the San Francisco 49ers beat the defending champions in overtime"),
        )

    def test_every_team_the_channel_knows(self):
        from apis.nba_teams import NBA_TEAM_NAMES
        from apis.nfl_entities import NFL_TEAM_NAMES
        from apis.team_gazetteer import teams
        from apis.topic_tokens import search_query, title_phrases

        names = (
            set(NFL_TEAM_NAMES.values()) | set(NBA_TEAM_NAMES.values()) | {t.full for t in teams()}
        )
        missed = []
        for full in sorted(names):
            plain = full.replace(".", "")
            phrases = [
                p.replace(".", "") for p in title_phrases(f"{full} beat the defending champions")
            ]
            query = search_query(
                f"Why {full} beat the defending champions on Sunday night in overtime"
            )
            if plain not in phrases or plain.lower() not in query.replace(".", "").lower():
                missed.append(full)
        self.assertEqual(missed, [])


class RenderGuardTests(unittest.TestCase):
    """#1465 and #1467: a memory check before each render, a 2-second render before the first."""

    def _render(self, *, free=None, smoke=""):
        from core import batch_review

        drafts = [SimpleNamespace(run_id=n, title="t", script="s") for n in (5, 6)]
        rendered: list[int] = []
        env = {"OVERNIGHT_MIN_FREE_GB": "3", "OVERNIGHT_SMOKE": "true"}
        with (
            patch.dict(os.environ, env),
            patch.object(batch_review, "unattended_candidates", return_value=(drafts, [])),
            patch.object(batch_review, "shelf_max", return_value=0),
            patch.object(batch_review, "shelf_pause", return_value=""),
            patch.object(batch_review, "second_read", return_value=""),
            patch.object(batch_review, "_write_review"),
            patch("core.ram_preflight.available_ram_gb", return_value=free),
            patch(
                "video.render_smoke.smoke_render_synthetic",
                side_effect=RuntimeError(smoke) if smoke else None,
            ) as smoked,  # fmt: skip
        ):
            out = batch_review.render_unattended(
                "tapin", 2, render=lambda d, _o: rendered.append(d.run_id) or True,
                queue=lambda run_id, _c: run_id,
            )  # fmt: skip
        return out, rendered, smoked

    def test_too_little_memory_stops_the_night(self):
        out, rendered, _smoked = self._render(free=1.5)
        self.assertEqual(rendered, [])
        self.assertIn("only 1.5 GB of memory free (3 needed)", out["paused"])

    def test_a_failed_smoke_render_tries_no_render(self):
        out, rendered, smoked = self._render(free=12.0, smoke="ffmpeg exited 1")
        self.assertEqual(rendered, [])
        self.assertIn("the 2-second test render failed: ffmpeg exited 1", out["paused"])
        self.assertEqual(smoked.call_count, 1)

    def test_a_full_disk_stops_the_night(self):
        from collections import namedtuple

        usage = namedtuple("usage", "total used free")(340 * 1024**3, 340 * 1024**3, 0)
        with (
            patch.dict(os.environ, {"OVERNIGHT_MIN_DISK_GB": "5"}),
            patch("shutil.disk_usage", return_value=usage),
        ):
            out, rendered, _smoked = self._render(free=12.0)
        self.assertEqual(rendered, [])
        self.assertIn("only 0.0 GB free on the disk (5 needed)", out["paused"])

    def test_both_pass_and_the_smoke_runs_once(self):
        out, rendered, smoked = self._render(free=12.0)
        self.assertEqual(rendered, [5, 6])
        self.assertNotIn("paused", out)
        self.assertEqual(smoked.call_count, 1)


class FieldAuditTests(unittest.TestCase):
    """#1480: each week, the fields health and the learning read, against what was written."""

    def test_a_field_nobody_wrote_is_named(self):
        import json
        from datetime import datetime, timedelta, timezone

        from analytics import field_audit

        now = datetime(2026, 10, 22, 20, 0, tzinfo=timezone.utc)
        full = {key: 1 for _store, key, _reader, _why in field_audit.FIELDS if _store == "features"}
        full["technical_qc"] = {"video_duration": 40.0}
        runs = [SimpleNamespace(id=n, created_at=now - timedelta(days=1), status="drafted",
                                features_json=json.dumps({**full, "claim_verification": None} if n == 2 else full),
                                quality_json=json.dumps({"hook_score": 70})) for n in (1, 2)]  # fmt: skip
        fresh = (now - timedelta(days=1)).date().isoformat()
        stale = (now - timedelta(days=6)).date().isoformat()
        metrics = {
            key: 1 for _store, key, _reader, _why in field_audit.FIELDS if _store == "metrics"
        }
        rows = [SimpleNamespace(content_run_id=n, privacy_status="public", status="uploaded",
                                published_at=now - timedelta(days=10),
                                metrics_json=json.dumps({**metrics, "views_until": until}))
                for n, until in ((1, fresh), (2, stale))]  # fmt: skip
        lines = field_audit.audit_lines(runs, rows, now=now)
        self.assertIn("claim_verification on 1 of 2 runs", lines[0])
        self.assertIn("1 of 2 videos under 28 days last synced 3+ days ago (run 2", lines[1])

    def test_all_written(self):
        from analytics import field_audit

        self.assertEqual(field_audit.audit_lines([], [], now=None), [])

    def test_each_reader_reads_its_field(self):
        from analytics import field_audit

        for _store, key, reader, _why in field_audit.FIELDS:
            text = (ROOT / reader).read_text(encoding="utf-8")
            self.assertIn(f'"{key.split(".")[-1]}"', text, f"{reader} no longer reads {key}")


if __name__ == "__main__":
    unittest.main()
