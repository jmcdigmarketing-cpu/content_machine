"""The prediction ledger: what the system called when a video published (#559, #113).

`analytics/youtube_metrics` used to refit `predict_engaged_rate` at every metrics sync,
on training rows that included the video's own outcome - so its "surprise" was fitted on
the answer and moved every time a later video landed. `freeze()` runs once, when the
upload succeeds (`publishing/youtube_publisher`), fits without the video itself, and
stores the entry in the run's features under `prediction_ledger`. Nothing refits it.

A video published before this has no entry; `frozen_engagement()` writes a leave-one-out
prediction for it once, stamped `backfilled: true` - its training rows include videos
published after it, so it is not what the system would have said at the time, and every
report that uses it says so.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.predictions.ledger")

LEDGER_KEY = "prediction_ledger"


def _record(run_id: int) -> Any:
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository().get(int(run_id))


def _quality(record: Any) -> dict[str, Any]:
    try:
        loaded = json.loads(getattr(record, "quality_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def stored(run_id: int | None) -> dict[str, Any] | None:
    """The frozen entry for a run, or None."""
    if not run_id:
        return None
    from core.run_features import load_features

    entry = load_features(run_id).get(LEDGER_KEY)
    return entry if isinstance(entry, dict) else None


def _engaged(run_id: int, channel_id: str, quality: dict[str, Any]) -> dict[str, Any] | None:
    from core.engagement_predictor import predict_engaged_rate

    if not quality:
        return None
    pred = predict_engaged_rate(channel_id, quality=quality, exclude_run_id=int(run_id))
    if pred is None:
        return None
    return {"rate": pred.rate, "band": pred.band, "n": pred.n, "note": pred.note}


def _length(
    record: Any, channel_id: str, topic: str, *, exclude_run_id: int | None = None
) -> dict[str, Any] | None:
    try:
        from core.length_recommender import _length_choice_from_run, get_recommended_length

        rec = (
            get_recommended_length(channel_id, topic, exclude_run_id=exclude_run_id)
            if exclude_run_id
            else get_recommended_length(channel_id, topic)
        )
        return {
            "recommended": rec.length_choice,
            "chosen": _length_choice_from_run(getattr(record, "timings_json", "") or ""),
            "expected": rec.avg_engaged_rate if rec.source == "analytics" else None,
            "source": rec.source,
            "n": rec.supporting_runs,
        }
    except Exception as exc:
        logger.debug("length recommendation not frozen: %s", exc)
        return None


def _used_at(run_id: int, channel_id: str) -> datetime | None:
    """When this run's video went (or goes) public, from its publish-log row."""
    try:
        from publishing.idempotency import idempotency_key
        from storage.repositories.publish_log import get_publish_log_repository

        row = get_publish_log_repository().find_by_idempotency(
            idempotency_key(int(run_id), channel_id)
        )
        return row.published_at if row is not None else None
    except Exception as exc:
        logger.debug("publish time unavailable for run %s: %s", run_id, exc)
        return None


def _post_time(
    run_id: int, channel_id: str, topic: str, *, exclude_run_id: int | None = None
) -> dict[str, Any] | None:
    """#916: the claim about the slot the video used - not `get_recommended_time`, which
    after the upload answers for the next open slot (this video's own is reserved)."""
    used_at = _used_at(run_id, channel_id)
    if used_at is None:
        return None
    try:
        from analytics.post_timing import slot_claim

        claim = slot_claim(channel_id, topic, used_at, exclude_run_id=exclude_run_id)
    except Exception as exc:
        logger.debug("post-time claim not frozen: %s", exc)
        return None
    try:
        from core.experiments import assignment_for_run

        arm = assignment_for_run(run_id)
        if arm and arm.get("lever") == "post_time":
            claim["arm"] = arm.get("arm")  # #912
            if arm.get("offset_hours") is not None:
                claim["offset_hours"] = arm["offset_hours"]  # #567
    except Exception as exc:
        logger.debug("post-time arm unavailable: %s", exc)
    return claim


def _best_bet(record: Any) -> dict[str, Any] | None:
    """The best-bet card's call for this run, from `features["best_bet"]` (#909)."""
    try:
        features = json.loads(getattr(record, "features_json", None) or "{}")
    except (TypeError, ValueError):
        return None
    pick = features.get("best_bet") if isinstance(features, dict) else None
    if not isinstance(pick, dict):
        return None
    rank = pick.get("picked")
    offered = pick.get("offered") or []
    chosen = offered[rank - 1] if isinstance(rank, int) and 1 <= rank <= len(offered) else {}
    return {
        "picked": rank is not None,
        "rank": rank,
        "expected": chosen.get("expected") if chosen else None,
        "source": chosen.get("source") if chosen else None,
        "by": str(pick.get("by") or "operator"),  # #913: records before it were the card's
    }


