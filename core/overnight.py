"""Overnight operator (Pillar 5) — the whole loop, chained and unattended.

One command that composes the pillars into a hands-off overnight run:

    best-bet topics  →  batch drafts (graded + verified, Pillar 2/3)
                     →  vault dossiers (Pillar 4)
                     →  channel-health snapshot (Pillar 5)

Render-free by construction (it calls `batch_generation.run_batch`, which drafts
scripts only — no TTS/render/publish), so it is **cadence-safe**: drafts wake up
graded, verified, and dossier'd for the operator to approve. Emits an
`overnight_completed` webhook (`core/events.py`). Schedulable like `daily_sync`
(Task Scheduler / cron).

    py -m scripts.ops overnight --channel tapin --count 3
    py -m core.overnight --channel tapin --file ideas.txt
    py -m scripts.ops overnight --facts-file facts.txt --file ideas.txt

`--file` is topics (one per line). `--facts-file` is operator key facts, parsed
the same way as `auto_generate --facts-file` and passed through
`run_batch(..., key_facts=)`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.overnight")


def _append_tts_cache_line(lines: list[str]) -> None:
    try:
        from core.tts import format_tts_cache_line

        lines.append(format_tts_cache_line())
    except Exception as exc:
        logger.debug("overnight tts cache line skipped: %s", exc)


def _append_retention_line(lines: list[str]) -> None:
    try:
        from core.artifact_retention import format_retention_line

        line = format_retention_line()
        if line:
            lines.append(line)
    except Exception as exc:
        logger.debug("overnight retention line skipped: %s", exc)


@dataclass
class OvernightResult:
    channel_id: str
    requested: int = 0
    drafted: int = 0
    dossiers: int = 0
    corrections: int = 0
    outcomes: list[Any] = field(default_factory=list)
    health_line: str = ""
    skillopt_line: str = ""
    quota_line: str = ""
    pause_line: str = ""
    canary_line: str = ""
    post_publish_line: str = ""
    # #1078: what the unattended render did - {rendered, queued, failed, waiting}.
    renders: dict[str, Any] = field(default_factory=dict)
    # #1154: the sign-in is dead, or about to be - on the one report read after a night away.
    sign_in_line: str = ""
    # #1168: how many waiting drafts were set aside as past twice their window.
    expired: int = 0
    # #1580: renders retired a day past their game.
    retired: list[int] = field(default_factory=list)
    # #1190: what went to TikTok and Instagram through Buffer.
    crosspost_line: str = ""
    week_line: str = ""  # #138: the Monday compilation
    calls_line: str = ""  # wave 112: the week's marquee games called
    # #1253: how many drafts were already waiting, when that cut tonight's count.
    draft_line: str = ""
    gate_line: str = ""  # #1595: the stories the topic gate held back for the menu
    series_line: str = ""  # decision 84: a dated entry due tonight and skipped, with why
    # #1430: chapter Shorts cut to fill an empty week.
    chapter_lines: list[str] = field(default_factory=list)


_DRAFT_WAIT_CAP = 8


def draft_count(waiting: int, requested: int) -> tuple[int, str]:
    """How many new drafts to write while `waiting` drafts have no decision.

    At the cap of 8, a night that asked for 3 writes fewer. 22 waiting writes
    none, and the line says so.
    """
    want = min(max(0, requested), max(0, _DRAFT_WAIT_CAP - max(0, waiting)))
    if want < requested:
        return (
            want,
            f"{waiting} drafts are waiting for a decision; drafting {want} not {requested}",
        )
    return want, ""


def _sign_in_line(channel_id: str) -> str:
    """What is wrong with the channel's YouTube sign-in, or that it is about to end, or "".

    #1154: the 7-day reminder (#974) was on the header, `ops status` and `ops all`. The sign-in
    expired on 2026-10-13 with the overnight report - the one thing read that day - silent.
    """
    try:
        from youtube import oauth

        if oauth.live_youtube_forbidden():
            return ""
        problem = str(oauth.sign_in_status(channel_id) or "")
        if len(problem) > 120:  # #1176: the full message is printed where it is read once
            problem = oauth.short_sign_in(channel_id)
        return problem or str(oauth.sign_in_reminder(channel_id) or "")
    except Exception as exc:
        logger.debug("overnight sign-in line skipped: %s", exc)
        return ""


def run_overnight(
    channel_id: str | None = None,
    *,
    count: int = 3,
    topics: list[str] | None = None,
    file: str | None = None,
    facts_file: str | None = None,
) -> OvernightResult:
    """Chain best-bet → drafts → dossiers → health. Fail-open at every step."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    result = OvernightResult(channel_id=channel)
    result.sign_in_line = _sign_in_line(channel)
    if result.sign_in_line:
        logger.warning("%s", result.sign_in_line)

    try:
        from core.overnight_pause import is_paused

        if is_paused():
            from core.overnight_pause import status_line

            result.pause_line = f"{status_line()} (operator flag)."  # #1338: and until when
            return result
    except Exception as exc:
        logger.debug("overnight pause check skipped: %s", exc)

    try:  # wave 113: the metrics sync ran only from `ops morning`; once a day it runs here too
        from analytics.sync_metrics import maybe_sync

        maybe_sync(channel)
    except Exception as exc:
        logger.debug("overnight metrics sync skipped: %s", exc)

    try:
        return _run_overnight_body(
            channel,
            result,
            count=count,
            topics=topics,
            file=file,
            facts_file=facts_file,
        )
    finally:
        _probe_signals(result)
        _post_publish(result)
        _crosspost(result)
        _score_calls()
        _call_week(result)
        _week_compile(result)


