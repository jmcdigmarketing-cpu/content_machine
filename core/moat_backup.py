"""Weekly moat backup plan (candidate 85).

Lists pg_dump + vault + data/traces. Encrypted secrets and .env are excluded.
Default is a dry-run plan; copy only when dest is set and apply=True.
Never writes quota_state. Tests use temp dirs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config.paths import DATA_DIR, ROOT_DIR, SECRETS_DIR, TRACES_DIR
from core.logging import get_logger

logger = get_logger("core.moat_backup")

_EXCLUDE_NAMES = {
    ".env",
    ".env.local",
    "quota_state.json",
    "youtube_quota.json",
    "cache_stats.json",
    "experiments.json",
    "operator_heartbeat.json",
}


@dataclass
class BackupItem:
    kind: str
    src: str
    note: str = ""
    copy: bool = True


@dataclass
class BackupPlan:
    dest: str
    items: list[BackupItem] = field(default_factory=list)
    skipped_secrets: list[str] = field(default_factory=list)


def plan(dest: str | os.PathLike[str] | None = None) -> BackupPlan:
    target = str(dest) if dest else "(no dest — dry-run only)"
    out = BackupPlan(dest=target)
    traces = TRACES_DIR
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    out.items.append(
        BackupItem(
            "traces",
            traces,
            "run ledger JSON (no secrets)",
            copy=os.path.isdir(traces),
        )
    )
    if vault:
        out.items.append(BackupItem("vault", vault, "Obsidian knowledge OS", copy=True))
    else:
        out.items.append(BackupItem("vault", "", "OBSIDIAN_VAULT_PATH unset", copy=False))
    db = os.getenv("DATABASE_URL") or os.getenv("DATABASE_KEY") or ""
    if db:
        out.items.append(
            BackupItem(
                "pg_dump",
                "[DATABASE_URL redacted]",
                "pg_dump --no-password (command only; not executed in dry-run)",
                copy=False,
            )
        )
    else:
        out.items.append(BackupItem("pg_dump", "", "no DATABASE_URL", copy=False))
    out.skipped_secrets = [
        os.path.join(ROOT_DIR, ".env"),
        SECRETS_DIR,
        os.path.join(DATA_DIR, "quota_state.json"),
    ]
    return out


def apply_plan(planned: BackupPlan, *, apply: bool = False) -> int:
    """Copy copy=True file/dir sources into dest. Never copies secrets."""
    if not apply:
        return 0
    dest = Path(planned.dest)
    if not planned.dest or planned.dest.startswith("("):
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in planned.items:
        if not item.copy or not item.src or item.kind == "pg_dump":
            continue
        src = Path(item.src)
        if not src.exists():
            continue
        name = src.name or item.kind
        target = dest / name
        try:
            if src.is_dir():
                import shutil

                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(
                    src,
                    target,
                    ignore=shutil.ignore_patterns(*_EXCLUDE_NAMES, "secrets"),
                )
            else:
                if src.name in _EXCLUDE_NAMES:
                    continue
                import shutil

                shutil.copy2(src, target)
            copied += 1
        except Exception as exc:
            logger.debug("moat backup copy skipped %s: %s", src, exc)
    return copied


def render(planned: BackupPlan, *, apply: bool = False) -> str:
    lines = [
        "Moat backup (secrets excluded)",
        f"  dest : {planned.dest}",
        f"  mode : {'copy' if apply else 'dry-run'}",
    ]
    for item in planned.items:
        flag = "copy" if item.copy else "skip"
        src = item.src or "(none)"
        lines.append(f"  [{flag}] {item.kind:<8} {src}  {item.note}")
    lines.append("  excluded:")
    for s in planned.skipped_secrets:
        lines.append(f"    {s}")
    return "\n".join(lines)


def run(dest: str | None = None, *, apply: bool = False) -> dict[str, Any]:
    planned = plan(dest)
    n = apply_plan(planned, apply=apply)
    return {"copied": n, "text": render(planned, apply=apply), "dest": planned.dest}
