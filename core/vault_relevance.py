"""Deterministic, corpus-aware subject relevance for vault facts (candidate 329 P2).

The legacy reader chains boolean topic-token and franchise gates.  This module keeps
each signal independent so strong corpus evidence can compensate for a missing hand-
maintained anchor, while a competing family remains visible as a negative feature.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core import process_state
from core.authenticity import _content_cosine
from core.channel_context import anchor_families
from core.fact_grounding import mentions, specific_entities
from core.fact_store import tier_weight
from core.logging import get_logger

logger = get_logger("core.vault_relevance")

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "vault_relevance.json"
_VALID_MODES = frozenset({"legacy", "shadow", "scored"})
_VALID_POLICIES = frozenset({"operator", "public", "web_skip"})


@dataclass(frozen=True)
class VaultRelevanceConfig:
    schema_version: str
    scorer_version: str
    default_mode: str
    cosine_reference: float
    weights: dict[str, float]
    thresholds: dict[str, dict[str, float]]


@dataclass(frozen=True)
class VaultRelevanceDecision:
    score: float
    band: str
    scorer_version: str
    policy: str
    breakdown: dict[str, Any]
    pre_tiebreak_band: str = ""
    tiebreak_status: str = ""
    tiebreak_reason: str = ""

    @property
    def attaches(self) -> bool:
        return self.band != "reject"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "score": self.score,
            "band": self.band,
            "scorer_version": self.scorer_version,
            "policy": self.policy,
            "breakdown": dict(self.breakdown),
        }
        if self.pre_tiebreak_band:
            out["pre_tiebreak_band"] = self.pre_tiebreak_band
        if self.tiebreak_status:
            out["tiebreak_status"] = self.tiebreak_status
        if self.tiebreak_reason:
            out["tiebreak_reason"] = self.tiebreak_reason
        return out


_config_cache: VaultRelevanceConfig | None = None


def _as_float_map(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def load_relevance_config(*, refresh: bool = False) -> VaultRelevanceConfig:
    """Load the shipped scorer settings; invalid config is a visible hard error.

    Relevance config controls public citations and paid-search skipping once P3 flips,
    so silently substituting guessed defaults would be worse than refusing scored mode.
    """
    global _config_cache
    if _config_cache is not None and not refresh:
        return _config_cache
    with _CONFIG_PATH.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    weights = _as_float_map(raw.get("weights"))
    expected = {
        "bullet_entity",
        "note_entity",
        "bullet_cosine",
        "note_cosine",
        "anchor",
        "tier",
    }
    if set(weights) != expected or any(value < 0 for value in weights.values()):
        raise ValueError("vault relevance weights are missing or invalid")
    thresholds: dict[str, dict[str, float]] = {}
    for policy in _VALID_POLICIES:
        values = _as_float_map((raw.get("thresholds") or {}).get(policy))
        if not {"uncertain", "confident"} <= set(values):
            raise ValueError(f"vault relevance thresholds missing for {policy}")
        if not 0 <= values["uncertain"] <= values["confident"] <= 1:
            raise ValueError(f"vault relevance thresholds invalid for {policy}")
        thresholds[policy] = values
    default_mode = str(raw.get("default_mode") or "legacy").strip().lower()
    if default_mode not in _VALID_MODES:
        raise ValueError("vault relevance default_mode is invalid")
    cosine_reference = float(raw.get("cosine_reference") or 0)
    if cosine_reference <= 0:
        raise ValueError("vault relevance cosine_reference must be positive")
    scorer_version = str(raw.get("scorer_version") or "").strip()
    if not scorer_version:
        raise ValueError("vault relevance scorer_version is required")
    _config_cache = VaultRelevanceConfig(
        schema_version=str(raw.get("schema_version") or "v1"),
        scorer_version=scorer_version,
        default_mode=default_mode,
        cosine_reference=cosine_reference,
        weights=weights,
        thresholds=thresholds,
    )
    return _config_cache


def relevance_mode() -> str:
    """Runtime rollout mode. Invalid overrides fall back visibly to shipped config."""
    config = load_relevance_config()
    raw = os.getenv("VAULT_RELEVANCE_MODE", "").strip().lower()
    if not raw:
        return config.default_mode
    if raw in _VALID_MODES:
        return raw
    logger.warning(
        "Unknown VAULT_RELEVANCE_MODE=%r; using shipped default %s",
        raw,
        config.default_mode,
    )
    return config.default_mode


def build_relevance_corpus(
    signals: dict[str, Any] | None,
    *,
    operator_facts: Iterable[str] | None = None,
    include_web: bool = True,
) -> str:
    """Subject evidence from signal text plus explicit operator/link facts.

    The candidate fact and editorial angle are intentionally not accepted arguments,
    which prevents self-grounding and the run-71 angle ambiguity by construction.
    """
    from core.signal_facts import DEMAND_SIGNALS, format_signal_facts

    # Popularity payloads name whatever is trending, not the subject: run 98's Twitch
    # top-games dump put "Marvel Rivals" in this corpus and gave an unrelated Marvel
    # Rivals vault bullet full entity support on a Manchester City topic.
    selected = {
        name: signal
        for name, signal in (signals or {}).items()
        if not name.startswith("_")
        and name not in DEMAND_SIGNALS
        and (include_web or name != "web_search")
    }
    signal_text = format_signal_facts(selected)
    if signal_text == "No structured facts from signals.":
        signal_text = ""
    facts = [str(fact).strip() for fact in operator_facts or [] if str(fact).strip()]
    return "\n".join(part for part in (signal_text.strip(), "\n".join(facts)) if part)


def _entity_support(text: str, corpus: str) -> tuple[float | None, int, int, list[str]]:
    entities = specific_entities(text or "")
    if not entities:
        return None, 0, 0, []
    supported = [entity for entity in entities if mentions(corpus, entity)]
    return len(supported) / len(entities), len(supported), len(entities), entities


def _anchor_alignment(
    topic: str, note_context: str, bullet: str
) -> tuple[float, list[str], list[str]]:
    topic_families = anchor_families(topic)
    fact_families = anchor_families(f"{note_context} {bullet}")
    if topic_families and (fact_families - topic_families):
        alignment = -1.0
    elif topic_families & fact_families:
        alignment = 1.0
    else:
        alignment = 0.0
    return alignment, sorted(topic_families), sorted(fact_families)


def _scaled_cosine(text: str, corpus: str, reference: float) -> tuple[float, float]:
    raw = _content_cosine(text or "", corpus or "")
    return raw, min(max(raw / reference, 0.0), 1.0)


def score_vault_fact(
    *,
    topic: str,
    corpus: str,
    bullet: str,
    note_context: str,
    tier: str,
    policy: str = "operator",
    config: VaultRelevanceConfig | None = None,
) -> VaultRelevanceDecision:
    """Return an additive evidence score and an explainable confidence band."""
    config = config or load_relevance_config()
    policy = policy if policy in _VALID_POLICIES else "operator"
    weights = config.weights

    bullet_entity, bullet_supported, bullet_total, bullet_entities = _entity_support(bullet, corpus)
    note_entity, note_supported, note_total, note_entities = _entity_support(note_context, corpus)
    bullet_cosine, bullet_cosine_scaled = _scaled_cosine(bullet, corpus, config.cosine_reference)
    note_cosine, note_cosine_scaled = _scaled_cosine(note_context, corpus, config.cosine_reference)
    anchor, topic_families, fact_families = _anchor_alignment(topic, note_context, bullet)
    tier_value = tier_weight(tier)

    values: dict[str, float | None] = {
        "bullet_entity": bullet_entity,
        "note_entity": note_entity,
        "bullet_cosine": bullet_cosine_scaled,
        "note_cosine": note_cosine_scaled,
        # Missing anchors are weak/unknown evidence, not an automatic rejection.
        "anchor": anchor if topic_families or fact_families else None,
        "tier": tier_value,
    }
    contributions: dict[str, float] = {}
    numerator = 0.0
    denominator = 0.0
    for name, value in values.items():
        if value is None:
            contributions[name] = 0.0
            continue
        weight = weights[name]
        contribution = value * weight
        contributions[name] = contribution
        numerator += contribution
        denominator += weight
    score = min(max(numerator / denominator if denominator else 0.0, 0.0), 1.0)
    score = round(score, 4)

    thresholds = config.thresholds[policy]
    if score >= thresholds["confident"]:
        band = "confident"
    elif score >= thresholds["uncertain"]:
        band = "uncertain"
    else:
        band = "reject"

    breakdown: dict[str, Any] = {
        "bullet_entity_support": (round(bullet_entity, 4) if bullet_entity is not None else None),
        "bullet_entities_supported": bullet_supported,
        "bullet_entities_total": bullet_total,
        "bullet_entities": bullet_entities,
        "note_entity_support": round(note_entity, 4) if note_entity is not None else None,
        "note_entities_supported": note_supported,
        "note_entities_total": note_total,
        "note_entities": note_entities,
        "bullet_cosine": round(bullet_cosine, 4),
        "note_cosine": round(note_cosine, 4),
        "anchor_alignment": anchor,
        "topic_families": topic_families,
        "fact_families": fact_families,
        "tier_weight": tier_value,
    }
    for name, contribution in contributions.items():
        breakdown[f"{name}_contribution"] = round(contribution, 4)

    return VaultRelevanceDecision(
        score=score,
        band=band,
        scorer_version=config.scorer_version,
        policy=policy,
        breakdown=breakdown,
    )


_INSPECT_REJECT_WINDOW = 0.1


def is_inspect_reject(
    decision: VaultRelevanceDecision, *, config: VaultRelevanceConfig | None = None
) -> bool:
    """True when a reject is close enough to the uncertain floor to show, not attach."""
    if decision.band != "reject":
        return False
    config = config or load_relevance_config()
    floor = float(config.thresholds[decision.policy]["uncertain"]) - _INSPECT_REJECT_WINDOW
    return decision.score >= max(0.0, floor)


def compact_reasons(decision: VaultRelevanceDecision, *, limit: int = 3) -> list[str]:
    """Largest-magnitude score contributions, suitable for one console line."""
    rows: list[tuple[float, str]] = []
    labels = {
        "bullet_entity": "bullet entity",
        "note_entity": "note entity",
        "bullet_cosine": "bullet cosine",
        "note_cosine": "note cosine",
        "anchor": "anchor",
        "tier": "tier",
    }
    for name, label in labels.items():
        value = decision.breakdown.get(f"{name}_contribution")
        if isinstance(value, int | float) and value:
            rows.append((abs(float(value)), f"{label} {float(value):+.2f}"))
    rows.sort(reverse=True)
    return [text for _, text in rows[:limit]]


TIEBREAK_PROMPT_VERSION = "vault_tiebreak_v1"
_tiebreak_cache: dict[str, VaultRelevanceDecision] = {}


def reset_tiebreak_cache() -> None:
    _tiebreak_cache.clear()


def _tiebreak_enabled() -> bool:
    return os.getenv("VAULT_RELEVANCE_TIEBREAK", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _tiebreak_key(topic: str, bullet: str, corpus: str, scorer_version: str) -> str:
    digest = hashlib.sha256((corpus or "").encode("utf-8")).hexdigest()[:16]
    return "|".join(
        (
            TIEBREAK_PROMPT_VERSION,
            scorer_version,
            (topic or "").strip().lower(),
            (bullet or "").strip().lower(),
            digest,
        )
    )


def maybe_tiebreak_uncertain(
    decision: VaultRelevanceDecision,
    *,
    topic: str,
    corpus: str,
    bullet: str,
    note_context: str,
) -> VaultRelevanceDecision:
    """Optional extract-tier JSON judge for operator-facing uncertain records.

    Default off. Never used for public Sources: or web-search skip. Failure keeps
    the deterministic uncertain band and records the miss (decisions §25).
    """
    if decision.band != "uncertain" or decision.policy != "operator":
        return decision
    if not _tiebreak_enabled():
        return decision
    key = _tiebreak_key(topic, bullet, corpus, decision.scorer_version)
    cached = _tiebreak_cache.get(key)
    if cached is not None:
        return cached
    try:
        from core.llm_router import complete_json

        payload = complete_json(
            (
                f"Topic: {topic}\nCorpus:\n{(corpus or '')[:1500]}\n"
                f"Note: {note_context}\nBullet: {bullet}\n"
            ),
            tier="extract",
            system=(
                "Decide whether the vault bullet is about the SAME subject as the "
                "topic, using the corpus as evidence. Return JSON "
                '{"band": "confident"|"uncertain"|"reject", "reason": "short"}.'
            ),
            temperature=0,
            max_tokens=120,
            stage="vault_tiebreak",
        )
    except Exception as exc:
        logger.warning("vault relevance tiebreak failed; keeping uncertain: %s", exc)
        return replace(
            decision,
            pre_tiebreak_band=decision.band,
            tiebreak_status="failed",
            tiebreak_reason=str(exc)[:160],
        )
    band = ""
    reason = ""
    if isinstance(payload, dict):
        band = str(payload.get("band") or "").strip().lower()
        reason = str(payload.get("reason") or "").strip()[:160]
    if band not in {"confident", "uncertain", "reject"}:
        logger.warning(
            "vault relevance tiebreak returned an unusable band %r; keeping uncertain",
            band,
        )
        return replace(
            decision,
            pre_tiebreak_band=decision.band,
            tiebreak_status="failed",
            tiebreak_reason=f"unusable band {band!r}",
        )
    out = replace(
        decision,
        band=band,
        pre_tiebreak_band="uncertain",
        tiebreak_status="ok",
        tiebreak_reason=reason,
    )
    _tiebreak_cache[key] = out
    return out


# --- process-global state reset (#827) --------------------------------------
def _reset_process_state() -> None:
    global _config_cache
    _config_cache = None
    _tiebreak_cache.clear()


process_state.register_reset("core.vault_relevance", _reset_process_state)
