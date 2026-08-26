"""Expert-Panel persona grading seam (Pillar 2 borrow; ericosiu/ai-marketing-skills).

An optional *qualitative* pre-publish pass: send the draft to a small panel of domain
personas (skeptical editor, SEO analyst, shorts editor …) and collect a score + written
justification from each. Personas are prompt files in `prompts/expert_panel/*.md` — the
filename (minus extension) is the persona name, the file body is that persona's system
prompt. Uses the existing `core/llm_router` (cheap tier) — no new dependency.

    EXPERT_PANEL_ENABLED=true     # default: false

OFF by default and fail-open: composes *beside* the deterministic report card in
`core/video_grade.grade_from_parts` (Pillar 2); it never blocks a publish (mirrors the
authenticity gate's opt-in posture). No personas or LLM ⇒ `ProviderResult.fail_open`.
"""

from __future__ import annotations

from pathlib import Path

from core.logging import get_logger
from core.providers import (
    STATUS_ERROR,
    STATUS_NOT_CONFIGURED,
    ProviderResult,
    flag_enabled,
)

logger = get_logger("core.grade")

SLOT = "expert_panel"
_PERSONA_DIR = Path(__file__).resolve().parent.parent / "prompts" / "expert_panel"


def _load_personas() -> list[tuple[str, str]]:
    """Return `(name, system_prompt)` for each `prompts/expert_panel/*.md`."""
    if not _PERSONA_DIR.is_dir():
        return []
    personas: list[tuple[str, str]] = []
    for path in sorted(_PERSONA_DIR.glob("*.md")):
        try:
            body = path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            logger.debug("Persona %s unreadable: %s", path.stem, exc)
            continue
        if body:
            personas.append((path.stem, body))
    return personas


def expert_panel_review(draft: str, channel_id: str | None = None) -> ProviderResult:
    """Run each persona over the draft; `data` is a list of `{persona, review}` dicts."""
    if not flag_enabled("EXPERT_PANEL_ENABLED"):
        return ProviderResult.fail_open(
            SLOT, "EXPERT_PANEL_ENABLED off", status=STATUS_NOT_CONFIGURED
        )
    personas = _load_personas()
    if not personas:
        return ProviderResult.fail_open(
            SLOT, "no persona prompts in prompts/expert_panel/", status=STATUS_NOT_CONFIGURED
        )
    try:
        from core.llm_router import complete
    except Exception as exc:
        return ProviderResult.fail_open(SLOT, f"llm_router unavailable: {exc}", status=STATUS_ERROR)

    reviews: list[dict[str, str]] = []
    for name, system_prompt in personas:
        try:
            out = complete(
                draft, tier="cheap", system=system_prompt, temperature=0.3, max_tokens=400
            )
        except Exception as exc:
            logger.info("expert-panel persona %s failed: %s", name, exc)
            continue
        if out and out.strip():
            reviews.append({"persona": name, "review": out.strip()})
    if not reviews:
        return ProviderResult.fail_open(SLOT, "no persona returned a review", status=STATUS_ERROR)
    return ProviderResult.success(SLOT, "expert_panel", data=reviews)


def persist_expert_panel(run_id: int, reviews: list[dict[str, str]]) -> None:
    """Merge panel output onto the run's quality_json (pre-existing keys stay)."""
    import json

    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    record = repo.get(run_id)
    quality: dict = {}
    if record is not None:
        try:
            loaded = json.loads(record.quality_json or "{}")
            if isinstance(loaded, dict):
                quality = loaded
        except Exception:
            quality = {}
    quality["expert_panel"] = reviews
    repo.update(run_id, {"quality_json": json.dumps(quality)})
