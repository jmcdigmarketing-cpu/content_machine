"""Same-run bind for the review room: never pair a leftover mp4 with a drafted run."""

from __future__ import annotations

import os
from typing import Any

from core.review_keys import approve_command


def bind_review_media(
    *,
    run_id: Any,
    run_status: str,
    run_mp4: str | None,
    leftover_mp4: str | None,
) -> dict[str, Any]:
    """Pick one run whose file exists. A leftover output/default mp4 is not that run."""
    run_file = str(run_mp4 or "").strip()
    leftover = str(leftover_mp4 or "").strip()
    status = str(run_status or "").strip().lower()
    if run_file and os.path.isfile(run_file) and status != "drafted":
        return {
            "mp4_path": os.path.abspath(run_file),
            "run_id": run_id,
            "run_status": status,
            "can_approve": True,
            "refuse_reason": "",
        }
    label = run_id if run_id not in (None, "") else "(unknown)"
    reason = f"Run {label} has no MP4 on disk. Status: {status or 'unknown'}"
    if leftover and os.path.isfile(leftover):
        reason += f". Player will not load leftover {os.path.basename(leftover)}"
    return {
        "mp4_path": "",
        "run_id": run_id,
        "run_status": status,
        "can_approve": False,
        "refuse_reason": reason,
    }


def claim_rows(run_id: Any) -> list[dict[str, Any]]:
    """Flagged claims for the review room, each with the research line that carries it."""
    if run_id in (None, ""):
        return []
    from core.facts.claim_confirm import load_features, run_flagged_claims, source_problem

    features = load_features(int(run_id)) or {}
    settled = {
        str(row.get("claim") or "").strip()
        for row in features.get("claims_confirmed") or []
        if isinstance(row, dict) and not source_problem(str(row.get("source") or ""))
    }
    return [
        {
            "number": row.number,
            "claim": row.claim,
            "source_line": row.found_in,
        }
        for row in run_flagged_claims(int(run_id))
        if row.claim not in settled
    ]


def confirm_from_room(run_id: Any, number: int, source: str) -> dict[str, Any]:
    """Confirm one claim. An empty or placeholder source does not write."""
    from core.facts.claim_confirm import confirm_claim

    result = confirm_claim(int(run_id), int(number), source=source or "", dry_run=False)
    return {
        "status": result.status,
        "detail": result.detail,
        "claim": result.claim,
        "open_claims": len(claim_rows(run_id)) if result.status == "confirmed" else None,
    }


def reject_from_room(run_id: Any, number: int) -> dict[str, Any]:
    """Cut: the sentences that carry the claim. The run stays held."""
    from core.facts.claim_confirm import reject_claim

    result = reject_claim(int(run_id), int(number), dry_run=False)
    return {
        "status": result.status,
        "detail": result.detail,
        "claim": result.claim,
        "sentences": list(result.sentences),
    }


def go_public_block(run_id: Any) -> str:
    """Why Go public stays off, or "" when no flagged claim is still open."""
    rows = claim_rows(run_id)
    if rows:
        return f"{len(rows)} flagged claim(s) still open"
    return ""


def go_public_from_room(run_id: Any, video_id: str, *, channel_id: str = "tapin") -> dict[str, str]:
    """Flip privacy only after the flagged claims are settled (#1064)."""
    block = go_public_block(run_id)
    if block:
        return {"status": "refused", "detail": block}
    from publishing.go_public import apply_go_public

    result = apply_go_public(video_id, channel_id=channel_id or "tapin", dry_run=False)
    return {"status": result.status, "detail": str(result.detail or "")}


def queued_approve_command(ctx: dict[str, Any] | None) -> str | None:
    """None when Approve would queue a drafted or empty-path run."""
    data = dict(ctx or {})
    if data.get("can_approve") is False:
        return None
    status = str(data.get("run_status") or "").strip().lower()
    if status == "drafted":
        return None
    mp4 = str(data.get("mp4_path") or data.get("mp4") or "").strip()
    if not mp4 or not os.path.isfile(mp4):
        return None
    cmd = approve_command(data)
    if "requeue-upload" in cmd and status == "drafted":
        return None
    return cmd
