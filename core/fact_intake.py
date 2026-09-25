"""#348 operator fact-intake linter — before vault capture, never on empty paste."""

from __future__ import annotations

from core.link_facts import looks_like_url
from core.logging import get_logger

logger = get_logger("core.fact_intake")


def lint_fact_intake(
    lines: list[str],
    *,
    vault_claims: list[str] | None = None,
) -> list[str]:
    """Warn on URL-only lines, duplicates, and paste that contradicts a vault note.

    Empty input returns [] and logs nothing (a blank paste is not a defect).
    """
    cleaned = [str(x).strip() for x in lines if str(x).strip()]
    if not cleaned:
        return []
    warnings: list[str] = []
    seen: set[str] = set()
    for line in cleaned:
        if looks_like_url(line) and len(line.split()) == 1:
            warnings.append(f"URL-only line (fetch it or add a claim): {line}")
        key = line.lower()
        if key in seen:
            warnings.append(f"duplicate fact: {line}")
        seen.add(key)
    if vault_claims:
        try:
            from core.fact_conflicts import find_fact_conflicts

            hits = find_fact_conflicts(cleaned, "\n".join(vault_claims))
            for hit in hits:
                warnings.append(f"contradicts vault: {hit.operator_line} vs {hit.other_line}")
        except Exception as exc:
            logger.debug("fact-intake conflict check skipped: %s", exc)
    return warnings