def _crosspost(result: OvernightResult) -> None:
    """#1190: videos made public since the last run go to TikTok and Instagram."""
    try:
        from publishing.crosspost import step

        result.crosspost_line = "\n".join(step(result.channel_id))
    except Exception as exc:
        logger.debug("overnight crosspost skipped: %s", exc)


def _week_compile(result: Any, now: datetime | None = None) -> None:
    """#138 (the operator: a $0 compilation, public at a slot): on Monday mornings in the
    channel's zone, last week's public Shorts become one long video, queued for a slot."""
    if os.getenv("WEEK_COMPILE", "true").strip().lower() in ("0", "false", "no", "off"):
        return
    moment = now or datetime.now(timezone.utc)
    try:
        from core.spaced_queue import _channel_tz

        if moment.astimezone(_channel_tz(result.channel_id)).weekday() != 0:
            return
        from core.nightly_task import beat_step
        from video.week_compile import compile_week

        beat_step("the weekly compilation")  # #1468
        result.week_line = "\n".join(
            compile_week(result.channel_id, apply=True, queue=True, now=moment)
        )
    except Exception as exc:
        logger.warning("overnight week compilation skipped: %s", exc)


def _call_week(result: Any) -> None:
    """Wave 112: a call for every marquee game of the week, not only the menu's five previews -
    the ledger keeps each one (made once) and "Picks, graded" counts them."""
    try:
        from core.best_bet import suggested_games
        from core.predictions import calls
        from core.seasonal_calendar import fetch_week_topics

        games = suggested_games(fetch_week_topics(), covered_topics=[])
        if not games:
            return
        made = calls.preview_calls(games, headlines=lambda: calls.headlines_for(games))
        if made:
            result.calls_line = (
                f"Calls: {len(made)} of this week's {len(games)} marquee games called "
                "(py -m scripts.ops predictions)"
            )
    except Exception as exc:
        logger.debug("overnight week calls skipped: %s", exc)


def _score_calls() -> None:
    """#1304: last night's games score their preview calls (ops predictions prints them)."""
    try:
        from core.predictions.calls import score_calls

        score_calls()
    except Exception as exc:
        logger.debug("overnight call scoring skipped: %s", exc)


def _post_publish(result: OvernightResult) -> None:
    """#600. Uploads 48h+ old looked at once more: removed, blocked, age-restricted, kids."""
    try:
        from core.post_publish_check import post_publish_line

        result.post_publish_line = post_publish_line(result.channel_id)
    except Exception as exc:
        logger.debug("overnight post-publish check skipped: %s", exc)


def _probe_signals(result: OvernightResult) -> None:
    """#663. Nightly liveness, fail-open, never via all-checks (CI has no network)."""
    try:
        from core.signal_canary import check_signals, render, save_results

        rows = check_signals()
        save_results(rows)
        result.canary_line = render(rows)
    except Exception as exc:
        logger.debug("overnight signal canary skipped: %s", exc)