def _grade(quality: dict[str, Any]) -> dict[str, Any] | None:
    """The grade shown for this draft: its #808 snapshot when there is one."""
    score = quality.get("grade_score")
    if isinstance(score, int | float) and not isinstance(score, bool):
        return {"score": score, "letter": str(quality.get("grade_letter") or "")}
    try:
        from core.video_grade import grade_from_parts

        grade = grade_from_parts(quality=quality)
        return {"score": round(grade.score, 1), "letter": grade.letter}
    except Exception as exc:
        logger.debug("grade not frozen: %s", exc)
        return None


def freeze(
    run_id: int | None,
    channel_id: str,
    *,
    backfilled: bool = False,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Write the run's ledger entry once and return it; an existing entry is returned as is.

    Never raises: a publish must not fail because a prediction could not be recorded.
    """
    if not run_id:
        return None
    try:
        existing = stored(run_id)
        if existing is not None:
            return existing
        record = _record(run_id)
        if record is None:
            return None
        quality = _quality(record)
        topic = str(getattr(record, "selected_topic", "") or "")
        # #560: a backfilled claim is made after the outcome exists, so every recommender
        # fits without this video (the engaged-rate fit always does).
        leave_out = int(run_id) if backfilled else None
        entry: dict[str, Any] = {
            "frozen_at": (now or datetime.now(timezone.utc)).isoformat(),
            "backfilled": bool(backfilled),
            "engaged_rate": _engaged(run_id, channel_id, quality),
            # #113: the recommenders' own claims, kept beside it.
            "length": _length(record, channel_id, topic, exclude_run_id=leave_out),
            "post_time": _post_time(int(run_id), channel_id, topic, exclude_run_id=leave_out),
            "grade": _grade(quality),
            "best_bet": _best_bet(record),  # #909
        }
        if backfilled and entry["engaged_rate"] is None:
            return entry  # too few measured videos yet; a later sync may still backfill it
        from core.run_features import merge_features

        merge_features(run_id, {LEDGER_KEY: entry})
        return entry
    except Exception as exc:
        logger.debug("prediction ledger not frozen for run %s: %s", run_id, exc)
        return None


def frozen_engagement(run_id: int | None, channel_id: str) -> dict[str, Any] | None:
    """`{rate, band, n, note}` as frozen for this run; backfilled once when absent."""
    entry = stored(run_id)
    if entry is None:
        entry = freeze(run_id, channel_id, backfilled=True)
    engaged = (entry or {}).get("engaged_rate")
    return engaged if isinstance(engaged, dict) else None


# --- #113: score the ledger once outcomes land -----------------------------------------
_MIN_MEASURED = 5


def ledger_rows(channel_id: str) -> list[dict[str, Any]]:
    """One row per measured run that has a ledger entry: each call beside the outcome."""
    from core.engagement_predictor import run_engagement_map
    from storage.repositories.content_runs import get_content_run_repository

    outcomes = run_engagement_map(channel_id)
    rows: list[dict[str, Any]] = []
    for run in get_content_run_repository().list_for_channel(channel_id):
        rate = outcomes.get(int(run.id))
        entry = stored(int(run.id))
        if rate is None or entry is None:
            continue
        row: dict[str, Any] = {
            "run_id": int(run.id),
            "actual": float(rate),
            "backfilled": bool(entry.get("backfilled")),
        }
        engaged = entry.get("engaged_rate") or {}
        if engaged.get("rate") is not None:
            row["engaged_error"] = float(rate) - float(engaged["rate"])
            row["engaged_band"] = float(engaged.get("band") or 0.0)
            row["inside_band"] = abs(row["engaged_error"]) <= row["engaged_band"]
        length = entry.get("length") or {}
        if length.get("expected") is not None and length.get("chosen") == length.get("recommended"):
            row["length_error"] = float(rate) - float(length["expected"])
        post = entry.get("post_time") or {}
        if post and "used_at" not in post:
            row["post_before_916"] = True  # scored the next slot, not this video's
        elif post.get("expected") is not None and post.get("on_slot"):
            row["post_error"] = float(rate) - float(post["expected"])
        if post.get("on_slot") is False:
            row["post_off_slot"] = True
        bet = entry.get("best_bet") or {}
        if bet:
            row["best_bet_picked"] = bool(bet.get("picked"))
            row["best_bet_by"] = str(bet.get("by") or "operator")
            if (
                bet.get("picked")
                and bet.get("source") == "analytics"
                and bet.get("expected") is not None
            ):
                row["best_bet_error"] = float(rate) - float(bet["expected"])
        grade = entry.get("grade") or {}
        if grade.get("score") is not None:
            row["grade"] = float(grade["score"])
        rows.append(row)
    return sorted(rows, key=lambda r: r["run_id"])


def _frozen_count(channel_id: str) -> int:
    from storage.repositories.content_runs import get_content_run_repository

    return sum(
        1 for run in get_content_run_repository().list_for_channel(channel_id) if stored(run.id)
    )


def _error_line(label: str, errors: list[float]) -> str:
    if len(errors) < _MIN_MEASURED:
        return f"  {label}: collecting (n={len(errors)}, a rate needs {_MIN_MEASURED})"
    mean_abs = sum(abs(e) for e in errors) / len(errors)
    bias = sum(errors) / len(errors)
    return (
        f"  {label}: mean |error| {mean_abs * 100:.1f}pp, bias {bias * 100:+.1f}pp "
        f"(n={len(errors)})"
    )


def report_lines(channel_id: str) -> list[str]:
    """`ops predictions`: each recommender's frozen claim against what happened."""
    from core.grade_calibration import _pearson, n_for_significance

    rows = ledger_rows(channel_id)
    frozen = _frozen_count(channel_id)
    backfilled = sum(1 for r in rows if r["backfilled"])
    lines = [
        f"Prediction ledger (#113) - {channel_id}: {frozen} frozen, {len(rows)} measured"
        + (f" ({backfilled} backfilled - fitted after the fact)" if backfilled else "")
    ]
    # #560: the headline error is forward rows only - claims frozen before the outcome.
    forward = [r for r in rows if not r["backfilled"]]
    back = [r for r in rows if r["backfilled"]]

    def _claim(label: str, key: str, detail: list[str] | None = None) -> None:
        lines.append(_error_line(label, [r[key] for r in forward if key in r]))
        lines.extend(detail or [])
        late = [r[key] for r in back if key in r]
        if late:
            lines.append("    " + _error_line("backfilled, left out of the fit", late).strip())

    measured = [r for r in forward if "engaged_error" in r]
    band_line: list[str] = []
    if len(measured) >= _MIN_MEASURED:
        band = sum(r["engaged_band"] for r in measured) / len(measured)
        mean_abs = sum(abs(r["engaged_error"]) for r in measured) / len(measured)
        inside = sum(1 for r in measured if r.get("inside_band"))
        band_line.append(
            f"    claimed band +/-{band * 100:.1f}pp (in-sample spread) vs forward "
            f"|error| {mean_abs * 100:.1f}pp; inside the band {inside}/{len(measured)}"
        )
    _claim("engagement predictor (frozen before the outcome)", "engaged_error", band_line)
    _claim("length recommender (when followed)", "length_error")
    _claim("post-time slot (videos on a slot)", "post_error")
    off_slot = sum(1 for r in rows if r.get("post_off_slot"))
    before = sum(1 for r in rows if r.get("post_before_916"))
    if off_slot or before:
        parts = []
        if off_slot:
            parts.append(f"{off_slot} off-slot (py -m scripts.ops experiment)")
        if before:
            parts.append(f"{before} frozen before #916, not scored")
        lines.append("    " + "; ".join(parts))
    lines.append(
        _error_line(
            "best-bet pick (analytics)",
            [r["best_bet_error"] for r in rows if "best_bet_error" in r],
        )
    )
    picked = [r["actual"] for r in rows if r.get("best_bet_picked") is True]
    own = [r["actual"] for r in rows if r.get("best_bet_picked") is False]
    if picked or own:

        def _mean(xs: list[float]) -> str:
            return f"{sum(xs) / len(xs) * 100:.1f}%" if xs else "-"

        by_you = sum(
            1 for r in rows if r.get("best_bet_picked") is True and r["best_bet_by"] == "operator"
        )
        lines.append(
            f"    picked {len(picked)} (mean {_mean(picked)}; {by_you} by you, "
            f"{len(picked) - by_you} automatic) vs own topic {len(own)} (mean {_mean(own)})"
            + ("" if min(len(picked), len(own)) >= _MIN_MEASURED else " - collecting")
        )
    try:
        from analytics.view_curve import report_line

        lines.append(report_line(channel_id))  # #563: the faster outcome
    except Exception as exc:
        logger.debug("time-to-first-views line skipped: %s", exc)
    try:
        from core.engagement import basis_line, low_view_line

        lines.append(basis_line(channel_id))  # #920
        lines.append(low_view_line(channel_id))  # #564
    except Exception as exc:
        logger.debug("low-view line skipped: %s", exc)
    graded = [(r["grade"], r["actual"]) for r in rows if "grade" in r]
    if len(graded) < _MIN_MEASURED:
        lines.append(f"  grade vs engaged rate: collecting (n={len(graded)})")
    else:
        r = _pearson([g for g, _ in graded], [a for _, a in graded])
        need = n_for_significance(r)
        tail = f"; n={need} would settle it" if need and need > len(graded) else ""
        lines.append(
            f"  grade vs engaged rate: r={r:+.2f} (n={len(graded)}){tail}"
            if r is not None
            else f"  grade vs engaged rate: undefined (n={len(graded)}; no variance)"
        )
    return lines


def summary_line(channel_id: str) -> str | None:
    """One line for the weekly report; None until anything has been frozen."""
    try:
        frozen = _frozen_count(channel_id)
        if not frozen:
            return None
        measured = len(ledger_rows(channel_id))
        return (
            f"prediction ledger: {frozen} frozen, {measured} measured "
            "(py -m scripts.ops predictions)"
        )
    except Exception as exc:
        logger.debug("prediction ledger summary skipped: %s", exc)
        return None
