"""Windows Explorer reveal + Start Menu pyw shortcut.

Smallest leave-the-terminal helpers: `explorer /select,` on the last mp4 or
thumbnail, and a pythonw shortcut so Content OS launches without a console flash.
"""

from __future__ import annotations

import os
import subprocess
import sys

from core.logging import get_logger

logger = get_logger("core.win_shell")

SHORTCUT_NAME = "Content OS.lnk"
BOOTH_SHORTCUT_NAME = "Content OS Review Booth.lnk"


def _ps_single_quote(text: str) -> str:
    return str(text).replace("'", "''")


def last_trace_file(channel_id: str | None = None) -> str | None:
    """Newest run-trace JSON on disk (data/traces/<id>.json)."""
    try:
        from config.paths import TRACES_DIR
        from core.run_trace import list_traces

        traces = list_traces(limit=5, channel_id=channel_id)
    except Exception as exc:
        logger.debug("list_traces skipped: %s", exc)
        return None
    for t in traces:
        rid = t.get("run_id")
        if rid is None:
            continue
        path = os.path.join(TRACES_DIR, f"{int(rid)}.json")
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def last_media_file(kind: str = "mp4", *, channel_id: str | None = None) -> str | None:
    """Newest mp4 under output/{channel}/video or newest thumb under thumbnails/."""
    if kind in ("trace", "json", "traces"):
        return last_trace_file(channel_id)
    try:
        from core.output_paths import ensure_channel_output_dirs

        dirs = ensure_channel_output_dirs(channel_id)
    except Exception as exc:
        logger.debug("output dirs skipped: %s", exc)
        return None
    if kind in ("thumb", "thumbnail", "jpg", "png"):
        folder = dirs.get("thumbnails") or ""
        suffixes = (".jpg", ".jpeg", ".png", ".webp")
    else:
        folder = dirs.get("video") or ""
        suffixes = (".mp4", ".webm", ".mov")
    if not folder or not os.path.isdir(folder):
        return None
    paths = [
        os.path.join(folder, name) for name in os.listdir(folder) if name.lower().endswith(suffixes)
    ]
    if not paths:
        return None
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return os.path.abspath(paths[0])


def reveal_in_explorer(path: str | None) -> bool:
    """Select `path` in Explorer. No-op / False when missing or not Windows."""
    if not path or not os.path.exists(path):
        return False
    abs_path = os.path.abspath(path)
    if os.name != "nt":
        logger.debug("reveal skipped (not Windows): %s", abs_path)
        return False
    try:
        subprocess.run(
            ["explorer", f"/select,{abs_path}"],
            check=False,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as exc:
        logger.debug("explorer /select skipped: %s", exc)
        return False


def reveal_last(*, kind: str = "mp4", channel_id: str | None = None) -> str | None:
    path = last_media_file(kind, channel_id=channel_id)
    if path:
        reveal_in_explorer(path)
    return path


def open_folder(path: str | None) -> bool:
    """Open a directory in Explorer. Fail-open."""
    if not path or not os.path.isdir(path):
        return False
    abs_path = os.path.abspath(path)
    try:
        if os.name == "nt":
            os.startfile(abs_path)  # type: ignore[attr-defined]
            return True
        import webbrowser

        return bool(webbrowser.open(abs_path))
    except Exception as exc:
        logger.debug("open folder skipped: %s", exc)
        return False


def open_last_output_folder(*, channel_id: str | None = None) -> str | None:
    """Open output/{channel}/ (video dir if present). Tray menu helper."""
    try:
        from core.output_paths import ensure_channel_output_dirs

        dirs = ensure_channel_output_dirs(channel_id)
    except Exception as exc:
        logger.debug("output dirs skipped: %s", exc)
        return None
    folder = dirs.get("video") or dirs.get("root") or ""
    if folder and os.path.isdir(folder):
        open_folder(folder)
        return os.path.abspath(folder)
    return None


def pyw_launcher_path() -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "content_os.pyw")


def booth_launcher_path() -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "booth_os.pyw")


def start_menu_dir() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")


def start_menu_shortcut_path() -> str:
    return os.path.join(start_menu_dir(), SHORTCUT_NAME)


def desktop_dir() -> str:
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, "Desktop")


def desktop_booth_shortcut_path() -> str:
    return os.path.join(desktop_dir(), BOOTH_SHORTCUT_NAME)


def pythonw_executable() -> str:
    exe = sys.executable or "python"
    if os.name == "nt":
        candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(candidate):
            return candidate
        if exe.lower().endswith("python.exe"):
            return exe[:-10] + "pythonw.exe"
    return exe


def _install_pythonw_shortcut(*, dest: str, script: str, description: str) -> str:
    from config.paths import ROOT_DIR

    target = pythonw_executable()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.name != "nt":
        # Non-Windows: drop a tiny .cmd/.desktop stand-in so tests can still assert a file.
        with open(dest, "w", encoding="utf-8") as f:
            f.write(f"{target} {script}\n")
        return dest
    dest_q = _ps_single_quote(dest)
    target_q = _ps_single_quote(target)
    script_q = _ps_single_quote(script)
    work_q = _ps_single_quote(ROOT_DIR)
    ps = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$lnk = $s.CreateShortcut('{dest_q}'); "
        f"$lnk.TargetPath = '{target_q}'; "
        f"$lnk.Arguments = '\"{script_q}\"'; "
        f"$lnk.WorkingDirectory = '{work_q}'; "
        f"$lnk.Description = '{_ps_single_quote(description)}'; "
        "$lnk.Save()"
    )
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
        creationflags=creation,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "shortcut failed")[:400])
    return dest


def install_start_menu_shortcut() -> str:
    """Write a Start Menu .lnk that launches content_os.pyw via pythonw. Returns path."""
    return _install_pythonw_shortcut(
        dest=start_menu_shortcut_path(),
        script=pyw_launcher_path(),
        description="Content OS operator (no console flash)",
    )


def install_booth_desktop_shortcut() -> str:
    """Write a Desktop .lnk that starts and keeps the review booth alive."""
    return _install_pythonw_shortcut(
        dest=desktop_booth_shortcut_path(),
        script=booth_launcher_path(),
        description="Content OS last-run review booth",
    )


def default_sendto_dir() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "Microsoft", "Windows", "SendTo")


def default_facts_txt_path() -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "facts.txt")


def install_sendto_facts_shortcut(
    *, sendto_dir: str | None = None, facts_path: str | None = None
) -> str:
    """Write an Explorer Send-to shortcut targeting overnight ``--facts-file``.

    Tests pass a temp ``sendto_dir`` so the operator's ``%APPDATA%`` is untouched.
    """
    dest_dir = sendto_dir or default_sendto_dir()
    facts = os.path.abspath(facts_path or default_facts_txt_path())
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "Content OS facts.txt.lnk")
    # Explicit sendto_dir (tests / dry operator run) never touches %APPDATA%.
    if sendto_dir or os.name != "nt":
        with open(dest, "w", encoding="utf-8") as f:
            f.write(f"{sys.executable} -m scripts.ops overnight --facts-file {facts}\n")
        return dest
    return _install_pythonw_shortcut(
        dest=dest,
        script=os.path.join(os.path.dirname(pyw_launcher_path()), "scripts", "ops.py"),
        description=f"Content OS overnight --facts-file {facts}",
    )
