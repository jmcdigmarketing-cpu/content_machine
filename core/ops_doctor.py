"""ops doctor (candidate 30).

One command: free-stack readiness + feeds snapshot + oauth scopes (file only,
no token refresh) + quota snapshot + caption/TTS + CUDA probe. Nested try so
an optional import cannot wipe the rest. No extra HTTP vs cached probes.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("core.ops_doctor")


def gather(channel_id: str = "tapin") -> dict[str, Any]:
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

    return out


def render(data: dict[str, Any] | None = None, *, channel_id: str = "tapin") -> str:
    data = data or gather(channel_id)
    lines = [f"ops doctor - {data.get('channel_id') or channel_id}", "=" * 48]
    for c in data.get("checks") or []:
        mark = "PASS" if c.get("ok") else "FAIL"
        lines.append(f"  [{mark}] {c.get('name')}: {c.get('detail')}")
    return "\n".join(lines)