def _run_overnight_body(
    channel: str,
    result: OvernightResult,
    *,
    count: int,
    topics: list[str] | None,
    file: str | None,
    facts_file: str | None,
) -> OvernightResult:
    from core.batch_generation import collect_topics, topic_gate_line
    from core.operator_facts import load_key_facts

    want = count
    try:
        from core.overnight_quota import adjust_count

        want, quota_reason = adjust_count(count)
        if quota_reason:
            result.quota_line = quota_reason
        if want <= 0:
            logger.warning("overnight skipped by quota gate: %s", quota_reason)
            result.requested = 0
            return result
    except Exception as exc:
        logger.debug("overnight quota gate skipped: %s", exc)

    # #1168: drafts past twice their window leave the waiting count before anything renders.
    # Wave 104: and before #1253's cap counts them - set aside tonight, they hold nothing back.
    try:
        from core.batch_review import expire_enabled, expire_old_drafts

        if expire_enabled():
            result.expired = len(expire_old_drafts(channel))
    except Exception as exc:
        logger.debug("overnight draft expiry skipped: %s", exc)
    try:  # #1580: a render a day past its game leaves the shelf for good (the file stays)
        from core.stale_renders import retire_dead_renders

        result.retired = retire_dead_renders(channel)
    except Exception as exc:
        logger.debug("dead renders not retired: %s", exc)

    try:
        from core.batch_review import pending_drafts

        want, draft_line = draft_count(len(pending_drafts(channel)), want)
        result.draft_line = draft_line
    except Exception as exc:
        logger.warning("overnight draft queue unread: %s", exc)

    picks: dict[str, dict] = {}
    picked: list[str] = []
    if want <= 0:
        # Draft fewer while some wait (#1253). Expiry and the rest of the night still run.
        result.requested = 0
        if not topics and not file:  # #1847: the day's countdown is made on its day or never
            skipped: list[str] = []
            picked = collect_topics(channel, None, None, 0, picks=picks, notes=skipped)
            result.requested = len(picked)
            result.series_line = "; ".join(skipped)
    else:
        held_back: list[str] = []
        skipped = []
        picked = collect_topics(
            channel, topics, file, want, picks=picks, held_back=held_back, notes=skipped
        )
        result.series_line = "; ".join(skipped)
        result.requested = len(picked)
        result.gate_line = topic_gate_line(held_back)  # #1595
    if want > 0 and not picked:
        logger.warning("overnight: no topics (best bets unavailable) for %s", channel)
        return result
    if picked:
        key_facts = load_key_facts(facts_file) if facts_file else None
        batch_kwargs: dict[str, Any] = {}
        if key_facts:
            batch_kwargs["key_facts"] = key_facts
        if picks:
            batch_kwargs["picks"] = picks  # #913: the best-bet ranks the batch took
        # #1229: one child per draft. A native crash records its exit and the night goes on.
        result.outcomes = draft_each(channel, picked, **batch_kwargs)
        result.drafted = sum(1 for o in result.outcomes if getattr(o, "ok", False))

        # Mirror each drafted run into the vault (Pillar 4). run_batch persists a
        # content_run per draft, so dossiers can join grade/quality/cost by run_id.
        try:
            from core.vault.dossiers import write_run_dossier

            for o in result.outcomes:
                rid = getattr(o, "run_id", None)
                if getattr(o, "ok", False) and rid and write_run_dossier(rid):
                    result.dossiers += 1
        except Exception as exc:
            logger.debug("overnight dossier step skipped: %s", exc)

    # #1078 (operator, 2026-10-11): overnight may render. Only when the channel says how
    # many, only drafts nothing is flagged on, and every one is queued unlisted.
    try:
        from core.batch_review import overnight_render_limit, render_unattended

        limit, why_more = overnight_render_limit(channel)  # #1428: one more for an empty day
        if limit > 0:
            result.renders = render_unattended(channel, limit)
            if why_more:
                result.renders["empty_day"] = why_more
    except Exception as exc:
        logger.warning("overnight render step did not run: %s", exc)

    try:  # #1430 (the operator: gaming and evergreen only): fill an empty week
        from core.chapter_shorts import fill_empty_slots

        result.chapter_lines = fill_empty_slots(channel)
    except Exception as exc:
        logger.warning("overnight chapter Shorts did not run: %s", exc)

    try:
        from core.channel_health import build_health, health_line, record_history

        report = build_health(channel)
        result.health_line = health_line(report)
        record_history(report)  # #1475: the night's read is the day's line (never raises)
    except Exception:
        result.health_line = ""

    # Pillar 7: nightly SkillOpt-Sleep — gated skill-directive optimization. Opt-in (LLM
    # calls) and fail-open; only proposes gate-beating directives, never edits live prompts.
    import os

    if os.getenv("SKILLOPT_ENABLED", "false").lower() in ("1", "true", "yes"):
        try:
            from core.skillopt import run_skillopt

            r = run_skillopt(channel)
            if r.improved:
                result.skillopt_line = (
                    f"SkillOpt: proposed a directive (+{r.margin:.1f} vs baseline) "
                    f"-> {r.proposal_path or 'vault unset'}"
                )
            elif r.n_topics:
                result.skillopt_line = "SkillOpt: no candidate beat the gate (prompts unchanged)"
        except Exception as exc:
            logger.debug("overnight skillopt step skipped: %s", exc)

    try:
        from core.events import emit_event

        emit_event(
            "overnight_completed",
            {
                "channel_id": channel,
                "requested": result.requested,
                "drafted": result.drafted,
                "dossiers": result.dossiers,
                "health": result.health_line,
            },
        )
    except Exception as exc:
        logger.debug("overnight event not emitted: %s", exc)
    try:
        from core.win_notify import notify_overnight_done

        notify_overnight_done(result.drafted, result.requested)
    except Exception as exc:
        logger.debug("overnight toast skipped: %s", exc)
    try:
        from core.retraction_watch import notify_retractions_if_due

        notify_retractions_if_due(channel)
    except Exception as exc:
        logger.debug("overnight retraction toast skipped: %s", exc)
    try:
        # #112. The toast above is transient: first hit only, deduped per
        # process, joined to no run. This writes the dossier that survives the
        # night. It never touches the published video.
        from core.correction_dossier import scan_published_for_corrections

        filed = scan_published_for_corrections(channel)
        if filed:
            result.corrections = len(filed)
            logger.warning(
                "%s correction dossier(s) filed for published videos on %s",
                len(filed),
                channel,
            )
    except Exception as exc:
        logger.warning("overnight correction scan did not run: %s", exc)
    if topics:
        try:
            from core.best_bet import get_best_bet
            from core.counterfactual import record_override

            bet = get_best_bet(channel)
            chosen = {str(t) for t in topics}
            if bet and bet.topic not in chosen:
                record_override(bet.topic, ";".join(topics))
        except Exception as exc:
            logger.debug("overnight counterfactual skipped: %s", exc)
    return result


