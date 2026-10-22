"""Channel Health Agent (Pillar 5) - one Green/Yellow/Red read per channel.

Composes the signals the other pillars already expose into a single operational
health verdict - the "is this channel OK right now?" glance. Rules only, no LLM;
read-only and fail-open per sub-score (the `creator_coach` pattern): a subsystem
that errors reads **"unknown"** (#1472), never RED and never crashes the view.

Sub-scores (each `green|yellow|red` + a one-line rationale):
- **engagement** - recent engaged-rate vs the channel baseline (trend).
- **cadence** - headroom under `MAX_VIDEOS_PER_WEEK` when one is set (decision 65: none by default).
- **authenticity** - mean authenticity score over recent runs' `quality_json`.
- **reliability** - Apify/LLM/signal breakers + budgets (`core/reliability.py`).
- **cost** - per-video cost, and margin when revenue exists (`core/unit_economics.py`).
- **data quality** - `core/data_quality.py` warnings (signal streaks, join gaps).

Overall folds worst-first (any red ⇒ red, any yellow ⇒ yellow). **Thin data reads
yellow "collecting," never green** - health is earned, not defaulted on.

Surfaced via `py -m scripts.ops health` and a line in `ops daily-brief`. Each run keeps one
line a day in `data/health_history_<channel>.jsonl` (#1475); `ops health --history` prints it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.channel_health")

GREEN, YELLOW, RED = "green", "yellow", "red"
# #1472 (S18): a line whose input could not be read says so - it is never RED, and it holds
# the overall at YELLOW, since a check that read nothing cannot call the channel green.
UNKNOWN = "unknown"
# #1479 (S18): every colour's threshold, in one place. Changing one bumps THRESHOLDS_VERSION;
# each day's history line carries it, so two days are compared on the same rules.
THRESHOLDS_VERSION = 1
THRESHOLDS: dict[str, float] = {
    "engagement_min_views": 20,  # #1238: run 119 - 3 views, 0% engaged - turned it RED alone
    "long_video_seconds": 180.0,  # #1491: past a Short's limit, read apart
    "engagement_yellow_drop": 0.01,  # recent under the baseline by more than 1pp: softening
    "engagement_red_drop": 0.05,  # by more than 5pp: declining
    "cadence_goal": 7,  # S13: 7 a week (#1435)
    "cadence_yellow_under": 5,
    "cadence_near_cap_room": 1,  # with a cap set: this many left or fewer is near it
    "authenticity_red_under": 55,  # #815: the binary gate sum
    "authenticity_yellow_under": 72,
    "cost_yellow_over_usd": 0.10,  # a video's cost, estimated or entered
    "data_quality_red_at": 3,  # warnings
}
_RANK = {GREEN: 0, UNKNOWN: 1, YELLOW: 1, RED: 2}
_MARK = {GREEN: "+", YELLOW: "~", RED: "!", UNKNOWN: "?"}  # cp1252-safe (no forced UTF-8)
HISTORY_TEMPLATE = os.path.join(DATA_DIR, "health_history_{channel}.jsonl")  # #1475


@dataclass
class HealthSub:
    name: str
    status: str
    detail: str
    why: list[str] = field(default_factory=list)  # #1271: what a falling metric has in common
    source: str = ""  # #1471: where the number came from


@dataclass
class HealthReport:
    channel_id: str
    overall: str = YELLOW
    subs: list[HealthSub] = field(default_factory=list)


def _worst(statuses: list[str]) -> str:
    worst = max(statuses, key=lambda s: _RANK.get(s, 1)) if statuses else YELLOW
    return YELLOW if worst == UNKNOWN else worst


def _t(name: str) -> float:
    return THRESHOLDS[name]


def _seconds(info: dict[str, object] | None) -> float:
    try:
        return float((info or {}).get("seconds") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _engagement_sub(channel_id: str) -> HealthSub:
    from core.engagement_predictor import run_engagement_map

    min_views = int(_t("engagement_min_views"))
    measured = run_engagement_map(channel_id, min_views=min_views)  # {run_id: rate}
    everything = run_engagement_map(channel_id)
    left = len(everything) - len(measured)
    # #1491 (wave 114): the engaged rate is the average view % (#920), which falls with length;
    # run 120, a 406 s NBA video at 11%, sat in the same baseline as 40 s Shorts. Shorts are read
    # against Shorts; long videos are counted apart.
    info = _engagement_info(list(measured))
    long_ids = {rid for rid in measured if _seconds(info.get(rid)) > _t("long_video_seconds")}
    rates = {rid: rate for rid, rate in measured.items() if rid not in long_ids}
    if len(rates) < 3:
        return HealthSub("engagement", YELLOW, f"collecting ({len(rates)} measured)")
    ordered = [rates[rid] for rid in sorted(rates)]
    baseline = sum(ordered) / len(ordered)
    recent = ordered[-5:]
    recent_mean = sum(recent) / len(recent)
    delta = recent_mean - baseline
    span = sorted(rates)[-5:]
    # #1291: "recent" was runs 109-133 (Oct 1-10) while four newer videos had no rate yet.
    # #1476 (wave 120): with their dates, and the newest video that has a rate at all.
    detail = (
        f"recent {recent_mean * 100:.1f}% ({window_text(span, _made([*span, max(measured)]), newest=max(measured))}) "
        f"vs baseline {baseline * 100:.1f}% ({delta * 100:+.1f}pp)"
    )
    if long_ids:
        held = sorted(measured[rid] for rid in long_ids)
        plural = "video" if len(long_ids) == 1 else "videos"
        detail += (
            f"; {len(long_ids)} long {plural} read apart (median {held[len(held) // 2] * 100:.0f}% - "
            "a long video holds a smaller share)"
        )
    if left > 0:
        plural = "video" if left == 1 else "videos"
        detail += f"; {left} {plural} under {min_views} views left out"
    unmeasured = _unmeasured_recent(channel_id, measured=set(everything))
    if unmeasured:
        plural = "video" if len(unmeasured) == 1 else "videos"
        detail += (
            f"; {len(unmeasured)} newer {plural} not measured yet "
            f"(runs {', '.join(str(r) for r in unmeasured)})"
        )
        try:  # wave 113: lag or no sync - the line said neither
            from analytics.sync_metrics import sync_note

            detail += f" - {sync_note(channel_id)}"
        except Exception as exc:
            logger.debug("sync note skipped: %s", exc)
    if delta < -_t("engagement_yellow_drop"):
        why = engagement_why(rates, {rid: info[rid] for rid in rates if rid in info})
        red = delta < -_t("engagement_red_drop")
        status, word = (RED, "declining") if red else (YELLOW, "softening")
        return HealthSub("engagement", status, f"{word} - " + detail, why=why)
    return HealthSub("engagement", GREEN, "steady/up - " + detail)


def _unmeasured_recent(channel_id: str, *, measured: set[int], days: float = 7.0) -> list[int]:
    """Public videos of the last ``days`` with no engaged rate yet - YouTube's numbers lag."""
    from datetime import datetime, timedelta, timezone

    try:
        from storage.repositories.publish_log import get_publish_log_repository

        rows = get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
    except Exception as exc:
        logger.debug("unmeasured videos unread: %s", exc)
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out: set[int] = set()
    for row in rows:
        run_id = getattr(row, "content_run_id", None)
        when = getattr(row, "published_at", None)
        if isinstance(when, str):
            try:
                when = datetime.fromisoformat(when.replace("Z", "+00:00"))
            except ValueError:
                when = None
        if not run_id or int(run_id) in measured or not isinstance(when, datetime):
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= since:
            out.add(int(run_id))
    return sorted(out)


