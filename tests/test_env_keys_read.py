"""#855: every setting documented in `.env.example` is read by something.

`INGEST_ENABLED` was documented as the auto-ingest gate, and no code read it: nothing
auto-ingests, and `ops ingest` is explicit. An operator setting it changed nothing. This
scan fails when a documented key has no reader.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_KEY = re.compile(r"^#?\s*([A-Z][A-Z0-9_]{3,})=", re.M)
_PRUNE = {
    ".git",
    "tests",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "output",
    "data",
    "cache",
}

# Keys read through a name built at runtime; each family names its reader.
DYNAMIC_FAMILIES: dict[str, str] = {
    r"LLM_(CHEAP|EXTRACT|PREMIUM)_(PROVIDER|MODEL)": "core/llm_router.py f'LLM_{tier}_...'",
    r"[A-Z]+_MODEL(_(CHEAP|EXTRACT|PREMIUM))?": "core/llm_router.py f'{prefix}_MODEL[_{tier}]'",
}


def _code_text() -> str:
    parts: list[str] = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if (d not in _PRUNE and not d.startswith(".")) or d == ".github"]
        for name in files:
            if name.endswith((".py", ".ps1", ".yml", ".yaml")):
                path = Path(folder) / name
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


class EnvKeysReadTests(unittest.TestCase):
    def test_every_documented_key_has_a_reader(self):
        keys = set(_KEY.findall((ROOT / ".env.example").read_text(encoding="utf-8")))
        code = _code_text()
        read = set(re.findall(r"""["']([A-Z][A-Z0-9_]{3,})["']|\$env:([A-Z][A-Z0-9_]{3,})""", code))
        literal = {name for pair in read for name in pair if name}
        unread = []
        for key in sorted(keys):
            if key in literal:
                continue
            if any(re.fullmatch(pattern, key) for pattern in DYNAMIC_FAMILIES):
                continue
            unread.append(key)
        self.assertEqual(unread, [], "documented in .env.example and read by nothing")


if __name__ == "__main__":
    unittest.main()
