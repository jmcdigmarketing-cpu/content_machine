"""ComfyUI HTTP client seam (Pillar 6) — one endpoint for image / video / upscale models.

ComfyUI is a self-hosted node-graph server the operator runs (default
`http://localhost:8188`). This is the single HTTP client the AI-video / thumbnail /
upscale slots submit workflows through, so we add one client instead of N model SDKs.

Fail-open by construction: if the server is unreachable (the common case — it isn't
running), every call returns `ProviderResult.fail_open` and callers keep their current
path (e.g. stock B-roll). No heavy deps — just `requests` (already required).

    COMFYUI_URL=http://localhost:8188

Build a workflow in the ComfyUI UI, export it as JSON under `workflows/`, and submit it
here with the prompt swapped in (see LTX-Video note in `workflows/README.md`).
"""

from __future__ import annotations

import os
import time

import requests

from core.logging import get_logger
from core.providers import STATUS_ERROR, STATUS_NOT_CONFIGURED, ProviderResult

logger = get_logger("core.comfy_client")

SLOT = "comfyui"


def base_url() -> str:
    return os.getenv("COMFYUI_URL", "http://localhost:8188").rstrip("/")


def _timeout() -> float:
    try:
        return float(os.getenv("COMFYUI_TIMEOUT", "8"))
    except (TypeError, ValueError):
        return 8.0


def submit_workflow(workflow: dict) -> ProviderResult:
    """POST a workflow graph to /prompt. `data` is the returned prompt_id on success."""
    try:
        resp = requests.post(f"{base_url()}/prompt", json={"prompt": workflow}, timeout=_timeout())
        resp.raise_for_status()
        prompt_id = (resp.json() or {}).get("prompt_id")
        if not prompt_id:
            return ProviderResult.fail_open(SLOT, "no prompt_id in response", status=STATUS_ERROR)
        return ProviderResult.success(SLOT, "comfyui", data=prompt_id)
    except Exception as exc:
        logger.debug("ComfyUI submit failed (%s): %s", base_url(), exc)
        return ProviderResult.fail_open(SLOT, f"submit failed: {exc}", status=STATUS_NOT_CONFIGURED)


def poll(prompt_id: str, *, max_wait: float = 120.0, interval: float = 2.0) -> ProviderResult:
    """Poll /history/{prompt_id} until outputs appear or `max_wait` elapses."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url()}/history/{prompt_id}", timeout=_timeout())
            resp.raise_for_status()
            history = resp.json() or {}
        except Exception as exc:
            logger.debug("ComfyUI poll failed: %s", exc)
            return ProviderResult.fail_open(
                SLOT, f"poll failed: {exc}", status=STATUS_NOT_CONFIGURED
            )
        entry = history.get(prompt_id)
        if entry and entry.get("outputs"):
            return ProviderResult.success(SLOT, "comfyui", data=entry["outputs"])
        time.sleep(interval)
    return ProviderResult.fail_open(SLOT, "timed out waiting for outputs", status=STATUS_ERROR)


def generate(prompt: str, *, workflow: dict | None = None) -> ProviderResult:
    """High-level: submit a workflow (with `prompt` swapped in) and wait for outputs.

    Baseline: without a saved workflow template this fails open — the operator supplies
    a `workflows/*.json` graph and the prompt-injection point once ComfyUI is running.
    """
    if not workflow:
        return ProviderResult.fail_open(
            SLOT,
            "no workflow template provided (see workflows/README.md)",
            status=STATUS_NOT_CONFIGURED,
        )
    submitted = submit_workflow(workflow)
    if not submitted.ok:
        return submitted
    return poll(str(submitted.data))
