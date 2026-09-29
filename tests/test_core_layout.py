"""#834: `core/` grows sub-packages, and the flat list may shrink but never grow.

`core/` was ~240 flat modules with no sub-packages; the prefix clusters (`fact_*`,
`run_*`, `vault_*`, `voice_*` ...) already named the seams. The backlog said the rule
matters more than the moves, so this ratchets the rule and makes the first move:
`voice_plan`, `voice_catalog` and `voice_consistency` are now `core/voice/`. The old
names stay one wave as aliases of the same module objects, so in-flight code (and the
other agent) keeps importing and a `patch("core.voice_plan.x")` still patches the
module that runs.

#901 (wave 45) ended the voice aliases' wave and made the second move: the seven
`vault_*` modules are `core/vault/`, their old names aliases for one wave.

#907 (wave 46) ended the vault aliases' wave and moved the eight `fact_*` modules into
`core/facts/`.
"""

from __future__ import annotations

import importlib
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
# Non-alias flat modules in core/ (with __init__.py) after the facts move (#907). Lower it
# as modules move into sub-packages; never raise it.
FLAT_CEILING = 228
# Moves whose old name is still a one-wave alias.
MOVED = {
    "fact_store": "core.facts.store",
    "fact_selection": "core.facts.selection",
    "fact_grounding": "core.facts.grounding",
    "fact_intake": "core.facts.intake",
    "fact_enrichment": "core.facts.enrichment",
    "fact_conflicts": "core.facts.conflicts",
    "fact_expiry": "core.facts.expiry",
    "fact_recency": "core.facts.recency",
}
# Moves whose alias wave is over: the old file is gone (#901 voice, #907 vault).
RETIRED_ALIASES = {
    "voice_plan": "core.voice.plan",
    "voice_catalog": "core.voice.catalog",
    "voice_consistency": "core.voice.consistency",
    "vault_dossiers": "core.vault.dossiers",
    "vault_evals": "core.vault.evals",
    "vault_index": "core.vault.index",
    "vault_ingest": "core.vault.ingest",
    "vault_relevance": "core.vault.relevance",
    "vault_retier": "core.vault.retier",
    "vault_writeback": "core.vault.writeback",
}
# A prefix a sub-package owns: no new flat module may start with it.
OWNED_PREFIXES = {"voice_": "core/voice/", "vault_": "core/vault/", "fact_": "core/facts/"}


def _is_alias(path: Path) -> bool:
    return "sys.modules[__name__]" in path.read_text(encoding="utf-8")


def _flat() -> list[Path]:
    return sorted(p for p in CORE.glob("*.py") if not _is_alias(p))


class CoreLayoutTests(unittest.TestCase):
    def test_the_flat_list_does_not_grow(self):
        self.assertLessEqual(len(_flat()), FLAT_CEILING, "new code goes in a core/ sub-package")

    def test_the_packages_exist(self):
        for new in (*MOVED.values(), *RETIRED_ALIASES.values()):
            with self.subTest(module=new):
                self.assertTrue(importlib.import_module(new))

    def test_the_old_names_are_the_same_modules(self):
        for old, new in MOVED.items():
            with self.subTest(old=old):
                self.assertIs(importlib.import_module(f"core.{old}"), importlib.import_module(new))

    def test_a_finished_alias_wave_leaves_no_file(self):
        for old in RETIRED_ALIASES:
            with self.subTest(old=old):
                self.assertFalse((CORE / f"{old}.py").exists(), f"core/{old}.py outlived its wave")

    def test_no_flat_module_takes_an_owned_prefix(self):
        for prefix, home in OWNED_PREFIXES.items():
            with self.subTest(prefix=prefix):
                strays = [p.name for p in _flat() if p.name.startswith(prefix)]
                self.assertEqual(strays, [], f"{prefix}* modules live in {home}")

    def test_nothing_imports_the_old_names(self):
        names = [*MOVED, *RETIRED_ALIASES]
        pattern = re.compile(r"core\.(" + "|".join(names) + r")\b")
        # `from core import vault_index` names the old module without a dot - on one
        # line, or inside a parenthesized list (#907: two test files hid there).
        bare = re.compile(r"from core import (?:\([^)]*|[^\n]*)\b(" + "|".join(names) + r")\b")
        hits = []
        for path in ROOT.rglob("*.py"):
            parts = set(path.relative_to(ROOT).parts)
            if parts & {".git", ".venv", "venv", "node_modules", "build"}:
                continue
            if path.parent == CORE and path.stem in MOVED:
                continue
            if path.name == "test_core_layout.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text) or bare.search(text):
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [])

    def test_the_wheel_ships_it(self):
        with (ROOT / "pyproject.toml").open("rb") as f:
            packages = tomllib.load(f)["tool"]["setuptools"]["packages"]
        self.assertIn("core.voice", packages)
        self.assertIn("core.vault", packages)
        self.assertIn("core.facts", packages)

    def test_the_rule_is_written_where_agents_read(self):
        self.assertIn("Where a new module goes", (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
