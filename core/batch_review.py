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
import re
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
        # draft.md is this folder's own copy and wins; the #774 trace sidecar is the
        # fallback for a draft written before draft.md carried the full script.
        from core.run_trace import full_script

        script = draft_script(folder) or full_script(meta.get("run_id")) or ""
        draft = PendingDraft(folder=folder, meta=meta, script=script)
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

        return float(render_cost_lines(draft.script, length_choice=draft.length_choice)["tts"])
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


_REJECTION_REASONS = ("pace", "facts", "angle", "hook", "topic", "other")
_REJECTION_INITIALS = {name[0]: name for name in _REJECTION_REASONS}


def normalize_rejection_reason(raw: str) -> str:
    """Map a one-keystroke or word answer onto the closed reason set."""
    token = (raw or "").strip().lower()
    if token in _REJECTION_REASONS:
        return token
    if token in _REJECTION_INITIALS:
        return _REJECTION_INITIALS[token]
    return "other"


_NEWS_WINDOW_DAYS = 2.0
_EVERGREEN_WINDOW_DAYS = 7.0
_NEWS_DOMAINS = frozenset({"ufc", "mma", "nba", "nfl", "mlb", "nhl", "sports"})
_NEWS_WORDS_RE = re.compile(
    r"\b(trailer|leak(?:s|ed)?|announce[sd]?|announcement|tonight|this week|results?|"
    r"card|fight night|breaking|reveal(?:s|ed)?|release date|patch notes|trade[sd]?|"
    r"signs?|signed|injur(?:y|ed)|odds|preview|recap)\b",
    re.IGNORECASE,
)


def draft_age_days(meta: dict[str, Any]) -> float | None:
    """Days since the draft was made (#763), None when `created_at` is missing or bad."""
    try:
        made = datetime.fromisoformat(str(meta.get("created_at")))
    except (TypeError, ValueError):
        return None
    now = datetime.now(made.tzinfo) if made.tzinfo else datetime.now()
    return max(0.0, (now - made).total_seconds() / 86400.0)


def freshness_window_days(meta: dict[str, Any]) -> float:
    """2 days for a news-shaped draft, 7 for anything else (operator call 2026-09-16)."""
    text = " ".join(str(meta.get(key) or "") for key in ("topic", "variant", "title"))
    if _NEWS_WORDS_RE.search(text):
        return _NEWS_WINDOW_DAYS
    try:
        from core.publish_windows import is_ufc_topic
        from core.rumor_language import is_leak_topic

        if is_leak_topic(text) or is_ufc_topic(text):
            return _NEWS_WINDOW_DAYS
    except Exception as exc:
        logger.debug("news-topic check skipped: %s", exc)
    try:
        from core.engagement import safe_infer_domain

        channel = str(meta.get("channel_id") or "tapin")
        if safe_infer_domain(text, channel) in _NEWS_DOMAINS:
            return _NEWS_WINDOW_DAYS
    except Exception as exc:
        logger.debug("domain check skipped: %s", exc)
    return _EVERGREEN_WINDOW_DAYS


def _local(when: Any, channel_id: str) -> str:
    try:
        from analytics.post_timing import format_scheduled_local

        return str(format_scheduled_local(when, channel_id))
    except Exception:
        return str(when)


def _show(draft: PendingDraft, index: int, total: int, print_fn: Callable[..., Any]) -> list[str]:
    meta = draft.meta
    age = draft_age_days(meta)
    made = f"  made {age:.0f}d ago" if age is not None else ""
    print_fn(f"\n  [{index}/{total}] {draft.title}  (run {draft.run_id}){made}")
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
    from core.facts.freshness import review_note

    note = review_note(meta.get("research"), pasted=int(meta.get("key_facts_count") or 0))
    if note:
        print_fn(f"    ? {note}")
    from core.facts.freshness import mode_note

    mode = mode_note(meta.get("research"))  # #339
    if mode:
        print_fn(f"    ~ {mode}")
    for warning in (meta.get("title_warnings") or [])[:2]:  # #1150
        print_fn(f"    ! title: {warning}")
    game = game_block_reason(meta)  # #1151
    if game:
        print_fn(f"    ! {game}")
        if meta.get("unplayed_result"):
            print_fn(f"      {str(meta['unplayed_result'])[:140]}")
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
        age = draft_age_days(draft.meta)
        if age is not None and age > freshness_window_days(draft.meta):
            current = ask(f"  This is {age:.0f} days old - still current? [y/N]: ").strip().lower()
            if current != "y":
                print_fn("    Left for later.")
                summary.later.append(draft.run_id)
                continue
        answer = ask("  Render it? [y / n = reject / Enter = later / q = stop]: ").strip().lower()
        if answer == "q":
            break
        if answer == "n":
            typed = ask("  Why? [pace / facts / angle / hook / topic / other]: ")
            reason = normalize_rejection_reason(typed)
            _write_review(draft, decision="rejected", reason=reason)
            print_fn(f"    rejected ({reason})")
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


