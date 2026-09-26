"""#867: every key a run stores has a reader.

The wave 36 review found 7 of 68 persisted feature/quality keys written and read by
nothing - audit data the operator could never see. The run dossier now renders them in
an Audit block, and this scan fails when a new key is stored with no reader.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_WRITE = re.compile(r"""(?:quality|features|result\.features)\[["']([a-z_]+)["']\]\s*=(?!=)""")
_SCAN = ("core", "analytics", "publishing", "scripts", "video", "storage", "desktop")

# Keys whose only reader is outside Python (none today); each needs a reason.
ALLOWED_UNREAD: dict[str, str] = {}


def _py_files():
    for folder in _SCAN:
        yield from (ROOT / folder).rglob("*.py")
    yield ROOT / "main.py"


class PersistedKeysReadTests(unittest.TestCase):
    def test_every_stored_key_has_a_reader(self):
        texts = {p: p.read_text(encoding="utf-8") for p in _py_files()}
        writers: dict[str, set[Path]] = {}
        for path, text in texts.items():
            if path.parts[-2] not in ("core", "analytics"):
                continue
            for key in _WRITE.findall(text):
                writers.setdefault(key, set()).add(path)
        unread = []
        for key, wrote in sorted(writers.items()):
            if key in ALLOWED_UNREAD:
                continue
            pattern = re.compile(rf"""["']{key}["']""")
            if not any(pattern.search(t) for p, t in texts.items() if p not in wrote):
                unread.append(key)
        self.assertEqual(unread, [], "stored but read by nothing - render it or stop storing it")


class DossierAuditTests(unittest.TestCase):
    def test_audit_block_renders_every_key(self):
        from core.vault_dossiers import audit_lines

        lines = "\n".join(
            audit_lines(
                {
                    "all_angles": True,
                    "chapter_opener_notes": ["chapter 2 opener trimmed"],
                    "artifact_manifest": {"mp4_sha256": "a" * 64, "script_sha256": "b" * 64},
                    "brief_fallback": "deadline",
                    "brief_deadline_s": 45,
                    "vault_relevance": [
                        {"band": "confident", "note": "Palworld patch 1.2"},
                        {"band": "reject", "note": "NBA trade"},
                    ],
                },
                {"pre_rewrite_unsupported_count": 7},
            )
        )
        for want in (
            "All angles",
            "chapter 2 opener trimmed",
            "aaaaaaaaaaaa",
            "deadline",
            "45",
            "7 unsupported before the rewrite",
            "2 vault notes",
            "reject 1",
        ):
            self.assertIn(want, lines)

    def test_empty_run_has_no_audit_block(self):
        from core.vault_dossiers import audit_lines

        self.assertEqual(audit_lines({}, {}), [])


if __name__ == "__main__":
    unittest.main()