def render_lines(result: OvernightResult) -> list[str]:
    """#1078: what was rendered overnight and what to do with it, or []."""
    done = result.renders or {}
    lines: list[str] = []
    rendered = [int(r) for r in done.get("rendered") or []]
    if rendered:
        runs = ", ".join(f"run {r}" for r in rendered)
        lines.append(
            f"Rendered overnight: {len(rendered)} ({runs}), queued unlisted - watch each, "
            f"then: py -m scripts.ops go-public --channel {result.channel_id}"
        )
    if done.get("empty_day"):  # #1428
        lines.append(f"One more render tonight: {done['empty_day']}")
    for run_id, why in done.get("failed") or []:
        lines.append(f"Not rendered: run {run_id} ({why})")
    if done.get("paused"):  # #1152
        lines.append(f"Overnight rendering paused: {done['paused']}")
    elif done and not rendered and not done.get("failed"):
        waiting = len(done.get("waiting") or [])
        lines.append(f"Nothing rendered overnight: no draft qualified ({waiting} wait for you)")
    if result.expired:
        lines.append(
            f"Set aside {result.expired} drafts past twice their window - "
            "py -m scripts.ops batch-review --expired"
        )
    if result.retired:  # #1580
        lines.append(
            f"Retired {len(result.retired)} render(s) a day past their game (files kept): runs "
            + ", ".join(str(r) for r in result.retired)
        )
    return lines


