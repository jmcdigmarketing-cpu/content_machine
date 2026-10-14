"""`ops script-check` (#1143): is the finished script clean - over recorded runs, or one new draft.

Operator, 2026-10-11: "make sure it can output a clean script matching what I have recently
expressed". The check itself is `core.script_craft.script_check`; this module points it at the
scripts on record (no model call) and at one fresh draft of an idea the operator types (model
calls, no voice, no render), so the claim can be read off real output.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from core.logging import get_logger

logger = get_logger("core.runs.script_report")


def _features(run: Any) -> dict[str, Any]:
    try:
        value = json.loads(getattr(run, "features_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _script(run: Any) -> str:
    try:
        from core import run_trace

        return str(run_trace.full_script(run.id) or getattr(run, "script_preview", "") or "")
    except Exception as exc:
        logger.debug("script for run %s unreadable: %s", getattr(run, "id", "?"), exc)
        return str(getattr(run, "script_preview", "") or "")


def check_run(run: Any) -> dict[str, Any] | None:
    """The run's own stored check when it has one, else the check worked out from what the
    run kept (script, title, idea, flagged claims). None when there is no script."""
    features = _features(run)
    stored = features.get("script_clean")
    if isinstance(stored, dict) and "ok" in stored:
        return stored
    script = _script(run)
    if not script.strip():
        return None
    from core.angle_intent import intent_of
    from core.claim_types import blocking_unsupported
    from core.script_craft import script_check

    idea = str(getattr(run, "input_topic", "") or getattr(run, "selected_topic", "") or "")
    return script_check(
        script=script,
        title=str(getattr(run, "title", "") or ""),
        idea=idea,
        intent=intent_of(idea),
        unsupported=blocking_unsupported(features.get("claim_verification")),
    )


def _kind(reason: str) -> str:
    """The reason without its particulars, so the same fault counts once."""
    for key in (
        "claim(s) the facts",
        "knocks the stance",
        "points missing",
        "label",
        "hard to say",
    ):
        if key in reason:
            return {
                "claim(s) the facts": "a claim the facts do not support",
                "knocks the stance": "a sentence knocks the stance",
                "points missing": "one of your points is missing",
                "label": "a label in the title",
                "hard to say": "a sentence hard to say",
            }[key]
    return reason


def recorded_lines(channel_id: str, *, limit: int = 30) -> list[str]:
    """How many of the channel's newest `limit` scripts are clean, and what the rest carry."""
    from storage.repositories.content_runs import get_content_run_repository

    runs = sorted(
        get_content_run_repository().list_for_channel(channel_id) or [],
        key=lambda r: r.id,
        reverse=True,
    )
    checked: list[tuple[Any, dict[str, Any]]] = []
    for run in runs:
        if len(checked) >= limit:
            break
        check = check_run(run)
        if check is not None:
            checked.append((run, check))
    if not checked:
        return [f"Script check - {channel_id}: no recorded scripts."]
    clean = sum(1 for _run, check in checked if check.get("ok"))
    lines = [f"Script check - {channel_id}, newest {len(checked)} scripts: {clean} clean"]
    tally = Counter(_kind(str(why)) for _run, check in checked for why in check.get("why") or [])
    for reason, count in tally.most_common():
        lines.append(f"  {count:>3}  {reason}")
    shown = 0
    for run, check in checked:
        if check.get("ok") or shown >= 5:
            continue
        lines.append(f"  run {run.id}: {'; '.join(str(w) for w in check.get('why') or [])}")
        shown += 1
    return lines


def _own_idea_draft(channel_id: str, idea: str) -> Any:
    """One script for the operator's own idea, the way angle 1 writes it: their words as the
    brief, no take pushed onto it, stopped before the voice."""
    from core.batch_generation import _length_choice
    from core.pipeline import run_discovery, run_pipeline

    discovery = run_discovery(idea, channel_id=channel_id, brief=idea)
    if not discovery.evaluated:
        return None
    return run_pipeline(
        idea,
        discovery=discovery,
        variant_index=0,
        length_choice=_length_choice(channel_id, idea),
        proceed_video=False,
        channel_id=channel_id,
        creative_brief=idea,
        own_idea=True,
        own_topic=idea,
    )


def draft_lines(channel_id: str, idea: str) -> list[str]:
    """Write one draft for `idea` and print its script and its check."""
    from core.angle_intent import intent_of
    from core.script_craft import script_check_line

    try:
        result = _own_idea_draft(channel_id, idea)
    except Exception as exc:
        return [f"No draft for {idea!r}: {type(exc).__name__}: {exc}"]
    script = str(getattr(result, "script", "") or "") if result is not None else ""
    if not script.strip():
        why = getattr(result, "abort_reason", "") if result is not None else "no angles came back"
        return [f"No draft for {idea!r}: {why or 'the pipeline wrote no script'}"]
    features = getattr(result, "features", None) or {}
    check = features.get("script_clean")
    lines = [
        f"Idea:  {idea}",
        f"Read as: {intent_of(idea) or 'neutral'}   (run {getattr(result, 'run_id', '?')}, no render)",
        f"Title: {getattr(result, 'title', '')}",
        "",
        script.strip(),
        "",
        script_check_line(check) or "Script check: not stored for this run",
    ]
    return lines
