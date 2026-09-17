"""Review a batch of drafts in one pass, render the accepted ones, space them out (#760).

The operator's target is 3-5 uploads a week (2026-09-15). The ends already existed:
`core.batch_generation` makes N drafts overnight with no voice cost, and
`core.spaced_queue` gives each rendered run its own open slot inside the cadence cap. This
is the middle, as the operator chose it on 2026-09-16 - one pass, a human yes per draft:

    py -m scripts.ops batch-review --channel tapin

Every decision is written to the draft's `meta.json` the moment it is made, so a Ctrl+C or
a failed render resumes where it stopped: a rejected draft is never shown again, and an
accepted one that did not finish rendering is rendered on the next pass without asking.
A draft whose claims fail the #345 bar needs `force` typed, which records the same
`grounding_override` as the interactive "Render anyway?" (#754) - so it never goes public.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.spaced_queue import plan_spaced_uploads, queue_spaced_uploads

logger = get_logger("core.batch_review")

_SCRIPT_HEADING = "## Script"


@dataclass
class PendingDraft:
    folder: str
    meta: dict[str, Any]
    script: str

    @property
    def run_id(self) -> int:
        return int(self.meta.get("run_id") or 0)

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.meta.get("variant") or self.meta.get("topic"))

    @property
    def topic(self) -> str:
        return str(self.meta.get("variant") or self.meta.get("topic") or "")

    @property
    def length_choice(self) -> str:
        return str(self.meta.get("length_choice") or "2")

    @property
    def decision(self) -> str:
        review = self.meta.get("review")
        return str(review.get("decision") or "") if isinstance(review, dict) else ""


@dataclass
class ReviewSummary:
    accepted: list[int] = field(default_factory=list)
    rejected: list[int] = field(default_factory=list)
    later: list[int] = field(default_factory=list)
    rendered: list[int] = field(default_factory=list)
    queued: list[int] = field(default_factory=list)


def draft_script(folder: str) -> str:
    """The script section of a batch draft's `draft.md`."""
    try:
        with open(os.path.join(folder, "draft.md"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    _head, found, rest = text.partition(_SCRIPT_HEADING)
    if not found:
        return ""
    return rest.split("\n## ", 1)[0].strip()


def pending_drafts(channel_id: str, *, root: str | None = None) -> list[PendingDraft]:
    """Drafts nobody has decided on, plus accepted ones that never finished rendering."""
    if root is None:
        from core.batch_generation import _drafts_dir

        root = _drafts_dir(channel_id)
    out: list[PendingDraft] = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for name in names:
        folder = os.path.join(root, name)
        try:
            with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or not meta.get("run_id"):
            continue
        draft = PendingDraft(folder=folder, meta=meta, script=draft_script(folder))
        if draft.decision not in ("", "accepted") or not draft.script:
            continue
        out.append(draft)
    return out


def _write_review(draft: PendingDraft, **review: Any) -> None:
    existing = draft.meta.get("review")
    current: dict[str, Any] = existing if isinstance(existing, dict) else {}
    draft.meta["review"] = {**current, **review, "at": datetime.now().isoformat(timespec="seconds")}
    try:
        with open(os.path.join(draft.folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(draft.meta, f, indent=2, default=str)
    except OSError as exc:
        logger.warning("review not saved for %s: %s", draft.folder, exc)


def _blocking_claims(draft: PendingDraft) -> list[str]:
    from core.claim_types import blocking_unsupported

    return blocking_unsupported(draft.meta.get("claim_verification"))


def _projected_voice(draft: PendingDraft) -> float | None:
    try:
        from core.cost_meter import render_cost_lines
        from core.tts import length_context

        with length_context(draft.length_choice):
            return float(render_cost_lines(draft.script)["tts"])
    except Exception as exc:
        logger.debug("voice projection skipped: %s", exc)
        return None


def _render(draft: PendingDraft, override: bool) -> bool:
    """Voice + render one accepted draft onto its existing run row."""
    from core.pipeline import run_media_only

    run_media_only(
        draft.topic,
        draft.script,
        channel_id=str(draft.meta.get("channel_id") or "") or None,
        content_run_id=draft.run_id,
        title=draft.title,
        length_choice=draft.length_choice,
    )
    if override:
        from core.claim_verifier import override_features
        from core.run_features import merge_features

        merge_features(draft.run_id, override_features(draft.meta.get("claim_verification")))
    return True


def _local(when: Any, channel_id: str) -> str:
    try:
        from analytics.post_timing import format_scheduled_local

        return str(format_scheduled_local(when, channel_id))
    except Exception:
        return str(when)


def _show(draft: PendingDraft, index: int, total: int, print_fn: Callable[..., Any]) -> list[str]:
    meta = draft.meta
    print_fn(f"\n  [{index}/{total}] {draft.title}  (run {draft.run_id})")
    print_fn(f"    angle: {draft.topic}")
    hook = meta.get("hook_score")
    print_fn(
        f"    hook {hook if hook is not None else 'n/a'} ({meta.get('hook_verdict') or 'n/a'})"
        f" - authenticity {meta.get('authenticity_verdict') or 'n/a'}"
        f" - {len(draft.script.split())} words"
    )
    voice = _projected_voice(draft)
    if voice is not None:
        print_fn(f"    voice: ~${voice:.2f}")
    words = draft.script.split()
    opener = " ".join(words[:30]) + (" ..." if len(words) > 30 else "")
    print_fn(f"    opens: {opener}")
    blocking = _blocking_claims(draft)
    for claim in blocking[:3]:
        print_fn(f"    ! unsupported: {claim}")
    from core.claim_types import warn_only_unsupported

    for claim in warn_only_unsupported(draft.meta.get("claim_verification"))[:2]:
        print_fn(f"    ~ hedged, warn only: {claim}")
    return blocking


def review_drafts(
    channel_id: str,
    *,
    root: str | None = None,
    ask: Callable[[str], str] = input,
    print_fn: Callable[..., Any] = print,
) -> ReviewSummary:
    """One pass: decide every waiting draft, then render the yeses and space them out."""
    summary = ReviewSummary()
    drafts = pending_drafts(channel_id, root=root)
    if not drafts:
        print_fn(
            "  No drafts waiting. Make some: py -m scripts.ops batch-drafts --channel", channel_id
        )
        return summary

    accepted: list[tuple[PendingDraft, bool]] = []
    for index, draft in enumerate(drafts, 1):
        if draft.decision == "accepted":
            review = draft.meta.get("review") or {}
            print_fn(f"\n  [{index}/{len(drafts)}] {draft.title}: accepted earlier, rendering")
            accepted.append((draft, bool(review.get("override"))))
            continue
        blocking = _show(draft, index, len(drafts), print_fn)
        answer = ask("  Render it? [y / n = reject / Enter = later / q = stop]: ").strip().lower()
        if answer == "q":
            break
        if answer == "n":
            _write_review(draft, decision="rejected")
            summary.rejected.append(draft.run_id)
            continue
        if answer != "y":
            summary.later.append(draft.run_id)
            continue
        override = False
        if blocking:
            typed = ask("  It has unsupported claims. Type force to render anyway: ")
            if typed.strip().lower() != "force":
                print_fn("    Left for later.")
                summary.later.append(draft.run_id)
                continue
            override = True
        _write_review(draft, decision="accepted", override=override)
        accepted.append((draft, override))
    summary.accepted = [draft.run_id for draft, _override in accepted]

    items: list[tuple[int, str]] = []
    drafts_by_run: dict[int, PendingDraft] = {}
    for draft, override in accepted:
        print_fn(f"\n  Rendering run {draft.run_id}: {draft.title}")
        try:
            _render(draft, override)
        except Exception as exc:
            print_fn(f"    ! not rendered ({exc}); it stays accepted and renders next pass")
            continue
        _write_review(draft, decision="rendered", override=override)
        summary.rendered.append(draft.run_id)
        items.append((draft.run_id, draft.title))
        drafts_by_run[draft.run_id] = draft
    if not items:
        return summary

    plan = plan_spaced_uploads(items, channel_id=channel_id, topic=items[0][1])
    summary.queued = queue_spaced_uploads(plan, channel_id=channel_id)
    print_fn("\n  Upload slots")
    for slot in plan:
        slotted = drafts_by_run.get(int(slot.run_id))
        if slot.publish_at is None:
            print_fn(f"    ! [{slot.run_id}] {slot.skipped} - rendered, left on disk")
            continue
        privacy = getattr(slot, "privacy", "") or "not queued"
        print_fn(f"    [{slot.run_id}] {privacy} at {_local(slot.publish_at, channel_id)}")
        if slotted is not None:
            _write_review(slotted, publish_at=str(slot.publish_at), privacy=privacy)
    print_fn(f"  Queued {len(summary.queued)}. Run the worker: py -m jobs.worker --loop 30")
    return summary
