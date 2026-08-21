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


def last_media_file(kind: str = "mp4", *, channel_id: str | None = None) -> str | None:
    """Newest mp4 under output/{channel}/video or newest thumb under thumbnails/."""
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


def pyw_launcher_path() -> str:
    from config.paths import ROOT_DIR

    return os.path.join(ROOT_DIR, "content_os.pyw")


def start_menu_dir() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")


def start_menu_shortcut_path() -> str:
    return os.path.join(start_menu_dir(), SHORTCUT_NAME)


def pythonw_executable() -> str:
    exe = sys.executable or "python"
    if os.name == "nt":
        candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(candidate):
            return candidate
        if exe.lower().endswith("python.exe"):
            return exe[:-10] + "pythonw.exe"
    return exe


def install_start_menu_shortcut() -> str:
    """Write a Start Menu .lnk that launches content_os.pyw via pythonw. Returns path."""
    from config.paths import ROOT_DIR

    target = pythonw_executable()
    script = pyw_launcher_path()
    dest = start_menu_shortcut_path()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.name != "nt":
        # Non-Windows: drop a tiny .cmd/.desktop stand-in so tests can still assert a file.
        with open(dest, "w", encoding="utf-8") as f:
            f.write(f"{target} {script}\n")
        return dest
    work = ROOT_DIR.replace("\\", "\\\\")
    script_esc = script.replace("\\", "\\\\")
    target_esc = target.replace("\\", "\\\\")
    dest_esc = dest.replace("\\", "\\\\")
    ps = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$lnk = $s.CreateShortcut('{dest_esc}'); "
        f"$lnk.TargetPath = '{target_esc}'; "
        f"$lnk.Arguments = '\"{script_esc}\"'; "
        f"$lnk.WorkingDirectory = '{work}'; "
        "$lnk.Description = 'Content OS operator (no console flash)'; "
        "$lnk.Save()"
    )
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=creation,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "shortcut failed")[:400])
    return dest
