"""Write machine-learned channel beliefs back into the Obsidian vault.

This is the machine half of the "two faces of Channel Intelligence" (see
docs/content_intelligence_roadmap.md §7): human-authored notes and machine-learned
beliefs live in the *same* vault, and both are read back by core.obsidian_facts.

Today the beliefs are synthesized from the analytics that already exist (per-domain
engagement, top/bottom performing topics from content-run history). When the full
Analytics Intelligence Agent lands, it becomes the richer source feeding this same
writeback — the file format and read path do not change.

Safety:
- Only ever writes a single, clearly-marked, auto-generated file per channel
  (`<vault>/<channel>/_machine-beliefs.md`). Never touches human notes.
- No-ops when OBSIDIAN_VAULT_PATH is unset.
- Beliefs are channel-level patterns (angle/title-style/format that over- or
  under-perform), NOT per-topic — naming a specific past topic as "repeat this"
  makes the system reinforce its own (sometimes fabricated) seeds. Tagged
  `[machine, beliefs, evergreen]` so these channel priors inform every script, and
  each line is prefixed "Machine belief:" so it reads as a heuristic prior.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from config.channels import get_channel_profile, resolve_channel_id
from core.logging import get_logger
from core.obsidian_facts import _vault_path

logger = get_logger("core.vault_writeback")

_FILENAME = "_machine-beliefs.md"


def _domain_engagement(entries: list[dict]) -> list[tuple[str, float, int]]:
    """(domain, avg_engaged_rate, n) sorted best-first, only domains with data."""
    by_domain: dict[str, list[float]] = {}
    for e in entries:
        rate = e.get("engaged_rate")
        if rate is None:
            continue
        by_domain.setdefault(e.get("domain") or "neutral", []).append(float(rate))
    ranked = [(d, sum(v) / len(v), len(v)) for d, v in by_domain.items() if v]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def build_channel_beliefs(channel_id: str) -> list[str]:
    """Synthesize belief bullet lines from current analytics. May be empty."""
    from core.best_bet import _build_entries

    try:
        entries = _build_entries(channel_id)
    except Exception as exc:  # analytics/storage hiccup must not break callers
        logger.debug("vault writeback: could not build entries for %s: %s", channel_id, exc)
        return []
    if not entries:
        return []

    beliefs: list[str] = []

    ranked = _domain_engagement(entries)
    if ranked:
        best_d, best_r, best_n = ranked[0]
        beliefs.append(
            f"Machine belief: {best_d} is the strongest domain — "
            f"{best_r:.0%} avg engagement across {best_n} video(s)."
        )
        if len(ranked) > 1:
            worst_d, worst_r, worst_n = ranked[-1]
            beliefs.append(
                f"Machine belief: {worst_d} underperforms by comparison — "
                f"{worst_r:.0%} avg engagement across {worst_n} video(s)."
            )

    # Pattern-based beliefs (angle/title-structure/format) from the feature store.
    # Deliberately NOT per-topic: naming a specific past topic as "repeat this" makes
    # the system reinforce its own (sometimes fabricated) seeds — a feedback loop.
    # Patterns generalize the lesson without recycling a literal topic string.
    beliefs.extend(_pattern_beliefs(channel_id))
    return beliefs


# Dimension -> human label for belief lines.
_DIM_LABELS = {
    "angle": "angle",
    "title_structure": "title style",
    "format": "format",
}


def _pattern_beliefs(channel_id: str) -> list[str]:
    try:
        from analytics.weekly_report import build_report
    except Exception:
        return []
    try:
        report = build_report(channel_id)
    except Exception as exc:
        logger.debug("vault writeback: report failed for %s: %s", channel_id, exc)
        return []
    if not report.get("ready"):
        return []

    baseline = report.get("baseline", 0.0)
    out: list[str] = []
    for dim, label in _DIM_LABELS.items():
        groups = report.get("dimensions", {}).get(dim) or []
        if not groups:
            continue
        top = groups[0]
        if top["delta"] > 0.02:
            out.append(
                f"Machine belief: {top['value']} {label} over-performs — "
                f"{top['avg']:.0%} vs {baseline:.0%} baseline (n={top['n']}); lean into it."
            )
        bottom = groups[-1]
        if bottom["delta"] < -0.02 and bottom["value"] != top["value"]:
            out.append(
                f"Machine belief: {bottom['value']} {label} under-performs — "
                f"{bottom['avg']:.0%} vs {baseline:.0%} baseline (n={bottom['n']}); use sparingly."
            )
    return out


def _render_note(channel_id: str, beliefs: list[str]) -> str:
    profile = get_channel_profile(channel_id)
    body = "\n".join(f"- {b}" for b in beliefs)
    return (
        "---\n"
        f"channel: {channel_id}\n"
        "tags: [machine, beliefs, evergreen]\n"
        f"generated: {date.today().isoformat()}\n"
        "source: content-machine analytics\n"
        "---\n\n"
        f"# {profile.name} — Machine-Learned Beliefs (auto-generated)\n\n"
        "> Auto-written by Content Machine from performance analytics. **Do not hand-edit** —\n"
        "> this file is overwritten on each sync. Human-authored notes live in the other\n"
        "> files in this folder. These are heuristic priors, not verified facts.\n\n"
        "## What the data says\n"
        f"{body}\n"
    )


def write_channel_beliefs(channel_id: str | None = None) -> Path | None:
    """Write the machine-beliefs note into the vault. Returns the path or None.

    None when the vault is unset or there are no beliefs to write (so it is always
    safe to call, e.g. from a daily sync).
    """
    channel_id = resolve_channel_id(channel_id)
    vault = _vault_path()
    if not vault:
        logger.debug("vault writeback skipped: OBSIDIAN_VAULT_PATH not set")
        return None

    beliefs = build_channel_beliefs(channel_id)
    if not beliefs:
        logger.debug("vault writeback skipped: no beliefs for %s", channel_id)
        return None

    target_dir = vault / channel_id
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / _FILENAME
        path.write_text(_render_note(channel_id, beliefs), encoding="utf-8", newline="\n")
    except OSError as exc:
        logger.warning("vault writeback failed for %s: %s", channel_id, exc)
        return None

    logger.info("Wrote %d machine belief(s) to %s", len(beliefs), path)
    return path
