"""Windows toasts + quota chip (AppUserModelID so they group as Content OS).

Notify-only: never writes quota stores, never trips a breaker. Nested try so a
toast failure cannot wipe reliability.gather() or a render. Tests set
CONTENT_TOAST=false (see tests/__init__.py).
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
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


def _ps_single_quote(text: str) -> str:
    """Escape for embedding inside a PowerShell SINGLE-quoted string.

    _xml_escape covers & < > " for the XML payload, but the payload is itself
    pasted into a PowerShell literal delimited by '. PowerShell escapes that
    delimiter by doubling it. Without this an ordinary title - live run 69's was
    "...Stop Killing Games' Condemnation..." - ends the literal early: the toast
    fails to parse, and whatever follows is read as PowerShell.
    """
    return str(text).replace("'", "''")


def _toast_script(title: str, body: str, *, launch: str = "") -> str:
    """Build the PowerShell one-liner. Split out so the quoting is testable."""
    title_x = _ps_single_quote(_xml_escape(title))
    body_x = _ps_single_quote(_xml_escape(body))
    app_id = _ps_single_quote(APP_ID)
    attrs = ""
    if launch:
        launch_x = _ps_single_quote(_xml_escape(launch))
        attrs = f' activationType="protocol" launch="{launch_x}"'
    return (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
        " ContentType = WindowsRuntime] | Out-Null; "
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom,"
        " ContentType = WindowsRuntime] | Out-Null; "
        f'$xml = \'<toast{attrs}><visual><binding template="ToastGeneric">'
        f"<text>{title_x}</text><text>{body_x}</text></binding></visual></toast>'; "
        "$doc = New-Object Windows.Data.Xml.Dom.XmlDocument; $doc.LoadXml($xml); "
        "$t = [Windows.UI.Notifications.ToastNotification]::new($doc); "
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        f"'{app_id}').Show($t)"
    )


def _toast_powershell(title: str, body: str, *, launch: str = "") -> bool:
    """WinRT toast via PowerShell (no extra pip). Fire-and-forget; never blocks discovery."""
    script = _toast_script(title, body, launch=launch)
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creation,
    )
    return True


def toast(
    title: str,
    body: str,
    *,
    key: str | None = None,
    launch: str = "",
    urgent: bool = False,
) -> bool:
    """Show a Windows toast. Dedupes on `key` within the process. Never raises.

    `urgent=True` bypasses quiet-hours DND (#292). Reserved for breaker trips: the
    overnight batch runs *inside* the 1-8am window, so muting everything would silence
    exactly the notifications worth waking for.
    """
    if not toast_enabled():
        return False
    if not urgent and _toasts_muted():
        return False
    token = key or f"{title}|{body}"
    if token in _toasted:
        return False
    try:
        try:
            set_app_user_model_id()
        except Exception as exc:
            logger.debug("AppUserModelID skipped: %s", exc)
        try:
            ok = _toast_powershell(title, body, launch=launch)
        except Exception as exc:
            logger.debug("toast powershell skipped: %s", exc)
            return False
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
            # A tripped breaker is the one thing worth waking the operator for, and the
            # overnight batch runs inside the quiet window — so it bypasses DND (#292).
            urgent=True,
        )
    except Exception as exc:
        logger.debug("notify_breaker skipped: %s", exc)


def _toasts_muted(*, when: datetime | None = None) -> bool:
    """Quiet-hours DND for Action Center toasts (#292). Reads shipped #116.

    Resolved **machine-level**: muted when *any* configured channel is inside its quiet
    window. A desktop toast interrupts the human, not a channel, and `toast()` has no
    channel to hand down — which is what made the first cut inert. It called
    `quiet_hours_reason()` with no channel, that resolved to `default`, and `default`
    carries no `quiet_hours` block (only `tapin` and `moneywise` do), so the answer was
    always None and nothing was ever muted at any hour.

    `when` exists so the tests can drive the clock while the channel lookup stays live;
    production never passes it.
    """
    if os.getenv("CONTENT_TOAST_DND", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    try:
        from config.channels import list_channel_ids
        from core.publish_windows import quiet_hours_reason

        # quiet_hours_reason still honours the QUIET_HOURS master flag and returns
        # None for a channel with no window configured.
        return any(
            bool(quiet_hours_reason(channel_id=cid, when=when)) for cid in list_channel_ids()
        )
    except Exception as exc:
        logger.debug("toast DND skipped: %s", exc)
        return False


def _toast_open_mp4_enabled() -> bool:
    return os.getenv("CONTENT_TOAST_OPEN_MP4", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _file_launch_uri(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    try:
        from pathlib import Path

        return Path(path).resolve().as_uri()
    except Exception as exc:
        logger.debug("toast launch uri skipped: %s", exc)
        return ""


def notify_ffmpeg_done(path: str) -> None:
    try:
        name = os.path.basename(path) if path else "render"
        launch = _file_launch_uri(path) if _toast_open_mp4_enabled() else ""
        toast(
            f"{APP_NAME}: ffmpeg finished",
            name or "render complete",
            key=f"ffmpeg:{path}",
            launch=launch,
        )
    except Exception as exc:
        logger.debug("notify_ffmpeg_done skipped: %s", exc)


def notify_upload_scheduled(title: str, publish_at: str) -> None:
    try:
        when = (publish_at or "queued").strip() or "queued"
        toast(
            f"{APP_NAME}: upload scheduled",
            f"{(title or 'video')[:80]} at {when}",
            key=f"scheduled:{title}:{when}",
        )
    except Exception as exc:
        logger.debug("notify_upload_scheduled skipped: %s", exc)


def notify_overnight_done(drafted: int, requested: int) -> None:
    try:
        toast(
            f"{APP_NAME}: overnight drafts",
            f"{int(drafted)}/{int(requested)} drafts ready (cadence-safe, no TTS)",
            key="overnight-drafts",
        )
    except Exception as exc:
        logger.debug("notify_overnight_done skipped: %s", exc)


def notify_uploads_left(n: int | None = None) -> None:
    """Action Center balloon: N uploads left this reset (~1,600 units each)."""
    try:
        left = n
        if left is None:
            from apis.youtube_quota import uploads_remaining

            left = uploads_remaining()
        toast(
            f"{APP_NAME}: uploads left",
            f"~{int(left)} uploads left this reset",
            key="uploads-left",
        )
    except Exception as exc:
        logger.debug("notify_uploads_left skipped: %s", exc)


def cost_mode_label() -> str:
    try:
        from core.run_mode import COST_MODE_FREE, resolve_cost_mode

        mode = resolve_cost_mode()
        return "Free" if mode == COST_MODE_FREE else "Standard"
    except Exception as exc:
        logger.debug("cost mode label skipped: %s", exc)
        return "Standard"


def quota_chip_lines(
    snap: dict[str, Any] | None = None, *, channel_id: str | None = None
) -> list[str]:
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
    lines.append(f"Mode: {cost_mode_label()}")
    letter = last_grade_letter(channel_id)
    lines.append(f"Grade: {letter or 'n/a'}")
    domain = last_domain_label(channel_id)
    lines.append(f"Domain: {domain or 'n/a'}")
    try:
        from core.overnight_pause import status_line

        lines.append(status_line())
    except Exception as exc:
        logger.debug("overnight pause status skipped: %s", exc)
    if os.getenv("CONTENT_TRAY_PRESENCE", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    ):
        try:
            from core.human_presence import last_seen_label

            lines.append(last_seen_label())
        except Exception as exc:
            logger.debug("human last-seen skipped: %s", exc)
    return lines


def last_grade_letter(channel_id: str | None = None) -> str:
    """Last-run report-card letter for the tray chip. Fail-open to ''."""
    if os.getenv("CONTENT_TRAY_GRADE", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return ""
    try:
        from core.review_booth import last_trace
        from core.video_grade import grade_from_parts

        quality = (last_trace(channel_id) or {}).get("quality") or {}
        if not quality:
            return ""
        return str(grade_from_parts(quality=quality).letter or "")
    except Exception as exc:
        logger.debug("last grade skipped: %s", exc)
        return ""


def domain_chip_text(topic: str, domain: str = "") -> str:
    """UFC / GTA / NBA (etc.) for the tray chip — RPM×cost is useless without this."""
    import re

    text = topic or ""
    if re.search(r"\bgta\b|grand theft auto", text, re.I):
        return "GTA"
    key = (domain or "").strip().lower()
    labels = {
        "ufc": "UFC",
        "nba": "NBA",
        "nfl": "NFL",
        "finance": "Finance",
        "gaming": "Gaming",
    }
    return labels.get(key, key)


def last_domain_label(channel_id: str | None = None) -> str:
    """Last-run inferred domain for the tray chip. Fail-open to ''."""
    if os.getenv("CONTENT_TRAY_DOMAIN", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return ""
    try:
        from apis.topic_scorer import infer_domain
        from core.review_booth import last_trace

        trace = last_trace(channel_id) or {}
        topic = str(trace.get("selected_topic") or trace.get("input_topic") or "")
        domain = str(trace.get("domain") or "")
        feats = trace.get("features") or {}
        if not domain and isinstance(feats, dict):
            domain = str(feats.get("domain") or "")
        if not domain:
            domain = str(infer_domain(topic) or "")
        return domain_chip_text(topic, domain)
    except Exception as exc:
        logger.debug("last domain skipped: %s", exc)
        return ""


def open_doctor_html(channel_id: str = "tapin") -> str:
    """Write ops doctor as themed HTML (pairs with #198)."""
    from core.html_report import dump_pre
    from core.ops_doctor import render

    return dump_pre("ops doctor", render(channel_id=channel_id), filename="doctor.html")


def chip_text(snap: dict[str, Any] | None = None, *, channel_id: str | None = None) -> str:
    return " | ".join(quota_chip_lines(snap, channel_id=channel_id))


def show_quota_chip(*, toast_it: bool = True, channel_id: str | None = None) -> str:
    """Print + optional toast of the three quota numbers. Returns the chip text."""
    try:
        set_app_user_model_id()
    except Exception as exc:
        logger.debug("AppUserModelID on chip skipped: %s", exc)
    text = chip_text(channel_id=channel_id)
    if toast_it:
        toast(f"{APP_NAME} quota", text, key="quota-chip")
        notify_uploads_left()
    return text


def run_tray(
    *,
    stay: bool = False,
    open_output: bool = False,
    doctor_html: bool = False,
    pause_overnight: bool = False,
    resume_overnight: bool = False,
    channel_id: str | None = None,
) -> int:
    """Quota chip: toast + print. Optional always-on-top tkinter chip (not a daemon)."""
    cid = channel_id or "tapin"
    if pause_overnight or resume_overnight:
        try:
            from core.overnight_pause import set_paused

            wanted = bool(pause_overnight and not resume_overnight)
            if not set_paused(wanted):
                print("Overnight pause state was not changed.")
                return 1
        except Exception as exc:
            logger.warning("overnight pause action failed: %s", exc)
            return 1
    text = show_quota_chip(toast_it=True, channel_id=cid)
    print(text)
    if open_output:
        try:
            from core.win_shell import open_last_output_folder

            folder = open_last_output_folder(channel_id=cid)
            if folder:
                print(folder)
        except Exception as exc:
            logger.debug("tray open-output skipped: %s", exc)
    if doctor_html:
        try:
            path = open_doctor_html(cid)
            print(path)
        except Exception as exc:
            logger.debug("tray doctor html skipped: %s", exc)
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

        def _open_folder() -> None:
            try:
                from core.win_shell import open_last_output_folder

                open_last_output_folder(channel_id=cid)
            except Exception as exc:
                logger.debug("tray folder button skipped: %s", exc)

        def _doctor() -> None:
            try:
                open_doctor_html(cid)
            except Exception as exc:
                logger.debug("tray doctor button skipped: %s", exc)

        def _pause_label() -> str:
            try:
                from core.overnight_pause import is_paused

                return "Resume overnight" if is_paused() else "Pause overnight"
            except Exception:
                return "Pause overnight"

        def _toggle_overnight() -> None:
            try:
                from core.overnight_pause import is_paused, set_paused

                if set_paused(not is_paused()):
                    btn3.configure(text=_pause_label())
            except Exception as exc:
                logger.warning("tray overnight toggle failed: %s", exc)

        btn = tk.Button(root, text="Open last output folder", command=_open_folder)
        btn.pack(padx=12, pady=(0, 6))
        btn2 = tk.Button(root, text="Doctor HTML", command=_doctor)
        btn2.pack(padx=12, pady=(0, 6))
        btn3 = tk.Button(root, text=_pause_label(), command=_toggle_overnight)
        btn3.pack(padx=12, pady=(0, 10))
        root.mainloop()
    except Exception as exc:
        logger.debug("tray window skipped: %s", exc)
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Content OS quota chip / toasts")
    parser.add_argument("--stay", action="store_true", help="Keep a small on-top chip window")
    parser.add_argument(
        "--open-output",
        action="store_true",
        help="Open the last channel output folder in Explorer",
    )
    parser.add_argument(
        "--doctor-html",
        action="store_true",
        help="Write ops doctor as themed HTML and open it",
    )
    parser.add_argument(
        "--pause-overnight",
        action="store_true",
        help="Pause future scheduled overnight batches",
    )
    parser.add_argument(
        "--resume-overnight",
        action="store_true",
        help="Resume future scheduled overnight batches",
    )
    parser.add_argument(
        "--channel",
        default="tapin",
        help="Channel id for last-output folder / doctor / grade chip",
    )
    args = parser.parse_args()
    return run_tray(
        stay=bool(args.stay),
        open_output=bool(args.open_output),
        doctor_html=bool(args.doctor_html),
        pause_overnight=bool(args.pause_overnight),
        resume_overnight=bool(args.resume_overnight),
        channel_id=args.channel,
    )


if __name__ == "__main__":
    raise SystemExit(main())
