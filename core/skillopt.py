"""SkillOpt-Sleep (Pillar 7 C2) — nightly, validation-gated skill optimization.

Proposes a natural-language STYLE DIRECTIVE for the script prompt and keeps it ONLY when it
beats the current prompts on the **frozen** prompt-evals rubric (`core/prompt_evals`) across
the golden topics. The winner is written to the vault as a reviewable PROPOSAL record — it
does NOT auto-edit live prompts; the operator promotes a proposal by adding it as a
`[strategy]` playbook bullet (which then flows into generation via `playbook_block`).

This is the offline, frozen-gate optimizer SkillOpt describes. It costs LLM calls (generate
each golden topic per candidate), so it is opt-in: `overnight` runs it when
`SKILLOPT_ENABLED=true`, and it's render-free (cadence-safe).

    py -m core.skillopt --channel tapin
    py -m scripts.ops skillopt --channel tapin
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger("core.skillopt")

# Candidate skill directives — short, bounded, non-factual style rules, each targeting a
# rubric lever (hook / filler / grounding). Frozen library v1; extend deliberately.
_CANDIDATE_DIRECTIVES: tuple[str, ...] = (
    "Open on a concrete number, name, or fact in the first sentence — never a rhetorical "
    "question or a hype phrase.",
    "Cut every hedging adverb (basically, honestly, actually, really, literally) and every "
    "stock transition phrase.",
    "Name a specific subject in every claim; replace vague nouns like 'things', 'stuff', or "
    "'a lot' with the actual thing.",
)


def _aggregate(scores: dict[str, Any]) -> float:
    """Frozen scalar (v1) from the prompt-evals rubric — higher is better.

    hook rewards, ungrounded specifics and filler penalize, a length fit adds a flat bonus.
    Kept simple + fixed so a candidate's win is comparable across runs.
    """
    val = 0.0
    hook = scores.get("hook_score")
    if hook is not None:
        val += float(hook)
    ungrounded = scores.get("ungrounded_count")
    if ungrounded is not None:
        val -= 10.0 * float(ungrounded)
    val -= 5.0 * float(scores.get("filler_count") or 0)
    if scores.get("length_fit"):
        val += 10.0
    return val


def _score_directive(channel_id: str, directive: str) -> tuple[float, int]:
    """Mean aggregate rubric score over the golden topics, generating each with `directive`
    applied (or the live prompts when directive == ""). Returns (mean_aggregate, n_scored).
    Fail-open per topic; never raises."""
    from core.content_engine import generate_content_package
    from core.prompt_evals import _load_config, score_script
    from core.script_length import word_range

    config = _load_config()
    cases = (config.get("channels") or {}).get(channel_id) or []
    totals: list[float] = []
    today = datetime.now().strftime("%Y-%m-%d")
    for case in cases:
        topic = str(case.get("topic") or "")
        if not topic:
            continue
        facts = [str(f) for f in case.get("key_facts") or []]
        length_choice = str(case.get("length_choice") or "2")
        try:
            package = generate_content_package(
                topic=topic,
                signals={},
                word_range=word_range(length_choice),
                today=today,
                channel_id=channel_id,
                research_brief=None,
                length_choice=length_choice,
                key_facts=list(facts),
                extra_directive=directive,
            )
            script = str(package.get("script") or "")
            scores = score_script(script, key_facts=facts, length_choice=length_choice)
            totals.append(_aggregate(scores))
        except Exception as exc:
            logger.warning("skillopt scoring failed for '%s': %s", topic, exc)
            continue
    if not totals:
        return 0.0, 0
    return sum(totals) / len(totals), len(totals)


@dataclass
class SkillOptResult:
    channel_id: str
    baseline: float = 0.0
    n_topics: int = 0
    best_directive: str = ""
    best_score: float = 0.0
    improved: bool = False
    margin: float = 0.0
    proposal_path: str = ""
    candidates: list[tuple[str, float]] = field(default_factory=list)


def _min_margin() -> float:
    try:
        return float(os.getenv("SKILLOPT_MIN_MARGIN", "1.0"))
    except ValueError:
        return 1.0


def run_skillopt(
    channel_id: str | None = None,
    *,
    directives: tuple[str, ...] | None = None,
) -> SkillOptResult:
    """Score the live prompts (baseline) vs each candidate directive on the frozen rubric;
    keep the best only if it clears the baseline by SKILLOPT_MIN_MARGIN. A winner is written
    to the vault as a proposal record + emits a `skillopt_proposal` event. Never raises."""
    from config.channels import resolve_channel_id

    channel = resolve_channel_id(channel_id)
    result = SkillOptResult(channel_id=channel)

    baseline, n = _score_directive(channel, "")
    result.baseline, result.n_topics = baseline, n
    if not n:
        logger.warning("skillopt: no golden topics (config/prompt_evals.json) for %s", channel)
        return result

    cands = directives if directives is not None else _CANDIDATE_DIRECTIVES
    scored = [(d, s) for d in cands for s, sn in [_score_directive(channel, d)] if sn]
    result.candidates = scored
    if not scored:
        return result

    result.best_directive, result.best_score = max(scored, key=lambda x: x[1])
    result.margin = result.best_score - baseline
    result.improved = result.best_score >= baseline + _min_margin()
    if result.improved:
        result.proposal_path = _write_proposal(channel, result)
        try:
            from core.events import emit_event

            emit_event(
                "skillopt_proposal",
                {
                    "channel_id": channel,
                    "directive": result.best_directive,
                    "baseline": round(baseline, 2),
                    "candidate": round(result.best_score, 2),
                    "margin": round(result.margin, 2),
                },
            )
        except Exception as exc:
            logger.debug("skillopt event not emitted: %s", exc)
    return result


def _write_proposal(channel_id: str, result: SkillOptResult) -> str:
    """Write a reviewable proposal record into the vault (a machine record — excluded from
    grounding/playbook, so it never feeds prompts). Fail-open: "" when the vault is unset."""
    vault = (os.getenv("OBSIDIAN_VAULT_PATH", "") or "").strip()
    if not vault:
        return ""
    try:
        folder = os.path.join(vault, channel_id, "_skillopt")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        path = os.path.join(folder, f"{stamp}.md")
        lines = [
            "---",
            "tags: [skillopt, proposal]",
            f"channel: {channel_id}",
            "---",
            "",
            f"# SkillOpt proposal - {stamp}",
            "",
            f"Frozen prompt-evals rubric over {result.n_topics} golden topic(s).",
            f"Baseline aggregate: {result.baseline:.2f}",
            f"Winning aggregate:  {result.best_score:.2f}  (+{result.margin:.2f})",
            "",
            "## Proposed STYLE DIRECTIVE",
            "",
            f"> {result.best_directive}",
            "",
            "To adopt: add this as a `[strategy]` bullet in the channel playbook (it then",
            "flows into the script prompt via playbook_block). This file is a record only.",
            "",
            "## All candidates (aggregate score)",
            "",
        ]
        lines += [f"- ({s:.2f}) {d}" for d, s in sorted(result.candidates, key=lambda x: -x[1])]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return path
    except Exception as exc:
        logger.warning("skillopt proposal write failed: %s", exc)
        return ""


def render_skillopt(result: SkillOptResult) -> str:
    lines = [f"SkillOpt-Sleep - {result.channel_id}", "=" * 44]
    if not result.n_topics:
        lines.append("No golden topics (config/prompt_evals.json) - nothing to optimize.")
        return "\n".join(lines)
    lines.append(f"Baseline: {result.baseline:.2f} over {result.n_topics} topic(s)")
    for d, s in sorted(result.candidates, key=lambda x: -x[1]):
        mark = "*" if d == result.best_directive and result.improved else " "
        lines.append(f"  {mark} {s:6.2f}  {d[:66]}")
    lines.append("")
    if result.improved:
        lines.append(f"WINNER (+{result.margin:.2f}): {result.best_directive}")
        lines.append(f"Proposal: {result.proposal_path or '(vault unset - not written)'}")
        lines.append("Review it, then add it as a [strategy] playbook bullet to adopt.")
    else:
        lines.append("No candidate beat the gate - prompts unchanged.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="SkillOpt-Sleep - gated skill optimizer")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args(argv)
    print(render_skillopt(run_skillopt(args.channel)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
