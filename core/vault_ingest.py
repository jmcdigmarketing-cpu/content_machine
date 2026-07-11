"""Multi-source → vault-note ingestion (Pillar 4 extension; anything-to-notebooklm pattern).

Replicates the *pattern* (not the package) from qiaomu/anything-to-notebooklm: turn a
URL / PDF / YouTube link into a provenance-tagged markdown note under the Obsidian vault,
so the verified-fact base grows from more than pasted text. Notes are written with the
same frontmatter keys `core/fact_store.py` reads (`tier`, `source`, `verified_at`), so
`core/obsidian_facts.load_fact_records()` picks them up on related topics.

`ingest_url` reuses the article extractor in `core/link_facts.py` — which, after the
goose3 phase, is goose3-first with a BeautifulSoup fallback (one extractor, two callers).

    INGEST_ENABLED=true      # gate for any *auto* ingestion; explicit calls always work

`ingest(source)` detects the kind (local .pdf → `ingest_pdf` via lazy pypdf; YouTube link →
`ingest_youtube_transcript` via lazy youtube-transcript-api; else → `ingest_url`/goose3).
Everything fails open (empty record / `None`) — it never raises, and does nothing when
`OBSIDIAN_VAULT_PATH` is unset. Operator entry: `py -m scripts.ops ingest <url|pdf|yt>`.
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
    """PDF → extracted text via pypdf (lazy, [providers] extra). Fail-open to empty."""
    text = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(p.strip() for p in parts if p.strip())
    except Exception as exc:  # missing pypdf / unreadable file — never raise
        logger.debug("ingest_pdf failed for %s: %s", path, exc)
        text = ""
    return _record(text, path, kind="pdf", confidence="high" if text else "low")


def ingest_youtube_transcript(url: str) -> dict[str, Any]:
    """YouTube → full transcript via youtube-transcript-api (lazy); falls back to the
    video title/description (the link extractor) when no transcript is available."""
    text = ""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        from apis.youtube_api import extract_youtube_video_id

        vid = extract_youtube_video_id(url)
        if vid:
            chunks = YouTubeTranscriptApi.get_transcript(vid)
            text = " ".join(c.get("text", "").strip() for c in chunks if c.get("text"))
    except Exception as exc:  # no transcript / lib missing — fall back below
        logger.debug("ingest_youtube_transcript transcript unavailable for %s: %s", url, exc)
        text = ""
    if not text:
        try:
            from core.link_facts import extract_facts_from_url

            text = "\n".join(extract_facts_from_url(url))
        except Exception as exc:
            logger.debug("ingest_youtube_transcript fallback failed for %s: %s", url, exc)
            text = ""
    return _record(text, url, kind="youtube", confidence="high" if text else "low")


def _looks_like_youtube(url: str) -> bool:
    low = (url or "").lower()
    return "youtube.com/watch" in low or "youtu.be/" in low or "youtube.com/shorts" in low


def ingest(source: str) -> dict[str, Any]:
    """Detect the source kind and ingest it: local .pdf path, YouTube link, or URL."""
    s = (source or "").strip()
    if not s:
        return _record("", s, kind="unknown", confidence="low")
    if s.lower().endswith(".pdf"):
        return ingest_pdf(s)
    if _looks_like_youtube(s):
        return ingest_youtube_transcript(s)
    return ingest_url(s)


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
