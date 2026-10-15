"""ops doctor (candidate 30).

One command: free-stack readiness + feeds snapshot + oauth scopes (file only,
no token refresh) + quota snapshot + caption/TTS + CUDA probe. Nested try so
an optional import cannot wipe the rest. The Apify status page is the one
extra HTTP call (#392); everything else stays on cached probes.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.ops_doctor")

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
        add(
            "oauth",
            exists,
            f"token {'present' if exists else 'missing'}; "
            f"upload={'yes' if upload else 'no'} analytics={'yes' if analytics else 'no'}",
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
                + ("ready" if not missing else "waits on " + ", ".join(missing)),
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
    data = data or gather(channel_id)
    lines = [f"ops doctor - {data.get('channel_id') or channel_id}", "=" * 48]
    for c in data.get("checks") or []:
        mark = "PASS" if c.get("ok") else "FAIL"
        lines.append(f"  [{mark}] {c.get('name')}: {c.get('detail')}")
    return "\n".join(lines)
