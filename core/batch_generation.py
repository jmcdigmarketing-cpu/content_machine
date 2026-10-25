"""Batch generation — N ideas → N draft scripts in one unattended pass.

Roadmap "Efficiency & integrations": feeds A/B and volume-with-variation
without babysitting the interactive flow. Strictly headless (no input()) and
render-free: each topic runs discovery → best variant → recommended length →
script/title/description, then saves a review-ready draft folder under
output/<channel>/drafts/<timestamp>-<slug>/ with the same quality checks the
interactive flow shows (hook score, authenticity verdict, grounding flags).

Nothing is rendered or published — drafts are cheap (LLM + signals only), so
an unattended batch can't burn TTS credits or trip the cadence guardrail.

    py -m core.batch_generation --channel tapin --count 3
    py -m core.batch_generation --channel moneywise "Fed rate cut" "CPI print"
    py -m core.batch_generation --file ideas.txt        # one topic per line
    py -m scripts.ops batch-drafts --channel tapin --count 3

Topic sources, in priority order: explicit CLI topics → --file lines →
best-bet recommendations for the channel.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.batch_generation")


@dataclass
class DraftOutcome:
    topic: str
    ok: bool = False
    title: str = ""
    variant: str = ""
    score: float = 0.0
    hook_score: int | None = None
    hook_verdict: str = ""
    authenticity_verdict: str = ""
    authenticity_failed: list[str] = field(default_factory=list)  # #1213
    experiment_arm: str = ""
    ungrounded: list[str] = field(default_factory=list)
    unsupported_claims: int = 0
    fact_conflicts: int = 0
    run_id: int | None = None
    path: str = ""
    error: str = ""
    seconds: float = 0.0
    reused: bool = False  # #760 - an unreviewed draft for this topic already existed
    # #1159: what `ops script-check --idea` prints - the script and its finished-script check.
    script: str = ""
    script_clean: dict | None = None


@contextmanager
def hook_arm_env(arm: tuple[str, str, str] | None) -> Iterator[None]:
    """#1502: the "off" arm turns the hook rewrite off for this one draft (HOOK_REGEN_ENABLED,
    read by `hook_score.hook_regen_enabled`), and puts the setting back after."""
    if not arm or arm[1] != "off":
        yield
        return
    before = os.environ.get("HOOK_REGEN_ENABLED")
    os.environ["HOOK_REGEN_ENABLED"] = "false"
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("HOOK_REGEN_ENABLED", None)
        else:
            os.environ["HOOK_REGEN_ENABLED"] = before


def hook_options(script: str, passes: Any, *, limit: int = 3) -> list[str]:
    """#1503: the script's first sentence, then up to two openers the hook rewrite wrote that
    failed only on "no better than the current opener" (or were kept) - [] without any."""
    import ast

    from core.hook_score import extract_hook

    current = extract_hook(script or "")
    rows: list[Any] = []
    for entry in passes if isinstance(passes, list) else []:
        if isinstance(entry, dict) and entry.get("name") == "improve_hook":
            raw = entry.get("variants")
            if isinstance(raw, str):
                try:
                    raw = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    raw = []
            rows.extend(raw if isinstance(raw, list) else [])
    options = [current] if current else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        refused = str(row.get("refused") or "")
        opener = str(row.get("opener") or "").strip()
        if opener and opener not in options and (not refused or refused.startswith("no better")):
            options.append(opener)
        if len(options) >= limit:
            break
    return options if len(options) > 1 else []


def _slug(topic: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "draft"


def _drafts_dir(channel_id: str) -> str:
    from core.output_paths import channel_output_root

    path = os.path.join(channel_output_root(channel_id), "drafts")
    os.makedirs(path, exist_ok=True)
    return path


_REUSE_DAYS = 3


def unreviewed_draft(channel_id: str, topic: str, *, max_age_days: float = _REUSE_DAYS):
    """(folder, meta) of a recent draft for this topic nobody has reviewed, else None.

    A second batch the same week used to pay for discovery and the script again for a
    topic already waiting in `ops batch-review` (#760).
    """
    key = " ".join((topic or "").lower().split())
    try:
        root = _drafts_dir(channel_id)
        names = sorted(os.listdir(root), reverse=True)
    except OSError:
        return None
    for name in names:
        folder = os.path.join(root, name)
        try:
            with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or meta.get("review"):
            continue
        if " ".join(str(meta.get("topic") or "").lower().split()) != key:
            continue
        try:
            age = datetime.now() - datetime.fromisoformat(str(meta.get("created_at")))
        except (TypeError, ValueError):
            continue
        if age.total_seconds() <= max_age_days * 86400:
            return folder, meta
    return None


def collect_topics(
    channel_id: str,
    topics: list[str] | None = None,
    file: str | None = None,
    count: int = 3,
    *,
    picks: dict[str, dict] | None = None,
) -> list[str]:
    """Explicit topics → file lines → best bets, capped at `count` for implicit sources.

    ``picks`` (optional) is filled with each best-bet topic's `pick_record` (#913) so the
    run records that the batch took it and at which rank; explicit and file topics are
    not picks.
    """
    if topics:
        return [t.strip() for t in topics if t.strip()]
    if file:
        with open(file, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        return lines
    try:
        from core.best_bet import get_idea_menu, pick_record

        # Decision 66: an idea, then a preview, in turn.
        ideas, previews = get_idea_menu(channel_id)
        bets: list[Any] = []
        for pair in zip(ideas, previews, strict=False):
            bets.extend(pair)
        longer = ideas if len(ideas) > len(previews) else previews
        bets.extend(longer[min(len(ideas), len(previews)) :])
        candidates = list(bets)
        chosen = candidates[:count]
        held = _swap_holdouts(chosen, candidates)
        if picks is not None:
            for rank, bet in enumerate(chosen, 1):
                if bet.topic in held:  # #83: recorded at its rank in the top ten it came from
                    record = pick_record(candidates, candidates.index(bet) + 1, by="batch")
                    record["holdout"] = True
                else:
                    record = pick_record(chosen, rank, by="batch")
                picks[bet.topic] = record
        return _with_follow_up(channel_id, [b.topic for b in chosen], held, picks)
    except Exception as exc:
        logger.warning("No topics given and best bets unavailable: %s", exc)
        return []


FOLLOW_UP_DAYS = 14  # a follow-up on old news is not one


def follow_up_topic(channel_id: str, *, now: datetime | None = None) -> str:
    """#1452 (wave 117, the operator: in one of its draft slots): a follow-up on a recent video
    that brought 2+ subscribers, "" when there is none or it was drafted already. On 10-20 the
    morning named run 162 (the Pistons bench, 2 subscribers) and nothing drafted one."""
    try:
        from analytics.growth import _rows, subscriber_flags
        from storage.repositories.content_runs import get_content_run_repository

        moment = now or datetime.now(timezone.utc)
        for row in subscriber_flags(_rows(channel_id)):
            published = row.get("published")
            if not published or (moment - published).days > FOLLOW_UP_DAYS:
                continue
            run = (
                get_content_run_repository().get(int(row["run_id"])) if row.get("run_id") else None
            )
            title = str(getattr(run, "title", "") or row.get("title") or "").strip()
            if not title or _followed_up(channel_id, title):  # once per video, in any wording
                continue
            # #1536 (wave 118 drafted it, wave 119): the original's date - "what has happened
            # since" drew last season's "clinched the No. 1 seed" into run 179.
            day = f"{published:%b} {published.day}"
            return f'Follow-up to "{title}" ({day}): what has happened since {day}'
    except Exception as exc:
        logger.debug("follow-up topic skipped: %s", exc)
    return ""


def _followed_up(channel_id: str, title: str) -> bool:
    """A follow-up on this title was drafted already - wave 118's words or wave 119's."""
    from core.channel_context import recent_input_topics

    prefix = f'follow-up to "{title}"'.lower()
    if any(
        str(t).strip().lower().startswith(prefix) for t in recent_input_topics(channel_id, limit=60)
    ):
        return True
    return unreviewed_draft(channel_id, f'Follow-up to "{title}"') is not None


def _with_follow_up(
    channel_id: str, topics: list[str], held: set[str], picks: dict[str, dict] | None
) -> list[str]:
    """The night's last slot that is not a holdout goes to the follow-up; its pick record is
    dropped - a follow-up is not a best bet. Two slots or more only."""
    if len(topics) < 2:
        return topics
    follow = follow_up_topic(channel_id)
    slots = [i for i, topic in enumerate(topics) if topic not in held]
    if not follow or not slots or follow in topics:
        return topics
    i = slots[-1]
    if picks is not None:
        picks.pop(topics[i], None)
    logger.info("overnight: %s takes the slot of %s", follow, topics[i])
    return [*topics[:i], follow, *topics[i + 1 :]]


def _swap_holdouts(chosen: list, candidates: list) -> set[str]:
    """#83: the night's holdout slots each take another of the top ten; their topics."""
    try:
        from core.predictions.holdouts import holdout_choice, next_slots

        slots = next_slots(len(chosen))
    except Exception as exc:
        logger.debug("holdouts skipped: %s", exc)
        return set()
    held: set[str] = set()
    day = datetime.now().strftime("%Y-%m-%d")
    for index, is_holdout in enumerate(slots):
        if not is_holdout:
            continue
        other = holdout_choice(candidates, {b.topic for b in chosen}, seed=f"{day}:{index}")
        if other is not None:
            chosen[index] = other
            held.add(other.topic)
    return held


def pick_facts(best_bet: dict | None) -> list[str]:
    """The lines a series pick is written from (#991), or []."""
    return [str(f) for f in ((best_bet or {}).get("facts") or []) if str(f).strip()]


def series_drafted(channel_id: str, topic: str) -> bool:
    """This week's series topic is already a draft or a run (#991): it is made once a week."""
    try:
        from core.channel_context import recent_input_topics

        key = topic.strip().lower()
        if any(str(t).strip().lower() == key for t in recent_input_topics(channel_id, limit=60)):
            return True
        return unreviewed_draft(channel_id, topic) is not None
    except Exception as exc:
        logger.debug("series lookup skipped: %s", exc)
        return False


def _length_choice(channel_id: str, topic: str) -> str:
    try:
        from core.length_recommender import get_recommended_length

        return get_recommended_length(channel_id, topic).length_choice
    except Exception:
        return "2"


def authenticity_fields(report: Any) -> dict[str, Any]:
    """#1213: the verdict and the checks that failed it, for the draft record."""
    return {
        "authenticity_verdict": str(report.verdict),
        "authenticity_failed": [
            c.name for c in (getattr(report, "checks", None) or []) if not c.passed
        ],
    }


def generate_draft(
    topic: str,
    channel_id: str,
    *,
    key_facts: list[str] | None = None,
    best_bet: dict | None = None,
    own_idea: bool = False,
) -> DraftOutcome:
    """One headless draft: discovery → best variant → script → saved folder.

    ``key_facts`` (optional) are shared operator ground truth applied to this
    topic — same ``run_pipeline(key_facts=)`` path as ``auto_generate --facts-file``.
    ``best_bet`` is the topic's `pick_record` when the batch took it from the best bets.

    ``own_idea`` (#1159): `topic` is an idea the operator typed. It is written the way angle
    1 writes it in `main.py` - `idea_angle`'s wording, index -1, the idea as the brief, no
    generated angle and no experiment directive. `ops script-check --idea` had passed index
    0, the first generated angle: runs 140-142 were reported as the operator's ideas and were
    written from angles a model made up.
    """
    from core.pipeline import run_discovery, run_pipeline

    out = DraftOutcome(topic=topic)
    started = time.time()

    key_facts = [*pick_facts(best_bet), *(key_facts or [])] or None  # #991: a series pick's
    # #1151 / #1169: a schedule pick knows when its game is; ahead of it, the angles and the
    # script are written as a preview.
    event_at = _game_start(topic, best_bet) or _named_event_start(topic)
    from core.facts.event_dates import PREVIEW_MIN_LEAD_HOURS, game_started, starts_within

    upcoming = bool(event_at) and game_started(event_at) is False
    if upcoming and starts_within(event_at, PREVIEW_MIN_LEAD_HOURS):
        # #1577: run 193 was drafted 31 minutes before its kickoff.
        out.error = (
            f"its game starts in under {PREVIEW_MIN_LEAD_HOURS:.0f} hours - too close to draft, "
            "render and decide (#1577)"
        )
        return out
    # #1301: the brief carries the call the preview was offered with.
    preview = draft_brief(topic, best_bet) if upcoming else ""

    if own_idea:
        discovery = run_discovery(topic, channel_id=channel_id, brief=topic)
    elif preview:
        discovery = run_discovery(topic, channel_id=channel_id, brief=preview)
    else:
        discovery = run_discovery(topic, channel_id=channel_id)
    experiment: tuple[str, str, str] | None = None
    if own_idea:
        from apis.topic_variants import idea_angle

        variant_index = -1
        best_topic = idea_angle(topic, channel_id) or topic
        best_score, best_signals = 0.0, discovery.base_signals
    else:
        if not discovery.evaluated:
            out.error = "discovery returned no scored variants"
            return out
        # The one ranking rule — this used to `max` on the displayed score alone and
        # so picked arbitrarily whenever the composites tied, which is every run.
        from core.pipeline import best_variant_index

        variant_index = best_variant_index(
            discovery.evaluated, discovery.raw_scores, discovery.angle_scores
        )
        best_topic, best_score, best_signals = discovery.evaluated[variant_index]

        # Active script-lever A/B experiment: the least-used arm's directive
        # shapes this draft (thumbnail levers apply at render, not here).
        try:
            from core.experiments import next_arm

            experiment = next_arm(channel_id, kind="script")
        except Exception as exc:
            logger.debug("next_arm skipped: %s", exc)
    hook_arm: tuple[str, str, str] | None = None
    if not own_idea:
        try:  # #1502: the hook rewrite on or off for this draft
            from core.experiments import next_arm

            hook_arm = next_arm(channel_id, kind="hook")
        except Exception as exc:
            logger.debug("hook arm skipped: %s", exc)
    shape_arm = None if own_idea else preview_shape_arm(channel_id, preview)  # #1366
    out.variant, out.score = best_topic, float(best_score or 0)

    from core.facts.selection import select_headless_facts
    from core.vault.relevance import build_relevance_corpus

    corpus = build_relevance_corpus(best_signals, operator_facts=key_facts or [])
    packed = select_headless_facts(key_facts, topic=topic, corpus=corpus) if key_facts else None
    length_choice = _length_choice(channel_id, best_topic)
    with hook_arm_env(hook_arm):  # #1502
        result = run_pipeline(
            topic,
            discovery=discovery,
            variant_index=variant_index,
            length_choice=length_choice,
            proceed_video=False,
            channel_id=channel_id,
            creative_brief=topic
            if own_idea
            else "\n".join(
                part
                for part in (
                    preview,
                    shape_arm[2] if shape_arm else "",
                    experiment[2] if experiment else "",
                )
                if part
            ),
            key_facts=packed,
            relevance_corpus=corpus,
            best_bet=best_bet,
            own_idea=own_idea,
            own_topic=best_topic if own_idea else "",
        )
    if hook_arm and result.run_id:
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, hook_arm[0], hook_arm[1])
        except Exception as exc:
            logger.debug("hook arm not recorded: %s", exc)
    if shape_arm and result.run_id:
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, shape_arm[0], shape_arm[1])
        except Exception as exc:
            logger.debug("preview shape not recorded: %s", exc)
    # #779: a script-only run always comes back aborted with "proceed_video=False" - the
    # pipeline records that as "drafted". Treating it as a failure kept 0 of 3 drafts on
    # the first real overnight run.
    drafted = result.abort_reason == "proceed_video=False"
    if (result.aborted and not drafted) or not (result.script or "").strip():
        out.error = result.abort_reason or "pipeline produced no script"
        return out
    out.title, out.run_id = result.title, result.run_id
    out.script = str(result.script or "")
    out.script_clean = result.features.get("script_clean")

    if experiment:
        lever, arm, _ = experiment
        out.experiment_arm = f"{lever}={arm}"
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, lever, arm)
        except Exception as exc:
            logger.debug("record_assignment skipped: %s", exc)

    # Same quality surface the interactive flow prints, persisted instead.
    try:
        from core.hook_score import score_script_hook

        hook = score_script_hook(result.script)
        out.hook_score, out.hook_verdict = hook.score, hook.verdict
    except Exception as exc:
        logger.debug("score_script_hook skipped: %s", exc)
    fact_count = 0
    used = (result.features or {}).get("fact_lines")
    if isinstance(used, int) and not isinstance(used, bool):
        fact_count = used  # #1217: the count the run was written from, not a second fetch
    else:
        try:
            from core.facts.enrichment import _fact_line_count, enrich_facts

            fact_count = _fact_line_count(
                enrich_facts(best_topic, best_signals, channel_id=channel_id, seed_topic=topic)
            )
        except Exception as exc:
            logger.debug("_fact_line_count skipped: %s", exc)
    try:
        from core.authenticity import evaluate_authenticity

        fields = authenticity_fields(
            evaluate_authenticity(
                result.script, channel_id, fact_count=fact_count, exclude_run_id=result.run_id
            )
        )
        out.authenticity_verdict = fields["authenticity_verdict"]
        out.authenticity_failed = fields["authenticity_failed"]
    except Exception as exc:
        logger.debug("evaluate_authenticity skipped: %s", exc)
    out.ungrounded = list(result.features.get("ungrounded_entities") or [])
    out.unsupported_claims = len(
        (result.features.get("claim_verification") or {}).get("unsupported") or []
    )
    out.fact_conflicts = len(result.features.get("fact_conflicts") or [])

    # #1151: say when the draft already calls the result of a game not yet played.
    unplayed = ""
    if upcoming:
        from core.facts.event_dates import unplayed_result

        unplayed = unplayed_result(str(result.title or ""), topic) or unplayed_result(
            result.script, topic
        )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = os.path.join(_drafts_dir(channel_id), f"{stamp}-{_slug(best_topic)}")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
        f.write(f"# {result.title or best_topic}\n\n")
        f.write(f"**Topic:** {topic}\n**Angle:** {best_topic} (score {best_score})\n\n")
        f.write("## Script\n\n")
        f.write(result.script.strip() + "\n\n")
        f.write("## Description\n\n")
        f.write((result.description or "").strip() + "\n")
        if result.tags:
            f.write("\n## Tags\n\n" + ", ".join(result.tags) + "\n")
    meta = {
        "topic": topic,
        "variant": best_topic,
        "variant_score": best_score,
        "title": result.title,
        "run_id": result.run_id,
        "channel_id": channel_id,
        "own_idea": bool(own_idea),  # #1159
        "length_choice": length_choice,
        "hook_score": out.hook_score,
        "hook_verdict": out.hook_verdict,
        # #1503: the opener and the rewrite's sound runners-up, picked from at review
        "hook_options": hook_options(result.script, result.features.get("script_passes")),
        "authenticity_verdict": out.authenticity_verdict,
        "authenticity_failed": list(out.authenticity_failed),
        "script_clean": result.features.get("script_clean"),  # #1143
        # #1150: run 139's title was flagged and overnight rendered it - the flag stopped here.
        "title_warnings": list(result.features.get("title_warnings") or []),
        # #1151; #1286: a headline naming a coming event (run 160) records that event's start.
        "event_at": event_at or _named_event_start(f"{topic} {result.title or ''}") or None,
        "unplayed_result": unplayed or None,
        "fact_count": fact_count,
        "ungrounded_entities": out.ungrounded,
        "tier_warnings": result.features.get("tier_warnings") or [],
        "fact_conflicts": result.features.get("fact_conflicts") or [],
        "claim_verification": result.features.get("claim_verification"),
        # #965: settled or fresh, and whether anyone pasted facts for it.
        "research": result.features.get("research"),
        "key_facts_count": len(packed or []),
        "experiment": out.experiment_arm or None,
        "cost": result.features.get("cost"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)

    out.path, out.ok, out.seconds = folder, True, round(time.time() - started, 1)
    return out


def _named_event_start(text: str, *, now: datetime | None = None) -> str:
    """#1286: the start of a coming event `text` names, or "". Only a coming one: a headline
    about a card already fought is a recap, and a recap has no window to miss."""
    try:
        from core.seasonal_calendar import _start_of, event_for

        _name, start = event_for(text)
    except Exception as exc:
        logger.debug("named event unread: %s", exc)
        return ""
    when = _start_of(start) if start else None
    if when is None or when <= (now or datetime.now(timezone.utc)):
        return ""
    return start


def preview_shape_arm(channel_id: str, preview: str) -> tuple[str, str, str] | None:
    """#1366 (decision 78): the shape a preview draft takes - the `preview_shape` experiment's
    next arm - or None for any other draft, or while the experiment is not running."""
    if not preview:
        return None
    try:
        from core.experiments import next_arm

        return next_arm(channel_id, kind="preview")
    except Exception as exc:
        logger.debug("preview shape skipped: %s", exc)
        return None


def draft_brief(topic: str, best_bet: dict | None) -> str:
    """The preview brief for a coming game or card - with the call it was offered with (#1301)
    - or "". main.py and overnight both write a preview from it; main.py wrote none."""
    from core.facts.event_dates import game_started, preview_brief

    event_at = _game_start(topic, best_bet) or _named_event_start(topic)
    if not event_at or game_started(event_at) is not False:
        return ""
    offered = (best_bet or {}).get("offered") or []
    call = next(
        (
            str(option.get("call") or "")
            for option in offered
            if isinstance(option, dict) and option.get("topic") == topic
        ),
        "",
    )
    return preview_brief(event_at, call=call)


def _game_start(topic: str, best_bet: dict | None) -> str:
    """The start of the game `topic` names when the pick came off the schedule, else ""."""
    offered = (best_bet or {}).get("offered") or []
    if not any(
        isinstance(option, dict)
        and option.get("topic") == topic
        and option.get("source") == "schedule"
        for option in offered
    ):
        return ""
    try:
        from core.seasonal_calendar import event_start

        return str(event_start(topic) or "")
    except Exception as exc:
        logger.debug("game start unavailable for %r: %s", topic, exc)
        return ""


def run_batch(
    channel_id: str,
    topics: list[str],
    *,
    key_facts: list[str] | None = None,
    picks: dict[str, dict] | None = None,
) -> list[DraftOutcome]:
    """Generate a draft per topic; one failure never kills the batch.

    ``key_facts`` apply to every topic (one overnight digest, N drafts). ``picks`` maps
    a best-bet topic to its `pick_record` (#913).
    """
    from apis.register_signals import franchise_batch_cache

    outcomes: list[DraftOutcome] = []
    with franchise_batch_cache(topics, channel_id=channel_id):
        for i, topic in enumerate(topics, 1):
            logger.info("Batch draft %d/%d: %s", i, len(topics), topic)
            existing = unreviewed_draft(channel_id, topic)
            if existing is not None:
                folder, meta = existing
                outcomes.append(
                    DraftOutcome(
                        topic=topic,
                        ok=True,
                        reused=True,
                        title=str(meta.get("title") or ""),
                        variant=str(meta.get("variant") or ""),
                        run_id=meta.get("run_id"),
                        path=folder,
                    )
                )
                continue
            try:
                pick = (picks or {}).get(topic)
                if pick:
                    outcome = generate_draft(topic, channel_id, key_facts=key_facts, best_bet=pick)
                else:
                    outcome = generate_draft(topic, channel_id, key_facts=key_facts)
                outcomes.append(outcome)
            except Exception as exc:
                logger.warning("Draft failed for %r: %s", topic, exc)
                outcomes.append(DraftOutcome(topic=topic, error=str(exc)))
    try:
        from core.pipeline import finalize_run_observability

        finalize_run_observability()
    except Exception as exc:
        logger.debug("finalize_run_observability skipped: %s", exc)
    try:
        from core.events import emit_event

        emit_event(
            "batch_completed",
            {
                "channel_id": channel_id,
                "requested": len(topics),
                "saved": sum(1 for o in outcomes if o.ok),
                "drafts": [
                    {"topic": o.topic, "ok": o.ok, "title": o.title, "path": o.path}
                    for o in outcomes
                ],
            },
        )
    except Exception as exc:
        logger.debug("batch_completed event not emitted: %s", exc)
    return outcomes


def render_summary(outcomes: list[DraftOutcome]) -> str:
    lines = ["", "Batch drafts", "=" * 40]
    for o in outcomes:
        if o.reused:
            lines.append(f"  KEEP {o.title or o.topic} - draft already waiting for review")
            lines.append(f"       {o.path}")
        elif o.ok:
            hook = f"hook {o.hook_score}" if o.hook_score is not None else "hook n/a"
            auth = o.authenticity_verdict or "n/a"
            flags = f", {len(o.ungrounded)} ungrounded" if o.ungrounded else ""
            if o.unsupported_claims:
                flags += f", {o.unsupported_claims} unsupported claim(s)"
            if o.fact_conflicts:
                flags += f", {o.fact_conflicts} fact conflict(s)"
            arm = f", A/B {o.experiment_arm}" if o.experiment_arm else ""
            lines.append(f"  OK   {o.title or o.variant}")
            lines.append(f"       {hook} ({o.hook_verdict}), authenticity {auth}{flags}{arm}")
            lines.append(f"       {o.path}  [{o.seconds:.0f}s]")
        else:
            lines.append(f"  FAIL {o.topic} — {o.error}")
    made = sum(1 for o in outcomes if o.ok)
    lines.append(f"  {made}/{len(outcomes)} drafts saved")
    if made:
        lines.append("  Review them: py -m scripts.ops batch-review")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="N ideas -> N draft scripts, unattended")
    parser.add_argument("topics", nargs="*", help="Topics (default: best bets)")
    parser.add_argument("--channel", default="tapin", help="Channel id (default: tapin)")
    parser.add_argument("--file", default=None, help="File with one topic per line")
    parser.add_argument(
        "--count", type=int, default=3, help="How many best-bet topics when none given"
    )
    parser.add_argument(
        "--facts-file",
        default="",
        help="Operator key facts (paste-block file) applied to every draft in the batch",
    )
    args = parser.parse_args(argv)

    from core.run_mode import CostModeBlocked, apply_and_guard

    try:
        apply_and_guard()
    except CostModeBlocked as exc:
        print(f"  {exc}")
        return 2

    from core.operator_facts import load_key_facts

    key_facts = load_key_facts(args.facts_file)
    picks: dict[str, dict] = {}
    topics = collect_topics(args.channel, args.topics, args.file, args.count, picks=picks)
    if not topics:
        print("No topics to draft (give topics, --file, or record analytics for best bets).")
        return 1
    outcomes = run_batch(args.channel, topics, key_facts=key_facts or None, picks=picks)
    print(render_summary(outcomes))
    return 0 if any(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    from core.console_encoding import ensure_utf8_stdout

    ensure_utf8_stdout()  # #767: redirected / scheduled runs are cp1252
    raise SystemExit(main())