def _engagement_info(run_ids: list[int]) -> dict[int, dict[str, object]]:
    """Per run: domain, video length, hook score and footage - what `engagement_why` compares."""
    import json

    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    out: dict[int, dict[str, object]] = {}
    for run_id in run_ids:
        try:
            run = repo.get(int(run_id))
            features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
            quality = json.loads(getattr(run, "quality_json", "") or "{}") if run else {}
        except Exception as exc:
            logger.debug("engagement info for run %s unread: %s", run_id, exc)
            continue
        out[int(run_id)] = {
            "domain": features.get("domain") or "",
            "seconds": (features.get("technical_qc") or {}).get("video_duration"),
            "hook": quality.get("hook_score"),
            "footage": str(quality.get("footage") or "").split(" ")[0],
        }
    return out


def _length_band(info: dict[str, object]) -> str:
    try:
        seconds = float(info.get("seconds") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return "over 75 s" if seconds > 75 else ("under 45 s" if seconds < 45 else "45-75 s")


def _hook_band(info: dict[str, object]) -> str:
    try:
        hook = float(info.get("hook") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if hook <= 0:
        return ""
    return "a hook under 70" if hook < 70 else "a hook of 70+"


_WHY_FACTORS = (
    ("run", _length_band),
    ("are", lambda i: f"{i.get('domain')} videos" if i.get("domain") else ""),
    ("have", _hook_band),
    ("use", lambda i: f"{i.get('footage')} footage" if i.get("footage") else ""),
)


def engagement_why(rates: dict[int, float], info: dict[int, dict[str, object]]) -> list[str]:
    """#1271: the one thing most of the last five share that the channel's better videos do not
    - "4 of the last 5 run over 75 s: those average 20% against 35% for the rest". [] when no
    such thing stands out, or with too few videos to say."""
    from collections import Counter

    ordered = sorted(rates)
    recent = ordered[-5:]
    if len(ordered) < 8 or len(recent) < 3:
        return []
    best: tuple[float, str] | None = None
    for verb, band in _WHY_FACTORS:
        groups = {run: band(info.get(run, {})) for run in ordered}
        labels = Counter(groups[run] for run in recent if groups[run])
        if not labels:
            continue
        label, count = labels.most_common(1)[0]
        inside = [rates[run] for run in ordered if groups[run] == label]
        rest = [rates[run] for run in ordered if groups[run] and groups[run] != label]
        if count < 3 or len(inside) < 2 or not rest:
            continue
        mean_in, mean_rest = sum(inside) / len(inside), sum(rest) / len(rest)
        gap = mean_rest - mean_in
        if gap <= 0.02:
            continue
        line = (
            f"{count} of the last {len(recent)} {verb} {label}: those average {mean_in:.0%} "
            f"against {mean_rest:.0%} for the rest"
        )
        if best is None or gap * count > best[0]:
            best = (gap * count, line)
    if best:
        return [best[1]]
    # Live, 2026-10-17: no shared trait (the long videos did better) - one video drags it.
    weakest = min(recent, key=lambda run: rates[run])
    baseline = sum(rates[run] for run in ordered) / len(ordered)
    if baseline - rates[weakest] <= 0.05:
        return []
    traits = info.get(weakest, {})
    parts = [str(traits.get("domain") or "")]
    try:
        seconds = float(traits.get("seconds") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds > 0:
        parts.append(f"{seconds:.0f} s")
    hook = traits.get("hook")
    if isinstance(hook, (int, float)) and hook:
        parts.append(f"hook {hook:.0f}")
    described = ", ".join(part for part in parts if part)
    return [
        f"no one thing the last {len(recent)} share - the weakest is run {weakest}"
        + (f" ({described})" if described else "")
        + f" at {rates[weakest]:.0%}, against {baseline:.0%}"
    ]


def _cadence_sub(channel_id: str) -> HealthSub:
    from core.cadence import cadence_status

    c = cadence_status(channel_id)
    if not c.capped:  # decision 65: no cap - so S13's floor is the rule (#1435)
        # #1435 (wave 117): it said "17 in the 7-day window" for 15 published in the last 7 days
        # plus 3 scheduled in the next 7, and nothing was ever short.
        detail = (
            f"{c.recent} published in the last {c.window_days} days, {c.upcoming} scheduled in "
            f"the next {c.window_days}"
        )
        floor, goal = int(_t("cadence_yellow_under")), int(_t("cadence_goal"))
        if c.recent < floor:
            return HealthSub("cadence", YELLOW, f"{detail} - under {floor} a week")
        if c.recent < goal:
            detail += f" - short of {goal} a week"
        return HealthSub("cadence", GREEN, detail)
    room = c.cap - c.total
    detail = f"{c.total}/{c.cap} in the {c.window_days}-day window"
    if c.total > c.cap:
        return HealthSub("cadence", RED, f"over cap - {detail} (authenticity/policy risk)")
    if room <= _t("cadence_near_cap_room"):
        return HealthSub("cadence", YELLOW, f"near cap - {detail}")
    return HealthSub("cadence", GREEN, f"room for {room} more - {detail}")


def _authenticity_sub(channel_id: str) -> HealthSub:
    import json

    from config.channels import resolve_channel_id
    from core.run_quality import authenticity_gate_value
    from storage.repositories.content_runs import get_content_run_repository

    channel = resolve_channel_id(channel_id)
    scores: list[float] = []
    for run in get_content_run_repository().list_for_channel(channel)[:15]:
        try:
            q = json.loads(run.quality_json or "{}")
        except Exception as exc:
            logger.debug("Unreadable quality_json on run %s: %s", run.id, exc)
            continue
        # #815: the binary gate sum, not #804's continuous grade — the 55/72
        # thresholds below were set when the gate sum was the only number.
        val = authenticity_gate_value(q)
        if val is not None:
            scores.append(val)
    if len(scores) < 3:
        return HealthSub("authenticity", YELLOW, f"collecting ({len(scores)} scored)")
    mean = sum(scores) / len(scores)
    detail = f"mean {mean:.0f}/100 over {len(scores)} recent"
    if mean < _t("authenticity_red_under"):
        return HealthSub("authenticity", RED, "thin/synthetic - " + detail)
    if mean < _t("authenticity_yellow_under"):
        return HealthSub("authenticity", YELLOW, "watch - " + detail)
    return HealthSub("authenticity", GREEN, "solid - " + detail)


def _reliability_sub() -> HealthSub:
    from core.reliability import gather

    data = gather()
    problems: list[str] = []
    apify = data.get("apify") or {}
    if apify.get("disabled") or apify.get("persisted_exhausted"):
        problems.append("Apify off")
    llm = data.get("llm") or {}
    disabled = llm.get("disabled_providers") or {}
    if disabled:
        problems.append(f"LLM {len(disabled)} provider(s) off")
    sig = data.get("signals") or {}
    persisted = sig.get("persisted") or {}
    if persisted:
        problems.append(f"{len(persisted)} signal(s) disabled")
    budget = llm.get("daily_budget")
    spend = llm.get("spend_today")
    over_budget = budget and spend and spend >= budget
    if over_budget:
        problems.append("LLM over daily budget")
    if not problems:
        return HealthSub("reliability", GREEN, "no breakers tripped")
    # LLM fully off would stop generation → red; degraded paid signals → yellow.
    status = RED if over_budget or "LLM" in " ".join(problems) else YELLOW
    return HealthSub("reliability", status, "; ".join(problems))


def _uploaded_videos() -> int:
    """#1478: videos uploaded on every channel - the spend entered is the project's."""
    from config.channels import list_channel_ids
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    repo = get_publish_log_repository()
    return sum(
        1
        for channel in list_channel_ids()
        for row in repo.list_uploaded_for_channel(channel) or []
        if str(getattr(row, "youtube_video_id", "") or "").strip() and not is_seeded(row)
    )


_SPEND_SOURCE = "the spend you entered (ops spend), shared over every video, and the runs' API cost"


def _entered_cost_sub(econ: Any, spent: dict[str, Any], videos: int) -> HealthSub:
    """#1478 (S18): what was paid - subscriptions, credits, ads - over every video made."""
    per_video = float(spent["total"]) / videos
    estimate = econ.total_cost / len(econ.videos)
    detail = (
        f"${per_video:.2f}/video from the spend you entered (${float(spent['total']):.2f} over "
        f"{videos} videos, every channel); API estimate ${estimate:.3f}/video"
    )
    revenue = econ.total_revenue if isinstance(econ.total_revenue, (int, float)) else None
    if revenue:
        covered = sum(1 for v in econ.videos if getattr(v, "revenue_usd", None) is not None)
        margin = revenue - per_video * covered
        if margin < 0:
            return HealthSub("cost", RED, f"negative margin ${margin:+.2f} against the spend "
                             f"you entered - {detail}", source=_SPEND_SOURCE)  # fmt: skip
        return HealthSub("cost", GREEN, f"positive margin ${margin:+.2f} - {detail}",
                         source=_SPEND_SOURCE)  # fmt: skip
    note = " (revenue $0.00 - not monetized yet)" if revenue == 0 else " (revenue not synced)"
    status = GREEN if per_video <= _t("cost_yellow_over_usd") else YELLOW
    return HealthSub("cost", status, detail + note, source=_SPEND_SOURCE)


def _cost_sub(channel_id: str) -> HealthSub:
    from core.money.ledger import total_spent
    from core.unit_economics import channel_economics

    econ = channel_economics(channel_id)
    if not econ.videos:
        return HealthSub("cost", YELLOW, "collecting (no uploaded videos)")
    try:
        spent = total_spent()
        videos = _uploaded_videos() if spent.get("count") and spent.get("total") else 0
    except Exception as exc:
        logger.debug("entered spend unread: %s", exc)
        spent, videos = {}, 0
    if videos:
        return _entered_cost_sub(econ, spent, videos)
    avg = econ.total_cost / len(econ.videos)
    cheap = avg <= _t("cost_yellow_over_usd")
    margin = econ.total_margin
    if margin is not None and all(getattr(v, "revenue_usd", None) == 0 for v in econ.videos):
        # #1472: YouTube reports $0.00 for a channel that is not monetized - no revenue, not a
        # loss, so the line reads on cost alone.
        return HealthSub("cost", GREEN if cheap else YELLOW,
                         f"API estimate ${avg:.3f}/video (revenue $0.00 - not monetized yet)")  # fmt: skip
    if margin is not None:
        if margin < 0:
            return HealthSub("cost", RED, f"negative margin ${margin:+.2f} (rev < cost)")
        return HealthSub("cost", GREEN, f"positive margin ${margin:+.2f}, ${avg:.3f}/video")
    return HealthSub(
        "cost",
        GREEN if cheap else YELLOW,
        f"API estimate ${avg:.3f}/video (revenue not synced; what you paid is not entered - "
        "py -m scripts.ops spend add)",
    )


def _data_quality_sub(channel_id: str) -> HealthSub:
    from core.data_quality import warnings

    warns = warnings(channel_id=channel_id)
    if not warns:
        return HealthSub("data quality", GREEN, "no issues")
    status = RED if len(warns) >= _t("data_quality_red_at") else YELLOW
    return HealthSub("data quality", status, f"{len(warns)} warning(s): {warns[0]}")


# #1471 (wave 120): where each line's number comes from - health read RED on a number
# nobody stored (S18), and no line said what it had read.
HEALTH_SOURCES = {
    "engagement": "the publish log's synced metrics",
    "cadence": "the publish log",
    "authenticity": "the last 15 runs' quality",
    "reliability": "the breakers and quota state, read now",
    "cost": "the runs' recorded API cost",
    "data quality": "the last 25 runs, the publish log and signal traces",
}


_CHECKS = (
    ("engagement", lambda ch: _engagement_sub(ch)),
    ("cadence", lambda ch: _cadence_sub(ch)),
    ("authenticity", lambda ch: _authenticity_sub(ch)),
    ("reliability", lambda _ch: _reliability_sub()),
    ("cost", lambda ch: _cost_sub(ch)),
    ("data quality", lambda ch: _data_quality_sub(ch)),
)


def build_health(channel_id: str | None = None) -> HealthReport:
    """Assemble the per-channel health verdict (read-only, fail-open per sub)."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    report = HealthReport(channel_id=channel)
    for name, check in _CHECKS:
        try:
            report.subs.append(check(channel))
        except Exception as exc:
            logger.debug("health sub '%s' skipped: %s", name, exc)
            source = HEALTH_SOURCES.get(name, "its input")
            report.subs.append(HealthSub(name, UNKNOWN, f"unknown - could not read {source}"))
    for sub in report.subs:
        sub.source = sub.source or HEALTH_SOURCES.get(sub.name, "")  # #1471
    report.overall = _worst([s.status for s in report.subs])
    # Thin data must not read green: if every informative sub is "collecting/n/a",
    # hold at yellow.
    if report.overall == GREEN and all(
        ("collecting" in s.detail or s.status == UNKNOWN)
        for s in report.subs
        if s.name in ("engagement", "authenticity", "cost")
    ):
        report.overall = YELLOW
    return report


def render_health(report: HealthReport) -> str:
    lines = [
        f"Channel health - {report.channel_id}: {_MARK.get(report.overall, '~')} "
        f"{report.overall.upper()}",
        "=" * 52,
    ]
    for s in report.subs:
        source = f" (from {s.source})" if s.source else ""  # #1471
        lines.append(
            f"  {_MARK.get(s.status, '~')} {s.name:<13} {s.status.upper():<7} {s.detail}{source}"
        )
        lines.extend(f"      why: {line}" for line in s.why)
    lines.append(f"  (thresholds v{THRESHOLDS_VERSION}: core/channel_health.THRESHOLDS)")  # #1479
    return "\n".join(lines)


def health_line(report: HealthReport) -> str:
    """One-line summary for embedding (e.g. daily-brief)."""
    reds = [s.name for s in report.subs if s.status == RED]
    yellows = [s.name for s in report.subs if s.status == YELLOW]
    unknown = [s.name for s in report.subs if s.status == UNKNOWN]
    tail = ""
    if reds:
        tail = " - red: " + ", ".join(reds)
    elif yellows:
        tail = " - watch: " + ", ".join(yellows)
    if unknown:  # #1472
        tail += " - unknown: " + ", ".join(unknown)
    return f"Health: {report.overall.upper()}{tail}"


def _history_path(channel_id: str) -> str:
    return HISTORY_TEMPLATE.format(channel=channel_id)


def _history_rows(channel_id: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    try:
        with open(_history_path(channel_id), encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("date"):
                    rows.append(row)
    except OSError:
        return []
    return rows


def record_history(report: HealthReport, *, today: date | None = None) -> None:
    """#1475 (S18): one line a day per channel - the day's last read replaces its earlier one,
    so a run on Tuesday morning and another at night leave Tuesday's last colours."""
    try:  # fail-open, as every read here is: a history that cannot be written loses one day
        day = (today or date.today()).isoformat()
        row: dict[str, object] = {
            "date": day,
            "overall": str(report.overall),
            "subs": {str(s.name): str(s.status) for s in report.subs},
            "thresholds": THRESHOLDS_VERSION,  # #1479
        }
        rows = [r for r in _history_rows(str(report.channel_id)) if r.get("date") != day]
        rows.append(row)
        rows.sort(key=lambda r: str(r.get("date")))
        path = _history_path(str(report.channel_id))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rows)
        os.replace(tmp, path)
    except Exception as exc:
        logger.debug("health history not written: %s", exc)


def history_lines(channel_id: str, *, days: int = 14) -> list[str]:
    """#1475: newest first - "10-22 GREEN  engagement +, cadence ~, cost ?". #1479: a day read
    on other thresholds than the day before it says so - "[thresholds v2]"."""
    out: list[str] = []
    rows = sorted(_history_rows(channel_id), key=lambda r: str(r["date"]), reverse=True)
    for at, row in enumerate(rows[:days]):
        subs = row.get("subs")
        marks = ", ".join(
            f"{name} {_MARK.get(str(status), '~')}"
            for name, status in (subs.items() if isinstance(subs, dict) else ())
        )
        line = f"{str(row['date'])[5:]} {str(row.get('overall', '')).upper():<7} {marks}"
        older = rows[at + 1] if at + 1 < len(rows) else None
        if older is not None and older.get("thresholds") != row.get("thresholds"):
            line += f" [thresholds v{row.get('thresholds', '?')}]"
        out.append(line)
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Channel health (Green/Yellow/Red)")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args(argv)
    print(render_health(build_health(args.channel)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _day(when: datetime) -> str:
    return f"{when:%b} {when.day}"


def window_text(span: list[int], made: dict[int, datetime], *, newest: int | None = None) -> str:
    """#1476 (wave 120): "runs 131-157, Oct 9-17; newest measured run 169 (Oct 19)" - the window
    said its run numbers only, and nobody reads a run number as a date."""
    text = f"runs {span[0]}-{span[-1]}"
    first, last = made.get(span[0]), made.get(span[-1])
    if first and last:
        same = first.month == last.month
        text += f", {_day(first)}-{last.day if same else _day(last)}"
    if newest is not None and newest != span[-1]:
        text += f"; newest measured run {newest}" + (
            f" ({_day(made[newest])})" if made.get(newest) else ""
        )
    return text


def _made(run_ids: list[int]) -> dict[int, datetime]:
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    out: dict[int, datetime] = {}
    for run_id in set(run_ids):
        try:
            when = getattr(repo.get(int(run_id)), "created_at", None)
        except Exception:
            when = None
        if isinstance(when, datetime):
            out[int(run_id)] = when
    return out