# ---- #1078: a render nobody is watching (operator, 2026-10-11: "yes, up to 2 a night") ------
#
# Overnight wrote drafts every night and rendered none, by a recorded rule; 69 runs had stopped
# at `proceed_video=False`. The rule is reversed for a channel that sets `overnight.renders`.
# An unattended render takes only a draft a person would wave through: nothing unsupported,
# nothing flagged, still current. It is queued **unlisted, now** - never public - so the
# operator's step in the morning is to watch it and run `go-public`.


def drafts_line(channel_id: str, *, root: str | None = None) -> str:
    """#1132: the drafts waiting, split into what overnight will take and what needs a person.

    69 runs had stopped at a draft and no line the operator reads said any were waiting.
    """
    eligible, skipped = unattended_candidates(channel_id, root=root)
    total = len(eligible) + len(skipped)
    if not total:
        return ""
    limit = unattended_limit(channel_id)
    stale = sum(1 for _draft, why in skipped if "past its window" in why)
    parts = []
    if eligible and limit > 0 and shelf_pause(channel_id):
        parts.append(f"{len(eligible)} clean (overnight is paused: the shelf is full)")
    elif eligible and limit > 0:
        parts.append(f"{len(eligible)} could render overnight ({limit} a night)")
    elif eligible:
        parts.append(f"{len(eligible)} clean")
    if len(skipped) - stale:
        parts.append(f"{len(skipped) - stale} need you")
    if stale:
        parts.append(f"{stale} past their window")
    return (
        f"Drafts waiting: {total} - {', '.join(parts)}: "
        f"py -m scripts.ops batch-review --channel {channel_id}"
    )


