"""Copy capture clips into the local gameplay library (ops ingest-clips).

Dry-run default. --apply remuxes to muted H.264. Unmatched files are listed, never
dumped into a generic gaming/ folder. HUD is not detected — persisted as null.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from assets.local_provider import _GENERIC_FOLDER_NAMES, _keyword_choose_folder
from assets.local_provider import BASE_VIDEO_DIR as _DEFAULT_LIBRARY
from config.paths import CLIP_INDEX_FILE, ensure_data_dir
from core.logging import get_logger

logger = get_logger("assets.clip_ingest")

BASE_VIDEO_DIR = _DEFAULT_LIBRARY
_VIDEO_EXTS = (".mp4", ".mov", ".mkv")
_GENERIC = _GENERIC_FOLDER_NAMES | frozenset(
    {"open world", "multiplayer games", "library", "captures"}
)

# Longest phrase first. Values are library folder basenames (case-insensitive).
_NAME_ALIASES: tuple[tuple[str, str], ...] = (
    ("grand theft auto vi", "GTA V"),
    ("grand theft auto v", "GTA V"),
    ("grand theft auto 5", "GTA V"),
    ("marvel rivals", "Marvel Rivals"),
    ("call of duty", "Call of Duty"),
    ("gta vi", "GTA V"),
    ("gta 6", "GTA V"),
    ("gta 5", "GTA V"),
    ("gta v", "GTA V"),
    ("ufc 5", "UFC 5"),
    ("fortnite", "Fortnite"),
)


@dataclass
class IngestRow:
    source: str
    dest: str | None
    status: str
    reason: str = ""


@dataclass
class IngestResult:
    rows: list[IngestRow] = field(default_factory=list)
    dry_run: bool = True
    move: bool = False


def default_source_dirs() -> list[str]:
    raw = (os.getenv("CLIP_INGEST_DIRS") or "").strip()
    if raw:
        return [
            os.path.expandvars(os.path.expanduser(p.strip())) for p in raw.split(",") if p.strip()
        ]
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "OneDrive", "Videos", "Xbox Game DVR"),
        os.path.join(home, "Videos", "NVIDIA"),
        os.path.join(home, "Videos", "NVIDIA Share"),
    ]
    return [p for p in candidates if os.path.isdir(p)]


def _norm_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def _library_folders(root: str) -> list[str]:
    folders: list[str] = []
    if not root or not os.path.isdir(root):
        return folders
    for dirpath, _dirnames, _files in os.walk(root):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        folders.append(dirpath)
    return folders


def _folder_by_basename(folders: list[str], wanted: str) -> str | None:
    needle = _norm_name(wanted)
    if not needle:
        return None
    scored: list[tuple[int, str]] = []
    for folder in folders:
        name = os.path.basename(folder)
        if _norm_name(name) == needle:
            scored.append((len(name), folder))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def match_folder(filename: str, folders: list[str]) -> str | None:
    """Map a capture filename to a library folder, or None if nothing matches."""
    stem = Path(filename).stem
    hay = _norm_name(stem)
    if not hay or not folders:
        return None
    for phrase, folder_name in _NAME_ALIASES:
        if phrase in hay:
            hit = _folder_by_basename(folders, folder_name)
            if hit:
                return hit
    return _keyword_choose_folder(stem, folders)


def _iter_source_files(source_dirs: list[str]) -> list[str]:
    out: list[str] = []
    for directory in source_dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.lower().endswith(_VIDEO_EXTS):
                out.append(os.path.join(directory, name))
    return out


def _unique_dest(folder: str, stem: str) -> str:
    candidate = os.path.join(folder, stem + ".mp4")
    if not os.path.exists(candidate):
        return candidate
    n = 2
    while True:
        candidate = os.path.join(folder, f"{stem}_{n}.mp4")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def plan_ingest(
    *,
    source_dirs: list[str] | None = None,
    library_root: str | None = None,
) -> list[IngestRow]:
    sources = source_dirs if source_dirs is not None else default_source_dirs()
    library = library_root if library_root is not None else BASE_VIDEO_DIR
    folders = _library_folders(library)
    rows: list[IngestRow] = []
    for src in _iter_source_files(sources):
        folder = match_folder(os.path.basename(src), folders)
        if not folder:
            rows.append(IngestRow(source=src, dest=None, status="unmatched", reason="no folder"))
            continue
        dest = _unique_dest(folder, Path(src).stem)
        rows.append(IngestRow(source=src, dest=dest, status="matched"))
    return rows


def _probe_duration(path: str) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError) as exc:
        logger.debug("ffprobe duration skipped: %s", exc)
    return None


def _probe_stream(path: str) -> tuple[int | None, int | None, str | None]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,codec_name",
                "-of",
                "csv=p=0",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("ffprobe stream skipped: %s", exc)
        return None, None, None
    blob = (result.stdout or "").strip().replace("|", ",")
    if result.returncode != 0 or not blob:
        return None, None, None
    parts = [p.strip() for p in blob.split(",")]
    width = height = None
    codec = None
    try:
        if len(parts) >= 1 and parts[0]:
            width = int(float(parts[0]))
        if len(parts) >= 2 and parts[1]:
            height = int(float(parts[1]))
    except (TypeError, ValueError):
        pass
    if len(parts) >= 3 and parts[2]:
        codec = parts[2]
    return width, height, codec


def _remux_muted_h264(src: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-an",
        "-movflags",
        "+faststart",
        dest,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0 or not os.path.isfile(dest):
        err = (result.stderr or result.stdout or "ffmpeg remux failed")[-400:]
        raise RuntimeError(err)


def _load_index(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {"clips": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("clips"), dict):
            return data
    except (OSError, ValueError) as exc:
        logger.warning("clip index unreadable (%s): %s", path, exc)
    return {"clips": {}}


def _save_index(path: str, data: dict[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="clip_index_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _hud_flag(dest: str) -> bool | None:
    """True/False from the frame detector; None only when the detector itself fails."""
    try:
        from core.hud_detect import detect_hud

        return bool(detect_hud(dest))
    except Exception as exc:
        logger.debug("hud detect skipped: %s", exc)
        return None


def _record_index(dest: str, source: str) -> None:
    ensure_data_dir()
    path = CLIP_INDEX_FILE
    data = _load_index(path)
    duration = _probe_duration(dest)
    width, height, codec = _probe_stream(dest)
    data.setdefault("clips", {})[dest] = {
        "source": source,
        "duration_s": duration,
        "width": width,
        "height": height,
        "codec": codec,
        "hud": _hud_flag(dest),
    }
    _save_index(path, data)


def ingest_clips(
    *,
    source_dirs: list[str] | None = None,
    library_root: str | None = None,
    apply: bool = False,
    move: bool = False,
) -> IngestResult:
    rows = plan_ingest(source_dirs=source_dirs, library_root=library_root)
    result = IngestResult(rows=rows, dry_run=not apply, move=move)
    if not apply:
        return result
    done: list[IngestRow] = []
    for row in rows:
        if row.status != "matched" or not row.dest:
            done.append(row)
            continue
        try:
            _remux_muted_h264(row.source, row.dest)
            _record_index(row.dest, row.source)
            if move:
                try:
                    os.remove(row.source)
                except OSError as exc:
                    logger.warning("ingest-clips move skipped (%s): %s", row.source, exc)
            done.append(IngestRow(source=row.source, dest=row.dest, status="copied"))
        except Exception as exc:
            logger.warning("ingest-clips remux failed (%s): %s", row.source, exc)
            done.append(
                IngestRow(source=row.source, dest=row.dest, status="failed", reason=str(exc)[:200])
            )
    result.rows = done
    return result


def render_ingest(result: IngestResult) -> str:
    lines = [
        "DRY RUN — no files copied" if result.dry_run else "APPLY — remuxing matched clips",
        f"{len(result.rows)} capture file(s)",
    ]
    for row in result.rows:
        if row.status == "unmatched":
            lines.append(f"  unmatched  {row.source}")
            continue
        dest = row.dest or ""
        folder = os.path.basename(os.path.dirname(dest)) if dest else ""
        lines.append(f"  {row.status:<9} {os.path.basename(row.source)} -> {folder}/")
    return "\n".join(lines)
