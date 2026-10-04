"""What gameplay to record, and which past videos may show another game (#955).

`ops footage` lists the clips each playlist has. This reads the runs instead:

- A rendered run whose background fell through to stock B-roll or a plain background had no
  footage for its topic, so its playlist goes on the shopping list (while the chooser still
  finds no folder for it).
- A run rendered before #955 recorded no footage choice. If its topic matches no folder by
  name or playlist key, its folder was picked by the model from a trademark-stripped query, or
  at random - the Wemby Short cut UFC 5 fighters. Those videos are listed with what the chooser
  picks now, so they can be checked in Studio.

The chooser runs without the model here (`use_llm=False`): a report spends nothing.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.footage_gaps")

_LOCAL_PROVIDERS = frozenset({"local", "fast_cut", "hybrid", "owned"})
_FELL_THROUGH = frozenset({"none", "plain"})


def _run_repo():
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository()


def _asset_repo():
    from storage.repositories.assets import get_asset_repository

    return get_asset_repository()


def _background(run_id: int) -> Any | None:
    try:
        rows = _asset_repo().list_for_run(run_id) or []
    except Exception as exc:
        logger.debug("assets for run %s unavailable: %s", run_id, exc)
        return None
    backgrounds = [r for r in rows if getattr(r, "asset_type", "") == "background"]
    return backgrounds[-1] if backgrounds else None


def recorded_choice(source_id: str) -> tuple[str, str] | None:
    """(how, folder) from a `footage:<how>:<folder>` id; None before #955 or for stock."""
    text = str(source_id or "")
    if not text.startswith("footage:"):
        return None
    _prefix, how, folder = (text.split(":", 2) + ["", ""])[:3]
    return how, folder


def _playlist(channel_id: str, topic: str) -> str:
    try:
        from core.playlists import playlists_for

        names = playlists_for(channel_id, topic)
    except Exception as exc:
        logger.debug("playlist for %r unavailable: %s", topic, exc)
        names = []
    if names:
        return str(names[0])
    try:
        from apis.topic_scorer import infer_topic_domain

        domain = infer_topic_domain(topic)
    except Exception:
        domain = "neutral"
    return "no playlist" if domain in ("", "neutral") else f"{domain} (no playlist)"


def _used(provider: str, path: str) -> str:
    from assets import local_provider as lp

    base = os.path.abspath(lp.BASE_VIDEO_DIR)
    folder = os.path.dirname(os.path.abspath(path or ""))
    if path and (folder == base or folder.startswith(base + os.sep)):
        return f"{provider}: {os.path.basename(folder)}"
    return provider


def footage_gaps(channel_id: str, *, limit: int = 60) -> dict[str, Any]:
    """{rendered, wanted: [{playlist, runs, topics}], at_risk: [{run_id, topic, used, now, how}]}."""
    from assets import local_provider as lp

    base = lp.BASE_VIDEO_DIR
    folders = lp._get_subfolders(base) if os.path.isdir(base) else []
    try:
        runs = list(_run_repo().list_for_channel(channel_id) or [])
    except Exception as exc:
        logger.debug("runs unavailable: %s", exc)
        runs = []
    runs = sorted(runs, key=lambda r: int(getattr(r, "id", 0) or 0))[-limit:]
    wanted: dict[str, dict[str, Any]] = {}
    at_risk: list[dict[str, Any]] = []
    rendered = 0
    for run in runs:
        background = _background(int(run.id))
        if background is None:
            continue
        rendered += 1
        topic = str(getattr(run, "selected_topic", "") or getattr(run, "input_topic", "") or "")
        provider = str(getattr(background, "provider", "") or "")
        recorded = recorded_choice(getattr(background, "source_id", ""))
        folder, how = (
            lp.choose_footage(topic, folders, channel_id, use_llm=False)
            if folders
            else (None, "none")
        )
        pre_955_local = recorded is None and provider in _LOCAL_PROVIDERS
        if pre_955_local and how not in ("keyword", "alias"):
            at_risk.append(
                {
                    "run_id": int(run.id),
                    "topic": topic,
                    "used": _used(provider, str(getattr(background, "path", "") or "")),
                    "now": os.path.basename(folder) if folder else None,
                    "how": how,
                }
            )
        fell_through = (
            (recorded is not None and recorded[0] in _FELL_THROUGH)
            or provider == "plain"
            or (recorded is None and provider not in _LOCAL_PROVIDERS)
            or pre_955_local
        )
        if fell_through and folder is None:
            name = _playlist(channel_id, topic)
            row = wanted.setdefault(name, {"playlist": name, "runs": [], "topics": []})
            row["runs"].append(int(run.id))
            row["topics"].append(topic)
    ordered = sorted(wanted.values(), key=lambda r: (-len(r["runs"]), r["playlist"]))
    return {"rendered": rendered, "runs": len(runs), "wanted": ordered, "at_risk": at_risk}


def footage_gap_lines(channel_id: str, *, limit: int = 60) -> list[str]:
    report = footage_gaps(channel_id, limit=limit)
    head = (
        f"Footage gaps - {channel_id} ({report['runs']} most recent runs, "
        f"{report['rendered']} rendered)"
    )
    if not report["wanted"] and not report["at_risk"]:
        return [head, "  Every rendered topic had matching footage."]
    lines = [head]
    if report["wanted"]:
        lines.append("  Record gameplay for (topics that had no matching footage):")
        for row in report["wanted"]:
            count = len(row["runs"])
            examples = "; ".join(f'"{t}"' for t in row["topics"][:2])
            lines.append(
                f"    {row['playlist']:<16} {count} run{'s' if count != 1 else ''}  e.g. {examples}"
            )
    if report["at_risk"]:
        lines.append(
            "  Past videos that may show another game (before #955 an unmatched topic drew a "
            "model-picked or random folder):"
        )
        for row in report["at_risk"]:
            now = (
                f"now {row['now']} (by its {row['how']})"
                if row["now"]
                else "now no footage: stock or plain"
            )
            lines.append(f'    run {row["run_id"]:<5} "{row["topic"]}" ({row["used"]}) -> {now}')
    lines.append("  py -m scripts.ops footage lists the clips each playlist has.")
    return lines
