"""An `ops` command from Task Scheduler with no console window (wave 123).

The overnight task ran `cmd /c ... python.exe -m scripts.ops overnight ... > overnight-last.log`:
a `C:\\WINDOWS\\system32\\cmd.exe` window open for the whole run - on 10-22 from 16:52, when the
PC came on after missing 5:00. This runs the same command under `pythonw`:

    pythonw scripts\\ops_task.pyw [--log PATH] overnight --channel tapin --count 3

It sets the working folder to the repo, empties the log as `>` did (default
`output\\logs\\<command>-last.log`), points the process's own stdout and stderr at it - so the
draft subprocess and a native crash's traceback still land there - and starts every console
tool without a window (`core.win_shell.hide_child_windows`). It exits with the command's code.
"""

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_log(args: list[str]) -> str:
    name = next((a for a in args if not a.startswith("-")), "ops")
    return os.path.join("output", "logs", f"{name}-last.log")


def _point_std_at(log) -> None:
    """fds 1 and 2, and the Windows std handles a child inherits, all to the log."""
    log.flush()
    os.dup2(log.fileno(), 1)
    os.dup2(log.fileno(), 2)
    if os.name == "nt":
        import ctypes
        import msvcrt

        kernel32 = ctypes.windll.kernel32
        kernel32.SetStdHandle(-11, msvcrt.get_osfhandle(1))  # STD_OUTPUT_HANDLE
        kernel32.SetStdHandle(-12, msvcrt.get_osfhandle(2))  # STD_ERROR_HANDLE
    sys.stdout = sys.stderr = open(1, "w", encoding="utf-8", errors="replace", closefd=False)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    log_path = ""
    if args[:1] == ["--log"] and len(args) > 1:
        log_path, args = args[1], args[2:]
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    log_path = log_path or default_log(args)
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        _point_std_at(log)
        from core.win_shell import hide_child_windows

        hide_child_windows(share_std=True)
        sys.argv = ["scripts.ops", *args]
        code = 0
        try:
            runpy.run_module("scripts.ops", run_name="__main__")
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else (0 if stop.code is None else 1)
        except Exception as exc:
            print(f"ops_task: {type(exc).__name__}: {exc}")
            code = 1
        sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
