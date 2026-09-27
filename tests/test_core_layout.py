"""#834: `core/` grows sub-packages, and the flat list may shrink but never grow.

`core/` was ~240 flat modules with no sub-packages; the prefix clusters (`fact_*`,
`run_*`, `vault_*`, `voice_*` ...) already named the seams. The backlog said the rule
matters more than the moves, so this ratchets the rule and makes the first move:
`voice_plan`, `voice_catalog` and `voice_consistency` are now `core/voice/`. The old
names stay one wave as aliases of the same module objects, so in-flight code (and the
other agent) keeps importing and a `patch("core.voice_plan.x")` still patches the
module that runs.
"""

from __future__ import annotations

import importlib
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
# Non-alias flat modules in core/ (with __init__.py) after the voice move. Lower it as
# modules move into sub-packages; never raise it.
FLAT_CEILING = 243
MOVED = {
    "voice_plan": "core.voice.plan",
    "voice_catalog": "core.voice.catalog",
    "voice_consistency": "core.voice.consistency",
}
# A prefix a sub-package owns: no new flat module may start with it.
OWNED_PREFIXES = {"voice_": "core/voice/"}


def _is_alias(path: Path) -> bool:
    return "sys.modules[__name__]" in path.read_text(encoding="utf-8")


def _flat() -> list[Path]:
    return sorted(p for p in CORE.glob("*.py") if not _is_alias(p))


class CoreLayoutTests(unittest.TestCase):
    def test_the_flat_list_does_not_grow(self):
        self.assertLessEqual(len(_flat()), FLAT_CEILING, "new code goes in a core/ sub-package")

    def test_the_voice_package_exists(self):
        for new in MOVED.values():
            with self.subTest(module=new):
                self.assertTrue(importlib.import_module(new))

    def test_the_old_names_are_the_same_modules(self):
        for old, new in MOVED.items():
            with self.subTest(old=old):
                self.assertIs(importlib.import_module(f"core.{old}"), importlib.import_module(new))

    def test_no_flat_module_takes_an_owned_prefix(self):
        for prefix, home in OWNED_PREFIXES.items():
            with self.subTest(prefix=prefix):
                strays = [p.name for p in _flat() if p.name.startswith(prefix)]
                self.assertEqual(strays, [], f"{prefix}* modules live in {home}")

    def test_nothing_imports_the_old_names(self):
        pattern = re.compile(r"core\.(" + "|".join(MOVED) + r")\b")
        hits = []
        for path in ROOT.rglob("*.py"):
            parts = set(path.relative_to(ROOT).parts)
            if parts & {".git", ".venv", "venv", "node_modules", "build"}:
                continue
            if path.parent == CORE and path.stem in MOVED:
                continue
            if path.name == "test_core_layout.py":
                continue
            if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [])

    def test_the_wheel_ships_it(self):
        with (ROOT / "pyproject.toml").open("rb") as f:
            packages = tomllib.load(f)["tool"]["setuptools"]["packages"]
        self.assertIn("core.voice", packages)

    def test_the_rule_is_written_where_agents_read(self):
        self.assertIn("Where a new module goes", (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
