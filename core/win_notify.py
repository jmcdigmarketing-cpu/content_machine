"""Windows toasts + quota chip (AppUserModelID so they group as Content OS).

Notify-only: never writes quota stores, never trips a breaker. Nested try so a
toast failure cannot wipe reliability.gather() or a render. Tests set
CONTENT_TOAST=false (see tests/__init__.py).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from core.logging import get_logger

logger = get_logger("core.win_notify")

APP_ID = "ContentOS.Operator"
APP_NAME = "Content OS"

_toasted: set[str] = set()


def toast_enabled() -> bool:
    if os.getenv("CONTENT_TOAST", "true").strip().lower() in ("0", "false", "no", "off"):
        return False
    return os.name == "nt" or os.getenv("CONTENT_TOAST_FORCE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def set_app_user_model_id(app_id: str = APP_ID) -> bool:
    """Pin this process so Action Center groups toasts as Content OS, not python.exe."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
        return True
    except Exception as exc:
        logger.debug("AppUserModelID skipped: %s", exc)
        return False


def _xml_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )[:180]


def _toast_powershell(title: str, body: str) -> bool:
    """WinRT toast via PowerShell (no extra pip). Fail-open."""
    title_x = _xml_escape(title)
    body_x = _xml_escape(body)
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
        " ContentType = WindowsRuntime] | Out-Null; "
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom,"
        " ContentType = WindowsRuntime] | Out-Null; "
        f'$xml = \'<toast><visual><binding template="ToastGeneric">'
        f"<text>{title_x}</text><text>{body_x}</text></binding></visual></toast>'; "
        "$doc = New-Object Windows.Data.Xml.Dom.XmlDocument; $doc.LoadXml($xml); "
        "$t = [Windows.UI.Notifications.ToastNotification]::new($doc); "
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        f"'{APP_ID}').Show($t)"
    )
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
        creationflags=creation,
    )
    return result.returncode == 0


def toast(title: str, body: str, *, key: str | None = None) -> bool:
    """Show a Windows toast. Dedupes on `key` within the process. Never raises."""
    if not toast_enabled():
        return False
    token = key or f"{title}|{body}"
    if token in _toasted:
        return False
    try:
        set_app_user_model_id()
        ok = _toast_powershell(title, body)
        if ok:
            _toasted.add(token)
        return ok
    except Exception as exc:
        logger.debug("toast skipped: %s", exc)
        return False


def notify_breaker(kind: str, reason: str) -> None:
    """Toast when a breaker trips (Apify / signal / LLM / ElevenLabs). Notify only."""
    try:
        kind_s = (kind or "breaker").strip() or "breaker"
        reason_s = (reason or "tripped").strip() or "tripped"
        toast(
            f"{APP_NAME}: {kind_s} breaker",
            reason_s,
            key=f"breaker:{kind_s}:{reason_s[:80]}",
        )
    except Exception as exc:
        logger.debug("notify_breaker skipped: %s", exc)


def notify_ffmpeg_done(path: str) -> None:
    try:
        name = os.path.basename(path) if path else "render"
        toast(f"{APP_NAME}: ffmpeg finished", name or "render complete", key=f"ffmpeg:{path}")
    except Exception as exc:
        logger.debug("notify_ffmpeg_done skipped: %s", exc)


def quota_chip_lines(snap: dict[str, Any] | None = None) -> list[str]:
    """Uploads-left, ElevenLabs leftover chars, Apify breaker — one line each."""
    data = snap
    if data is None:
        try:
            from core.quota_governor import snapshot

            data = snapshot()
        except Exception as exc:
            logger.debug("quota snapshot skipped: %s", exc)
            data = {}
    data = data or {}
    lines: list[str] = []
    try:
        from apis.youtube_quota import uploads_remaining

        yt = data.get("youtube") or {}
        left = uploads_remaining(yt) if yt else uploads_remaining()
        lines.append(f"YouTube: ~{left} uploads left this reset")
    except Exception as exc:
        logger.debug("uploads_remaining skipped: %s", exc)
        lines.append("YouTube: n/a")
    el = data.get("elevenlabs") or {}
    used = int(el.get("chars_used") or 0)
    raw = os.getenv("ELEVENLABS_MONTHLY_CHAR_BUDGET", "").strip()
    budget = None
    if raw.lower() not in ("", "0", "off", "false", "no"):
        try:
            budget = int(raw)
        except ValueError:
            budget = None
    if budget and budget > 0:
        lines.append(f"ElevenLabs: {max(0, budget - used):,} chars leftover")
    else:
        lines.append("ElevenLabs: no char budget set")
    ap = data.get("apify") or {}
    if ap.get("exhausted"):
        lines.append(f"Apify: OFF - {ap.get('reason') or 'exhausted'}")
    else:
        lines.append("Apify: ON")
    return lines


def chip_text(snap: dict[str, Any] | None = None) -> str:
    return " | ".join(quota_chip_lines(snap))


def show_quota_chip(*, toast_it: bool = True) -> str:
    """Print + optional toast of the three quota numbers. Returns the chip text."""
    try:
        set_app_user_model_id()
    except Exception as exc:
        logger.debug("AppUserModelID on chip skipped: %s", exc)
    text = chip_text()
    if toast_it:
        toast(f"{APP_NAME} quota", text, key="quota-chip")
    return text


def run_tray(*, stay: bool = False) -> int:
    """Quota chip: toast + print. Optional always-on-top tkinter chip (not a daemon)."""
    text = show_quota_chip(toast_it=True)
    print(text)
    if not stay:
        return 0
    try:
        import tkinter as tk

        root = tk.Tk()
        root.title(APP_NAME)
        root.attributes("-topmost", True)
        root.resizable(False, False)
        lbl = tk.Label(root, text=text, justify="left", padx=12, pady=10, font=("Segoe UI", 11))
        lbl.pack()
        root.mainloop()
    except Exception as exc:
        logger.debug("tray window skipped: %s", exc)
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Content OS quota chip / toasts")
    parser.add_argument("--stay", action="store_true", help="Keep a small on-top chip window")
    args = parser.parse_args()
    return run_tray(stay=bool(args.stay))


if __name__ == "__main__":
    raise SystemExit(main())
