"""#630: run every safety gate against fixtures and report what it does.

Six gates stand between a draft and paid TTS or a publish (`main.py:356-621`), plus the
unattended render gate (`jobs/worker.py:199`) and the publish dead-man's switch
(`publishing/youtube_publisher.py:490`). Three of them default to warn or off, so "the
gate works" and "the gate is armed on this machine" were both taken on trust.

Each gate gets a fixture that must block and one that must pass, run with the gate's
env armed and restored afterwards. Every fixture is passed in, so no store is read and
the verdict cannot depend on the operator's data. `armed_here` repeats the blocking
fixture under the real environment: a gate off by choice is shown, never failed.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace

from core.logging import get_logger

logger = get_logger("core.selftest")

_CHANNEL = "tapin"
_COPIED_SCRIPT = "Jones beat Pereira at UFC three twenty in the second round. " * 6
_CLEAN_SCRIPT = (
    "I think Jones wins the rematch, and the numbers from their first fight explain why. "
    "He landed forty two significant strikes to Pereira's thirty, took him down twice, "
    "and controlled the clinch for most of the third round. Pereira adjusted late, but "
    "the judges had already seen enough. My prediction is a decision win again, unless "
    "Pereira finds the left hook that dropped Jones in the fourth."
)
_NOW = 1_000_000.0


@dataclass
class GateResult:
    name: str
    label: str
    blocks: bool
    allows: bool
    armed_here: bool
    arm: str
    detail: str = ""

    @property
    def works(self) -> bool:
        return self.blocks and self.allows


@dataclass
class _Case:
    name: str
    label: str
    arm: dict[str, str]
    blocked: Callable[[], bool]
    allowed: Callable[[], bool]


@contextmanager
def env_overlay(values: dict[str, str]) -> Iterator[None]:
    """Set env keys for the block; restore each one, including absent ones, after."""
    saved = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def _authenticity(script: str, *, facts: int, recent: list[str]) -> bool:
    from core.authenticity import blocks_render, evaluate_authenticity

    return blocks_render(evaluate_authenticity(script, _CHANNEL, fact_count=facts, recent=recent))


def _grounding(unsupported: list[str]) -> bool:
    from core.claim_verifier import gate_blocks

    return gate_blocks({"total": 2, "supported": 2 - len(unsupported), "unsupported": unsupported})


def _negative(items: list[str]) -> bool:
    from core.negative_facts import negative_gate_blocks

    return negative_gate_blocks(items)


def _thin(fact_count: int, support: float) -> bool:
    from core.thin_facts import thin_facts_abort_reason

    return (
        thin_facts_abort_reason(fact_count=fact_count, features={"claim_support_rate": support})
        is not None
    )


def _over_length(script: str) -> bool:
    from core.tts_char_cap import tts_char_cap_reason

    return tts_char_cap_reason(script) is not None


def _metrics(metrics_json: str) -> bool:
    from core.metrics_gate import metrics_gate_reason

    row = SimpleNamespace(
        published_at=datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc), metrics_json=metrics_json
    )
    return metrics_gate_reason(_CHANNEL, today=date(2026, 1, 15), rows=[row]) is not None


def _render_missing_run() -> bool:
    from core.render_gate import block_reason_for_run

    return block_reason_for_run(None) is not None


def _render_good_draft() -> bool:
    from core.render_gate import unattended_render_block_reason

    return unattended_render_block_reason(letter="A", authenticity_verdict="ok") is not None


def _deadman(age_seconds: float) -> bool:
    from core.publish_deadman import deadman_block_reason

    return deadman_block_reason(last_human_at=_NOW - age_seconds, now=_NOW) is not None


_CASES: tuple[_Case, ...] = (
    _Case(
        "authenticity",
        "Authenticity gate",
        {"AUTHENTICITY_GATE": "block"},
        lambda: _authenticity(_COPIED_SCRIPT, facts=0, recent=[_COPIED_SCRIPT]),
        lambda: not _authenticity(_CLEAN_SCRIPT, facts=3, recent=[]),
    ),
    _Case(
        "grounding",
        "Grounding gate",
        {"GROUNDING_GATE": "block"},
        lambda: _grounding(["Jones holds three belts"]),
        lambda: not _grounding([]),
    ),
    _Case(
        "negative_fact",
        "Negative-fact veto",
        {"NEGATIVE_FACT_GATE": "block"},
        lambda: _negative(["negative-fact: Pereira retired in 2024"]),
        lambda: not _negative(["Pereira"]),
    ),
    _Case(
        "thin_facts",
        "Thin facts",
        {
            "THIN_FACTS_TTS_ABORT": "true",
            "THIN_FACTS_MIN_LINES": "3",
            "THIN_FACTS_MIN_SUPPORT": "0.5",
        },
        lambda: _thin(0, 0.9),
        lambda: not _thin(5, 0.9),
    ),
    _Case(
        "over_length",
        "Over length for TTS",
        {"TTS_MAX_CHARS": "5000"},
        lambda: _over_length("word " * 1500),
        lambda: not _over_length("A short script about the rematch."),
    ),
    _Case(
        "metrics",
        "Metrics gate",
        {"METRICS_BEFORE_NEXT": "true"},
        lambda: _metrics("{}"),
        lambda: not _metrics('{"views": 10}'),
    ),
    _Case(
        "unattended_render",
        "Unattended render gate",
        {"OVERNIGHT_RENDER_GATE": "true"},
        _render_missing_run,
        lambda: not _render_good_draft(),
    ),
    _Case(
        "publish_deadman",
        "Publish dead-man's switch",
        {"PUBLISH_DEADMAN_DAYS": "3"},
        lambda: _deadman(30 * 86400),
        lambda: not _deadman(3600),
    ),
)


def run_selftest() -> list[GateResult]:
    results: list[GateResult] = []
    for case in _CASES:
        detail = ""
        try:
            with env_overlay(case.arm):
                blocks = bool(case.blocked())
                allows = bool(case.allowed())
        except Exception as exc:
            blocks = allows = False
            detail = f"raised {type(exc).__name__}: {exc}"
        try:
            armed = bool(case.blocked())
        except Exception as exc:
            logger.debug("selftest armed-here probe for %s failed: %s", case.name, exc)
            armed = False
        if not detail and not blocks:
            detail = "the blocking fixture passed through"
        elif not detail and not allows:
            detail = "the clean fixture was blocked"
        arm = ", ".join(f"{key}={value}" for key, value in case.arm.items())
        results.append(GateResult(case.name, case.label, blocks, allows, armed, arm, detail))
    return results


def render_selftest(results: list[GateResult]) -> str:
    failed = [r for r in results if not r.works]
    lines = [f"Safety gate selftest: {len(results) - len(failed)}/{len(results)} gates work"]
    for r in results:
        status = "ok" if r.works else "FAIL"
        armed = "yes" if r.armed_here else f"no  (arm with {r.arm})"
        lines.append(f"  {r.name:<18} {status:<5} armed here: {armed}")
        if r.detail:
            lines.append(f"  {'':<18} {r.detail}")
    lines.append("")
    lines.append(
        "works = blocks its bad fixture and passes its clean one with the gate armed. "
        "armed here = would block with this machine's settings; off by choice is not a failure."
    )
    return "\n".join(lines)
