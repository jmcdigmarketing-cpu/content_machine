"""YouTube snippet/status helpers (candidates 102, 107, 108, 117, 129).

Category from infer_domain, selfDeclaredMadeForKids audit, default language,
title uniqueness vs own catalog, UFC/trademark title lint. Nested try; store
failures fail-open. Never writes quota stores.
"""

from __future__ import annotations

import os
import re
from typing import Any

from core.logging import get_logger

logger = get_logger("core.youtube_meta")

# YouTube Data API category ids.
# 17 Sports · 20 Gaming · 24 Entertainment · 25 News & Politics
CATEGORY_BY_DOMAIN = {
    "ufc": "17",
    "nba": "17",
    "nfl": "17",
    "gaming": "20",
    "finance": "25",
    "anime": "24",
    "popculture": "24",
}
DEFAULT_CATEGORY_ID = "20"

_TITLE_PUNCT = re.compile(r"[^a-z0-9]+")
_UFC_WORD = re.compile(r"\bufc\b", re.IGNORECASE)
_UFC_OFFICIAL = re.compile(r"\b(official\s+ufc|ufc\s+official)\b", re.IGNORECASE)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def category_id_for_domain(domain: str | None) -> str:
    key = (domain or "").strip().lower()
    return CATEGORY_BY_DOMAIN.get(key, DEFAULT_CATEGORY_ID)


def category_id_for_topic(topic: str, channel_id: str | None = None) -> str:
    try:
        from apis.topic_scorer import infer_domain

        domain = infer_domain(topic or "", channel_id)
    except Exception as exc:
        logger.debug("infer_domain skipped: %s", exc)
        domain = ""
    return category_id_for_domain(domain)


def default_language() -> str | None:
    """BCP-47 tag for snippet.defaultLanguage, or None when disabled."""
    raw = (os.getenv("YOUTUBE_DEFAULT_LANGUAGE", "en") or "en").strip()
    if raw.lower() in ("0", "off", "false", "no", ""):
        return None
    return raw


def apply_snippet_defaults(
    snippet: dict[str, Any], *, topic: str = "", channel_id: str | None = None
) -> dict[str, Any]:
    """Fill categoryId (when empty) + defaultLanguage / defaultAudioLanguage."""
    out = dict(snippet)
    cat = str(out.get("categoryId") or "").strip()
    if not cat:
        title = topic or str(out.get("title") or "")
        out["categoryId"] = category_id_for_topic(title, channel_id)
    lang = default_language()
    if lang:
        out["defaultLanguage"] = lang
        out["defaultAudioLanguage"] = lang
    return out


def audit_made_for_kids(status: dict[str, Any]) -> dict[str, Any]:
    """Force selfDeclaredMadeForKids=false on every insert. Log if it was True."""
    out = dict(status)
    if out.get("selfDeclaredMadeForKids") is True:
        logger.warning("madeForKids was True; forcing False (self-declared audit)")
    out["selfDeclaredMadeForKids"] = False
    return out


def normalize_title(title: str) -> str:
    return _TITLE_PUNCT.sub(" ", (title or "").casefold()).strip()


def uniqueness_mode() -> str:
    raw = (os.getenv("TITLE_UNIQUENESS", "warn") or "warn").strip().lower()
    if raw in ("0", "off", "false", "no"):
        return "off"
    if raw in ("block", "fail", "error"):
        return "block"
    return "warn"


def title_collision(
    title: str,
    channel_id: str,
    *,
    exclude_run_id: int | None = None,
) -> str | None:
    """Matching own-catalog title, or None. Store errors fail-open."""
    mode = uniqueness_mode()
    if mode == "off":
        return None
    needle = normalize_title(title)
    if not needle:
        return None
    try:
        from storage.repositories.content_runs import get_content_run_repository

        rows = get_content_run_repository().list_for_channel(channel_id)
    except Exception as exc:
        logger.debug("title uniqueness skipped: %s", exc)
        return None
    for row in rows:
        rid = getattr(row, "id", None)
        if exclude_run_id is not None and rid == exclude_run_id:
            continue
        other = normalize_title(getattr(row, "title", "") or "")
        if other and other == needle:
            return f"title collision vs run #{rid}: {getattr(row, 'title', '')[:80]}"
    return None


def lint_ufc_title(title: str, *, domain: str | None = None) -> list[str]:
    """Trademark-ish title warnings. Empty when UFC_TITLE_LINT is off."""
    if not _flag("UFC_TITLE_LINT", True):
        return []
    text = title or ""
    try:
        from core.publish_windows import is_ufc_videogame_topic

        if is_ufc_videogame_topic(text):
            return []
    except Exception as exc:
        logger.debug("ufc videogame title check skipped: %s", exc)
    warnings: list[str] = []
    if _UFC_OFFICIAL.search(text):
        warnings.append("title claims official UFC branding - use fight-night wording")
    if _UFC_WORD.search(text):
        dom = (domain or "").strip().lower()
        if dom and dom not in ("ufc", "mma"):
            warnings.append("UFC in title on a non-UFC topic - trademark/SEO mismatch")
    return warnings


