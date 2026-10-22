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
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger
from core.spaced_queue import queue_spaced_uploads

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
    expired: list[int] = field(default_factory=list)  # #1219: "not current" - set aside


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


def _draft_min_words(draft: PendingDraft) -> int:
    try:
        from core.script_length import get_length_preset

        return int(get_length_preset(draft.length_choice).min_words)
    except Exception:
        return 0


def _rewrite_script(folder: str, script: str) -> None:
    path = os.path.join(folder, "draft.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    head, found, rest = text.partition(_SCRIPT_HEADING)
    if not found:
        return
    tail = rest.split("\n## ", 1)
    after = f"\n\n## {tail[1]}" if len(tail) > 1 else "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{head}{_SCRIPT_HEADING}\n\n{script.strip()}{after}")


def why_not_cut(script: str, claims: list[str], min_words: int) -> str:
    """Why `cut_unsupported` left `script` as it was - one reason, the first that applies.

    Runs 143 and 145 (2026-10-14, on copies): one cut would have left 143 under its 127-word
    floor, and 145's claim sat in the first sentence. "Opens the script, cannot be found, or too
    short" said neither.
    """
    from core.script_craft import CUT_FLOOR_SHARE, CUT_MAX, claim_sentences, script_sentences

    doomed = claim_sentences(script, claims)
    if not doomed:
        return "the flagged claims are not found in any sentence - edit draft.md or reject it"
    if len(doomed) > CUT_MAX:
        return f"they take {len(doomed)} sentences and at most {CUT_MAX} are cut - edit draft.md"
    first = (script_sentences(script) or [""])[0]
    if all(sentence == first for sentence in doomed):
        return "the claim is in the first sentence, which is never cut - edit draft.md"
    floor = int(min_words * CUT_FLOOR_SHARE)
    return f"the cut would leave it under {floor} words"


