"""One checklist before an upload (#1065).

Disclosure, footage credits, chapters, title and made-for-kids were each decided somewhere -
when the description was built, when the run was saved, inside the insert body - and nothing
looked at the finished upload once, as a whole. Each check here wraps the function that
already decides it; none adds a rule.

Two refuse the upload, because nobody notices them afterwards: a title YouTube rejects, and a
footage credit a clip's licence requires (#1019) that is no longer in the description. The
rest warn. `YouTubePublisher.publish` runs it before any API call; `ops publish-dry-run`
prints it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from publishing.base import PublishRequest

logger = get_logger("publishing.prepublish")

TITLE_MAX = 100  # YouTube's limit on snippet.title


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    blocks: bool = False


def _disclosure_line(channel_id: str) -> str:
    from core.description_extras import ai_disclosure_line

    return ai_disclosure_line(channel_id) or ""


def _run(content_run_id: int | None) -> Any | None:
    if not content_run_id:
        return None
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository().get(int(content_run_id))


def _features(run: Any | None) -> dict[str, Any]:
    try:
        features = json.loads(getattr(run, "features_json", None) or "{}") if run else {}
    except (TypeError, ValueError):
        return {}
    return features if isinstance(features, dict) else {}


def required_credits(run_description: str) -> list[str]:
    """The lines of the run's "Footage:" block - what `persist_footage_credits` wrote."""
    lines = (run_description or "").splitlines()
    if "Footage:" not in lines:
        return []
    out: list[str] = []
    for line in lines[lines.index("Footage:") + 1 :]:
        if not line.strip():
            break
        out.append(line.strip())
    return out


def _title(request: PublishRequest) -> Check:
    title = (request.title or "").strip()
    if not title:
        return Check("title", False, "title is empty", True)
    if len(title) > TITLE_MAX:
        return Check(
            "title", False, f"title is {len(title)} characters; YouTube takes {TITLE_MAX}", True
        )
    return Check("title", True, f"{len(title)} characters", True)


def _disclosure(request: PublishRequest, channel_id: str) -> Check:
    line = _disclosure_line(channel_id)
    if not line:
        return Check("disclosure", True, "no disclosure line set for this channel")
    if line in (request.description or ""):
        return Check("disclosure", True, "AI disclosure line present")
    return Check("disclosure", False, "the AI disclosure line is not in the description")


def _credits(request: PublishRequest, run: Any | None) -> Check:
    needed = required_credits(str(getattr(run, "description", "") or ""))
    missing = [line for line in needed if line not in (request.description or "")]
    if missing:
        return Check(
            "credits", False, "footage credit missing from the description: " + missing[0], True
        )
    count = f"{len(needed)} credit line(s) present" if needed else "no clip licence needs a credit"
    return Check("credits", True, count, True)


def _chapters(request: PublishRequest, run: Any | None) -> Check:
    if not _features(run).get("all_angles"):
        return Check("chapters", True, "not an all-angles video")
    if "0:00" in (request.description or ""):
        return Check("chapters", True, "chapter list starts at 0:00")
    return Check("chapters", False, "an all-angles video with no 0:00 chapter list")


def _made_for_kids(request: PublishRequest, channel_id: str) -> Check:
    from publishing.youtube_publisher import build_video_status

    status = build_video_status(request, channel_id=channel_id)
    declared = status.get("selfDeclaredMadeForKids")
    return Check(
        "made_for_kids",
        declared is False,
        "declared not made for kids" if declared is False else f"declared {declared!r}",
        True,
    )


def checklist(
    request: PublishRequest, *, channel_id: str, content_run_id: int | None = None
) -> list[Check]:
    """Every check, in a fixed order. A check that cannot run is left out and logged."""
    try:
        run = _run(content_run_id)
    except Exception as exc:
        logger.warning("pre-publish: run %s not read: %s", content_run_id, exc)
        run = None
    makers = (
        lambda: _title(request),
        lambda: _disclosure(request, channel_id),
        lambda: _credits(request, run),
        lambda: _chapters(request, run),
        lambda: _made_for_kids(request, channel_id),
    )
    out: list[Check] = []
    for make in makers:
        try:
            out.append(make())
        except Exception as exc:
            logger.warning("pre-publish check skipped: %s", exc)
    return out


def block_reason(checks: list[Check]) -> str:
    """The first blocking failure as one line, or "" when the upload may go."""
    for check in checks:
        if not check.ok and check.blocks:
            return f"pre-publish check failed: {check.detail}"
    return ""


def render(checks: list[Check]) -> list[str]:
    def mark(check: Check) -> str:
        if check.ok:
            return "ok"
        return "BLOCK" if check.blocks else "warn"

    return [f"  [{mark(check)}] {check.name}: {check.detail}" for check in checks]