def title_grounding_mode() -> str:
    """`warn` (default) or `off` — mirrors TITLE_UNIQUENESS's shape (#117)."""
    raw = (os.getenv("TITLE_GROUNDING", "warn") or "warn").strip().lower()
    return raw if raw in ("warn", "off") else "warn"


def lint_title_grounding(
    title: str,
    *,
    facts_text: str,
    priority_facts: list[str] | None = None,
    topic: str = "",
) -> list[str]:
    """Warn when the TITLE asserts something the facts do not back (candidate 321).

    The title is generated after grounding and the claim verifier have already passed
    on the *script*, and nothing re-checks the string `generate_title` returns. Live-run
    71 shipped "GTA 6 Leak Forces Rockstar to Subpoena Microsoft and Discord Records"
    when the operator's own key fact said the subpoenas came from Rockstar's *parent*
    (Take-Two).

    Token grounding cannot catch that: `Rockstar`, `Microsoft` and `Discord` are all
    present in the facts, so `find_ungrounded_entities` passes the title clean. The
    error is *relational* — the wrong actor performed the action — which is exactly what
    `verify_claims` checks ("direction, names, and numbers must match"). So this reuses
    the claim verifier with the title as the text, rather than adding a second extractor.

    One extra extract-tier call (free-first router) per generated title. Warn-only and
    fail-open: a `None` verdict is "no opinion", never "ok".
    """
    if title_grounding_mode() == "off":
        return []
    if not (title or "").strip():
        return []
    try:
        from core.claim_verifier import verify_claims

        verification = verify_claims(
            title,
            facts_text,
            topic=topic,
            priority_facts=priority_facts,
        )
    except Exception as exc:
        logger.debug("title grounding skipped: %s", exc)
        return []
    if verification is None:
        return []
    return [
        f"title claim not backed by the facts: {c.claim[:140]}" for c in verification.unsupported
    ]


_TITLE_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _sentence_case_against(title: str, script: str) -> str:
    """Lower-case the Title Case words the script uses as ordinary words.

    Title Case capitalises every word, so proper-noun extraction read a title that says
    exactly what the script says as one long ungrounded name. A word keeps its capital
    when it is an acronym or the script never writes it (or its stem) in lower case —
    so a name the script never mentions is still checked.
    """
    words = _TITLE_WORD_RE.findall(title or "")
    capped = [w for w in words if w[:1].isupper()]
    if len(words) < 3 or len(capped) < 0.6 * len(words):
        return title

    def _fold(match: re.Match[str]) -> str:
        word = match.group(0)
        if not word[:1].isupper() or (len(word) > 1 and word.isupper()):
            return word
        stem = word.lower()[:5]
        if re.search(rf"(?<![A-Za-z]){re.escape(stem)}", script or ""):
            return word.lower()
        return word

    return _TITLE_WORD_RE.sub(_fold, title)


def _heuristic_title_script_check(title: str, script: str) -> dict[str, object]:
    """Deterministic fallback when verify_claims cannot run."""
    from core.fact_grounding import find_ungrounded_entities

    flagged = find_ungrounded_entities(_sentence_case_against(title, script), script)
    warnings = [
        f"title contradicts or is not supported by the final script: {name[:140]}"
        for name in flagged
    ]
    return {
        "status": "failed" if warnings else "passed",
        "passed": not warnings,
        "warnings": warnings,
        "total": len(flagged),
        "method": "heuristic",
    }


def check_title_script_consistency(
    title: str,
    script: str,
    *,
    topic: str = "",
) -> dict[str, object]:
    """Advisory relational check between the public title and final script (#549).

    This is separate from ``lint_title_grounding``: a title can use names found
    in the fact corpus while assigning the action differently from the script.
    ``unavailable`` is persisted explicitly rather than looking like a pass.
    """
    if title_grounding_mode() == "off" or not title.strip() or not script.strip():
        return {
            "status": "not_evaluated",
            "passed": False,
            "warnings": [],
            "total": 0,
        }
    try:
        from core.claim_verifier import verify_claims

        verification = verify_claims(title, script, topic=topic)
    except Exception as exc:
        logger.debug("title/script check failed: %s", exc)
        verification = None
    if verification is None:
        # Run 76: extract-tier miss persisted unavailable and the check did
        # not run. Token overlap is weaker than verify_claims but it always
        # produces a verdict the operator can act on (#748).
        return _heuristic_title_script_check(title, script)
    warnings = [
        f"title contradicts or is not supported by the final script: {claim.claim[:140]}"
        for claim in verification.unsupported
    ]
    return {
        "status": "failed" if warnings else "passed",
        "passed": not warnings,
        "warnings": warnings,
        "total": verification.total,
    }