def render_overnight(result: OvernightResult) -> str:
    from core.batch_generation import render_summary

    lines = [f"Overnight operator — {result.channel_id}", "=" * 44]
    if result.sign_in_line:
        lines.append(f"Sign-in: {result.sign_in_line}")
    if result.pause_line:
        lines.append(result.pause_line)
        lines.append("Nothing drafted. Resume from the tray before the next scheduled run.")
        return "\n".join(lines)
    if result.quota_line:
        lines.append(f"Quota: {result.quota_line}")
    if result.draft_line:
        lines.append(result.draft_line)
    if result.gate_line:
        lines.append(result.gate_line)
    if result.series_line:
        lines.append(result.series_line)
    if not result.requested:
        if result.draft_line:
            lines.append("Nothing drafted while those drafts wait for a decision.")
        elif result.quota_line:
            lines.append("Overnight skipped (quota gate). Nothing drafted.")
        else:
            lines.append("No topics to draft (best bets unavailable). Nothing done.")
        lines.extend(result.chapter_lines)  # #1430: a night of no drafts can still cut
        if result.canary_line:
            lines.append("")
            lines.append(result.canary_line)
        if result.post_publish_line:
            lines.append(result.post_publish_line)
        if result.crosspost_line:
            lines.append(result.crosspost_line)
        if result.week_line:
            lines.append(result.week_line)
        if result.calls_line:
            lines.append(result.calls_line)
        _append_tts_cache_line(lines)
        _append_retention_line(lines)
        return "\n".join(lines)
    try:
        lines.append(render_summary(result.outcomes).strip())
    except Exception:
        lines.append(f"{result.drafted}/{result.requested} drafts saved")
    lines.extend(render_lines(result))
    lines.extend(result.chapter_lines)  # #1430
    lines.append("")
    lines.append(f"Dossiers written to vault: {result.dossiers}")
    if result.corrections:
        lines.append(
            f"CORRECTIONS: {result.corrections} published video(s) rest on a claim whose "
            "source has since been retracted. Dossiers are in the vault; nothing was "
            "changed on YouTube."
        )
    if result.health_line:
        lines.append(result.health_line)
    if result.skillopt_line:
        lines.append(result.skillopt_line)
    if result.canary_line:
        lines.append("")
        lines.append(result.canary_line)
    if result.post_publish_line:
        lines.append(result.post_publish_line)
    if result.crosspost_line:
        lines.append(result.crosspost_line)
    if result.week_line:
        lines.append(result.week_line)
    if result.calls_line:
        lines.append(result.calls_line)
    _append_tts_cache_line(lines)
    _append_retention_line(lines)
    lines.append(
        f"Review them in one pass: py -m scripts.ops batch-review --channel {result.channel_id}"
    )
    try:
        from core.cadence import cadence_status, target_line

        week = target_line(cadence_status(result.channel_id))
        if week:
            lines.append(week)
    except Exception as exc:
        logger.debug("weekly target line skipped: %s", exc)
    try:
        from core.spend_week import spend_warning_line

        spend = spend_warning_line()
        if spend:
            lines.append(spend)
    except Exception as exc:
        logger.debug("weekly spend line skipped: %s", exc)
    return "\n".join(lines)


def crashed_draft_line(topic: str, code: int) -> str:
    """What the report says when a draft's process dies. The exit code is the one Python saw."""
    return f"{topic} crashed (exit {code})"


def draft_each(
    channel: str,
    topics: list[str],
    *,
    key_facts: list[str] | None = None,
    picks: dict[str, dict] | None = None,
) -> list[Any]:
    """One child process per topic. A crashed child is one failed draft."""
    from core.nightly_task import beat_step

    outcomes = []
    for i, topic in enumerate(topics, start=1):
        beat_step(f"drafting {i} of {len(topics)}: {topic[:40]}")  # #1468
        outcomes.append(
            _draft_one(channel, topic, key_facts=key_facts, pick=(picks or {}).get(topic))
        )
    return outcomes


