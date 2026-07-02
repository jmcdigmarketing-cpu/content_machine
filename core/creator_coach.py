"""Creator coach — "what should I make today, and why?" (Phase S).

Expands best-bet from a 3-line picker into a daily coach view (vidIQ-style,
but grounded in our own sourcing + analytics loop): ranked topic ideas each
with its *why*, plus the operating parameters the recommenders already learn —
post time, length, winning title patterns, cadence headroom, and the channel's
retention drop-off.

Read-only aggregation over existing recommenders; every section is fail-open
(a missing subsystem shows as absent, never raises).

    py -m scripts.ops coach --channel tapin     (or: py -m core.creator_coach)
"""

from __future__ import annotations

import argparse
from typing import Any

_DEFAULT_IDEAS = 5


def build_coach(channel_id: str, *, n_ideas: int = _DEFAULT_IDEAS) -> dict[str, Any]:
    """Assemble the coach snapshot (read-only, fail-open per section)."""
    from config.channels import resolve_channel_id

    channel_id = resolve_channel_id(channel_id)
    out: dict[str, Any] = {"channel_id": channel_id}

    try:
        from core.best_bet import get_best_bets

        out["ideas"] = [
            {
                "topic": b.topic,
                "domain": b.domain,
                "source": b.source,
                "why": b.rationale,
            }
            for b in get_best_bets(channel_id, n=n_ideas)
        ]
    except Exception:
        out["ideas"] = []

    try:
        from analytics.post_timing import get_recommended_time

        rec = get_recommended_time(channel_id)
        out["post_time"] = {"local": rec.local_str, "why": rec.rationale}
    except Exception:
        pass

    try:
        from core.length_recommender import get_recommended_length

        rec = get_recommended_length(channel_id)
        out["length"] = {"label": rec.label, "why": rec.rationale}
    except Exception:
        pass

    try:
        from core.title_experiments import pattern_leaderboard

        out["title_patterns"] = [
            {"tag": tag, "avg": avg, "n": n} for tag, avg, n in pattern_leaderboard(channel_id)[:3]
        ]
    except Exception:
        out["title_patterns"] = []

    try:
        from core.cadence import cadence_status

        cad = cadence_status(channel_id)
        out["cadence"] = {
            "total": cad.total,
            "cap": cad.cap,
            "window_days": cad.window_days,
            "ok": cad.ok,
        }
    except Exception:
        pass

    try:
        from core.retention import drop_off_ratio

        pos = drop_off_ratio(channel_id)
        if pos is not None:
            out["retention_dropoff"] = pos
    except Exception:
        pass

    return out


def render_coach(data: dict[str, Any]) -> str:
    """Format the snapshot as the operator-facing daily coach view."""
    lines = [f"Creator coach — {data.get('channel_id', '?')}", "=" * 44]

    ideas = data.get("ideas") or []
    if ideas:
        lines.append("Today's ideas (best first):")
        for i, idea in enumerate(ideas, 1):
            lines.append(f"  {i}. [{idea['domain']}] {idea['topic']}")
            lines.append(f"     why: {idea['why']}")
    else:
        lines.append("Today's ideas: none yet — run a few videos so the loop has history.")

    lines.append("")
    lines.append("How to ship it:")
    if data.get("length"):
        lines.append(f"  Length : {data['length']['label']} — {data['length']['why']}")
    if data.get("post_time"):
        lines.append(f"  Post at: {data['post_time']['local']} — {data['post_time']['why']}")

    patterns = data.get("title_patterns") or []
    if patterns:
        tags = ", ".join(f"{p['tag']} ({p['avg']:.0%}, n={p['n']})" for p in patterns)
        lines.append(f"  Titles : lean on proven patterns — {tags}")

    if data.get("retention_dropoff") is not None:
        pct = int(round(float(data["retention_dropoff"]) * 100))
        lines.append(f"  Pacing : viewers drop off ~{pct}% in — land the payoff before that.")

    cad = data.get("cadence")
    if cad:
        room = max(cad["cap"] - cad["total"], 0)
        if room:
            lines.append(
                f"  Cadence: {cad['total']}/{cad['cap']} used this {cad['window_days']}-day "
                f"window — room for {room} more."
            )
        else:
            lines.append(
                f"  Cadence: at the cap ({cad['total']}/{cad['cap']}) — "
                "hold off, or raise MAX_VIDEOS_PER_WEEK deliberately."
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily creator coach (ideas + why)")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument("--ideas", type=int, default=_DEFAULT_IDEAS)
    args = parser.parse_args(argv)
    print(render_coach(build_coach(args.channel, n_ideas=args.ideas)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
