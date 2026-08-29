"""Cap output/ by gigabytes (candidate 77) and optionally by file count (31).

Dry-run first. Never deletes unless ``apply=True``. Never touches data/,
config/secrets/, or .env. Tests pass a temp root — not the operator's output/.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config.paths import ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.artifact_retention")

_VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".wav", ".mp3", ".srt", ".ass"}


@dataclass
class ArtifactPlan:
    root: str
    total_bytes: int = 0
    file_count: int = 0
    max_bytes: int | None = None
    max_files: int | None = None
    victims: list[str] = field(default_factory=list)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)


def max_gb() -> float | None:
    raw = os.getenv("OUTPUT_MAX_GB", "").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def max_files() -> int | None:
    raw = os.getenv("OUTPUT_MAX_FILES", "").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = int(float(raw))
    except ValueError:
        return None
    return val if val > 0 else None


def _iter_files(root: Path) -> list[tuple[float, int, Path]]:
    found: list[tuple[float, int, Path]] = []
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                st = path.stat()
            except OSError:
                continue
            found.append((st.st_mtime, st.st_size, path))
    found.sort()  # oldest first
    return found


def plan(
    root: str | os.PathLike[str] | None = None,
    *,
    max_bytes: int | None = None,
    file_cap: int | None = None,
) -> ArtifactPlan:
    base = Path(root) if root is not None else Path(ROOT_DIR) / "output"
    out = ArtifactPlan(root=str(base))
    files = _iter_files(base)
    out.file_count = len(files)
    out.total_bytes = sum(sz for _, sz, _ in files)
    gb = max_gb() if max_bytes is None else (max_bytes / (1024**3) if max_bytes else None)
    if max_bytes is None and gb is not None:
        max_bytes = int(gb * (1024**3))
    if file_cap is None:
        file_cap = max_files()
    out.max_bytes = max_bytes
    out.max_files = file_cap

    keep = list(files)
    if max_bytes is not None and max_bytes >= 0:
        total = out.total_bytes
        i = 0
        while total > max_bytes and i < len(keep):
            _mtime, sz, path = keep[i]
            out.victims.append(str(path))
            total -= sz
            i += 1
        keep = keep[i:]
    if file_cap is not None and len(keep) > file_cap:
        extra = keep[: len(keep) - file_cap]
        out.victims.extend(str(p) for _m, _s, p in extra)
    # unique, oldest-first
    seen: set[str] = set()
    uniq: list[str] = []
    for v in out.victims:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    out.victims = uniq
    return out


def apply_plan(planned: ArtifactPlan, *, apply: bool = False) -> int:
    """Delete planned victims when apply=True. Returns deleted count."""
    if not apply:
        return 0
    deleted = 0
    for path in planned.victims:
        try:
            os.remove(path)
            deleted += 1
        except OSError as exc:
            logger.debug("artifact delete skipped %s: %s", path, exc)
    return deleted


def render(planned: ArtifactPlan, *, apply: bool = False) -> str:
    lines = [
        f"output/ retention — {planned.root}",
        f"  size   : {planned.total_gb:.2f} GB  ({planned.file_count} files)",
    ]
    if planned.max_bytes is not None:
        lines.append(f"  cap    : {planned.max_bytes / (1024**3):.2f} GB")
    if planned.max_files is not None:
        lines.append(f"  files  : cap {planned.max_files}")
    if not planned.victims:
        lines.append("  action : nothing over cap")
        return "\n".join(lines)
    mode = "DELETE" if apply else "dry-run"
    lines.append(f"  {mode} : {len(planned.victims)} oldest file(s)")
    for path in planned.victims[:12]:
        lines.append(f"    {path}")
    if len(planned.victims) > 12:
        lines.append(f"    ... +{len(planned.victims) - 12} more")
    return "\n".join(lines)


def run(root: str | os.PathLike[str] | None = None, *, apply: bool = False) -> dict[str, Any]:
    planned = plan(root)
    deleted = apply_plan(planned, apply=apply)
    return {
        "root": planned.root,
        "total_gb": round(planned.total_gb, 4),
        "file_count": planned.file_count,
        "victims": planned.victims,
        "deleted": deleted,
        "apply": apply,
        "text": render(planned, apply=apply),
    }


def retention_report(
    root: str | os.PathLike[str] | None = None,
    *,
    older_than_days: float | None = None,
) -> str:
    """Report old draft/trace/vault-clone artifacts. This path never deletes."""
    base = Path(root or os.getenv("ARTIFACT_RETENTION_ROOT", "").strip() or ROOT_DIR)
    if older_than_days is None:
        try:
            older_than_days = float(os.getenv("ARTIFACT_RETENTION_DAYS", "30"))
        except ValueError:
            older_than_days = 30.0
    cutoff = time.time() - max(0.0, older_than_days) * 86400
    candidates: list[tuple[float, int, Path]] = []
    scopes = [base]
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if vault:
        scopes.append(Path(vault))
    elif (base / "vault").is_dir():
        scopes.append(base / "vault")
    for scope in scopes:
        for mtime, size, path in _iter_files(scope):
            parts = {part.lower() for part in path.parts}
            is_target = (
                "drafts" in parts
                or ("traces" in parts and path.suffix.lower() == ".json")
                or "_runs" in parts
            )
            if is_target and mtime <= cutoff:
                candidates.append((mtime, size, path))
    candidates.sort()
    total = sum(size for _mtime, size, _path in candidates)
    lines = [
        f"Artifact retention report - DRY RUN ONLY ({older_than_days:g}+ days)",
        f"  root       : {base}",
        f"  candidates : {len(candidates)} file(s), {total / (1024**2):.2f} MB",
        "  action     : none (this command is report-only; --apply is ignored)",
    ]
    for _mtime, _size, path in candidates[:20]:
        lines.append(f"    {path}")
    if len(candidates) > 20:
        lines.append(f"    ... +{len(candidates) - 20} more")
    try:
        from core.disk_growth import project_days_until_full

        output_root = base / "output" if (base / "output").is_dir() else base
        free = shutil.disk_usage(str(output_root)).free
        lines.append(f"  growth    : {project_days_until_full(output_root, free_bytes=free)}")
    except Exception as exc:
        logger.debug("disk growth skipped: %s", exc)
    return "\n".join(lines)
