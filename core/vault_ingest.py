"""Multi-source → vault-note ingestion (Pillar 4 extension; anything-to-notebooklm pattern).

Replicates the *pattern* (not the package) from qiaomu/anything-to-notebooklm: turn a
URL / PDF / YouTube link into a provenance-tagged markdown note under the Obsidian vault,
so the verified-fact base grows from more than pasted text. Notes are written with the
same frontmatter keys `core/fact_store.py` reads (`tier`, `source`, `verified_at`), so
`core/obsidian_facts.load_fact_records()` picks them up on related topics.

`ingest_url` reuses the article extractor in `core/link_facts.py` — which, after the
goose3 phase, is goose3-first with a BeautifulSoup fallback (one extractor, two callers).

    INGEST_ENABLED=true      # gate for any *auto* ingestion; explicit calls always work

Baseline: `ingest_url` is real; `ingest_pdf` / `ingest_youtube_transcript` are thin
records pending markitdown / transcript backends. Everything fails open (empty record /
`None`) — it never raises, and does nothing when `OBSIDIAN_VAULT_PATH` is unset.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("core.vault_ingest")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _record(text: str, source_url: str, *, kind: str, confidence: str = "high") -> dict[str, Any]:
    return {
        "text": text,
        "source_url": source_url,
        "retrieved_at": _now_iso(),
        "confidence": confidence,
        "kind": kind,
    }


def ingest_url(url: str) -> dict[str, Any]:
    """URL → fact-line text via the shared `link_facts` extractor (goose3-first)."""
    try:
        from core.link_facts import extract_facts_from_url

        lines = extract_facts_from_url(url)
    except Exception as exc:  # never raise — ingestion is best-effort
        logger.debug("ingest_url failed for %s: %s", url, exc)
        lines = []
    return _record("\n".join(lines), url, kind="url", confidence="high" if lines else "low")


def ingest_pdf(path: str) -> dict[str, Any]:
    """PDF → text. Baseline stub (markitdown / pypdf backend is the follow-up)."""
    return _record("", path, kind="pdf", confidence="low")


def ingest_youtube_transcript(url: str) -> dict[str, Any]:
    """YouTube link → title/description now; full transcript is the follow-up."""
    try:
        from core.link_facts import extract_facts_from_url

        lines = extract_facts_from_url(url)
    except Exception as exc:
        logger.debug("ingest_youtube_transcript failed for %s: %s", url, exc)
        lines = []
    return _record("\n".join(lines), url, kind="youtube", confidence="low")


def _slugify(text: str, *, limit: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "source").lower()).strip("-")
    return (slug or "source")[:limit]


def _vault_root() -> Path | None:
    raw = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    return Path(raw) if raw else None


def save_to_vault(
    record: dict[str, Any], channel_id: str = "default", *, title: str | None = None
) -> str | None:
    """Write a provenance-frontmatter note into `{vault}/{channel}/_ingest/`.

    Returns the written path, or `None` when the vault is unset or there's no text.
    """
    root = _vault_root()
    if not root:
        return None
    text = (record.get("text") or "").strip()
    if not text:
        return None
    source = record.get("source_url") or ""
    heading = title or _slugify(text.splitlines()[0] if text else source)
    out_dir = root / channel_id / "_ingest"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{_now_iso()}_{_slugify(heading)}.md"
        frontmatter = (
            "---\n"
            "tier: link\n"
            f"source: {source}\n"
            f"verified_at: {record.get('retrieved_at') or _now_iso()}\n"
            f"channel: {channel_id}\n"
            "tags: [ingest, research]\n"
            "---\n\n"
        )
        path.write_text(f"{frontmatter}# {heading}\n\n{text}\n", encoding="utf-8")
        logger.info("Ingested %s → %s", source or record.get("kind"), path)
        return str(path)
    except Exception as exc:  # vault write is best-effort
        logger.warning("save_to_vault failed: %s", exc)
        return None
