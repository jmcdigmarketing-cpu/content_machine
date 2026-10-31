"""Analytics report v1 — rules-based weekly intelligence.

Joins content-run features (the feature store) to real engagement outcomes and
reports which feature values out/under-perform the channel baseline, with sample-size
gating so small-n noise isn't presented as signal. This is intentionally statistics,
not ML — it starts the habit and exposes feature-schema gaps early (roadmap 120-day).

    py -m analytics.weekly_report --channel tapin
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("analytics.weekly_report")

# A feature value needs at least this many videos before we trust its average.
_MIN_SAMPLES = 3

# Which feature dimensions to break performance down by.
_DIMENSIONS = ("domain", "angle", "title_structure", "format", "fact_source", "upload_mode")


def _load_rows(channel_id: str) -> list[dict[str, Any]]:
    """Runs joined to engagement + parsed features. Only rows with engagement data."""
    from core.engagement import engaged_rate as _engaged_rate
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    runs = get_content_run_repository().list_for_channel(channel_id)
    logs = {
        log.content_run_id: log
        for log in get_publish_log_repository().list_timed_outcomes(channel_id)
    }

    rows: list[dict[str, Any]] = []
    for run in runs:
        log = logs.get(run.id)
        rate = _engaged_rate(log.metrics_json) if log else None
        if rate is None:
            continue
        try:
            features = json.loads(run.features_json or "{}")
        except (json.JSONDecodeError, TypeError):
            features = {}
        features = features if isinstance(features, dict) else {}
        # #598: a scheduled upload keeps status "scheduled" (#915); anything else went live
        # when it uploaded. Read from the log here, never stored on the run.
        mode = "scheduled" if getattr(log, "status", "") == "scheduled" else "immediate"
        rows.append(
            {"run_id": run.id, "engaged_rate": rate, "features": {**features, "upload_mode": mode}}
        )
    return rows


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_report(channel_id: str) -> dict[str, Any]:
    """Return a structured report: baseline, per-dimension winners/losers, cost."""
    channel_id = resolve_channel_id(channel_id)
    rows = _load_rows(channel_id)
    if len(rows) < _MIN_SAMPLES:
        return {"channel_id": channel_id, "n": len(rows), "ready": False}

    baseline = _avg([r["engaged_rate"] for r in rows])

    dimensions: dict[str, list[dict[str, Any]]] = {}
    untested: list[dict[str, Any]] = []
    for dim in _DIMENSIONS:
        groups: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            val = r["features"].get(dim)
            if val:
                groups[str(val)].append(r["engaged_rate"])
        scored = [
            {
                "value": value,
                "avg": _avg(rates),
                "n": len(rates),
                "delta": _avg(rates) - baseline,
            }
            for value, rates in groups.items()
            if len(rates) >= _MIN_SAMPLES
        ]
        scored.sort(key=lambda g: g["avg"], reverse=True)
        if scored:
            dimensions[dim] = scored
        # #1061: values with too few videos to score - what "try next" is picked from.
        untested.extend(
            {"dimension": dim, "value": value, "avg": _avg(rates), "n": len(rates)}
            for value, rates in groups.items()
            if len(rates) < _MIN_SAMPLES
        )

    # Cost summary from whatever runs recorded it.
    costs = [
        float((r["features"].get("cost") or {}).get("total") or 0)
        for r in rows
        if r["features"].get("cost")
    ]

    report = {
        "channel_id": channel_id,
        "n": len(rows),
        "ready": True,
        "baseline": baseline,
        "dimensions": dimensions,
        "untested": untested,
        "shelf": _shelf(channel_id),
        "avg_cost": _avg(costs) if costs else None,
        "total_cost": round(sum(costs), 2) if costs else None,
    }
    report["next_actions"] = build_next_actions(report)
    return report


# Delta (vs baseline) below which a feature value is treated as neutral noise.
_ACTION_DELTA = 0.03

# How each dimension's winner/loser translates into an operator instruction.
_ACTION_PHRASES: dict[str, tuple[str, str]] = {
    "domain": ("Make more {value} videos", "Pause {value} topics"),
    "angle": ("Lead with the '{value}' angle again", "Retire the '{value}' angle"),
    "title_structure": ("Keep using {value} titles", "Drop {value} titles"),
    "format": ("Stick with the {value} format", "Rework the {value} format"),
    "fact_source": ("Keep sourcing facts via {value}", "Improve {value} fact sourcing"),
    "upload_mode": ("Keep using {value} uploads", "Use fewer {value} uploads"),
}


def build_next_actions(report: dict[str, Any], *, max_actions: int = 5) -> list[str]:
    """Concrete operator instructions from the per-dimension winners/losers.

    One "do more" from the strongest over-performer and one "do less" from the
    weakest under-performer per dimension (only past the noise threshold), then
    a cadence/coach pointer. Purely derived — no new data reads.
    """
    if not report.get("ready"):
        return []
    actions: list[str] = []
    for dim, groups in (report.get("dimensions") or {}).items():
        more_tpl, less_tpl = _ACTION_PHRASES.get(
            dim, (f"Do more {dim}={{value}}", f"Do less {dim}={{value}}")
        )
        best, worst = groups[0], groups[-1]
        if best["delta"] >= _ACTION_DELTA:
            actions.append(
                f"{more_tpl.format(value=best['value'])} "
                f"({best['avg']:.0%} vs {report['baseline']:.0%} baseline, n={best['n']})"
            )
        if worst is not best and worst["delta"] <= -_ACTION_DELTA:
            actions.append(
                f"{less_tpl.format(value=worst['value'])} "
                f"({worst['avg']:.0%} vs {report['baseline']:.0%} baseline, n={worst['n']})"
            )
    return actions[:max_actions]


_TRY_PHRASES: dict[str, str] = {
    "domain": "another {value} video",
    "angle": "the '{value}' angle again",
    "title_structure": "another {value} title",
    "format": "another {value} video",
    "fact_source": "facts via {value} again",
    "upload_mode": "another {value} upload",
}


def _shrunk_delta(group: dict[str, Any]) -> float:
    """The group's gap to the baseline after the recommenders' shrinkage (#352): four
    pseudo-videos at the baseline, so three lucky videos do not outrank twelve good ones."""
    from core.recommender_confidence import MODERATE_SAMPLES

    n = int(group["n"])
    return float(group["delta"]) * n / (n + MODERATE_SAMPLES)


def _shelf(channel_id: str) -> dict[str, int]:
    """Finished videos that are not public (#1122), or {} when they cannot be counted."""
    try:
        from core.stale_renders import shelf

        return shelf(channel_id)
    except Exception as exc:
        logger.debug("weekly report: shelf not read: %s", exc)
        return {}


def shelf_decision(report: dict[str, Any]) -> str:
    """The line that goes before the three decisions: publish what is finished first."""
    from core.stale_renders import shelf_total

    counts = report.get("shelf") or {}
    total = shelf_total(counts)
    if not total:
        return ""
    return (
        f"First: {total} finished video(s) are not public "
        f"({int(counts.get('unlisted') or 0)} unlisted, "
        f"{int(counts.get('renders') or 0)} never uploaded) - "
        "py -m scripts.ops status lists them."
    )


def three_decisions(report: dict[str, Any]) -> list[dict[str, Any]]:
    """#1061: more of / less of / try next, each {kind, dimension, value, line} with the
    number it came from. A decision the numbers do not support is left out.

    - more: the value furthest above the baseline after shrinkage;
    - less: the value furthest below it;
    - try: the best value with too few videos to score, else the thinnest winner.
    """
    if not report.get("ready"):
        return []
    from core.recommender_confidence import confidence_level

    baseline = float(report.get("baseline") or 0.0)
    groups = [
        {**group, "dimension": dim}
        for dim, rows in (report.get("dimensions") or {}).items()
        for group in rows
    ]

    def measured(group: dict[str, Any]) -> str:
        level = confidence_level(int(group["n"]))
        note = "" if level == "high" else f", {level} confidence"
        return f"{group['avg']:.0%} vs {baseline:.0%} baseline, n={group['n']}{note}"

    out: list[dict[str, Any]] = []
    winners = [g for g in groups if g["delta"] >= _ACTION_DELTA]
    losers = [g for g in groups if g["delta"] <= -_ACTION_DELTA]
    more = max(winners, key=_shrunk_delta, default=None)
    if more:
        phrase = _ACTION_PHRASES.get(more["dimension"], ("{value}", ""))[0]
        out.append({
            "kind": "more", "dimension": more["dimension"], "value": more["value"],
            "line": f"More of: {phrase.format(value=more['value'])} ({measured(more)})",
        })  # fmt: skip
    less = min(losers, key=_shrunk_delta, default=None)
    if less:
        phrase = _ACTION_PHRASES.get(less["dimension"], ("", "{value}"))[1]
        out.append({
            "kind": "less", "dimension": less["dimension"], "value": less["value"],
            "line": f"Less of: {phrase.format(value=less['value'])} ({measured(less)})",
        })  # fmt: skip
    untested = [u for u in report.get("untested") or [] if float(u["avg"]) > baseline]
    trial = max(untested, key=lambda u: (float(u["avg"]), int(u["n"])), default=None)
    if trial:
        phrase = _TRY_PHRASES.get(trial["dimension"], "{value} again")
        out.append({
            "kind": "try", "dimension": trial["dimension"], "value": trial["value"],
            "line": (
                f"Try next: {phrase.format(value=trial['value'])} ({trial['avg']:.0%} on "
                f"{trial['n']} video{'s' if trial['n'] != 1 else ''}, {baseline:.0%} baseline - "
                f"too few to call; {_MIN_SAMPLES} makes it count)"
            ),
        })  # fmt: skip
    else:
        rest = [g for g in winners if g is not more]
        thin = min(rest, key=lambda g: int(g["n"]), default=None)
        if thin:
            phrase = _TRY_PHRASES.get(thin["dimension"], "{value} again")
            out.append({
                "kind": "try", "dimension": thin["dimension"], "value": thin["value"],
                "line": f"Try next: {phrase.format(value=thin['value'])} ({measured(thin)})",
            })  # fmt: skip
    return out


def operator_digest(report: dict[str, Any], *, limit: int = 3) -> str:
    """#452: at most three decisions this week. Empty when the report is not ready.

    #1061: they are more of / less of / try next when the report has its dimensions; a
    report carrying only `next_actions` keeps the capped list."""
    if not report.get("ready"):
        return ""
    decided = [d["line"] for d in three_decisions(report)]
    actions = decided or [str(a) for a in (report.get("next_actions") or []) if str(a).strip()]
    actions = actions[:limit]
    if not actions:
        return ""
    channel = str(report.get("channel_id") or "this channel")
    lines = [f"This week's three decisions ({channel}):", ""]
    first = shelf_decision(report)
    if first:
        lines.extend([first, ""])
    lines.extend(f"{i}. {action}" for i, action in enumerate(actions, 1))
    return "\n".join(lines)


def write_operator_digest(channel_id: str, report: dict[str, Any]) -> Path | None:
    """Land the digest in the vault. Does not call YouTube."""
    draft = operator_digest(report)
    if not draft:
        return None
    from core.vault.dossiers import write_report_note

    return write_report_note(channel_id, "digest", "Operator digest", draft, fenced=False)


def community_post_draft(report: dict[str, Any]) -> str:
    """YouTube Community post text from this week's next actions. Never posted."""
    if not report.get("ready"):
        return ""
    actions = [str(a) for a in (report.get("next_actions") or []) if str(a).strip()]
    if not actions:
        return ""
    channel = str(report.get("channel_id") or "this channel")
    lines = [
        f"This week's plan for {channel} (draft — not posted to YouTube):",
        "",
    ]
    lines.extend(f"- {action}" for action in actions)
    return "\n".join(lines)


def write_community_post_draft(channel_id: str, report: dict[str, Any]) -> Path | None:
    """Land the community-post draft in the vault. Does not call YouTube."""
    draft = community_post_draft(report)
    if not draft:
        return None
    from core.vault.dossiers import write_report_note

    return write_report_note(
        channel_id,
        "community-draft",
        "Community post draft",
        draft,
        fenced=False,
    )


def _scoreboard_head(channel_id: str) -> str:
    """#934: the goal's scoreboard opens the weekly report, ready or not."""
    try:
        from core.success.goals import load_goal, scoreboard_lines

        if load_goal(channel_id) is None:
            return ""
        return "\n".join(scoreboard_lines(channel_id)) + "\n\n"
    except Exception as exc:
        logger.debug("scoreboard skipped in the weekly report: %s", exc)
        return ""


def _bridge_block(channel_id: str) -> str:
    """#1822: the bridge's scoreboard after the goal's - what counts toward YPP."""
    try:
        from core.success.bridge import scoreboard_lines

        return "\n".join(scoreboard_lines(channel_id)) + "\n\n"
    except Exception as exc:
        logger.debug("bridge scoreboard skipped in the weekly report: %s", exc)
        return ""


def _buffer_tail(channel_id: str) -> str:
    """What went to TikTok and Instagram, and which feed liked what (#979, #1198)."""
    parts: list[str] = []
    try:
        from publishing.crosspost import week_line

        line = week_line(channel_id)
        if line:
            parts.append(line)
    except Exception as exc:
        logger.debug("buffer line skipped in the weekly report: %s", exc)
    try:
        from publishing.platform_recommend import feed_lines

        parts.extend(feed_lines(channel_id))
    except Exception as exc:
        logger.debug("platform results skipped in the weekly report: %s", exc)
    if not parts:
        return ""
    return "\n\n" + "\n".join(f"  {part}" for part in parts)


def format_report(report: dict[str, Any]) -> str:
    channel_id = str(report.get("channel_id") or "")
    return (
        _scoreboard_head(channel_id)
        + _bridge_block(channel_id)
        + _format_body(report)
        + _buffer_tail(channel_id)
    )


def draft_mix_line(drafts: list[dict[str, Any]]) -> str:
    """#1365: the week's drafts as games (an event), news (a short window) and the rest -
    decision 66 asked for five ideas and five previews."""
    if not drafts:
        return ""
    from core.batch_review import freshness_window_days

    games = sum(1 for d in drafts if d.get("event_at"))
    news = sum(1 for d in drafts if not d.get("event_at") and freshness_window_days(d) < 7)
    other = len(drafts) - games - news
    game_word = "game" if games == 1 else "games"
    return (
        f"Overnight's mix this week: {games} {game_word}, {news} news, {other} other "
        f"({len(drafts)} drafts)"
    )


def _hold_kind(reason: str) -> str:
    """ "script check: 1 thing said twice" is "script check" - the kind of hold, not its detail."""
    import re

    head = re.split(r':|\s\(|\s"', str(reason or ""), maxsplit=1)[0].strip()
    return re.sub(r"\d+(?:\.\d+)?", "N", head) or "none recorded"


def draft_outcome_line(drafts: list[dict[str, Any]]) -> str:
    """#1585: the week's drafts by outcome, and what held the ones that expired - to track
    decision 78 (18 of 46 drafts had expired undecided in two weeks) and #1578."""
    if not drafts:
        return ""
    outcomes = {"rendered": 0, "expired": 0, "rejected": 0, "undecided": 0}
    held: dict[str, int] = {}
    for meta in drafts:
        raw_review, raw_hold = meta.get("review"), meta.get("hold")
        review: dict[str, Any] = raw_review if isinstance(raw_review, dict) else {}
        decision = str(review.get("decision") or "undecided")
        outcomes[decision] = outcomes.get(decision, 0) + 1
        if decision == "expired":
            hold: dict[str, Any] = raw_hold if isinstance(raw_hold, dict) else {}
            kind = _hold_kind(hold["reason"]) if hold.get("reason") else "none recorded"
            held[kind] = held.get(kind, 0) + 1
    parts = ", ".join(f"{n} {name}" for name, n in outcomes.items())
    line = f"Drafts this week: {parts} ({len(drafts)} drafts)"
    if held:
        ranked = sorted(held.items(), key=lambda kv: (-kv[1], kv[0]))
        line += "; expired after a hold: " + ", ".join(f"{k} {n}" for k, n in ranked)
    return line


def _week_drafts(channel_id: str, days: int = 7) -> list[dict[str, Any]]:
    import json as _json
    import os
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from core.batch_generation import _drafts_dir

    root = _drafts_dir(channel_id)
    cutoff = _dt.now() - _td(days=days)
    out: list[dict[str, Any]] = []
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        try:
            with open(os.path.join(root, name, "meta.json"), encoding="utf-8") as f:
                meta = _json.load(f)
            made = _dt.fromisoformat(str(meta.get("created_at")))
        except (OSError, ValueError, TypeError):
            continue
        if made.replace(tzinfo=None) >= cutoff:
            out.append(meta)
    return out


def claim_hold_lines(
    runs: list[Any], *, now: datetime | None = None, days: int = 7, limit: int = 5
) -> list[str]:
    """#1381: the share of the week's checked drafts an unsupported claim held, and up to
    `limit` of them (run and its first claim)."""
    from core.claim_types import blocking_unsupported

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    checked = 0
    held: list[tuple[int, str]] = []
    for run in runs:
        made = getattr(run, "created_at", None)
        if not isinstance(made, datetime):
            continue
        if (made if made.tzinfo else made.replace(tzinfo=timezone.utc)) < cutoff:
            continue
        try:
            features = json.loads(getattr(run, "features_json", "") or "{}") or {}
        except (TypeError, ValueError):
            continue
        verification = features.get("claim_verification") if isinstance(features, dict) else None
        if not isinstance(verification, dict):
            continue
        checked += 1
        claims = blocking_unsupported(verification)
        if claims:
            past = " (rendered past it)" if features.get("grounding_override") else ""
            held.append((int(run.id), f"{claims[0]}{past}"))
    if not checked:
        return []
    lines = [
        f"Held for a claim: {len(held)} of {checked} drafts this week "
        f"({round(100 * len(held) / checked)}%)"
    ]
    lines.extend(f"  run {run_id}: {claim}" for run_id, claim in sorted(held, reverse=True)[:limit])
    return lines


def _format_body(report: dict[str, Any]) -> str:
    if not report.get("ready"):
        return (
            f"Weekly report — {report['channel_id']}\n"
            f"  Not enough analytics yet ({report.get('n', 0)} videos with engagement; "
            f"need {_MIN_SAMPLES}+). Publish + sync metrics, then re-run."
        )

    lines = [
        f"Weekly intelligence — {report['channel_id']}",
        f"  {report['n']} videos analyzed · baseline engagement {report['baseline']:.1%}",
        "",
    ]
    first = shelf_decision(report)
    if first:
        lines.extend([f"  {first}", ""])
    decided = three_decisions(report)
    if decided:
        lines.append("  This week's three decisions:")
        lines.extend(f"    {d['line']}" for d in decided)
        lines.append("")
    for dim, groups in report["dimensions"].items():
        lines.append(f"  By {dim}:")
        for g in groups:
            marker = "+" if g["delta"] >= 0 else "-"
            lines.append(
                f"    [{marker}] {g['value']}: {g['avg']:.1%} "
                f"({g['delta']:+.1%} vs baseline, n={g['n']})"
            )
        lines.append("")

    if report.get("avg_cost") is not None:
        lines.append(
            f"  Cost: ~${report['avg_cost']:.3f}/video · "
            f"~${report['total_cost']:.2f} across {report['n']} tracked"
        )

    # Pillar 1 unit economics: contribution margin once revenue data exists.
    try:
        from core.unit_economics import channel_economics, summary_lines

        for line in summary_lines(channel_economics(report["channel_id"])):
            lines.append(f"  {line}")
    except Exception as exc:
        logger.debug("channel_economics skipped: %s", exc)

    # Pillar 2 calibration: is the pre-publish report card predictive yet?
    try:
        from core.claim_types import claim_type_coverage_line
        from core.grade_calibration import (
            build_calibration,
            coverage_line,
            significance_line,
            summary_line,
        )

        built = build_calibration(report["channel_id"])
    except Exception as exc:
        logger.debug("build_calibration skipped: %s", exc)
    else:
        # Each line fails open on its own so one refusal cannot hide the others.
        # (#826 found coverage_line was passed len(report["rows"]), a key build_report
        # never set, so #818's "N runs" never printed.)
        makers = (
            ("summary", lambda: summary_line(built)),
            # #824: the n that would settle the grade correlation, or "do not retune".
            ("significance", lambda: significance_line(built)),
            # #818: "collecting" reads like a volume problem; it is a history one.
            (
                "coverage",
                lambda: coverage_line(built, runs_total=getattr(built, "runs_total", 0) or None),
            ),
            ("claim types", lambda: claim_type_coverage_line(built.claim_type_coverage)),
        )
        for name, make in makers:
            try:
                extra: str | None = make()
            except Exception as exc:
                logger.debug("calibration %s line skipped: %s", name, exc)
                continue
            if isinstance(extra, str) and extra:
                lines.append(f"  {extra}")

    # #113: what was called at publish, scored once outcomes land.
    try:
        from core.predictions.ledger import summary_line as ledger_line

        ledger = ledger_line(report["channel_id"])
        if ledger:
            lines.append(f"  {ledger}")
    except Exception as exc:
        logger.debug("prediction ledger line skipped: %s", exc)

    try:  # #1463 (wave 119): runs that never finished, from the logs #1466 keeps
        from core.nightly_task import crash_count

        crashes = crash_count()
        lines.append(
            f"  Overnight crashes: {crashes} in 7 days (output/logs/crashes)"
            if crashes
            else "  Overnight crashes: none in 7 days"
        )
    except Exception as exc:
        logger.debug("crash count skipped: %s", exc)
    try:  # #1494 (wave 119): where each of the week's videos lost half its viewers
        from core.retention import week_drop_off_lines

        drops = week_drop_off_lines(report["channel_id"])
        if drops:
            lines.append("  Where each video lost half its viewers:")
            lines.extend(f"    {line}" for line in drops)
    except Exception as exc:
        logger.debug("drop-off lines skipped: %s", exc)
    try:  # #1381 (wave 120): how often an unsupported claim held a draft
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(report["channel_id"]) or []
        lines.extend(f"  {line}" for line in claim_hold_lines(runs))
    except Exception as exc:
        logger.debug("claim hold lines skipped: %s", exc)
    try:  # #1365 (wave 127): what overnight drafted this week, by kind
        week = _week_drafts(report["channel_id"])
        for line in (draft_mix_line(week), draft_outcome_line(week)):  # #1585
            if line:
                lines.append(f"  {line}")
    except Exception as exc:
        logger.debug("draft mix skipped: %s", exc)
    try:  # #1480 (wave 123): the fields health reads, against what the week wrote
        from analytics.field_audit import field_audit_lines

        lines.extend(f"  {line}" for line in field_audit_lines(report["channel_id"]))
    except Exception as exc:
        logger.debug("field audit lines skipped: %s", exc)

    actions = report.get("next_actions") or []
    if actions:
        lines.append("")
        lines.append("  Next actions:")
        for i, action in enumerate(actions, 1):
            lines.append(f"    {i}. {action}")
        lines.append("    (daily ideas: py -m scripts.ops coach)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rules-based weekly intelligence report")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    report = build_report(channel_id)
    rendered = format_report(report)
    print(rendered)
    # Pillar 4: land a copy in the vault (no-op without OBSIDIAN_VAULT_PATH).
    try:
        from core.vault.dossiers import write_weekly_report_note

        path = write_weekly_report_note(channel_id, rendered)
        if path:
            print(f"\n  (saved to vault: {path})")
        draft_path = write_community_post_draft(channel_id, report)
        if draft_path:
            print(f"  (community post draft: {draft_path})")
        digest_path = write_operator_digest(channel_id, report)
        if digest_path:
            print(f"  (operator digest: {digest_path})")
    except Exception as exc:
        logger.debug("write_weekly_report_note skipped: %s", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
