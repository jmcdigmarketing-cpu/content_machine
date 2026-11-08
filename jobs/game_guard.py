"""#2025 (the operator, 2026-11-08): background work waits while a game is running.

The operator: "I am experiencing lag in games ... I am certain it isnt connection or internet
based." The overnight run, missed at 5:00 with the PC off, caught up at 10:16 AM in the middle of a
game and would have rendered up to three videos with ffmpeg; the fast lane and the 1 PM step render
too. So a heavy step asks first:

- a process running from a game library folder (Steam's `steamapps\\common`, Epic Games, Xbox
  games, Riot Games, EA, Ubisoft, GOG), or a known game by name (`GAME_PROCESSES` adds more);
- or Windows' own word that a full-screen app is up (`SHQueryUserNotificationState`: busy or
  Direct3D full screen - what a game in full screen reports).

Launchers and always-on tools that live in those folders (Wallpaper Engine) are not games;
`GAME_IGNORE` names more. `GAME_GUARD=false` turns it off (the suite does).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from core.logging import get_logger

logger = get_logger("jobs.game_guard")

GAME_DIRS = (
    "\\steamapps\\common\\",
    "\\epic games\\",
    "\\xboxgames\\",
    "\\riot games\\",
    "\\ea games\\",
    "\\ubisoft game launcher\\games\\",
    "\\gog galaxy\\games\\",
    # Minecraft Java runs as javaw.exe from its launcher's runtime (CurseForge is installed here)
    "\\curseforge\\minecraft\\",
    "\\.minecraft\\runtime\\",
    "\\minecraft launcher\\runtime\\",
)
NOT_GAME_DIRS = (
    "\\epic games\\launcher\\",
    "\\epic games\\epic online services\\",
    "\\riot games\\riot client\\",
)
GAME_NAMES = (
    "cod.exe", "gta5.exe", "gta5_enhanced.exe", "playgtav.exe",
    "fortniteclient-win64-shipping.exe", "marvel-win64-shipping.exe",
    "valorant-win64-shipping.exe", "cs2.exe", "rocketleague.exe", "overwatch.exe",
    "robloxplayerbeta.exe", "minecraft.windows.exe", "eafc26.exe", "fc26.exe",
    "nba2k26.exe", "madden26.exe", "r5apex.exe", "eldenring.exe",
)  # fmt: skip
NOT_GAMES = (
    "wallpaper32.exe", "wallpaper64.exe", "webwallpaper32.exe", "ui32.exe",
    "steamwebhelper.exe", "crashreportclient.exe", "unrealcefsubprocess.exe",
    "easyanticheat.exe", "easyanticheat_eos.exe", "battleye.exe",
)  # fmt: skip
# SHQueryUserNotificationState: 2 busy (a full-screen app), 3 Direct3D full screen
FULL_SCREEN_STATES = (2, 3)
POLL_SECONDS = 300
WAIT_HOURS = 6.0


def enabled() -> bool:
    return os.getenv("GAME_GUARD", "true").strip().lower() not in ("0", "false", "no", "off")


def _names(key: str) -> set[str]:
    return {n.strip().lower() for n in (os.getenv(key) or "").split(",") if n.strip()}


def _processes() -> list[tuple[str, str]]:
    """(name, executable path) of every running process; [] when they cannot be read."""
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return []
    out: list[tuple[str, str]] = []
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            out.append((str(proc.info.get("name") or ""), str(proc.info.get("exe") or "")))
        except Exception:  # noqa: S112 - a process that ended or is protected is not a game here
            continue
    return out


def full_screen_state() -> int:
    """Windows' notification state (0 when it cannot be read - not Windows, or no shell)."""
    try:
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return 0
        state = ctypes.c_int(0)
        if windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return 0
        return int(state.value)
    except Exception as exc:
        logger.debug("full-screen state unread: %s", exc)
        return 0


def game_running(
    *, processes: list[tuple[str, str]] | None = None, state: int | None = None
) -> str:
    """Why a game is taken to be running ("cod.exe is running", "a full-screen app is up"), or
    "" - also "" with `GAME_GUARD` off. Never raises."""
    if not enabled():
        return ""
    try:
        extra, ignored = _names("GAME_PROCESSES"), _names("GAME_IGNORE") | set(NOT_GAMES)
        for name, exe in processes if processes is not None else _processes():
            low_name, low_exe = name.lower(), exe.lower().replace("/", "\\")
            if not low_name or low_name in ignored:
                continue
            if low_name in GAME_NAMES or low_name in extra:
                return f"{name} is running"
            if any(d in low_exe for d in GAME_DIRS) and not any(
                d in low_exe for d in NOT_GAME_DIRS
            ):
                return f"{name} is running"
        current = full_screen_state() if state is None else state
        if current in FULL_SCREEN_STATES:
            return "a full-screen app is up"
    except Exception as exc:
        logger.debug("game check skipped: %s", exc)
    return ""


def wait_while_gaming(
    label: str,
    *,
    max_hours: float = WAIT_HOURS,
    poll_seconds: float = POLL_SECONDS,
    check: Callable[[], str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Block while a game runs, looking every `poll_seconds`: "" once none does, or the reason it
    still does after `max_hours` (the caller then skips its heavy work)."""
    look = check or game_running
    start = clock()
    reason = look()
    while reason:
        if clock() - start >= max_hours * 3600:
            logger.warning("%s: %s for %.0f hours - skipped", label, reason, max_hours)
            return reason
        logger.info("%s waits: %s", label, reason)
        sleep(poll_seconds)
        reason = look()
    return ""