def _cut_flagged(draft: PendingDraft, blocking: list[str], print_fn: Callable[..., Any]) -> bool:
    """#1177 (operator: "cut it, tell me which"): cut the sentences that carry the draft's
    flagged claims, by the same rule overnight uses, and store the script and its check."""
    from core.claim_types import blocking_unsupported
    from core.script_craft import claim_sentences, cut_unsupported, script_check

    min_words = _draft_min_words(draft)
    new, cut = cut_unsupported(draft.script, blocking, min_words=min_words)
    if not cut:
        print_fn(f"    nothing was cut: {why_not_cut(draft.script, blocking, min_words)}")
        return False
    gone = {c for c in blocking if set(claim_sentences(draft.script, [c])) & set(cut)}
    ver = dict(draft.meta.get("claim_verification") or {})
    old = list(ver.get("unsupported") or [])
    types = ver.get("unsupported_types")
    if isinstance(types, list) and len(types) == len(old):
        ver["unsupported_types"] = [t for c, t in zip(old, types, strict=True) if c not in gone]
    ver["unsupported"] = [c for c in old if c not in gone]
    stored = draft.meta.get("script_clean")
    previous: dict[str, Any] = stored if isinstance(stored, dict) else {}
    check = script_check(
        script=new,
        title=str(draft.meta.get("title") or ""),
        idea=str(draft.meta.get("topic") or ""),
        unsupported=blocking_unsupported(ver),
        cut=[*(previous.get("cut") or []), *cut],
    )
    draft.meta["claim_verification"] = ver
    draft.meta["script_clean"] = check
    _rewrite_script(draft.folder, new)
    draft.script = new
    with open(os.path.join(draft.folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(draft.meta, f, indent=2, default=str)
    if draft.run_id:
        from core.run_features import merge_features

        merge_features(draft.run_id, {"claim_verification": ver, "script_clean": check})
    for sentence in cut:
        print_fn(f"    cut: {sentence}")
    return True


def _render_prompt(can_cut: bool) -> str:
    cut_offer = " / c = cut the flagged sentences" if can_cut else ""
    return f"  Render it? [y / n = reject / Enter = later / q = stop{cut_offer}]: "


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
_NEWS_DOMAINS = frozenset({"ufc", "mma", "nba", "nfl", "mlb", "nhl", "sports", "soccer"})
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
    from core.facts.event_dates import fixture_sides

    if fixture_sides(str(meta.get("topic") or "")):
        return _NEWS_WINDOW_DAYS  # #1219: run 137, "Cleveland Cavaliers at Orlando Magic", had 7
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
    if meta.get("own_idea"):  # #1159
        print_fn("    your own idea, written as angle 1")
        for line in typed_lines(str(meta.get("topic") or ""), draft.script):  # #1343
            print_fn(line)
    hook = meta.get("hook_score")
    verdict, reasons = authenticity_now(draft)
    print_fn(
        f"    hook {hook if hook is not None else 'n/a'} ({meta.get('hook_verdict') or 'n/a'})"
        f" - authenticity {verdict if meta.get('authenticity_verdict') else 'n/a'}"
        + (f" ({reasons})" if reasons else "")
        + f" - {len(draft.script.split())} words"
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
    drafts = review_order(pending_drafts(channel_id, root=root))  # wave 109: games first
    deadline = deadline_line(channel_id, root=root)
    if deadline:
        print_fn(f"  {deadline}")
    if not drafts:
        print_fn(
            "  No drafts waiting. Make some: py -m scripts.ops batch-drafts --channel", channel_id
        )
        return summary
    dead = [draft for draft in drafts if draft.decision != "accepted" and dead_reason(draft.meta)]
    if len(dead) > 1:
        # #1239: 16 of 22 waiting drafts were past their window, one "still current?" each.
        answer = ask(f"  Set aside the {len(dead)} drafts past their window? [Y/n]: ")
        if answer.strip().lower() in ("", "y", "yes"):
            for draft in dead:
                _write_review(
                    draft, decision="expired", by="operator", reason=dead_reason(draft.meta)
                )
                summary.expired.append(draft.run_id)
            print_fn(
                f"    Set aside {len(dead)} - nothing is deleted (batch-review --expired lists "
                "them)."
            )
            drafts = [draft for draft in drafts if draft not in dead]
            if not drafts:
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
            current = (
                ask(
                    f"  This is {age:.0f} days old - still current? "
                    "[y / n = set it aside / Enter = later]: "
                )
                .strip()
                .lower()
            )
            if current == "n":
                # #1219: "no" left it for later, and it was back the next morning.
                _write_review(
                    draft, decision="expired", by="operator", reason=f"{age:.0f} days old"
                )
                print_fn("    Set aside - nothing is deleted (batch-review --expired lists it).")
                summary.expired.append(draft.run_id)
                continue
            if current != "y":
                print_fn("    Left for later.")
                summary.later.append(draft.run_id)
                continue
        can_cut = bool(blocking)
        answer = ask(_render_prompt(can_cut)).strip().lower()
        while answer == "c" and can_cut:  # #1177
            if _cut_flagged(draft, blocking, print_fn):
                blocking = _blocking_claims(draft)
                from core.script_craft import script_check_line

                print_fn(f"    {script_check_line(draft.meta.get('script_clean'))}")
            can_cut = False  # one cut takes every sentence it can; a second finds the same
            answer = ask(_render_prompt(can_cut)).strip().lower()
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

    plan = plan_review_slots(channel_id, items)
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


def plan_review_slots(channel_id: str, items: list[tuple[int, str]]) -> list:
    """#1298: the slots for what this pass rendered, by the shelf's rules - a game before its
    kickoff (or as it uploads, #1295), news inside its window, the free noon/10 PM. The
    `planned_post_time` this used sent run 165, the Chargers preview, out three days after its
    game and run 164's two-day news on Friday. A cadence cap still holds (decision 65)."""
    from core import spaced_queue
    from core.cadence import cadence_status

    run_ids = [int(run_id) for run_id, _title in items]
    planned = {
        int(slot.run_id): slot for slot in spaced_queue.shelf_schedule(channel_id, run_ids=run_ids)
    }
    out = [
        planned.get(int(run_id))
        or spaced_queue.SpacedSlot(
            run_id=int(run_id),
            title=str(title),
            skipped="not on the shelf - py -m scripts.ops shelf says why",
        )
        for run_id, title in items
    ]
    try:
        status = cadence_status(channel_id)
        if status.capped:
            room = max(0, status.cap - status.total)
            for slot in [s for s in out if s.publish_at is not None][room:]:
                slot.publish_at = None
                slot.skipped = f"cadence cap {status.cap}/{status.window_days}d reached"
    except Exception as exc:
        logger.debug("batch-review: cadence unread: %s", exc)
    return out


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
    stale = sum(1 for _draft, why in skipped if _is_dead(why))
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
    try:  # #1272: overnight writes nothing new at the cap - say how many to decide
        from core.overnight import _DRAFT_WAIT_CAP

        waiting = len(pending_drafts(channel_id, root=root))
        if waiting >= _DRAFT_WAIT_CAP:
            parts.append(f"overnight drafts again once {waiting - _DRAFT_WAIT_CAP + 1} are decided")
    except Exception as exc:
        logger.debug("draft cap line skipped: %s", exc)
    return (
        f"Drafts waiting: {total} - {', '.join(parts)}: "
        f"py -m scripts.ops batch-review --channel {channel_id}"
    )


def _event_ahead(meta: dict[str, Any], now: datetime) -> datetime | None:
    raw = str(meta.get("event_at") or "")
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when if when > now else None


def review_order(drafts: list[PendingDraft], *, now: datetime | None = None) -> list[PendingDraft]:
    """Wave 109: a preview whose game is ahead first, soonest kickoff first; the rest as they
    came. Run 165, the Chargers at Chiefs preview, sat behind a day-old Pistons draft."""
    moment = now or datetime.now(timezone.utc)
    games = [d for d in drafts if _event_ahead(d.meta, moment) is not None]
    games.sort(key=lambda d: _event_ahead(d.meta, moment) or moment)
    first = {id(d) for d in games}
    return games + [d for d in drafts if id(d) not in first]


def _zone_clock(when: datetime, channel_id: str, *, day: bool = False) -> str:
    """ "10:30 AM EDT" (or "Sun Oct 18 4:25 PM EDT") in the channel's zone, as the slots are."""
    try:
        from zoneinfo import ZoneInfo

        from analytics.post_timing import _load_static_post_schedule

        local = when.astimezone(ZoneInfo(_load_static_post_schedule(channel_id).timezone))
    except Exception:
        local = when.astimezone(timezone.utc)
    hour = local.strftime("%I").lstrip("0") or "12"
    clock = f"{hour}:{local:%M %p} {local.tzname() or ''}".rstrip()
    return f"{local:%a %b} {local.day} {clock}" if day else clock


def deadline_line(channel_id: str, *, root: str | None = None, now: datetime | None = None) -> str:
    """Wave 109: the waiting preview with the soonest kickoff, and when it must be decided - the
    last free slot before kickoff, less the upload lead (`spaced_queue`). "" when no game waits.
    On 2026-10-18 nothing said the Chargers preview had to be reviewed that morning."""
    moment = now or datetime.now(timezone.utc)
    games = [
        (event, draft)
        for draft in pending_drafts(channel_id, root=root)
        if not draft.decision and (event := _event_ahead(draft.meta, moment)) is not None
    ]
    if not games:
        return ""
    event, draft = min(games, key=lambda pair: pair[0])
    kickoff = _zone_clock(event, channel_id, day=True)
    try:
        from core.spaced_queue import _EVENING, _FIRST_LEAD, _taken_slots, free_slots

        taken = _taken_slots(channel_id)
        slots = [
            *free_slots(channel_id, 4, now=moment, taken=taken),
            *free_slots(channel_id, 2, now=moment, hours=_EVENING, taken=taken),
        ]
    except Exception as exc:
        logger.debug("deadline slots unread: %s", exc)
        return f"Decide first: {draft.title} - kicks off {kickoff}"
    before = sorted(slot for slot in slots if slot < event)
    if not before:
        return (
            f"Decide first: {draft.title} - kicks off {kickoff}, and no upload slot is left "
            f"before kickoff. To post it anyway: review it, then py -m scripts.requeue_upload "
            f"--run-id {draft.run_id} --queue --private, then go-public with its video id"
        )
    slot = before[-1]
    # #1533 (wave 118): it said "review it by 8:30 PM EDT for the 10:00 PM EDT slot" for Fri
    # 10-23 - read on a Tuesday evening, that was tonight.
    return (
        f"Decide first: {draft.title} - kicks off {kickoff}; review it by "
        f"{_zone_clock(slot - _FIRST_LEAD, channel_id, day=True)} for its "
        f"{_zone_clock(slot, channel_id)} slot"
    )


def expire_enabled() -> bool:
    """`OVERNIGHT_EXPIRE_DRAFTS` (default on; the suite turns it off)."""
    raw = os.getenv("OVERNIGHT_EXPIRE_DRAFTS", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def expire_old_drafts(
    channel_id: str, *, root: str | None = None, apply: bool = True
) -> list[PendingDraft]:
    """Set aside each waiting draft past twice its window (#1168; operator, 2026-10-13: "set
    aside automatically"). Marked `expired` in its own record - nothing is deleted - so it
    leaves the waiting count. 6 of 32 waiting drafts were past their window that day."""
    old: list[PendingDraft] = []
    for draft in pending_drafts(channel_id, root=root):
        if draft.decision:
            continue
        age = draft_age_days(draft.meta)
        window = freshness_window_days(draft.meta)
        game = game_block_reason(draft.meta)
        if game.startswith("its game has started"):
            reason = game  # #1173: a preview after its game can never render
        elif age is None or age <= 2 * window:
            continue
        else:
            reason = f"{age:.0f} days old, twice its {window:.0f}-day window"
        old.append(draft)
        if apply:
            _write_review(draft, decision="expired", by="overnight", reason=reason)
    return old


def expired_lines(channel_id: str, *, root: str | None = None) -> list[str]:
    """`ops batch-review --expired`: what overnight set aside."""
    if root is None:
        from core.batch_generation import _drafts_dir

        root = _drafts_dir(channel_id)
    rows: list[str] = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for name in names:
        try:
            with open(os.path.join(root, name, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        review = meta.get("review") if isinstance(meta, dict) else None
        if not isinstance(review, dict) or review.get("decision") != "expired":
            continue
        title = str(meta.get("title") or meta.get("variant") or meta.get("topic") or "")
        rows.append(f"  run {meta.get('run_id')}  {title[:70]}  ({review.get('reason', '')})")
    head = f"Set aside - {channel_id}: {len(rows)} draft(s) past twice their window"
    return [head + (" (nothing was deleted)" if rows else ""), *rows]


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
    """How many finished videos are not public and can still go out - the rows `ops shelf`
    lists, less a render past its window (#1231)."""
    try:
        from core.stale_renders import shelf_rows

        return sum(1 for row in shelf_rows(channel_id) if not row.get("stale"))
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


def draft_meta_for_run(channel_id: str, run_id: int, *, root: str | None = None) -> dict[str, Any]:
    """The `meta.json` of the draft that became `run_id`, or {} (crosspost reads its game's
    start, 2026-10-17)."""
    if root is None:
        from core.batch_generation import _drafts_dir

        root = _drafts_dir(channel_id)
    try:
        names = sorted(os.listdir(root), reverse=True)  # newest first
    except OSError:
        return {}
    for name in names:
        try:
            with open(os.path.join(root, name, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and str(meta.get("run_id") or "") == str(run_id):
            return meta
    return {}


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


_CHECK_WORDS = {
    "original_insight": "no take found",
    "substance": "too few facts",
    "variation": "too like a recent video",
}


def authenticity_reasons(meta: dict[str, Any]) -> str:
    """#1213: which authenticity checks failed, in words; "" for a draft from before."""
    failed = meta.get("authenticity_failed") or []
    return ", ".join(_CHECK_WORDS.get(str(name), str(name)) for name in failed)


def authenticity_now(draft: PendingDraft) -> tuple[str, str]:
    """(verdict, reasons) - the stored verdict, except a draft held only for "no take found" is
    read again with today's take detector. Wave 109: overnight's 3 drafts of 2026-10-18 all
    waited on a verdict written before the detector knew "Watch who the UFC pairs him with next".
    Nothing in the draft's own record is rewritten."""
    meta = draft.meta
    verdict = str(meta.get("authenticity_verdict") or "ok").strip().lower()
    failed = [str(name) for name in meta.get("authenticity_failed") or []]
    if verdict != "ok" and failed == ["original_insight"]:
        try:
            from core.authenticity import has_insight

            if has_insight(draft.script):
                return "ok", ""
        except Exception as exc:
            logger.debug("take re-read skipped for run %s: %s", draft.run_id, exc)
    return verdict, authenticity_reasons(meta)


def arc_counter_reason(meta: dict[str, Any]) -> str:
    """#1211: a draft written from an arc seed that still carried the arc's counter ("Shavkat
    Rakhmonov week 4", before #1205) - its script reads the counter as the subject's. "" else."""
    from core.topic_graph import _WEEK_RE

    topic = str(meta.get("topic") or "")
    found = _WEEK_RE.search(topic)
    if not found:
        return ""
    try:
        from core.run_features import load_features

        offered = (load_features(int(meta.get("run_id") or 0)).get("best_bet") or {}).get(
            "offered"
        ) or []
    except Exception:
        offered = []
    if any(o.get("source") == "arc" and o.get("topic") == topic for o in offered):
        return f'drafted from the arc counter "{found.group(0)}" (#1205)'
    return ""


_SECOND_READ = (
    "You read a short video's title and its first sentence, before it is rendered with nobody "
    'watching. Answer JSON {"ok": false, "why": "<ten words>"} only when the first sentence is '
    "cut off or garbled, or the title and the first sentence are about different stories. A "
    "first sentence that opens on one part of the title's story is fine - it need not name "
    "everyone the title names, and a team may be its city or its nickname. Otherwise answer "
    '{"ok": true}.'
)


def second_read(title: str, script: str, *, call: Callable[[str, str], Any] | None = None) -> str:
    """#1341 (wave 119): a cheap second read of an unattended render's title and first sentence -
    "" when it reads fine, can't be read, or in the suite; else why (a "no" holds the render
    for a person, and the next eligible draft takes its place). One cheap-tier call a draft."""
    from apis.topic_tokens import split_sentences

    first = (split_sentences(script or "") or [""])[0]
    if call is None:
        if os.environ.get("CONTENT_SUITE") == "1":
            return ""

        def call(system: str, user: str) -> Any:
            from core.llm_router import complete_json

            return complete_json(user, system=system, tier="cheap", temperature=0.0, max_tokens=120)

    try:
        payload = call(_SECOND_READ, f"TITLE: {title}\nFIRST SENTENCE: {first}")
    except Exception as exc:
        logger.debug("second read skipped: %s", exc)
        return ""
    if isinstance(payload, dict) and payload.get("ok") is False:
        return str(payload.get("why") or "the title and first sentence disagree")[:120]
    return ""


def typed_lines(idea: str, script: str) -> list[str]:
    """#1343 and #1342 (wave 119): your typed idea beside the first two sentences it became, and
    how many of your words they kept - the review said only "your own idea, written as angle 1"."""
    from apis.topic_tokens import content_tokens, split_sentences

    first_two = " ".join(split_sentences(script or "")[:2])
    yours = list(dict.fromkeys(content_tokens(idea or "")))
    kept = set(content_tokens(first_two))
    hits = sum(1 for word in yours if word in kept)
    return [
        f"    you typed: {idea.strip()}",
        f"    it wrote:  {first_two}",
        f"    {hits} of your {len(yours)} words are in its first two sentences",
    ]


def follow_up_since(draft: PendingDraft) -> str:
    """#1536 (wave 119, the operator: hold for review): a follow-up that says "since" waits for a
    person. Run 179 said "Since then, Detroit clinched the No. 1 seed" from last season's playoff
    page - the claim check passed it, as the source supports it; it does not check when."""
    topic = str(draft.meta.get("topic") or "")
    if not topic.startswith('Follow-up to "') or not re.search(
        r"\bsince\b", draft.script or "", re.I
    ):
        return ""
    return 'a follow-up says "since" - check its source is newer than the original video'


def unattended_block_reason(draft: PendingDraft, *, now: datetime | None = None) -> str:
    """Why a draft must wait for a person, or "" when it may render unattended."""
    meta = draft.meta
    if draft.decision:
        return f"already {draft.decision}"
    dead = dead_reason(meta, now=now)
    if dead:  # #1219: checked first, so the count of drafts past their window is true
        return dead
    if _blocking_claims(draft):
        return "a claim is not supported"
    if follow_up_since(draft):
        return follow_up_since(draft)
    verdict, why = authenticity_now(draft)
    if verdict != "ok":
        return f"authenticity check says {verdict}" + (f" ({why})" if why else "")
    if meta.get("fact_conflicts"):
        return "its facts conflict"
    if meta.get("ungrounded_entities"):
        return "it names something the facts do not"
    if str(meta.get("hook_verdict") or "").strip().lower() == "weak":
        return "weak hook"
    check = meta.get("script_clean")
    if isinstance(check, dict) and check.get("ok") is False:
        # #1535 (wave 118, the operator: warn only): "hard to say" alone held 9 of 58 drafts;
        # the render goes up unlisted and is heard at review anyway (decision 60).
        reasons = [r for r in check.get("why") or ["not clean"] if "hard to say" not in str(r)]
        if reasons:
            return f"script check: {reasons[0]}"  # #1143
    if meta.get("title_warnings"):
        return "its title says something the facts do not"  # #1150
    game = game_block_reason(meta, now=now)
    if game:
        return game
    arc = arc_counter_reason(meta)
    if arc:
        return arc
    from core.title_generator import broken_place_name, title_label

    broken = broken_place_name(draft.title)
    if broken:  # #1211: a title written before #1181's check
        return f'its title breaks a name ("{broken}")'

    label = title_label(draft.title)
    if label:
        # Run 116's draft was titled "Contrarian: Spain's World Cup win ..." - the angle's
        # label, pasted in front of the title. A person fixes that; overnight must not ship it.
        return f'its title starts with a label ("{label}")'
    from core.title_generator import title_cut_off

    if title_cut_off(draft.title):  # #1225: run 158 ended "... positive outlook\u2026"
        return "its title is cut off"
    from core.authenticity import ad_limit_reason

    return ad_limit_reason(draft.title, draft.script)  # #1319: draft 166, "Hot Dads & Horny Art"


def dead_reason(meta: dict[str, Any], *, now: datetime | None = None) -> str:
    """#1219: why a draft can no longer be used - its game has started, or it is past its
    window - else "". 2026-10-16: 8 of 21 waiting drafts were past their window and the morning
    said 1, because the window was checked after the claims, the labels and the title."""
    game = game_block_reason(meta, now=now)
    if game.startswith("its game has started"):
        return game
    age = draft_age_days(meta)
    if age is not None and age > freshness_window_days(meta):
        return f"{age:.0f} days old, past its window"
    return ""


def _is_dead(why: str) -> bool:
    return "past its window" in why or why.startswith("its game has started")


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


def coming_day_empty(channel_id: str, *, now: datetime | None = None, hours: float = 24.0) -> bool:
    """#1428: nothing is scheduled to go public in the next `hours` - the upload queue's jobs
    and the publish log's future slots (`upload_queue.list_queue_entries`). A failed read is
    not empty (no extra render on a guess)."""
    moment = now or datetime.now(timezone.utc)
    try:
        from analytics.upload_queue import list_queue_entries

        entries = list_queue_entries(channel_id)
    except Exception as exc:
        logger.debug("empty-day check skipped: %s", exc)
        return False
    horizon = moment + timedelta(hours=hours)
    return not any(moment < e.publish_at <= horizon for e in entries)


def overnight_render_limit(channel_id: str, *, now: datetime | None = None) -> tuple[int, str]:
    """(how many drafts overnight renders, why one more). #1428 (wave 114, the operator: it
    renders and waits): a channel that renders overnight renders one more when nothing is
    scheduled for the next 24 hours; it goes up unlisted and waits like the rest (decision 60)."""
    limit = unattended_limit(channel_id)
    if limit > 0 and coming_day_empty(channel_id, now=now):
        return limit + 1, "nothing is scheduled for the next 24 hours - one more render"
    return limit, ""


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
    tried = 0
    for draft in eligible:
        if tried >= limit:
            break
        paused = shelf_pause(channel_id, waiting=on_shelf)
        if paused:
            out["paused"] = paused
            break
        doubt = second_read(draft.title, draft.script)  # #1341: the next draft takes its place
        if doubt:
            out["waiting"].append((draft.run_id, f"second read: {doubt}"))
            continue
        tried += 1
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


def _run_record(run_id: int) -> Any:
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository().get(int(run_id))


def _publish_row(run_id: int, channel_id: str) -> Any:
    from storage.repositories.publish_log import get_publish_log_repository

    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id):
        if getattr(row, "content_run_id", None) == int(run_id):
            return row
    return None


def video_lines(run_id: int, channel_id: str, *, tty: bool = False) -> list[str]:
    """#1192: where a rendered video is - its file, its YouTube link (Studio's page while it is
    not public), and TikTok/Instagram. [] when nothing can be read."""
    out: list[str] = []
    try:
        run = _run_record(run_id)
        path = str(getattr(run, "mp4_path", "") or "") if run is not None else ""
        if path:
            from config.paths import ROOT_DIR

            # The record keeps it relative to the repo; the operator needs where it is.
            full = path if os.path.isabs(path) else os.path.normpath(os.path.join(ROOT_DIR, path))
            out.append(f"file: {full}" + ("" if os.path.isfile(full) else "  (no longer on disk)"))
        row = _publish_row(run_id, channel_id)
        video = str(getattr(row, "youtube_video_id", "") or "") if row is not None else ""
        if video:
            privacy = str(getattr(row, "privacy_status", "") or "").strip().lower()
            if privacy == "public":
                out.append(f"YouTube: https://youtu.be/{video} (public)")
            else:
                out.append(
                    f"YouTube: https://studio.youtube.com/video/{video}/edit "
                    f"({privacy or 'not public'} - open it signed in)"
                )
        from publishing.crosspost import run_state_line

        state = run_state_line(channel_id, run_id)
        if state:
            out.append(state)
    except Exception as exc:
        logger.debug("video lines for run %s unreadable: %s", run_id, exc)
    if tty and out:
        from core.ui import linkify

        out = [linkify(line, tty=True) for line in out]
    return out


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
        return [*lines, *_deadline_lines(channel_id, root), *_timing_lines()]
    shelf: dict[int, dict[str, Any]] = {}
    try:
        from core.stale_renders import shelf_rows

        shelf = {int(row["run_id"]): row for row in shelf_rows(channel_id)}
    except Exception as exc:
        logger.debug("overnight-last: shelf unreadable: %s", exc)
    lines = [f"Overnight - {channel_id}: rendered {len(rows)} in the last {hours:.0f} hours"]
    for row in rows:
        lines.append(f"  run {row['run_id']}  {row['title'][:70]}")
        try:
            import sys

            linked = bool(sys.stdout) and sys.stdout.isatty()
        except Exception:
            linked = False
        lines.extend(
            f"      {line}" for line in video_lines(row["run_id"], channel_id, tty=linked)
        )  # #1192
        where = shelf.get(row["run_id"])
        if where:
            lines.append(f"      {where['state']}")
            lines.append(f"      {where['command']}")
        else:
            from core.stale_renders import gone_reason

            gone = gone_reason(row["run_id"], channel_id)  # #1166
            lines.append(f"      {gone or 'not on the shelf: already public, or retired'}")
    return [*lines, *_deadline_lines(channel_id, root), *_timing_lines()]


def _deadline_lines(channel_id: str, root: str | None) -> list[str]:
    try:
        line = deadline_line(channel_id, root=root)
    except Exception as exc:
        logger.debug("deadline line skipped: %s", exc)
        return []
    return [f"  {line}"] if line else []


def _timing_lines() -> list[str]:
    """#1167: the task ran late, or not at all; #1216: it stopped before it finished."""
    from core import nightly_task

    lines: list[str] = []
    for read in (nightly_task.overnight_timing_line, nightly_task.overnight_stop_line):
        try:
            line = read()
        except Exception as exc:
            logger.debug("overnight timing unreadable: %s", exc)
            line = ""
        if line:
            lines.append(f"  {line}")
    return lines


def drafts_made_since(
    channel_id: str,
    since: datetime,
    *,
    until: datetime | None = None,
    root: str | None = None,
) -> int:
    """#1216: drafts written since ``since`` (local time) - how far a stopped run got; #1223:
    before ``until``, when the run's end is known."""
    if root is None:
        from core.batch_generation import _drafts_dir

        root = _drafts_dir(channel_id)
    try:
        names = os.listdir(root)
    except OSError:
        return 0
    made = 0
    for name in names:
        try:
            with open(os.path.join(root, name, "meta.json"), encoding="utf-8") as f:
                when = datetime.fromisoformat(str(json.load(f).get("created_at")))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if when.tzinfo:
            when = when.astimezone().replace(tzinfo=None)
        if when >= since and (until is None or when <= until):
            made += 1
    return made


def unattended_plan_lines(channel_id: str, *, root: str | None = None) -> list[str]:
    """`ops overnight-plan`: what tonight would render, and why the rest wait."""
    limit = unattended_limit(channel_id)
    eligible, skipped = unattended_candidates(channel_id, root=root)
    lines = [f"Overnight render plan - {channel_id}: up to {limit} a night"]
    paused = shelf_pause(channel_id) if limit > 0 else ""
    old = expire_old_drafts(channel_id, root=root, apply=False) if expire_enabled() else []
    if old:  # #1168
        plural = len(old) != 1
        lines.append(
            f"  Tonight sets aside {len(old)} draft{'s' if plural else ''} past twice "
            f"{'their' if plural else 'its'} window (py -m scripts.ops batch-review --expired)"
        )
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