def unattended_limit(channel_id: str) -> int:
    """How many drafts overnight may render: `OVERNIGHT_RENDERS` when set, else the channel's
    `overnight.renders`. 0 means none."""
    raw = os.getenv("OVERNIGHT_RENDERS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    try:
        from config.channels import get_channel_profile

        return max(0, int(getattr(get_channel_profile(channel_id), "overnight_renders", 0) or 0))
    except Exception as exc:
        logger.debug("overnight render limit unreadable: %s", exc)
        return 0


def shelf_max() -> int:
    """`OVERNIGHT_SHELF_MAX` (default 3; 0 = no limit): overnight renders nothing while this
    many finished videos are not public (#1152, operator 2026-10-13: "pause at 3 waiting")."""
    raw = os.getenv("OVERNIGHT_SHELF_MAX", "3").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 3


def shelf_waiting(channel_id: str) -> int:
    """How many finished videos are not public - the rows `ops shelf` lists."""
    try:
        from core.stale_renders import shelf_rows

        return len(shelf_rows(channel_id))
    except Exception as exc:
        logger.debug("shelf not read for the overnight limit: %s", exc)
        return 0


def shelf_pause(channel_id: str, *, waiting: int | None = None) -> str:
    """Why overnight is not rendering, or "" when the shelf has room.

    2026-10-13: four finished videos were waiting, no upload task was installed and the
    sign-in had expired; overnight would have rendered two more that night and every night.
    """
    limit = shelf_max()
    if limit <= 0:
        return ""
    count = shelf_waiting(channel_id) if waiting is None else waiting
    if count < limit:
        return ""
    return (
        f"{count} finished videos are waiting (overnight stops at {limit}) - "
        f"py -m scripts.ops shelf --channel {channel_id}"
    )


def game_block_reason(meta: dict[str, Any], *, now: datetime | None = None) -> str:
    """#1151 (operator, 2026-10-13: "render only before the game"). "" for a draft that is
    not about a scheduled game."""
    from core.facts.event_dates import fixture_sides, game_started

    event_at = str(meta.get("event_at") or "")
    if not event_at:
        # A draft written before the start was recorded: a topic named like a fixture waits.
        return "its game time is not known" if fixture_sides(str(meta.get("topic") or "")) else ""
    started = game_started(event_at, now=now)
    if started is None:
        return "its game time is not known"
    if started:
        return f"its game has started ({event_at[:16].replace('T', ' ')} UTC)"
    if meta.get("unplayed_result"):
        return "it states a result for a game not yet played"
    return ""


def unattended_block_reason(draft: PendingDraft, *, now: datetime | None = None) -> str:
    """Why a draft must wait for a person, or "" when it may render unattended."""
    meta = draft.meta
    if draft.decision:
        return f"already {draft.decision}"
    if _blocking_claims(draft):
        return "a claim is not supported"
    verdict = str(meta.get("authenticity_verdict") or "ok").strip().lower()
    if verdict != "ok":
        return f"authenticity check says {verdict}"
    if meta.get("fact_conflicts"):
        return "its facts conflict"
    if meta.get("ungrounded_entities"):
        return "it names something the facts do not"
    if str(meta.get("hook_verdict") or "").strip().lower() == "weak":
        return "weak hook"
    check = meta.get("script_clean")
    if isinstance(check, dict) and check.get("ok") is False:
        reasons = check.get("why") or ["not clean"]
        return f"script check: {reasons[0]}"  # #1143
    if meta.get("title_warnings"):
        return "its title says something the facts do not"  # #1150
    game = game_block_reason(meta, now=now)
    if game:
        return game
    from core.title_generator import title_label

    label = title_label(draft.title)
    if label:
        # Run 116's draft was titled "Contrarian: Spain's World Cup win ..." - the angle's
        # label, pasted in front of the title. A person fixes that; overnight must not ship it.
        return f'its title starts with a label ("{label}")'
    age = draft_age_days(meta)
    if age is not None and age > freshness_window_days(meta):
        return f"{age:.0f} days old, past its window"
    return ""


def unattended_candidates(
    channel_id: str, *, root: str | None = None
) -> tuple[list[PendingDraft], list[tuple[PendingDraft, str]]]:
    """(drafts that may render, best hook first then newest; the rest with their reason)."""
    eligible: list[PendingDraft] = []
    skipped: list[tuple[PendingDraft, str]] = []
    for draft in pending_drafts(channel_id, root=root):
        reason = unattended_block_reason(draft)
        if reason:
            skipped.append((draft, reason))
        else:
            eligible.append(draft)

    def rank(draft: PendingDraft) -> tuple[float, float]:
        try:
            hook = float(draft.meta.get("hook_score") or 0)
        except (TypeError, ValueError):
            hook = 0.0
        age = draft_age_days(draft.meta)
        return (-hook, age if age is not None else 1e9)

    return sorted(eligible, key=rank), skipped


def _queue_unlisted(run_id: int, channel_id: str) -> int:
    from analytics.queue_manager import requeue_content_run

    return requeue_content_run(run_id, channel_id, privacy_status="unlisted")


def render_unattended(
    channel_id: str,
    limit: int,
    *,
    root: str | None = None,
    render: Callable[[PendingDraft, bool], bool] | None = None,
    queue: Callable[[int, str], int] | None = None,
    shelf: Callable[[str], int] | None = None,
) -> dict[str, Any]:
    """Render up to `limit` eligible drafts and queue each one unlisted.

    Returns {rendered, queued, failed: [(run, why)], waiting: [(run, why)], paused}. A draft
    that fails to render keeps its place for the operator; nothing is ever queued public.
    `paused` (#1152) says why it stopped when finished videos are already waiting.
    """
    out: dict[str, Any] = {"rendered": [], "queued": [], "failed": [], "waiting": []}
    if limit <= 0:
        return out
    eligible, skipped = unattended_candidates(channel_id, root=root)
    out["waiting"] = [(d.run_id, why) for d, why in skipped]
    on_shelf = (shelf or shelf_waiting)(channel_id) if shelf_max() > 0 else 0
    for draft in eligible[:limit]:
        paused = shelf_pause(channel_id, waiting=on_shelf)
        if paused:
            out["paused"] = paused
            break
        try:
            (render or _render)(draft, False)
        except Exception as exc:
            logger.warning("overnight render of run %s failed: %s", draft.run_id, exc)
            out["failed"].append((draft.run_id, str(exc)[:120]))
            continue
        _write_review(draft, decision="rendered", override=False, by="overnight")
        out["rendered"].append(draft.run_id)
        on_shelf += 1
        try:
            (queue or _queue_unlisted)(draft.run_id, channel_id)
            out["queued"].append(draft.run_id)
        except Exception as exc:
            logger.warning("overnight upload of run %s not queued: %s", draft.run_id, exc)
            out["failed"].append((draft.run_id, f"rendered, not queued: {str(exc)[:90]}"))
    return out


OVERNIGHT_LOOKBACK_HOURS = 48.0


def overnight_rendered(
    channel_id: str,
    *,
    root: str | None = None,
    hours: float = OVERNIGHT_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """The drafts overnight rendered in the last `hours`, newest first (#1140).

    `render_unattended` writes `review.by = "overnight"` on each one; nothing read it back, so
    the morning after there was no line saying what had been made while nobody watched.
    """
    if root is None:
        from core.batch_generation import _drafts_dir

        root = _drafts_dir(channel_id)
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    moment = now or datetime.now()
    out: list[dict[str, Any]] = []
    for name in names:
        try:
            with open(os.path.join(root, name, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        review = meta.get("review") if isinstance(meta, dict) else None
        if not isinstance(review, dict) or review.get("by") != "overnight":
            continue
        if review.get("decision") != "rendered" or not meta.get("run_id"):
            continue
        try:
            at = datetime.fromisoformat(str(review.get("at") or ""))
        except ValueError:
            continue
        if (moment - at).total_seconds() > hours * 3600:
            continue
        title = str(meta.get("title") or meta.get("variant") or meta.get("topic") or "")
        out.append({"run_id": int(meta["run_id"]), "title": title, "at": at})
    return sorted(out, key=lambda row: row["at"], reverse=True)


def overnight_rendered_lines(
    channel_id: str,
    *,
    root: str | None = None,
    hours: float = OVERNIGHT_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> list[str]:
    """`ops overnight-last`: what overnight rendered lately and where each one is now."""
    rows = overnight_rendered(channel_id, root=root, hours=hours, now=now)
    if not rows:
        lines = [f"Overnight - {channel_id}: nothing rendered in the last {hours:.0f} hours."]
        if unattended_limit(channel_id) <= 0:
            lines.append("  Overnight is render-free for this channel (overnight.renders is 0).")
        else:
            paused = shelf_pause(channel_id)
            if paused:
                lines.append(f"  Paused: {paused}")
        waiting = drafts_line(channel_id, root=root)
        if waiting:
            lines.append(f"  {waiting}")
        return lines
    shelf: dict[int, dict[str, Any]] = {}
    try:
        from core.stale_renders import shelf_rows

        shelf = {int(row["run_id"]): row for row in shelf_rows(channel_id)}
    except Exception as exc:
        logger.debug("overnight-last: shelf unreadable: %s", exc)
    lines = [f"Overnight - {channel_id}: rendered {len(rows)} in the last {hours:.0f} hours"]
    for row in rows:
        lines.append(f"  run {row['run_id']}  {row['title'][:70]}")
        where = shelf.get(row["run_id"])
        if where:
            lines.append(f"      {where['state']}")
            lines.append(f"      {where['command']}")
        else:
            lines.append("      not on the shelf: already public, or retired")
    return lines


def unattended_plan_lines(channel_id: str, *, root: str | None = None) -> list[str]:
    """`ops overnight-plan`: what tonight would render, and why the rest wait."""
    limit = unattended_limit(channel_id)
    eligible, skipped = unattended_candidates(channel_id, root=root)
    lines = [f"Overnight render plan - {channel_id}: up to {limit} a night"]
    paused = shelf_pause(channel_id) if limit > 0 else ""
    if limit <= 0:
        lines.append("  Overnight is render-free for this channel (overnight.renders is 0).")
    if paused:
        lines.append(f"  Paused: {paused}")
    take = 0 if paused else max(limit, 0)
    for draft in eligible[:take]:
        lines.append(f"  would render: run {draft.run_id}  {draft.title[:70]}")
    for draft in eligible[take:]:
        lines.append(f"  next in line: run {draft.run_id}  {draft.title[:70]}")
    if not eligible:
        lines.append("  No draft qualifies tonight.")
    reasons: dict[str, int] = {}
    for _draft, why in skipped:
        key = "past its window" if "past its window" in why else why
        if why.startswith("its game has started"):
            key = "its game has started"
        reasons[key] = reasons.get(key, 0) + 1
    if reasons:
        told = ", ".join(f"{n} {why}" for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]))
        lines.append(f"  Waiting for you ({len(skipped)}): {told}")
        lines.append(f"  Review them: py -m scripts.ops batch-review --channel {channel_id}")
    return lines
