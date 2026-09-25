"""#640: build the package and check what it would ship, before anyone ships it.

`config/secrets/` holds real OAuth files on disk and `config` is a shipped package, so
the only thing keeping a token out of a wheel was that nobody had put it in. This
builds the wheel and sdist exactly as `pip` would, from the working tree, into a temp
dir, and flags three things by member name only:

* a forbidden path - `.env*` (not `.env.example`), `config/secrets/` (not its README),
  runtime `data/` or `output/`, `*.pem` / `*.key`, token or client-secret JSON;
* a member whose text contains the current value of a secret-named env var
  (`core/run_trace.env_secret_values`, after loading `.env` like a real run);
* a member whose text contains an operator path (`core/chrome.redact_operator_paths`).

A PyInstaller bundle does not exist yet (desktop_app.md Stage 5); when it does, its
output goes through the same `scan_archive`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from config.paths import ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.package_audit")

_BUILD_TIMEOUT_S = 600
_FORBIDDEN_ANYWHERE = re.compile(
    r"(^|/)(\.env(?!\.example$)[^/]*$|config/secrets/(?!README\.md$)|[^/]*\.(pem|key)$"
    # An OAuth token file is `token.json` / `<name>_token[_<channel>].json`. The first
    # rule matched any name containing "token", so `config/design_tokens.json` - which
    # ships since #737 - made a clean package fail its own audit.
    r"|([^/]*_)?token(_[^/]*)?\.json$|[^/]*client_secret[^/]*\.json$)",
    re.IGNORECASE,
)
_FORBIDDEN_AT_ROOT = re.compile(r"^(data|output)/", re.IGNORECASE)


@dataclass
class ArchiveReport:
    name: str
    members: int = 0
    path_hits: list[str] = field(default_factory=list)
    secret_hits: list[str] = field(default_factory=list)
    operator_path_hits: list[str] = field(default_factory=list)

    @property
    def hits(self) -> int:
        return len(self.path_hits) + len(self.secret_hits) + len(self.operator_path_hits)


def _members(path: Path) -> list[tuple[str, bytes]]:
    if path.suffix == ".whl" or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return [(n, archive.read(n)) for n in archive.namelist() if not n.endswith("/")]
    out: list[tuple[str, bytes]] = []
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            handle = archive.extractfile(member) if member.isfile() else None
            if handle is not None:
                out.append((member.name, handle.read()))
    return out


def _relative(name: str, *, sdist: bool) -> str:
    """An sdist nests everything under `<name>-<version>/`; compare from inside it."""
    if sdist and "/" in name:
        return name.split("/", 1)[1]
    return name


def scan_archive(path: str | Path, *, secrets: list[str] | None = None) -> ArchiveReport:
    from core.chrome import redact_operator_paths
    from core.run_trace import env_secret_values

    archive = Path(path)
    values = env_secret_values() if secrets is None else secrets
    sdist = archive.name.endswith((".tar.gz", ".tgz"))
    report = ArchiveReport(archive.name)
    for name, data in _members(archive):
        report.members += 1
        rel = _relative(name, sdist=sdist)
        if _FORBIDDEN_ANYWHERE.search(rel) or _FORBIDDEN_AT_ROOT.search(rel):
            report.path_hits.append(name)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if any(value in text for value in values):
            report.secret_hits.append(name)
        if redact_operator_paths(text) != text:
            report.operator_path_hits.append(name)
    return report


def stage_tree(root: Path, dest: Path) -> int:
    """#736: copy what a build of this repo would see into `dest` - tracked files plus
    untracked files git does not ignore. An ignored `*.egg-info/`, `build/` or `data/`
    never reaches the build, so a stale `SOURCES.txt` cannot change the sdist."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if listing.returncode != 0:
        raise RuntimeError(f"cannot list files to stage: {(listing.stderr or '').strip()[-200:]}")
    copied = 0
    for rel in filter(None, listing.stdout.split("\0")):
        source = root / rel
        if not source.is_file():  # tracked but deleted in the working tree
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def build_archives(out_dir: Path, *, root: Path | None = None) -> list[Path]:
    """Wheel and sdist into `out_dir`, built from a staged copy of the tree so the build
    neither reads leftovers from the repo nor writes any into it."""
    source = Path(root or ROOT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-stage-") as stage:
        staged = Path(stage)
        stage_tree(source, staged)
        commands = (
            [sys.executable, "-m", "pip", "wheel", str(staged), "--no-deps",
             "--no-build-isolation", "-w", str(out_dir)],
            [sys.executable, "-c",
             f"from setuptools import build_meta as b; b.build_sdist({str(out_dir)!r})"],
        )  # fmt: skip
        for command in commands:
            proc = subprocess.run(
                command,
                cwd=str(staged),
                capture_output=True,
                text=True,
                timeout=_BUILD_TIMEOUT_S,
                check=False,
            )
            if proc.returncode != 0:
                kind = "wheel" if "wheel" in command else "sdist"
                tail = (proc.stderr or proc.stdout or "").strip()[-400:]
                raise RuntimeError(f"{kind} build failed: {tail}")
    return sorted(p for p in out_dir.iterdir() if p.name.endswith((".whl", ".tar.gz")))


def audit() -> list[ArchiveReport]:
    import config.settings  # noqa: F401  load .env so real secret values are known

    with tempfile.TemporaryDirectory(prefix="package-audit-") as tmp:
        return [scan_archive(path) for path in build_archives(Path(tmp))]


def render_audit(reports: list[ArchiveReport]) -> str:
    lines = ["Package audit (what a built wheel / sdist would ship)"]
    for report in reports:
        state = "clean" if not report.hits else f"{report.hits} hit(s)"
        lines.append(f"  {report.name}: {report.members} file(s) - {state}")
        lines.extend(f"    forbidden path: {name}" for name in report.path_hits)
        lines.extend(f"    env secret value in: {name}" for name in report.secret_hits)
        lines.extend(f"    operator path in: {name}" for name in report.operator_path_hits)
    lines.append("Member names only; file contents and secret values are never printed.")
    return "\n".join(lines)
