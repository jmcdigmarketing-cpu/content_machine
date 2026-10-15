"""#1184: an open correction note is written again on the next day's scan.

32 notes were on file for 5 video + claim pairs. `ops corrections-open` folds them.
The vault does not. The scan calls the real writer into a temp vault. Two dates,
because a second scan on the same day overwrites the one file and hides the bug.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

CLAIM = "Shavkat Rakhmonov withdrew from the title fight with a knee injury from sparring."
BODY = (
    "Shavkat Rakhmonov returns to training camp in Dubai ahead of his next bout, "
    "his coach said this week, with no date set for a return."
)


class _Day:
    def __init__(self, iso: str) -> None:
        self.iso = iso

    def today(self):
        return self

    def isoformat(self) -> str:
        return self.iso


class OpenNoteOnceTests(unittest.TestCase):
    def test_a_second_day_does_not_write_the_open_pair_again(self):
        from core.correction_dossier import scan_published_for_corrections

        row = SimpleNamespace(content_run_id=119, youtube_video_id="q6_QBAUrtiQ")
        run = SimpleNamespace(
            features_json=json.dumps(
                {
                    "claim_verification": {"claims": [{"claim": CLAIM, "supported": True}]},
                    "source_urls": ["https://www.mmafighting.com/ufc/514292/rakhmonov"],
                }
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "tapin"))

            def scan(day: str):
                with (
                    patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": tmp}),
                    patch("core.vault.dossiers.date", _Day(day)),
                ):
                    return scan_published_for_corrections(
                        "tapin",
                        published=[row],
                        run_lookup={119: run},
                        fetch=lambda url: BODY,
                        negative_store=lambda *a: None,
                        stamp_path=os.path.join(tmp, "stamp.json"),
                        force=True,
                    )

            first = scan("2026-10-14")
            folder = os.path.join(tmp, "tapin", "_reports")
            names = [n for n in os.listdir(folder) if "_correction-" in n]
            self.assertEqual(len(first), 1)
            self.assertEqual(names, ["2026-10-14_correction-q6QBAUrtiQ.md"])

            again = scan("2026-10-15")
            names = sorted(n for n in os.listdir(folder) if "_correction-" in n)
            self.assertEqual(names, ["2026-10-14_correction-q6QBAUrtiQ.md"])
            self.assertEqual(again, [])

            path = os.path.join(folder, names[0])
            with open(path, encoding="utf-8") as handle:
                text = handle.read().replace("**Status:** open", "**Status:** closed")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            closed = scan("2026-10-16")
            names = sorted(n for n in os.listdir(folder) if "_correction-" in n)
            self.assertEqual(len(closed), 1)
            self.assertEqual(
                names,
                [
                    "2026-10-14_correction-q6QBAUrtiQ.md",
                    "2026-10-16_correction-q6QBAUrtiQ.md",
                ],
            )
