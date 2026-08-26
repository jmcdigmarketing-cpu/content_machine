"""Dual-thumbnail gating, validation, and pick-time experiment assignment."""

from __future__ import annotations

import os
from typing import Any

from config.channels import resolve_channel_id

_TRUE = {"1", "true", "yes", "on"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def dual_thumbnail_enabled(channel_id: str | None = None) -> bool:
    if os.getenv("THUMBNAIL_DUAL", "").strip().lower() in _TRUE:
        return True
    try:
        from core.experiments import active_experiment

        active = active_experiment(resolve_channel_id(channel_id))
        return bool(active and active.get("lever") == "thumbnail_format")
    except Exception:
        return False


def _candidates(features: dict[str, Any]) -> list[dict[str, Any]]:
    raw = features.get("thumbnail_candidates") or []
    return [dict(item) for item in raw if isinstance(item, dict) and item.get("path")]


def chosen_thumbnail(content_run_id: int | None) -> str | None:
    if not content_run_id:
        return None
    from core.run_features import load_features

    selected = (load_features(content_run_id) or {}).get("thumbnail_pick") or {}
    path = str(selected.get("path") or "") if isinstance(selected, dict) else ""
    return path if path and os.path.isfile(path) else None


def ensure_thumbnail_ready(content_run_id: int | None) -> str | None:
    """Block only a generated dual set that still lacks an explicit validated pick."""
    if not content_run_id:
        return None
    from core.run_features import load_features

    features = load_features(content_run_id) or {}
    candidates = _candidates(features)
    selected = chosen_thumbnail(content_run_id)
    if len(candidates) >= 2 and not selected:
        raise RuntimeError(
            f"Run {content_run_id} has dual thumbnails but no pick; run "
            f"`py -m scripts.ops pick-thumbnail --run-id {content_run_id} --arm "
            "text_on|face_forward` before publishing."
        )
    return selected


def pick_thumbnail(
    content_run_id: int,
    path: str | None = None,
    *,
    arm: str | None = None,
    channel_id: str | None = None,
) -> dict[str, Any]:
    """Validate one generated candidate, persist it, then assign the experiment arm."""
    from core.run_features import load_features, merge_features

    features = load_features(content_run_id) or {}
    candidates = _candidates(features)
    if not candidates:
        raise ValueError(f"Run {content_run_id} has no thumbnail candidates")
    requested = os.path.abspath(path) if path else ""
    matches = [
        item
        for item in candidates
        if (requested and os.path.abspath(str(item["path"])) == requested)
        or (arm and str(item.get("arm")) == arm)
    ]
    if len(matches) != 1:
        raise ValueError("Choose exactly one candidate path or arm from the generated set")
    chosen = matches[0]
    chosen_path = os.path.abspath(str(chosen["path"]))
    if os.path.splitext(chosen_path)[1].lower() not in _IMAGE_EXTS:
        raise ValueError(f"Unsupported thumbnail type: {chosen_path}")
    if not os.path.isfile(chosen_path) or os.path.getsize(chosen_path) <= 0:
        raise ValueError(f"Thumbnail candidate is missing or empty: {chosen_path}")

    channel = resolve_channel_id(channel_id or str(features.get("channel_id") or ""))
    selected = {
        "path": chosen_path,
        "arm": str(chosen.get("arm") or ""),
        "provider": str(chosen.get("provider") or ""),
        "features": dict(chosen.get("features") or {}),
        "asset_id": None,
    }
    from storage.repositories.assets import get_asset_repository

    asset = get_asset_repository().create(
        {
            "channel_id": channel,
            "content_run_id": int(content_run_id),
            "asset_type": "thumbnail",
            "provider": selected["provider"],
            "path": chosen_path,
            "source_id": selected["arm"],
            "query": "",
            "attribution": "operator-picked dual thumbnail",
        }
    )
    selected["asset_id"] = getattr(asset, "id", None)
    merge_features(content_run_id, {"thumbnail_pick": selected})

    # Assignment happens only after file validation + durable selection metadata.
    if selected["arm"]:
        from core.experiments import record_assignment

        record_assignment(channel, int(content_run_id), "thumbnail_format", selected["arm"])
    return selected
