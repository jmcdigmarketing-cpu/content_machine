"""#342 (operator's choice: corrections only): a source that keeps being corrected loses
some of its weight.

The filed text said tiers are hand-assigned per source; they are per section (web, signal,
vault...), and nothing tied a correction back to a source. The only records that name one
are the post-publish correction dossiers (their negative facts carry the source URL in
the reason) and the operator's rejects at the key-facts prompt - which usually mean
"off-topic", not "wrong", so they are shown and never applied. Two or more corrections
lower a source's factor by 0.05 each, bounded at 0.85; the factor scales the tier part of
a vault fact's confidence and ranking. Promotion would need evidence of being right,
which nothing records.

Vault notes the machine writes kept their page URLs under `pages:`, which the fact store
never read, so their facts had no source to weigh; `pages:` now fills `source_url`.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

REASON = "source retracted after publish ({url}, video abc123)"


class _Store(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._path = Path(self._tmp.name) / "negative_facts.json"
        self._patch = patch("core.negative_facts.STORE_PATH", self._path)
        self._patch.start()
        self._env = patch.dict(os.environ, {"TRUST_MIN_CORRECTIONS": ""})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def _corrections(self, url, n):
        from core.negative_facts import record_negative

        for i in range(n):
            record_negative("ufc", f"claim number {i} from {url}", reason=REASON.format(url=url))


class SourceUrlTests(unittest.TestCase):
    META: ClassVar[dict[str, str]] = {"source": "content-machine (link facts)",
            "pages": "https://www.espn.com/mma/story/1 https://x.com/2"}  # fmt: skip

    def test_pages_give_the_source_to_weigh(self):
        from core.facts.store import trust_source

        self.assertEqual(trust_source(self.META, ""), "https://www.espn.com/mma/story/1")

    def test_a_url_source_still_wins(self):
        from core.facts.store import note_metadata, trust_source

        meta = {"source": "https://tapology.com/x", "pages": "https://espn.com/y"}
        url = note_metadata(meta, "a.md")[3]
        self.assertEqual(trust_source(meta, url), "https://tapology.com/x")

    def test_pages_never_become_a_public_citation(self):
        # `source_url` is cited in published descriptions (core/description_extras).
        from core.facts.store import note_metadata

        self.assertEqual(note_metadata(self.META, "tapin/_link_facts/a.md")[3], "")


class FactorTests(_Store):
    def test_counts_come_from_the_dossier_reason(self):
        from core.facts.trust import correction_counts

        self._corrections("https://www.mmafighting.com/2026/9/1/story", 2)
        self.assertEqual(correction_counts(), {"mmafighting.com": 2})

    def test_under_the_minimum_nothing_changes(self):
        from core.facts.trust import source_factor

        self._corrections("https://mmafighting.com/a", 1)
        self.assertEqual(source_factor("https://mmafighting.com/other"), 1.0)

    def test_demotion_is_bounded(self):
        from core.facts.trust import source_factor

        self._corrections("https://mmafighting.com/a", 2)
        self.assertAlmostEqual(source_factor("https://www.mmafighting.com/b"), 0.90)
        self._corrections("https://mmafighting.com/c", 6)
        self.assertAlmostEqual(source_factor("https://mmafighting.com/d"), 0.85)
        self.assertEqual(source_factor("https://espn.com/e"), 1.0)
        self.assertEqual(source_factor(""), 1.0)

    def test_the_minimum_can_be_set(self):
        from core.facts.trust import source_factor

        self._corrections("https://mmafighting.com/a", 1)
        with patch.dict(os.environ, {"TRUST_MIN_CORRECTIONS": "1"}):
            self.assertAlmostEqual(source_factor("https://mmafighting.com/b"), 0.95)

    def test_rejects_never_move_the_factor(self):
        from core.facts.trust import source_factor

        runs = [SimpleNamespace(id=i, features_json=json.dumps({"vault_relevance": [
            {"claim": "c", "source_url": "https://espn.com/x", "operator_override": "rejected"}
        ]})) for i in range(10)]  # fmt: skip
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=SimpleNamespace(list_for_channel=lambda c: runs),
        ):
            self.assertEqual(source_factor("https://espn.com/y"), 1.0)


class AppliedTests(_Store):
    def test_confidence_uses_it(self):
        from core.facts.confidence import record_confidence

        fact = SimpleNamespace(tier="link", relevance_score=None, verified_at=None,
                               source_url="", trust_source="https://mmafighting.com/z")  # fmt: skip
        before = record_confidence(fact).value
        self._corrections("https://mmafighting.com/a", 2)
        self.assertLess(record_confidence(fact).value, before)

    def test_ranking_uses_it(self):
        from core.facts.store import rank_bonus

        self.assertLess(rank_bonus(tier="link", trust=0.85), rank_bonus(tier="link"))
        self.assertLess(rank_bonus(tier="operator", trust=1.0), 1.0)

    def test_the_vault_reader_passes_the_note_source(self):
        text = (Path(__file__).resolve().parents[1] / "core" / "obsidian_facts.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("trust=source_factor(weighed_source)", text)
        self.assertIn("trust_source=weighed_source", text)


class ReportTests(_Store):
    def test_ops_source_trust(self):
        from scripts.ops import COMMANDS

        self._corrections("https://mmafighting.com/a", 2)
        runs = [SimpleNamespace(id=1, features_json=json.dumps({"vault_relevance": [
            {"claim": "c", "source_url": "https://espn.com/x", "operator_override": "rejected"},
            {"claim": "d", "source_url": "https://espn.com/y", "operator_override": "accepted"},
        ]}))]  # fmt: skip
        buf = io.StringIO()
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            redirect_stdout(buf),
        ):
            code = COMMANDS["source-trust"][1](Namespace(channel="tapin"))
        text = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("mmafighting.com: 2 correction(s) -> weight x0.90", text)
        self.assertIn("espn.com: 1 of 2 rejected at key facts (shown, not applied)", text)


if __name__ == "__main__":
    unittest.main()