def _draft_one(
    channel: str,
    topic: str,
    *,
    key_facts: list[str] | None,
    pick: dict | None,
) -> Any:
    import json
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    from core.batch_generation import DraftOutcome

    fd, job = tempfile.mkstemp(prefix="draftjob_", suffix=".json")
    os.close(fd)
    result_path = job + ".result.json"
    payload = {
        "channel": channel,
        "topic": topic,
        "key_facts": key_facts,
        "pick": pick,
        "result": result_path,
    }
    try:
        Path(job).write_text(json.dumps(payload), encoding="utf-8")
        # Not captured: the child's lines - and a crash's faulthandler traceback (#1216) - go to
        # the parent's stdout and stderr, which the task sends to overnight-last.log.
        proc = subprocess.run([sys.executable, "-m", "core.overnight", "--draft-job", job])
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("overnight draft was not started for %s: %s", topic, exc)
        return DraftOutcome(topic=topic, error=str(exc))
    finally:
        try:
            os.remove(job)
        except OSError:
            pass
    try:
        if proc.returncode != 0 or not os.path.isfile(result_path):
            line = crashed_draft_line(topic, int(proc.returncode))
            logger.warning("%s", line)
            return DraftOutcome(topic=topic, error=line)
        data = json.loads(Path(result_path).read_text(encoding="utf-8"))
        return _outcome_from(data)
    finally:
        try:
            os.remove(result_path)
        except OSError:
            pass


def _outcome_from(data: dict) -> Any:
    from dataclasses import fields

    from core.batch_generation import DraftOutcome

    known = {item.name for item in fields(DraftOutcome)}
    return DraftOutcome(**{key: value for key, value in data.items() if key in known})


def _write_outcome(path: str, outcome: Any) -> None:
    import json
    from dataclasses import asdict
    from pathlib import Path

    Path(path).write_text(json.dumps(asdict(outcome)), encoding="utf-8")


def _draft_job(path: str) -> int:
    """The child: one topic, then exit. A non-zero exit is the crash the parent records."""
    import json
    import os
    from pathlib import Path

    from core.batch_generation import DraftOutcome

    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    topic = str(spec.get("topic") or "")
    if os.getenv("OVERNIGHT_DRAFT_STUB") == "1":
        crash = os.getenv("OVERNIGHT_CRASH_TOPIC") or ""
        if crash and topic == crash:
            os._exit(int(os.getenv("OVERNIGHT_CRASH_CODE") or "74"))
        _write_outcome(
            str(spec["result"]),
            DraftOutcome(topic=topic, ok=True, title=topic, run_id=1),
        )
        return 0
    try:
        from core.nightly_task import enable_crash_traceback

        enable_crash_traceback()
    except Exception as exc:
        logger.debug("overnight child traceback hook skipped: %s", exc)
    from core.batch_generation import run_batch

    kwargs: dict[str, Any] = {}
    facts = spec.get("key_facts")
    if facts:
        kwargs["key_facts"] = facts
    pick = spec.get("pick")
    if pick:
        kwargs["picks"] = {topic: pick}
    outcomes = run_batch(str(spec.get("channel") or ""), [topic], **kwargs)
    outcome = outcomes[0] if outcomes else DraftOutcome(topic=topic, error="no outcome")
    _write_outcome(str(spec["result"]), outcome)
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    args_in = list(sys.argv[1:] if argv is None else argv)
    if args_in[:1] == ["--draft-job"]:
        if len(args_in) < 2:
            return 2
        from core.win_shell import hide_child_windows

        hide_child_windows()  # 2026-10-28: a child of pythonw opens a window per console tool
        return _draft_job(args_in[1])

    parser = argparse.ArgumentParser(description="Overnight operator (drafts + grade + dossiers)")
    parser.add_argument("--channel", default=None)
    parser.add_argument("--count", type=int, default=3, help="Best-bet topics when none given")
    parser.add_argument("--file", default=None, help="File of topics (one per line)")
    parser.add_argument(
        "--facts-file",
        default=None,
        help="Operator key facts (paste-block file; same as auto_generate --facts-file)",
    )
    parser.add_argument("topics", nargs="*", help="Explicit topics")
    args = parser.parse_args(argv)
    result = run_overnight(
        args.channel,
        count=args.count,
        topics=args.topics or None,
        file=args.file,
        facts_file=args.facts_file,
    )
    print(render_overnight(result))
    return 0


if __name__ == "__main__":
    from core.console_encoding import ensure_utf8_stdout

    ensure_utf8_stdout()  # #767: redirected / scheduled runs are cp1252
    raise SystemExit(main())
