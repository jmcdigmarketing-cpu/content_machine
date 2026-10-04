"""Game names learned from the operator's own confirmed runs (#876).

`infer_topic_domain` knows a fixed list of franchises; "Silksong delayed again" and
"Palworld update" named none of them and read neutral. A run already records the
evidence: `features["domains"]` (#866) holds what the words said (`topic`) and what the
run decided (`effective`). `topic == "neutral"` with `effective == "gaming"` means a live
gaming signal matched to the topic (RAWG or Twitch; IGDB and Steam retired, #854) made it a game - so its
names are game names.

A name also seen in a run resolved to another domain is dropped (a sponsor, a club).
Runs from before #866 stored no `domains`; their `domain` was the channel fallback, so
run 98's Manchester City story said "gaming", and they teach nothing.

Sport names (#946) are learned the same way from runs resolved to a sport: "Steveson signs
with the UFC" teaches `steveson` -> ufc, so "Steveson's debut" stops reading as the channel's
gaming. A name seen in a run resolved to any other domain teaches nothing, and a name made only
of news-register words ("New Update") is not a name.

Loaded once per process. `LEARNED_GAME_NAMES=false` turns both off; the suite pins that,
so the operator's history cannot change a test's verdict.
"""

from __future__ import annotations

import json
import os
from typing import Any

from core import process_state
from core.logging import get_logger

logger = get_logger("core.learned_domain_terms")

_sources: dict[str, list[int]] | None = None
_sport_sources: dict[str, tuple[str, list[int]]] | None = None

# The domains a name can be learned for (#946); apis/topic_scorer checks them last.
SPORT_DOMAINS = frozenset({"nba", "nfl", "ufc", "soccer"})


def _enabled() -> bool:
    return os.getenv("LEARNED_GAME_NAMES", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _run_repo():
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository()


def _channel_ids() -> list[str]:
    from config.channels import list_channel_ids

    return list(list_channel_ids())


def _domains(run: Any) -> dict[str, Any] | None:
    try:
        features = json.loads(getattr(run, "features_json", "") or "{}")
    except (TypeError, ValueError):
        return None
    stored = features.get("domains") if isinstance(features, dict) else None
    return stored if isinstance(stored, dict) else None


def _names(topic: str) -> list[str]:
    from apis.topic_tokens import FUNCTION_WORDS, title_phrases

    out = []
    for phrase in title_phrases(topic or "", max_words=3):
        key = phrase.lower().strip()
        if len(key) >= 3 and key not in FUNCTION_WORDS:
            out.append(key)
    return out


def _load() -> dict[str, list[int]]:
    learned: dict[str, list[int]] = {}
    elsewhere: set[str] = set()
    try:
        repo = _run_repo()
        runs = [run for cid in _channel_ids() for run in (repo.list_for_channel(cid) or [])]
    except Exception as exc:
        logger.debug("learned game names unavailable: %s", exc)
        return {}
    for run in runs:
        domains = _domains(run)
        if not domains:
            continue
        topic = str(getattr(run, "selected_topic", "") or getattr(run, "input_topic", "") or "")
        names = _names(topic)
        if domains.get("topic") == "neutral" and domains.get("effective") == "gaming":
            for name in names:
                learned.setdefault(name, []).append(int(getattr(run, "id", 0) or 0))
        elif domains.get("effective") not in (None, "", "gaming", "neutral"):
            elsewhere.update(names)
    return {name: sorted(ids) for name, ids in learned.items() if name not in elsewhere}


def _is_name(name: str) -> bool:
    from apis.topic_tokens import content_tokens, distinctive_tokens

    return bool(distinctive_tokens(content_tokens(name, min_len=3)))


def _load_sports() -> dict[str, tuple[str, list[int]]]:
    """{name: (sport, run ids)} - names only ever seen in runs resolved to one sport."""
    taught: dict[str, dict[str, list[int]]] = {}
    elsewhere: set[str] = set()
    try:
        repo = _run_repo()
        runs = [run for cid in _channel_ids() for run in (repo.list_for_channel(cid) or [])]
    except Exception as exc:
        logger.debug("learned sport names unavailable: %s", exc)
        return {}
    for run in runs:
        domains = _domains(run)
        if not domains:
            continue
        topic = str(getattr(run, "selected_topic", "") or getattr(run, "input_topic", "") or "")
        names = [name for name in _names(topic) if _is_name(name)]
        effective = domains.get("effective")
        if effective in SPORT_DOMAINS and domains.get("topic") == effective:
            rid = int(getattr(run, "id", 0) or 0)
            for name in names:
                taught.setdefault(name, {}).setdefault(str(effective), []).append(rid)
        elif effective not in (None, "", "neutral"):
            elsewhere.update(names)
    out: dict[str, tuple[str, list[int]]] = {}
    for name, sports in taught.items():
        if len(sports) != 1 or name in elsewhere:
            continue
        ((sport, ids),) = sports.items()
        out[name] = (sport, sorted(ids))
    return out


def learned_sport_name_sources() -> dict[str, tuple[str, list[int]]]:
    """{learned name: (sport, run ids that taught it)}; {} when off or unreadable (#946)."""
    global _sport_sources
    if not _enabled():
        return {}
    if _sport_sources is None:
        _sport_sources = _load_sports()
    return dict(_sport_sources)


def learned_sport_names() -> dict[str, str]:
    """{lower-cased athlete / fighter name: sport} learned from confirmed runs."""
    return {name: sport for name, (sport, _ids) in learned_sport_name_sources().items()}


def learned_game_name_sources() -> dict[str, list[int]]:
    """{learned name: run ids that taught it}; {} when off or unreadable."""
    global _sources
    if not _enabled():
        return {}
    if _sources is None:
        _sources = _load()
    return dict(_sources)


def learned_game_names() -> frozenset[str]:
    """Lower-cased game names learned from confirmed runs."""
    return frozenset(learned_game_name_sources())


def reset_learned_terms() -> None:
    global _sources, _sport_sources
    _sources = None
    _sport_sources = None


process_state.register_reset("core.learned_domain_terms", reset_learned_terms)
