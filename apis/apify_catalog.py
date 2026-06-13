"""
Loader for config/apify_sources.json — the curated catalog of high-value
Apify actors. Signals call into here to get their actor id, credential key,
TTL, and input template so targets can be retuned without code changes.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any

from core.logging import get_logger

logger = get_logger("apis.apify_catalog")

_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "apify_sources.json",
)

_cache: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("apify_sources.json unreadable (%s) — using empty catalog", exc)
        _cache = {}
    return _cache


def get_source(name: str) -> dict[str, Any]:
    """Return a source entry by catalog key (e.g. 'youtube_competitors')."""
    return copy.deepcopy(_load().get(name, {}))


def source_enabled(name: str) -> bool:
    """A source is enabled unless it explicitly sets enabled:false."""
    return get_source(name).get("enabled", True) is not False


def domain_targets(domain: str) -> dict[str, Any]:
    """Return the target lists (subreddits, twitter_accounts, ...) for a domain."""
    targets = _load().get("domain_targets", {})
    return copy.deepcopy(targets.get(domain) or targets.get("neutral") or {})


def build_input(name: str, query: str, **overrides: Any) -> dict[str, Any]:
    """
    Materialise a source's input_template, substituting '{query}' anywhere it
    appears (in strings or one-element list placeholders) and applying overrides.
    """
    src = get_source(name)
    template = src.get("input_template", {})
    resolved = _substitute(template, query)
    resolved.update(overrides)
    return resolved


def _substitute(obj: Any, query: str) -> Any:
    if isinstance(obj, str):
        return obj.replace("{query}", query)
    if isinstance(obj, list):
        return [_substitute(v, query) for v in obj]
    if isinstance(obj, dict):
        return {k: _substitute(v, query) for k, v in obj.items()}
    return obj
