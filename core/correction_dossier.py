"""#112. A correction dossier when a post-publish fact reverses.

#341 built the retraction watch, #686 gave it a toast, #696 made it reach a real
URL. What none of them did was *record* anything: the toast showed the first hit,
truncated to 180 chars, deduped per process, joined to no run. A reversal spotted
overnight was gone by morning.

Two things this deliberately does differently from the watch it grew out of:

* **It walks published videos, not the last draft.** `notify_retractions_if_due`
  reads `last_trace(channel)` -- one most-recent run, usually not published. #112
  is about a claim that reversed *after* it went out, so the unit of work is a
  `publish_log` row joined to its content run.
* **It pairs a claim with the source that backed it.** The watch pairs the run's
  *topic string* against every URL, so a hit can say a page changed but never
  which claim it supported. This reads `claim_verification.claims[].citation_line`
  -- persisted for the first time by this same wave.

Nothing here deletes, unlists or edits published content. A dossier is written and
the operator decides; `record_negative` gates only *future* scripts.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.correction_dossier")

_MAX_BODY_CHARS = 8000
_MAX_SOURCES_PER_RUN = 6
_RETRACTION_WORDS = ("retraction", "retracted", "correction:", "we regret")
_CLAIM_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "at",
        "of",
        "and",
        "or",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "during",
    }
)
# Fraction of claim content-tokens that must still appear on the page for the
# claim to count as present (verbatim or ordinary rewording). Below this, the
# claim has vanished. Deliberately token-overlap, not substring: "Jones beat
# Pereira" vs "Jon Jones defeated Alex Pereira" would miss a substring test.
_CLAIM_PRESENT_COVERAGE = 0.5
# Coverage is only meaningful against a body that plausibly contains the article.
# An empty response, a whitespace body or a client-rendered shell all score near
# zero and would otherwise read as "the claim vanished" -- which is this module's
# own unreachable-is-not-clean rule run backwards.
#
# Token COUNT alone cannot separate a shell from a short-but-real update: the
# shell scored 5 and a legitimate one-sentence news line scores 7. The honest
# discriminator is article text vs markup, so `_content_tokens` strips tags and
# script/style blocks first -- which leaves a shell at 0 and the real update at 7.
# That also stops tag names ("div", "span") counting as claim matches in coverage.
_MIN_READABLE_TOKENS = 5
STAMP_PATH_TEMPLATE = os.path.join(DATA_DIR, "correction_scan_{channel}.json")


def correction_scan_stamp_path(channel_id: str) -> str:
    safe = "".join(ch for ch in str(channel_id) if ch.isalnum() or ch in ("-", "_"))
    return STAMP_PATH_TEMPLATE.format(channel=safe or "default")


@dataclass
class CorrectionDossier:
    """One reversal, joined all the way from live evidence back to the upload."""

    channel_id: str
    video_id: str
    run_id: int | None
    claim: str
    source_url: str
    changed_evidence: str
    severity: str
    suggested_correction: str
    status: str = "open"
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def render(self) -> str:
        return "\n".join(
            [
                f"## {self.claim or '(claim not recorded)'}",
                "",
                f"- **Video:** {self.video_id or '(unknown)'}",
                f"- **Run:** {self.run_id if self.run_id is not None else '(unknown)'}",
                f"- **Source:** {self.source_url}",
                f"- **Changed evidence:** {self.changed_evidence}",
                f"- **Severity:** {self.severity}",
                f"- **Suggested correction:** {self.suggested_correction}",
                f"- **Status:** {self.status}",
                f"- **Detected:** {self.detected_at}",
                "",
                "Nothing has been changed on YouTube. Publishing a correction, "
                "editing the description, or taking the video down is an operator "
                "decision. The reversed claim is already blocked from future "
                "scripts via the negative-fact gate.",
            ]
        )


def _default_fetch(url: str) -> str:
    from urllib.request import urlopen

    with urlopen(url, timeout=8) as resp:
        return resp.read(_MAX_BODY_CHARS).decode("utf-8", errors="ignore")


def _claims_and_sources(run: Any) -> tuple[list[dict], list[str]]:
    """Read the claim->source edge this wave started persisting."""
    try:
        features = json.loads(getattr(run, "features_json", "") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return [], []
    if not isinstance(features, dict):
        return [], []
    verification = features.get("claim_verification") or {}
    # `claim_verification` is None on every run generated before the verifier ran,
    # and `claims` is absent on every run generated before this wave persisted it.
    claims = (verification.get("claims") or []) if isinstance(verification, dict) else []
    sources = features.get("source_urls") or []
    return (
        [c for c in claims if isinstance(c, dict)],
        [str(u) for u in sources if str(u).strip()][:_MAX_SOURCES_PER_RUN],
    )


def _severity_for(claim: dict, body_lc: str) -> str:
    if any(word in body_lc for word in _RETRACTION_WORDS):
        return "high" if claim.get("supported") else "medium"
    return "medium"


_SCRIPT_STYLE_RE = re.compile(r"<(script|style).*?</>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def strip_markup(text: str) -> str:
    """Article text only. Tag and attribute names are not evidence of a claim."""
    without_code = _SCRIPT_STYLE_RE.sub(" ", text or "")
    return _TAG_RE.sub(" ", without_code)


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", strip_markup(text).lower())
        if len(token) > 2 and token not in _CLAIM_STOPWORDS
    }


def _claim_coverage(claim: str, body: str) -> float:
    tokens = _content_tokens(claim)
    if not tokens:
        return 1.0
    return len(tokens & _content_tokens(body)) / len(tokens)


def scan_published_for_corrections(
    channel_id: str,
    *,
    published: list[Any] | None = None,
    run_lookup: dict[int, Any] | None = None,
    fetch: Callable[[str], str] | None = None,
    negative_store: Callable[[str, str, str], None] | None = None,
    window_days: int = 30,
    stamp_path: str | None = None,
    now: datetime | None = None,
    force: bool = False,
) -> list[CorrectionDossier]:
    """Re-check the sources behind recently published videos.

    Returns the dossiers written. An unreachable source logs a WARNING and is
    skipped -- it is NOT reported as clean, which is the distinction #686's
    blanket `except Exception: return False` collapsed.
    """
    from core.retraction_watch import toast_is_due, write_stamp

    stamp = stamp_path or correction_scan_stamp_path(channel_id)
    if not force and not toast_is_due(stamp, now=now):
        return []

    rows = published if published is not None else _recent_published(channel_id, window_days)
    runs = run_lookup if run_lookup is not None else _runs_for(rows)
    getter = fetch or _default_fetch
    store = negative_store if negative_store is not None else _default_negative_store
    found: list[CorrectionDossier] = []

    for row in rows or []:
        raw_run_id = getattr(row, "content_run_id", None)
        if raw_run_id is None:
            continue
        run_id = int(raw_run_id)
        if not run_id:
            continue
        run = (runs or {}).get(run_id)
        if run is None:
            continue
        claims, sources = _claims_and_sources(run)
        if not claims or not sources:
            continue
        for url in sources:
            try:
                body = getter(url) or ""
            except Exception as exc:
                # Not a clean result. The operator is told the check did not run.
                logger.warning("correction source unreachable, not cleared: %s (%s)", url, exc)
                continue
            body_lc = body.lower()
            has_retraction = any(word in body_lc for word in _RETRACTION_WORDS)
            # Retraction language is direct evidence and stands on its own. The
            # weak coverage signal needs a body worth measuring against:
            #   - too little readable text: the check did not run, say so;
            #   - a read stopped at the byte cap: the claim may simply be past it.
            body_tokens = _content_tokens(body)
            readable = len(body_tokens) >= _MIN_READABLE_TOKENS
            truncated = len(body) >= _MAX_BODY_CHARS
            if not has_retraction and not readable:
                logger.warning(
                    "correction source unreadable (%d content tokens), not cleared "
                    "and not reported as changed: %s",
                    len(body_tokens),
                    url,
                )
                continue
            for claim in claims:
                text = str(claim.get("claim") or "").strip()
                if not text:
                    continue
                coverage = _claim_coverage(text, body)
                if has_retraction:
                    severity = _severity_for(claim, body_lc)
                elif truncated:
                    # Low coverage against a truncated read says nothing.
                    continue
                elif coverage < _CLAIM_PRESENT_COVERAGE:
                    severity = "medium"
                else:
                    continue
                dossier = CorrectionDossier(
                    channel_id=channel_id,
                    video_id=str(getattr(row, "youtube_video_id", "") or ""),
                    run_id=run_id,
                    claim=text,
                    source_url=url,
                    changed_evidence=_evidence_snippet(body),
                    severity=severity,
                    suggested_correction=(
                        f"Publish a pinned comment or community post correcting: {text}"
                    ),
                )
                found.append(dossier)
                _write_note(dossier)
                if store is not None and has_retraction:
                    try:
                        store(
                            channel_id,
                            text,
                            f"source retracted after publish ({url}, video {dossier.video_id})",
                        )
                    except Exception as exc:
                        logger.warning("negative fact not recorded for %s: %s", text, exc)
                break  # one dossier per source; the operator reads the page next
    # A completed clean scan is still work: stamp it so every overnight run
    # does not re-fetch the same published sources (#703). Individual source
    # failures remain WARNINGs above and are retried on the next due scan.
    write_stamp(stamp, now=now)
    return found


def _evidence_snippet(body: str) -> str:
    lowered = (body or "").lower()
    for word in _RETRACTION_WORDS:
        at = lowered.find(word)
        if at >= 0:
            return " ".join(body[max(0, at - 120) : at + 200].split())[:300]
    return "source no longer carries the claim"


def _write_note(dossier: CorrectionDossier):
    from core.vault_dossiers import write_report_note

    # `write_report_note` writes `{date}_{kind}.md`, so `kind` has to carry the
    # video id or a second correction on the same day silently overwrites the
    # first -- which for this feature would lose the record entirely.
    slug = "".join(ch for ch in dossier.video_id if ch.isalnum())[:24] or "unknown"
    return write_report_note(
        dossier.channel_id,
        f"correction-{slug}",
        f"Correction needed: {dossier.video_id}",
        dossier.render(),
        fenced=False,
    )


def _default_negative_store(franchise: str, claim: str, reason: str) -> None:
    from core.negative_facts import franchise_for, record_negative

    record_negative(franchise_for(claim) or franchise, claim, reason=reason)


def _recent_published(channel_id: str, window_days: int) -> list[Any]:
    from datetime import timedelta

    from storage.repositories.publish_log import get_publish_log_repository

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, window_days))
    rows = []
    for row in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        when = getattr(row, "published_at", None)
        if isinstance(when, datetime):
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            if when < cutoff:
                continue
        rows.append(row)
    return rows


def _runs_for(rows: list[Any]) -> dict[int, Any]:
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    out: dict[int, Any] = {}
    for row in rows or []:
        raw_run_id = getattr(row, "content_run_id", None)
        if raw_run_id is None:
            continue
        run_id = int(raw_run_id)
        if not run_id or run_id in out:
            continue
        try:
            record = repo.get(run_id)
        except Exception as exc:
            logger.warning("run %s unreadable for correction scan: %s", run_id, exc)
            continue
        if record is not None:
            out[run_id] = record
    return out
