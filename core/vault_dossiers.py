"""Run dossiers into the Obsidian vault (Pillar 4 — Obsidian knowledge OS).

The vault was a one-way sidecar: facts flowed *in* (read by obsidian_facts),
but runs/scripts/outcomes never landed *back* in it. This writes one browsable
note per run — `{channel}/_runs/{date}_{slug}.md` — turning the vault into the
human-readable mirror of machine state (vision.md §7's "two faces").

A dossier is a **record of what we made**, not a fact about the world, so:
- it lives under `_runs/` (excluded from `obsidian_facts.load_facts` via
  `_is_machine_record`) and is tagged `[run, machine]`, never `evergreen`;
- `refresh_dossiers` upserts post-sync actuals (views/engaged/revenue) so a
  dossier written at draft time gains its outcome after `sync-metrics`.

Everything is fail-open and no-ops when `OBSIDIAN_VAULT_PATH` is unset.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.obsidian_facts import _vault_path

logger = get_logger("core.vault_dossiers")

_RUNS_DIR = "_runs"
_REPORTS_DIR = "_reports"


def _slug(text: str, *, limit: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:limit] or "run").rstrip("-")


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _dossier_path(vault: Path, channel_id: str, run_id: int, topic: str, day: str) -> Path:
    return vault / channel_id / _RUNS_DIR / f"{day}_{_slug(topic)}-{run_id}.md"


def _render_dossier(record: Any, *, run_id: int, day: str) -> str:
    features = _load_json(record.features_json)
    quality = _load_json(record.quality_json)
    topic = record.selected_topic or record.input_topic or ""

    grade_line = ""
    try:
        from core.video_grade import grade_run

        grade = grade_run(run_id)
        if grade is not None:
            grade_line = f"{grade.letter} ({grade.score:.0f}/100)"
    except Exception:
        pass

    publish = {}
    try:
        from core.run_ledger import _publish_for_run

        publish = _publish_for_run(run_id, record.channel_id)
    except Exception:
        pass
    metrics = publish.get("metrics") or {}

    cost = features.get("cost") or {}
    fm = [
        "---",
        f"channel: {record.channel_id}",
        "tags: [run, machine]",
        f"run_id: {run_id}",
        f"date: {day}",
        f"status: {record.status}",
        "source: content-machine (run dossier)",
        "---",
        "",
        f"# {record.title or topic}",
        "",
        f"- **Topic:** {topic}",
        f"- **Status:** {record.status}",
        f"- **Composite score:** {record.composite_score:.1f}",
    ]
    if grade_line:
        fm.append(f"- **Report card:** {grade_line}")
    for key, label in (
        ("domain", "Domain"),
        ("angle", "Angle"),
        ("format", "Format"),
        ("fact_source", "Fact source"),
    ):
        if features.get(key):
            fm.append(f"- **{label}:** {features[key]}")
    if quality:
        q_bits = []
        if quality.get("hook_score") is not None:
            q_bits.append(f"hook {quality['hook_score']}")
        if quality.get("authenticity_score") is not None:
            q_bits.append(f"authenticity {quality['authenticity_score']}")
        if quality.get("ungrounded_count"):
            q_bits.append(f"{quality['ungrounded_count']} ungrounded")
        if quality.get("fact_conflict_count"):
            q_bits.append(f"{quality['fact_conflict_count']} conflicts")
        if quality.get("claim_support_rate") is not None:
            q_bits.append(f"claim support {quality['claim_support_rate'] * 100:.0f}%")
        if q_bits:
            fm.append(f"- **Quality:** {', '.join(q_bits)}")
    if cost.get("total"):
        fm.append(f"- **Cost:** ${cost['total']:.3f}")
    if metrics:
        fm.append(
            f"- **Actuals:** {metrics.get('views', 0)} views, "
            f"{float(metrics.get('engaged_rate', 0) or 0) * 100:.1f}% engaged"
            + (
                f", ${float(metrics['estimated_revenue_usd']):.2f} est. revenue"
                if metrics.get("estimated_revenue_usd") is not None
                else ""
            )
        )
    if publish.get("youtube_video_id"):
        fm.append(f"- **Video:** https://youtu.be/{publish['youtube_video_id']}")

    fm.append("")
    fm.append("## Script")
    fm.append("")
    fm.append((record.script_preview or "").strip() or "_(no script recorded)_")
    fm.append("")
    return "\n".join(fm)


def write_run_dossier(run_id: int | None) -> Path | None:
    """Write/overwrite one run's dossier note. Returns the path or None (fail-open)."""
    if not run_id:
        return None
    vault = _vault_path()
    if not vault:
        return None
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
    except Exception as exc:
        logger.debug("dossier skipped for run %s: %s", run_id, exc)
        return None
    if record is None:
        return None
    day = date.today().isoformat()
    topic = record.selected_topic or record.input_topic or "run"
    try:
        path = _dossier_path(vault, record.channel_id, run_id, topic, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _render_dossier(record, run_id=run_id, day=day), encoding="utf-8", newline="\n"
        )
        return path
    except Exception as exc:
        logger.debug("dossier write failed for run %s: %s", run_id, exc)
        return None


def refresh_dossiers(channel_id: str | None = None, *, limit: int = 15) -> int:
    """Rewrite recent dossiers so post-sync actuals (views/engaged/revenue) land.

    Returns how many were written. Safe to call from daily_sync — no-op without a
    vault. Rewriting is idempotent (deterministic filename per run+day).
    """
    vault = _vault_path()
    if not vault:
        return 0
    try:
        from config.channels import resolve_channel_id
        from storage.repositories.content_runs import get_content_run_repository

        channel = resolve_channel_id(channel_id)
        runs = get_content_run_repository().list_for_channel(channel)[:limit]
    except Exception as exc:
        logger.debug("dossier refresh skipped: %s", exc)
        return 0
    written = 0
    for run in runs:
        if run.status not in ("drafted", "rendered"):
            continue
        if write_run_dossier(run.id):
            written += 1
    return written


def write_weekly_report_note(channel_id: str, rendered: str) -> Path | None:
    """Land the rendered weekly report in `{channel}/_reports/{date}_weekly.md`."""
    vault = _vault_path()
    if not vault or not (rendered or "").strip():
        return None
    day = date.today().isoformat()
    try:
        target = vault / channel_id / _REPORTS_DIR / f"{day}_weekly.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "---\n"
            f"channel: {channel_id}\n"
            "tags: [report, machine]\n"
            f"date: {day}\n"
            "source: content-machine (weekly report)\n"
            "---\n\n"
            f"# Weekly report — {day}\n\n```\n{rendered.strip()}\n```\n"
        )
        target.write_text(body, encoding="utf-8", newline="\n")
        return target
    except Exception as exc:
        logger.debug("weekly report note skipped: %s", exc)
        return None
