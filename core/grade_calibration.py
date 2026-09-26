"""Grade calibration loop (Pillar 2, data-gated).

Closes the audit gap "no pre-publish score is calibrated against outcomes":

- **Actual grade** — a published run's realized engaged-rate expressed as a
  percentile of the channel's measured distribution (0–100, comparable to the
  pre-publish report card).
- **Grade↔engagement correlation** — Pearson r between pre-publish grades and
  realized engaged-rates: the "is the report card meaningful yet?" number.
- **Thumbnail join** — the `thumbnail_scores` table finally gets its reader:
  correlation of pre-publish thumbnail `overall` vs realized engaged-rate
  (engagement stands in for CTR until YouTube exposes impressions).

Everything is read-only, fail-open, and confidence-gated (≥5 measured runs for
any correlation; below that the render says "collecting"). Surfaced via
`py -m scripts.ops calibration` and one line in the weekly report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from core import process_state
from core.logging import get_logger

logger = get_logger("core.grade_calibration")

MIN_MEASURED = 5
UNVERSIONED = "unversioned"

from core.claim_types import claim_type_coverage_line  # noqa: E402  (#826)


@dataclass
class CalibrationRow:
    run_id: int
    title: str
    grade: float  # pre-publish report card 0-100
    actual_percentile: float  # realized engaged-rate percentile 0-100
    engaged_rate: float
    predicted_rate: float | None = None
    grade_version: str = UNVERSIONED
    # #808. `grade` is the number the row's own rubric produced when one was
    # recorded; `regraded` is what today's code makes of the same inputs. The
    # gap between them is the measured effect of a component change - the thing
    # `GRADE_VERSION` could only assert. None when the row carries no snapshot,
    # in which case `grade` *is* today's re-grade.
    regraded: float | None = None
    recorded: bool = False
    # Component name -> score, as recorded and as today's code makes it. The
    # per-component pair is the whole point of #808: "the grade moved" is a
    # fact `GRADE_VERSION` could already assert, "authenticity moved 65 points"
    # is the one it could not.
    components: dict[str, float] = field(default_factory=dict)
    regraded_components: dict[str, float] = field(default_factory=dict)
    # #823: this grade was recomputed by today's code, not recorded by the
    # rubric that graded the run. It cannot be evidence that the rubric held.
    backfilled: bool = False
    # #821: how many of the recent scripts shared this one's opener/closer shape,
    # as #803 counted it at generation time (#823 backfilled it onto the archive).
    recurrence_n: int | None = None
    # #819: the editorial score of the chosen variant, once runs persist it.
    angle_score: float | None = None


@dataclass
class CalibrationReport:
    channel_id: str
    rows: list[CalibrationRow] = field(default_factory=list)
    grade_correlation: float | None = None
    thumbnail_correlation: float | None = None
    thumbnail_n: int = 0
    mixed_versions: bool = False
    # #805. The grade correlation needs a persisted `quality_json` and so is
    # stuck at n=3 on the only channel with data; `composite_score` sits on
    # every run row, which is why the same channel has n=12 here. Different
    # population, different number - never averaged together.
    composite_correlation: float | None = None
    composite_n: int = 0
    # #824: each grade component against engaged-rate, on the same rows the grade
    # correlation uses: name -> (r or None when the component never varied, n).
    component_correlations: dict[str, tuple[float | None, int]] = field(default_factory=dict)
    # #821 / #819: (r, n) for the two candidates the rubric might one day lean on.
    recurrence_correlation: tuple[float | None, int] = (None, 0)
    angle_correlation: tuple[float | None, int] = (None, 0)
    # #826: (typed, verified) over every run row, not just measured ones.
    claim_type_coverage: tuple[int, int] = (0, 0)
    runs_total: int = 0

    @property
    def measured(self) -> int:
        return len(self.rows)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if sx <= 1e-9 or sy <= 1e-9:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    return cov / (sx * sy)


def n_for_significance(r: float | None, *, t: float = 1.96) -> int | None:
    """Smallest n at which an observed |r| clears p<0.05 two-tailed (#824).

    From t = r * sqrt((n - 2) / (1 - r^2)): n = 2 + t^2 (1 - r^2) / r^2. |r|=0.32 -> 36,
    which is how far n=12 is from settling the anti-predictive report card either way.
    None when r is unknown or zero (no n settles a correlation of nothing); a perfect
    |r|=1 is significant as soon as a p-value exists, at n=3.
    """
    if r is None or abs(r) < 1e-9:
        return None
    if abs(r) >= 1.0:
        return 3
    import math

    return int(math.ceil(2 + (t * t) * (1 - r * r) / (r * r)))


def _recorded_components(quality: dict) -> dict[str, float]:
    """The per-component scores `run_quality.snapshot_grade` stored (#808)."""
    raw = quality.get("grade_components")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for name, entry in raw.items():
        value = entry.get("score") if isinstance(entry, dict) else entry
        if isinstance(value, int | float) and not isinstance(value, bool):
            out[str(name)] = float(value)
    return out


def worst_component_drift(row: CalibrationRow) -> tuple[str, float] | None:
    """Which component moved most between the recorded grade and today's."""
    shared = row.components.keys() & row.regraded_components.keys()
    deltas = [(name, row.regraded_components[name] - row.components[name]) for name in shared]
    deltas = [(n, d) for n, d in deltas if abs(d) >= 0.05]
    if not deltas:
        return None
    return max(deltas, key=lambda pair: abs(pair[1]))


def _percentile(value: float, population: list[float]) -> float:
    if not population:
        return 50.0
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return round(100.0 * (below + 0.5 * equal) / len(population), 1)


def _thumbnail_scores(channel_id: str) -> dict[int, float]:
    """content_run_id -> pre-publish thumbnail overall (best per run)."""
    out: dict[int, float] = {}
    try:
        from sqlalchemy import select

        from storage.db import get_session
        from storage.models import ThumbnailScore

        session = get_session()
        try:
            rows = session.scalars(
                select(ThumbnailScore).where(ThumbnailScore.channel_id == channel_id)
            ).all()
            for row in rows:
                if row.content_run_id and row.overall:
                    existing = out.get(row.content_run_id, 0.0)
                    out[row.content_run_id] = max(existing, float(row.overall))
        finally:
            session.close()
    except Exception as exc:
        logger.debug("thumbnail score load skipped: %s", exc)
    return out


def build_calibration(channel_id: str | None = None) -> CalibrationReport:
    from config.channels import resolve_channel_id
    from core.engagement_predictor import run_engagement_map
    from core.video_grade import grade_from_parts

    channel = resolve_channel_id(channel_id)
    report = CalibrationReport(channel_id=channel)

    try:
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(channel)
    except Exception:
        runs = []
    report.runs_total = len(runs)
    try:
        from core.claim_types import claim_type_coverage

        report.claim_type_coverage = claim_type_coverage(runs)  # #826: every row, measured or not
    except Exception as exc:
        logger.debug("claim type coverage skipped: %s", exc)

    engagement = run_engagement_map(channel)
    if not engagement:
        return report
    population = list(engagement.values())

    # #805, before the quality filter below: a run needs no quality dict to
    # have been scored and measured, and 12 of them are in exactly that state.
    composite_pairs = [
        (float(run.composite_score), engagement[run.id])
        for run in runs
        if run.composite_score and engagement.get(run.id) is not None
    ]
    report.composite_n = len(composite_pairs)
    if report.composite_n >= MIN_MEASURED:
        report.composite_correlation = _pearson(
            [c for c, _ in composite_pairs], [e for _, e in composite_pairs]
        )

    for run in runs:
        rate = engagement.get(run.id)
        if rate is None:
            continue
        try:
            quality = json.loads(run.quality_json or "{}")
        except Exception:
            quality = {}
        if not isinstance(quality, dict) or not quality:
            continue
        # Grade WITHOUT the predictor (channel_id=None) — calibration must not
        # recurse into prediction, and the grade should reflect content only.
        grade = grade_from_parts(quality=quality, composite_score=float(run.composite_score or 0))
        # #808: prefer the grade the row's own rubric recorded. Re-grading a v2
        # row with v4 code was never the row's grade, and until the snapshot
        # existed nothing could tell the two apart.
        snapshot = quality.get("grade_score")
        recorded = isinstance(snapshot, int | float) and not isinstance(snapshot, bool)
        score = float(snapshot) if isinstance(snapshot, int | float) else grade.score
        predicted = quality.get("predicted_engaged_rate")
        version = str(quality.get("grade_version") or UNVERSIONED)
        rec_n = quality.get("style_recurrence_n")
        angle = quality.get("angle_score")
        report.rows.append(
            CalibrationRow(
                run_id=run.id,
                title=(run.title or run.selected_topic or "")[:50],
                grade=score,
                regraded=grade.score if recorded else None,
                recorded=recorded,
                backfilled=bool(quality.get("grade_backfilled")),
                components=_recorded_components(quality) if recorded else {},
                regraded_components={c.name: float(c.score) for c in grade.components},
                actual_percentile=_percentile(rate, population),
                engaged_rate=rate,
                predicted_rate=float(predicted) if predicted is not None else None,
                grade_version=version,
                recurrence_n=int(rec_n) if isinstance(rec_n, int | float) else None,
                angle_score=float(angle) if isinstance(angle, int | float) else None,
            )
        )

    versions = {r.grade_version for r in report.rows}
    # "unversioned" is not a version. Every run graded before the stamp existed
    # carries no `grade_version`, and those are precisely the rows this guard was
    # filed about: four components moved across v1/v2/v3 while nothing recorded
    # which rubric produced which letter. Treating that population as one shared
    # rubric is the mistake, not the fix -- measured, it produced a 0.99998
    # correlation over eight unlabelled rows.
    report.mixed_versions = len(versions) > 1 or UNVERSIONED in versions
    if report.measured >= MIN_MEASURED and not report.mixed_versions:
        report.grade_correlation = _pearson(
            [r.grade for r in report.rows], [r.engaged_rate for r in report.rows]
        )

    # #824: the same rows, per component. Recorded component when the row has a
    # snapshot, else today's re-grade (labelled as such by `recorded`). Only under
    # the same conditions the grade correlation itself is allowed to exist.
    if report.measured >= MIN_MEASURED and not report.mixed_versions:
        names: dict[str, list[tuple[float, float]]] = {}
        for row in report.rows:
            comps = row.components or row.regraded_components
            for name, score in comps.items():
                names.setdefault(name, []).append((float(score), row.engaged_rate))
        for name, pairs in sorted(names.items()):
            if len(pairs) >= MIN_MEASURED:
                report.component_correlations[name] = (
                    _pearson([s for s, _ in pairs], [e for _, e in pairs]),
                    len(pairs),
                )
    # #821 / #819: the two candidates, measured before either moves the rubric.
    rec_pairs = [
        (float(r.recurrence_n), r.engaged_rate) for r in report.rows if r.recurrence_n is not None
    ]
    report.recurrence_correlation = (
        _pearson([a for a, _ in rec_pairs], [b for _, b in rec_pairs])
        if len(rec_pairs) >= MIN_MEASURED
        else None,
        len(rec_pairs),
    )
    ang_pairs = [
        (float(r.angle_score), r.engaged_rate) for r in report.rows if r.angle_score is not None
    ]
    report.angle_correlation = (
        _pearson([a for a, _ in ang_pairs], [b for _, b in ang_pairs])
        if len(ang_pairs) >= MIN_MEASURED
        else None,
        len(ang_pairs),
    )

    thumbs = _thumbnail_scores(channel)
    joined = [(thumbs[rid], engagement[rid]) for rid in thumbs.keys() & engagement.keys()]
    report.thumbnail_n = len(joined)
    if len(joined) >= MIN_MEASURED:
        report.thumbnail_correlation = _pearson([t for t, _ in joined], [e for _, e in joined])
    return report


_ACCURACY_CACHE: dict[str, str | None] = {}


def composite_line(report: CalibrationReport) -> str:
    """One line on whether the topic score has ever tracked engagement (#805)."""
    if report.composite_correlation is not None:
        return (
            f"Composite vs engaged-rate r={report.composite_correlation:+.2f} "
            f"(n={report.composite_n})"
        )
    return f"Composite vs engaged-rate: collecting ({report.composite_n}/{MIN_MEASURED})"


def component_line(report: CalibrationReport) -> str:
    """#824: the grade's components against engaged-rate, one line."""
    if not report.component_correlations:
        return ""
    parts = []
    for name, (r, _n) in report.component_correlations.items():
        parts.append(f"{name} r={r:+.2f}" if r is not None else f"{name} r=n/a (constant)")
    n_all = max(n for _, n in report.component_correlations.values())
    return f"Per component vs engaged-rate (n={n_all}): " + ", ".join(parts)


def significance_line(report: CalibrationReport) -> str:
    """#824: what n would settle the grade correlation - and until then, do not retune."""
    r = report.grade_correlation
    if r is None:
        return ""
    need = n_for_significance(r)
    if need is None:
        return f"Grade r={r:+.2f} at n={report.measured}: no n settles a correlation of zero"
    verdict = (
        "significant"
        if report.measured >= need
        else "not significant - do not retune the rubric on it"
    )
    return f"Grade r={r:+.2f} at n={report.measured}: |r|={abs(r):.2f} needs n>={need} to clear p<0.05; {verdict}"


def recurrence_line(report: CalibrationReport) -> str:
    """#821: does a recurring opener cost engagement? Promotion into the grade waits on this."""
    r, n = report.recurrence_correlation
    if r is None:
        return (
            f"Recurring opener vs engaged-rate: collecting ({n}/{MIN_MEASURED} measured runs carry "
            "style_recurrence_n); promotion into the grade waits on it"
        )
    need = n_for_significance(r)
    tail = f" (needs n>={need} to be significant)" if need and n < need else ""
    return f"Recurring opener vs engaged-rate r={r:+.2f} (n={n}){tail}; promotion into the grade waits on |r| clearing significance"


def angle_line(report: CalibrationReport) -> str:
    """#819: the tie-break candidate, measured before the tie leans on it."""
    r, n = report.angle_correlation
    if r is None:
        return (
            f"Angle score vs engaged-rate: collecting ({n} of {report.measured} measured runs carry "
            "one; runs before wave 32 never persisted it) - the tie keeps leaning on composite"
        )
    return f"Angle score vs engaged-rate r={r:+.2f} (n={n}); the tie leans on composite until this is positive"


def accuracy_line(channel_id: str | None = None, *, use_cache: bool = True) -> str | None:
    """The card's own track record, as one line. Fail-open, never raises.

    Cached per process: the card is printed once per run but `ops grade` can be
    called in a loop, and this walks every run row plus the analytics join.
    """
    key = str(channel_id or "")
    if use_cache and key in _ACCURACY_CACHE:
        return _ACCURACY_CACHE[key]
    line: str | None = None
    try:
        report = build_calibration(channel_id)
        grade_part = (
            f"grade r={report.grade_correlation:+.2f} (n={report.measured})"
            if report.grade_correlation is not None
            else f"grade collecting ({report.measured}/{MIN_MEASURED})"
        )
        composite_part = (
            f"composite r={report.composite_correlation:+.2f} (n={report.composite_n})"
            if report.composite_correlation is not None
            else f"composite collecting ({report.composite_n}/{MIN_MEASURED})"
        )
        line = f"card accuracy: {grade_part}, {composite_part}"
    except Exception as exc:
        logger.debug("card accuracy line skipped: %s", exc)
        line = None
    if use_cache:
        _ACCURACY_CACHE[key] = line
    return line


def snapshot_line(report: CalibrationReport) -> str:
    """How much of the archive can answer "what did this actually score?" (#808)."""
    recorded = [r for r in report.rows if r.recorded]
    backfilled = [r for r in recorded if r.backfilled]
    if not recorded:
        return (
            f"Recorded grades: 0/{report.measured} - every row above is re-graded with "
            "today's rubric. Rows generated from now on carry their own."
        )
    drifts: list[tuple[float, CalibrationRow]] = [
        (r.regraded - r.grade, r)
        for r in recorded
        if r.regraded is not None and abs(r.regraded - r.grade) >= 0.05
    ]
    line = f"Recorded grades: {len(recorded)}/{report.measured}"
    if drifts:
        delta, worst = max(drifts, key=lambda pair: abs(pair[0]))
        line += (
            f" - {len(drifts)} would grade differently today (worst {delta:+.1f} on #{worst.run_id}"
        )
        component = worst_component_drift(worst)
        line += f", {component[0]} {component[1]:+.0f})" if component else ")"
    elif len(backfilled) == len(recorded):
        # Tautological otherwise: the backfill computed these with today's code.
        line += (
            " - all backfilled (#823), so this says nothing about rubric "
            "stability; new runs from here carry their own"
        )
    elif backfilled:
        line += (
            f" - today's rubric reproduces every one, but {len(backfilled)} were "
            "backfilled and cannot show drift"
        )
    else:
        line += " - today's rubric reproduces every one"
    return line


def coverage_line(report: CalibrationReport, *, runs_total: int | None = None) -> str:
    """#818: why the correlation is collecting, when the reason is history.

    `summary_line` says "collecting (3/5)", which reads like "publish more".
    The actual shape on `tapin` is 87 runs, 37 with a grade, 12 with an
    outcome, 3 with both: quality persistence landed after most of the
    publishing did, so the overlap grows one row per *new* publish and no
    amount of past volume helps. Empty when every measured run already carries
    a grade - there is nothing to explain then.
    """
    try:
        measured = report.composite_n  # runs with an outcome
        both = report.measured  # runs with an outcome AND a quality dict
        if not measured or both >= measured:
            return ""
        graded = _graded_row_count(report.channel_id)
        total = f"{runs_total} runs, " if runs_total else ""
        return (
            f"Calibration coverage: {total}{graded} with a grade, {measured} with an outcome, "
            f"{both} with both - the overlap is historical (quality persistence postdates most "
            f"of the publishing) and grows one per publish, not one per past run"
        )
    except Exception as exc:
        logger.debug("coverage line skipped: %s", exc)
        return ""


def _graded_row_count(channel_id: str) -> int:
    """Runs carrying a non-empty `quality_json`, outcome or not."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
    except Exception:
        return 0
    return sum(1 for r in runs if (r.quality_json or "").strip() not in ("", "{}"))


def summary_line(report: CalibrationReport) -> str | None:
    """One weekly-report line, or None when still collecting."""
    if report.grade_correlation is None:
        # "still collecting" wins below the threshold: with too few runs the
        # version question has not bitten yet, and reporting a refusal implies
        # the data would otherwise be usable.
        if report.measured and report.measured < MIN_MEASURED:
            return (
                f"Grade calibration: collecting ({report.measured}/{MIN_MEASURED} "
                "measured runs with quality)"
            )
        if report.mixed_versions:
            versions = sorted({r.grade_version for r in report.rows})
            if versions == [UNVERSIONED]:
                return (
                    "Grade calibration: refusing to correlate unversioned grades "
                    f"({report.measured} runs predate the rubric stamp and span "
                    "more than one rubric)"
                )
            return (
                f"Grade calibration: refusing to mix rubric versions "
                f"({', '.join(versions)}; {report.measured} runs)"
            )
        if report.measured:
            return (
                f"Grade calibration: collecting ({report.measured}/{MIN_MEASURED} "
                "measured runs with quality)"
            )
        return None
    return (
        f"Grade calibration: report-card vs engaged-rate r={report.grade_correlation:+.2f} "
        f"over {report.measured} videos"
    )


def render(channel_id: str | None = None) -> str:
    report = build_calibration(channel_id)
    lines = [f"Grade calibration - {report.channel_id}", "=" * 64]
    if not report.rows:
        lines.append(
            "No measured runs with persisted quality yet - publish + sync-metrics, "
            "then re-run. (Runs recorded before the ledger have no quality_json.)"
        )
        coverage = claim_type_coverage_line(report.claim_type_coverage)
        if coverage:
            lines.append(f"  {coverage}")
        return "\n".join(lines)
    for r in sorted(report.rows, key=lambda r: r.run_id, reverse=True)[:15]:
        pred = f"  pred {r.predicted_rate * 100:.1f}%" if r.predicted_rate is not None else ""
        drift = ""
        if r.regraded is not None and abs(r.regraded - r.grade) >= 0.05:
            drift = f"  [{r.grade_version} {r.regraded - r.grade:+.1f} under today's rubric]"
        lines.append(
            f"  #{r.run_id:<5} {r.title:<50} grade {r.grade:5.1f} -> "
            f"actual p{r.actual_percentile:.0f} ({r.engaged_rate * 100:.1f}%){pred}{drift}"
        )
    lines.append("-" * 64)
    lines.append(f"  {snapshot_line(report)}")
    coverage = claim_type_coverage_line(report.claim_type_coverage)
    if coverage:
        lines.append(f"  {coverage}")
    grade_line = summary_line(report)
    if grade_line:
        lines.append(f"  {grade_line}")
    lines.append(f"  {composite_line(report)}")
    for extra in (
        significance_line(report),
        component_line(report),
        recurrence_line(report),
        angle_line(report),
    ):
        if extra:
            lines.append(f"  {extra}")
    if report.thumbnail_correlation is not None:
        lines.append(
            f"  Thumbnail score vs engaged-rate r={report.thumbnail_correlation:+.2f} "
            f"over {report.thumbnail_n} videos"
        )
    elif report.thumbnail_n:
        lines.append(
            f"  Thumbnail join: collecting ({report.thumbnail_n}/{MIN_MEASURED} scored+measured)"
        )
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Pre-publish grade vs realized engagement")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args()
    print(render(args.channel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --- process-global state reset (#827) --------------------------------------
process_state.register_reset("core.grade_calibration", _ACCURACY_CACHE.clear)
