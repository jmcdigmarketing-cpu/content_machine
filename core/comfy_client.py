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

import json
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


def _load_workflow_template() -> dict | None:
    """Load the ComfyUI workflow graph from COMFYUI_WORKFLOW (a workflows/*.json path).

    Returns None (⇒ fail-open) when unset, missing, or unparseable.
    """
    path = os.getenv("COMFYUI_WORKFLOW", "").strip()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError) as exc:
        logger.debug("ComfyUI workflow load failed (%s): %s", path, exc)
        return None


def _inject_prompt(workflow: dict, prompt: str) -> dict:
    """Replace the `__PROMPT__` placeholder in the graph's string values with `prompt`.

    Walks the structure rather than string-replacing serialized JSON, so any prompt
    text — quotes, backslashes, newlines — is injected safely and can never make the
    workflow unparseable (which would break generate()'s fail-open contract).
    """

    def _walk(node):
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(v) for v in node]
        if isinstance(node, str):
            return node.replace("__PROMPT__", prompt)
        return node

    return _walk(workflow)


def _extract_output_file(outputs: dict) -> dict | None:
    """First saved-file descriptor {filename, subfolder, type} in ComfyUI's outputs.

    ComfyUI groups a node's saved files under "images"/"gifs"/"videos"; a video
    workflow (LTX/Wan/VHS) lands under gifs or videos. Returns None when the graph
    produced no downloadable file.
    """
    for node in (outputs or {}).values():
        if not isinstance(node, dict):
            continue
        for key in ("videos", "gifs", "images"):
            items = node.get(key)
            if isinstance(items, list) and items and isinstance(items[0], dict):
                first = items[0]
                if first.get("filename"):
                    return {
                        "filename": first["filename"],
                        "subfolder": first.get("subfolder", ""),
                        "type": first.get("type", "output"),
                    }
    return None


def _download_output(descriptor: dict) -> str | None:
    """Download a ComfyUI output file via /view to a local path (None on failure)."""
    dest_dir = os.getenv("AI_VIDEO_OUTPUT_DIR", os.path.join("output", "ai_video"))
    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(str(descriptor["filename"])))
        resp = requests.get(
            f"{base_url()}/view",
            params={
                "filename": descriptor["filename"],
                "subfolder": descriptor.get("subfolder", ""),
                "type": descriptor.get("type", "output"),
            },
            timeout=max(30.0, _timeout() * 4),
        )
        resp.raise_for_status()
        with open(dest, "wb") as f:
            f.write(resp.content)
        return dest
    except Exception as exc:
        logger.debug("ComfyUI /view download failed: %s", exc)
        return None


def generate(prompt: str, *, workflow: dict | None = None) -> ProviderResult:
    """High-level: submit a workflow (prompt injected), wait for outputs, and
    download the produced media. `data` is the LOCAL PATH to the generated file on
    success. Fails open when no template is configured, ComfyUI is unreachable, or
    no output file comes back — so callers keep their stock/local path.
    """
    if workflow is None:
        workflow = _load_workflow_template()
    if not workflow:
        return ProviderResult.fail_open(
            SLOT,
            "no workflow template (set COMFYUI_WORKFLOW; see workflows/README.md)",
            status=STATUS_NOT_CONFIGURED,
        )
    submitted = submit_workflow(_inject_prompt(workflow, prompt))
    if not submitted.ok:
        return submitted
    polled = poll(str(submitted.data))
    if not polled.ok or not isinstance(polled.data, dict):
        return polled
    descriptor = _extract_output_file(polled.data)
    if not descriptor:
        return ProviderResult.fail_open(
            SLOT, "no output file in ComfyUI response", status=STATUS_ERROR
        )
    local_path = _download_output(descriptor)
    if not local_path:
        return ProviderResult.fail_open(SLOT, "output download failed", status=STATUS_ERROR)
    return ProviderResult.success(SLOT, "comfyui", data=local_path)
