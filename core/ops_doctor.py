"""ops doctor (candidate 30).

One command: free-stack readiness + feeds snapshot + oauth scopes (file only,
no token refresh) + quota snapshot + caption/TTS + CUDA probe. Nested try so
an optional import cannot wipe the rest. The Apify status page is the one
extra HTTP call (#392); everything else stays on cached probes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from config.paths import DATA_DIR, ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.ops_doctor")

# #457 (wave 114, the operator: a lock and a check, CI unchanged): `pip lock -e ".[app]"` wrote the
# exact versions this PC runs; #326 was the environment silently disagreeing with pyproject.
LOCK_FILE = os.path.join(ROOT_DIR, "pylock.toml")


def _canonical(name: str) -> str:
    return str(name or "").strip().lower().replace("_", "-").replace(".", "-")


def lock_drift(lock: dict[str, Any], installed: dict[str, str]) -> list[str]:
    """Each locked package whose installed version differs - "name lock X, installed Y" or
    "name lock X, not installed". The project itself (a directory entry) is not compared."""
    have = {_canonical(k): str(v) for k, v in (installed or {}).items()}
    out: list[str] = []
    for package in (lock or {}).get("packages") or []:
        if not isinstance(package, dict) or "version" not in package:
            continue
        name = _canonical(package.get("name", ""))
        want = str(package["version"])
        got = have.get(name)
        if got is None:
            out.append(f"{name} lock {want}, not installed")
        elif got != want:
            out.append(f"{name} lock {want}, installed {got}")
    return out


def _installed_versions() -> dict[str, str]:
    from importlib.metadata import distributions

    return {_canonical(d.metadata["Name"] or ""): d.version for d in distributions()}


def lock_check() -> tuple[bool, str]:
    """(ok, detail) for the doctor: the installed packages against pylock.toml."""
    import tomllib

    if not os.path.isfile(LOCK_FILE):
        return True, "no pylock.toml (write one: pip lock -e .[app])"
    with open(LOCK_FILE, "rb") as handle:
        lock = tomllib.load(handle)
    drift = lock_drift(lock, _installed_versions())
    locked = sum(1 for p in lock.get("packages") or [] if isinstance(p, dict) and "version" in p)
    if not drift:
        return True, f"the {locked} locked packages match pylock.toml"
    return False, (f"{len(drift)} of {locked} differ from pylock.toml: {'; '.join(drift[:3])} - "
                   "after an intended upgrade re-lock: pip lock -e .[app]")  # fmt: skip


APIFY_STATUS_URL = "https://status.apify.com/api/v2/status.json"
# Paid Apify signals (apis/register_signals._APIFY_PAID_SIGNALS). OpenRouter's
# status page answered 403, so it is not a second feed.
_APIFY_SIGNALS = frozenset({"reddit", "twitter", "tiktok_trends", "youtube_competitors"})


def _indicator(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    status = body.get("status")
    if not isinstance(status, dict):
        return ""
    return str(status.get("indicator") or "").lower()


def vendor_line(body: Any, local_failures: set[str] | None = None) -> tuple[bool, str]:
    """Apify's status page against our last signal failures. A fetch that returned
    nothing is not a warning: we cannot tell who is down."""
    indicator = _indicator(body)
    ours = {str(name) for name in (local_failures or set())} & _APIFY_SIGNALS
    if indicator in ("major", "critical"):
        return False, "Apify: they are down"
    if indicator == "none" and ours:
        return False, "Apify: we broke it"
    if indicator == "none":
        return True, "Apify: operational"
    if not indicator:
        return True, "Apify: status page unreachable"
    return True, f"Apify: {indicator}"


def _fetch_status(url: str) -> Any:
    if os.getenv("DOCTOR_STATUS_OFF", "").strip().lower() in ("1", "true", "yes", "on"):
        return {"status": {"indicator": "none", "description": "All Systems Operational"}}
    import requests

    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _local_signal_failures(channel_id: str) -> set[str]:
    try:
        from core.incident_ledger import rank_incidents
        from core.review_booth import last_trace

        trace = last_trace(channel_id) or {}
        rows = rank_incidents([trace] if trace else [])
    except Exception as exc:
        logger.debug("vendor status local failures skipped: %s", type(exc).__name__)
        return set()
    return {row.name for row in rows if row.kind == "signal"}


# Wave 112: `ops status` re-ran every check for a line that counts passes - 5.0 of its 7.9 s
# (torch's import for the CUDA probe, a timed-out localhost connect for Ollama). Each gather is
# kept; the status line reads one under FRESH_HOURS old.
DOCTOR_LAST_FILE = os.path.join(DATA_DIR, "doctor_last.json")
FRESH_HOURS = 12


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_last() -> dict[str, Any]:
    try:
        with open(DOCTOR_LAST_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_last(
    channel_id: str, checks: list[dict[str, Any]], *, now: datetime | None = None
) -> None:
    """Keep this channel's latest checks (name and pass only)."""
    data = _read_last()
    data[channel_id] = {
        "at": (now or _now()).isoformat(timespec="seconds"),
        "checks": [{"name": str(c.get("name")), "ok": bool(c.get("ok"))} for c in checks],
    }
    try:
        os.makedirs(os.path.dirname(DOCTOR_LAST_FILE) or ".", exist_ok=True)
        with open(DOCTOR_LAST_FILE, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
    except OSError as exc:
        logger.debug("doctor result not kept: %s", exc)


def last_checks(channel_id: str, *, max_age_hours: float = FRESH_HOURS) -> list[dict] | None:
    """The kept checks when under `max_age_hours` old, else None."""
    entry = _read_last().get(channel_id) or {}
    try:
        at = datetime.fromisoformat(str(entry.get("at") or ""))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    if _now() - at > timedelta(hours=max_age_hours):
        return None
    checks = entry.get("checks")
    return list(checks) if isinstance(checks, list) else None


def gather(
    channel_id: str = "tapin",
    *,
    status_fetch: Any = None,
    local_failures: set[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"channel_id": channel_id, "checks": []}

    def add(name: str, ok: bool, detail: str) -> None:
        out["checks"].append({"name": name, "ok": ok, "detail": detail})

    try:
        from core.run_mode import _ollama_ready, free_backend_readiness

        ready, model = _ollama_ready()
        r = free_backend_readiness()
        add("ollama", ready, f"model {model}" if ready else "not ready (no HTTP pull)")
        add("local_tts", bool(r.tts_provider), r.tts_provider or "no local TTS ready")
        add("youtube_free", bool(r.youtube_free), "yt-dlp" if r.youtube_free else "yt-dlp missing")
    except Exception as exc:
        logger.debug("doctor free-stack skipped: %s", exc)
        add("free_stack", False, type(exc).__name__)

    try:
        from core.feed_health import cached_warnings

        warns = cached_warnings()
        add("feeds", not warns, "ok" if not warns else "; ".join(warns[:3]))
    except Exception as exc:
        logger.debug("doctor feeds skipped: %s", exc)
        add("feeds", True, f"n/a ({type(exc).__name__})")

    try:
        from youtube.constants import SCOPE_YOUTUBE_UPLOAD, SCOPE_YT_ANALYTICS_READONLY
        from youtube.oauth import token_has_scope, token_path_for_channel

        path = token_path_for_channel(channel_id)
        exists = os.path.isfile(path)
        upload = exists and token_has_scope(channel_id, SCOPE_YOUTUBE_UPLOAD)
        analytics = exists and token_has_scope(channel_id, SCOPE_YT_ANALYTICS_READONLY)
        mode = ""
        if exists:
            from youtube.oauth import sign_in_mode_line

            mode = sign_in_mode_line(channel_id)  # #1443: Testing or In production
        add(
            "oauth",
            exists,
            f"token {'present' if exists else 'missing'}; "
            f"upload={'yes' if upload else 'no'} analytics={'yes' if analytics else 'no'}"
            + (f"; {mode}" if mode else ""),
        )
    except Exception as exc:
        logger.debug("doctor oauth skipped: %s", exc)
        add("oauth", False, type(exc).__name__)

    try:
        from apis.youtube_quota import format_uploads_left, get_usage_summary

        summary = get_usage_summary()
        add("youtube_quota", True, format_uploads_left(summary))
    except Exception as exc:
        logger.debug("doctor youtube quota skipped: %s", exc)
        add("youtube_quota", True, f"n/a ({type(exc).__name__})")

    try:
        caption = (os.getenv("CAPTION_ALIGN_BACKEND") or "none").strip() or "none"
        tts = (os.getenv("TTS_PROVIDER") or "elevenlabs").strip() or "elevenlabs"
        add("caption_tts", True, f"CAPTION_ALIGN_BACKEND={caption}; TTS_PROVIDER={tts}")
    except Exception as exc:
        logger.debug("doctor caption/tts skipped: %s", exc)
        add("caption_tts", True, type(exc).__name__)

    try:
        from core import cuda_probe

        cuda = cuda_probe.probe()
        rendered = cuda_probe.render(cuda)
        detail = rendered.splitlines()[1].strip() if rendered else "probed"
        smi = bool(cuda.get("nvidia_smi"))
        avail = bool(cuda.get("cuda_available"))
        if smi and not avail:
            tv = cuda.get("torch_version") or "not installed"
            add(
                "cuda",
                False,
                f"nvidia-smi present; torch {tv} is CPU (install CUDA wheel when ready)",
            )
        else:
            add("cuda", True, detail)
        out["cuda"] = cuda
        nvenc_ok = bool(cuda.get("nvenc_capable"))
        add("nvenc", True, "h264_nvenc yes" if nvenc_ok else "h264_nvenc no (CPU libx264)")
    except Exception as exc:
        logger.debug("doctor cuda skipped: %s", exc)
        add("cuda", True, f"n/a ({type(exc).__name__})")
        add("nvenc", True, f"n/a ({type(exc).__name__})")

    try:
        from core import ram_preflight

        ram = ram_preflight.snapshot()
        add("ram", True, ram_preflight.render(ram))
        out["ram"] = ram
    except Exception as exc:
        logger.debug("doctor ram skipped: %s", exc)
        add("ram", True, f"n/a ({type(exc).__name__})")

    try:
        from core import secrets_doctor

        secrets = secrets_doctor.gather(channel_id)
        required_missing = int(secrets.get("required_missing") or 0)
        add(
            "secrets",
            required_missing == 0,
            (
                f"{secrets.get('present', 0)} present / "
                f"{required_missing} required missing / "
                f"{secrets.get('optional_missing', 0)} optional missing / "
                f"{secrets.get('placeholder', 0)} placeholder (values not shown)"
            ),
        )
        out["secrets"] = {
            "present": secrets.get("present"),
            "missing": secrets.get("missing"),
            "required_missing": required_missing,
            "optional_missing": secrets.get("optional_missing"),
            "placeholder": secrets.get("placeholder"),
        }
    except Exception as exc:
        logger.debug("doctor secrets skipped: %s", exc)
        add("secrets", True, f"n/a ({type(exc).__name__})")

    try:  # #1193: lines python-dotenv skips, by number only
        from core import secrets_doctor

        bad_lines = secrets_doctor.env_file_problems()
        add("env-file", not bad_lines, secrets_doctor.env_file_line(bad_lines) or "ok")
    except Exception as exc:
        logger.debug("doctor env-file skipped: %s", exc)

    try:  # #1190: TikTok and Instagram through Buffer - informational, never a failure
        from publishing import buffer_api, crosspost

        if buffer_api.configured():
            missing = crosspost.setup_missing(channel_id)
            add(
                "crosspost",
                True,
                "TikTok + Instagram through Buffer: "
                + ("ready" if not missing else crosspost.waits_line(missing)),
            )
    except Exception as exc:
        logger.debug("doctor crosspost skipped: %s", exc)

    try:
        from core import nightly_task

        uploads_ok, uploads_line = nightly_task.worker_doctor(channel_id)  # #1130
        add("uploads", uploads_ok, uploads_line)
    except Exception as exc:
        logger.debug("doctor uploads skipped: %s", exc)
        add("uploads", True, f"n/a ({type(exc).__name__})")

    try:
        from analytics import reach_report

        reach_ok, reach_line = reach_report.status(channel_id)  # #1058
        add("reach", reach_ok, reach_line)
    except Exception as exc:
        logger.debug("doctor reach skipped: %s", exc)
        add("reach", True, f"n/a ({type(exc).__name__})")

    try:
        from core import workspace_hazards

        hazards = workspace_hazards.gather()
        names = hazards.get("hazards") or []
        add("workspace", not names, workspace_hazards.render(hazards))
        out["workspace"] = hazards
    except Exception as exc:
        logger.debug("doctor workspace skipped: %s", exc)
        add("workspace", True, f"n/a ({type(exc).__name__})")

    try:
        from core.run_mode import free_mode_strict

        paid_off = os.getenv("PAID_CALLS", "").strip().lower() in ("0", "off", "false", "no")
        if not paid_off:
            add("paid_calls", True, "PAID_CALLS allowed (Standard)")
        elif free_mode_strict():
            add("paid_calls", True, "PAID_CALLS=off; free seams armed")
        else:
            add(
                "paid_calls",
                False,
                "PAID_CALLS=off but FREE_MODE_STRICT is not set — apply_and_guard was not run",
            )
    except Exception as exc:
        logger.debug("doctor paid_calls skipped: %s", exc)
        add("paid_calls", True, f"n/a ({type(exc).__name__})")

    try:  # #457
        ok, detail = lock_check()
        add("lockfile", ok, detail)
    except Exception as exc:
        logger.debug("doctor lockfile skipped: %s", exc)
        add("lockfile", True, f"n/a ({type(exc).__name__})")

    try:
        from core.startup_budget import budget_for

        add(
            "startup_budget",
            True,
            f"core.chrome <= {budget_for('core.chrome'):.1f}s; "
            f"main <= {budget_for('main'):.2f}s; "
            f"core.pipeline <= {budget_for('core.pipeline'):.2f}s",
        )
    except Exception as exc:
        logger.debug("doctor startup budget skipped: %s", exc)
        add("startup_budget", True, f"n/a ({type(exc).__name__})")

    try:
        failures = (
            set(local_failures)
            if local_failures is not None
            else _local_signal_failures(channel_id)
        )
        fetch = status_fetch or _fetch_status
        try:
            body = fetch(APIFY_STATUS_URL)
        except Exception as exc:
            logger.debug("apify status page: %s", type(exc).__name__)
            body = None
        ok, detail = vendor_line(body, failures)
        add("apify_status", ok, detail)
    except Exception as exc:
        logger.debug("doctor vendor status skipped: %s", type(exc).__name__)
        add("apify_status", True, f"n/a ({type(exc).__name__})")

    return out


def render(data: dict[str, Any] | None = None, *, channel_id: str = "tapin") -> str:
    if data is None:
        data = gather(channel_id)
        save_last(channel_id, data.get("checks") or [])  # the status line reads it
    lines = [f"ops doctor - {data.get('channel_id') or channel_id}", "=" * 48]
    for c in data.get("checks") or []:
        mark = "PASS" if c.get("ok") else "FAIL"
        lines.append(f"  [{mark}] {c.get('name')}: {c.get('detail')}")
    return "\n".join(lines)
