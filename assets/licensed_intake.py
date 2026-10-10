"""Licensed footage from a recorded Commons, Internet Archive, or NASA search (#1040).

The adapters read the JSON those APIs return. They do not fetch it. ``footage-licence``
is the operator entry: a fixture file in, accepted clips under
``video/backgrounds/<niche>/<subject>/`` with a per-file ``license.yaml``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assets import clip_ingest
from assets.clip_ingest import IngestRow

_NC = re.compile(r"(?:^|[^a-z])nc(?:[^a-z]|$)|non-?commercial", re.I)
_BAD_NAME = re.compile(r'[<>:"/\\|?*]+')
_VIDEO_EXT = {".mp4", ".webm", ".mov", ".ogv", ".mkv"}
_ADAPTERS = ("commons", "archive", "cc0")


@dataclass(frozen=True)
class LicenceHit:
    title: str
    source_url: str
    licence: str
    owner: str
    commercial_use: bool | None
    download_url: str
    filename: str


def commercial_use_of(licence: str) -> bool:
    """False when the licence text is non-commercial or a copyright claim."""
    return refuse_reason(LicenceHit("", "", licence, "", None, "", "")) == "" and bool(
        (licence or "").strip()
    )


def refuse_reason(hit: LicenceHit) -> str:
    """Empty when the hit may be saved. Missing, non-commercial, or copyrighted is not."""
    licence = (hit.licence or "").strip()
    if not licence:
        return "missing licence"
    low = licence.lower()
    if "copyright" in low and "public domain" not in low:
        return "copyrighted; not a clear licence"
    if hit.commercial_use is False or _NC.search(licence):
        return "non-commercial licence"
    return ""


def _clean(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _filename(title: str, download_url: str) -> str:
    raw = _clean(title)
    raw = re.sub(r"^File:\s*", "", raw, flags=re.I)
    if not raw:
        raw = os.path.basename(download_url.split("?", 1)[0]) or "clip"
    raw = _BAD_NAME.sub(" ", raw).strip()
    ext = Path(raw).suffix.lower()
    stem = Path(raw).stem.strip() or "clip"
    if ext not in _VIDEO_EXT:
        url_ext = Path(download_url.split("?", 1)[0]).suffix.lower()
        ext = url_ext if url_ext in _VIDEO_EXT else ".mp4"
    return stem[:80] + ext


def _meta_value(block: dict[str, Any], key: str) -> str:
    raw = block.get(key)
    if isinstance(raw, dict):
        return _clean(raw.get("value"))
    return _clean(raw)


def commons_hits(payload: dict[str, Any]) -> list[LicenceHit]:
    """Wikimedia Commons ``prop=imageinfo&iiprop=url|extmetadata`` pages."""
    pages = ((payload.get("query") or {}).get("pages") or {}) if isinstance(payload, dict) else {}
    if not isinstance(pages, dict):
        return []
    hits: list[LicenceHit] = []
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        info = page.get("imageinfo") or []
        first = info[0] if isinstance(info, list) and info else None
        row: dict[str, Any] = first if isinstance(first, dict) else {}
        meta_raw = row.get("extmetadata")
        meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
        licence = _meta_value(meta, "LicenseShortName")
        url = _clean(row.get("url"))
        hits.append(
            LicenceHit(
                title=_clean(page.get("title")),
                source_url=_clean(row.get("descriptionurl")) or url,
                licence=licence,
                owner=_meta_value(meta, "Artist") or "third party (see sources)",
                commercial_use=None,
                download_url=url,
                filename=_filename(_clean(page.get("title")), url),
            )
        )
    return hits


def archive_hits(payload: dict[str, Any]) -> list[LicenceHit]:
    """Internet Archive advanced-search ``response.docs``."""
    docs = ((payload.get("response") or {}).get("docs") or []) if isinstance(payload, dict) else []
    if not isinstance(docs, list):
        return []
    hits: list[LicenceHit] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        downloads = doc.get("downloads") or []
        url = _clean(downloads[0]) if isinstance(downloads, list) and downloads else ""
        creator = doc.get("creator")
        if isinstance(creator, list):
            owner = _clean(creator[0] if creator else "")
        else:
            owner = _clean(creator)
        licence = _clean(doc.get("licenseurl"))
        hits.append(
            LicenceHit(
                title=_clean(doc.get("title")),
                source_url=(
                    f"https://archive.org/details/{_clean(doc.get('identifier'))}"
                    if doc.get("identifier")
                    else url
                ),
                licence=licence,
                owner=owner or "third party (see sources)",
                commercial_use=None,
                download_url=url,
                filename=_filename(_clean(doc.get("title")), url),
            )
        )
    return hits


def cc0_hits(payload: dict[str, Any]) -> list[LicenceHit]:
    """NASA images API ``collection.items``. Unmarked items are public domain.

    A ``rights`` string that claims copyright is kept as the licence so
    ``refuse_reason`` can reject it. NASA does not stamp a CC0 field on the
    public-domain items.
    """
    items = (
        ((payload.get("collection") or {}).get("items") or []) if isinstance(payload, dict) else []
    )
    if not isinstance(items, list):
        return []
    hits: list[LicenceHit] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data") or []
        row = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
        links = item.get("links") or []
        url = ""
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict) and link.get("href"):
                    url = _clean(link.get("href"))
                    break
        rights = _clean(row.get("rights"))
        licence = rights or "Public domain (NASA)"
        hits.append(
            LicenceHit(
                title=_clean(row.get("title")),
                source_url=url,
                licence=licence,
                owner=_clean(row.get("center")) or "NASA",
                commercial_use=True if not rights else None,
                download_url=url,
                filename=_filename(_clean(row.get("title")), url),
            )
        )
    return hits


def _safe_folder(name: str) -> str:
    clean = _BAD_NAME.sub(" ", name or "").strip()
    return clean or "untitled"


def ingest_accepted(
    hits: list[LicenceHit],
    *,
    niche: str,
    subject: str,
    library_root: str,
    bodies: dict[str, bytes],
    index_path: str,
) -> list[IngestRow]:
    """Write the hits a licence check accepts. A refusal writes no file."""
    folder = os.path.join(library_root, _safe_folder(niche), _safe_folder(subject))
    rows: list[IngestRow] = []
    for hit in hits:
        why = refuse_reason(hit)
        if why:
            rows.append(
                IngestRow(
                    source=hit.source_url or hit.download_url,
                    dest=None,
                    status="failed",
                    reason=why,
                )
            )
            continue
        body = bodies.get(hit.download_url)
        if not body:
            rows.append(
                IngestRow(
                    source=hit.source_url or hit.download_url,
                    dest=None,
                    status="failed",
                    reason="no file bytes for this hit",
                )
            )
            continue
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, hit.filename)
        if os.path.exists(dest):
            stem, ext = os.path.splitext(hit.filename)
            n = 2
            while os.path.exists(dest):
                dest = os.path.join(folder, f"{stem}_{n}{ext}")
                n += 1
        with open(dest, "wb") as fh:
            fh.write(body)
        sidecar = {
            "license": hit.licence,
            "owner": hit.owner,
            "commercial_use": commercial_use_of(hit.licence),
            "sources": [hit.source_url] if hit.source_url else [],
        }
        with open(clip_ingest.licence_sidecar_path(dest), "w", encoding="utf-8") as fh:
            json.dump(sidecar, fh, indent=2)
        clip_ingest._record_index(dest, hit.source_url or hit.download_url, index_path=index_path)
        rows.append(
            IngestRow(source=hit.source_url or hit.download_url, dest=dest, status="copied")
        )
    return rows


def hits_for(catalogue: str, payload: dict[str, Any]) -> list[LicenceHit]:
    key = (catalogue or "").strip().lower()
    if key == "commons":
        return commons_hits(payload)
    if key == "archive":
        return archive_hits(payload)
    if key == "cc0":
        return cc0_hits(payload)
    raise ValueError(f"catalogue must be one of {', '.join(_ADAPTERS)}")


def ingest_fixture(
    fixture_path: str,
    *,
    catalogue: str,
    niche: str,
    subject: str,
    library_root: str,
    index_path: str,
    apply: bool = False,
) -> list[IngestRow]:
    """``ops footage-licence``: parse a recorded search and, with ``--apply``, save it."""
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("fixture must be a JSON object")
    hits = hits_for(catalogue, data)
    if not apply:
        rows: list[IngestRow] = []
        for hit in hits:
            why = refuse_reason(hit)
            rows.append(
                IngestRow(
                    source=hit.source_url or hit.download_url,
                    dest=os.path.join(
                        library_root, _safe_folder(niche), _safe_folder(subject), hit.filename
                    ),
                    status="failed" if why else "matched",
                    reason=why,
                )
            )
        return rows
    raw_files = data.get("files")
    files = raw_files if isinstance(raw_files, dict) else {}
    base = os.path.dirname(os.path.abspath(fixture_path))
    bodies: dict[str, bytes] = {}
    for url, rel in files.items():
        bodies[str(url)] = Path(base, str(rel)).read_bytes()
    return ingest_accepted(
        hits,
        niche=niche,
        subject=subject,
        library_root=library_root,
        bodies=bodies,
        index_path=index_path,
    )
