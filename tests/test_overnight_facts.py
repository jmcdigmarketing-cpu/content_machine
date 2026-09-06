"""Overnight --facts-file reaches generate_draft via run_batch(key_facts=)."""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import overnight


class TestOvernightFactsFile(unittest.TestCase):
    def test_facts_file_is_passed_to_run_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            facts = os.path.join(tmp, "facts.txt")
            with open(facts, "w", encoding="utf-8") as fh:
                fh.write("Take-Two filed subpoenas against Microsoft over the GTA 6 leak.\n")
            with (
                patch("core.batch_generation.collect_topics", return_value=["GTA 6 leak"]),
                patch("core.batch_generation.run_batch", return_value=[]) as batch,
                patch("core.vault_dossiers.write_run_dossier", return_value=None),
                patch("core.channel_health.build_health", return_value=MagicMock()),
                patch("core.channel_health.health_line", return_value=""),
                patch("core.events.emit_event", return_value=True),
                patch("core.signal_canary.check_signals", return_value=[]),
                patch("core.signal_canary.save_results"),
            ):
                overnight.run_overnight("tapin", count=1, facts_file=facts)
            self.assertTrue(batch.called)
            kwargs = batch.call_args.kwargs
            self.assertIn("key_facts", kwargs)
            self.assertTrue(
                any("Take-Two" in line for line in (kwargs["key_facts"] or [])),
                kwargs["key_facts"],
            )

    def test_without_facts_file_behaviour_unchanged(self):
        with (
            patch("core.batch_generation.collect_topics", return_value=["a"]),
            patch("core.batch_generation.run_batch", return_value=[]) as batch,
            patch("core.vault_dossiers.write_run_dossier", return_value=None),
            patch("core.channel_health.build_health", return_value=MagicMock()),
            patch("core.channel_health.health_line", return_value=""),
            patch("core.events.emit_event", return_value=True),
            patch("core.signal_canary.check_signals", return_value=[]),
            patch("core.signal_canary.save_results"),
        ):
            overnight.run_overnight("tapin", count=1)
        self.assertTrue(batch.called)
        kwargs = batch.call_args.kwargs
        args = batch.call_args.args
        self.assertEqual(args[0], "tapin")
        self.assertEqual(args[1], ["a"])
        self.assertFalse(kwargs.get("key_facts"))

    def test_generate_draft_receives_facts_through_run_batch(self):
        captured = {}

        def fake_draft(topic, channel_id, *, key_facts=None):
            captured["topic"] = topic
            captured["key_facts"] = key_facts
            return SimpleNamespace(ok=True, run_id=None, topic=topic)

        with tempfile.TemporaryDirectory() as tmp:
            facts = os.path.join(tmp, "facts.txt")
            with open(facts, "w", encoding="utf-8") as fh:
                fh.write("Take-Two filed subpoenas against Microsoft over the GTA 6 leak.\n")
            from core.operator_facts import load_key_facts

            loaded = load_key_facts(facts)
            with patch("core.batch_generation.generate_draft", side_effect=fake_draft):
                from core.batch_generation import run_batch

                run_batch("tapin", ["GTA 6 leak"], key_facts=loaded)
        self.assertEqual(captured["topic"], "GTA 6 leak")
        self.assertTrue(any("Take-Two" in line for line in captured["key_facts"]))

    def test_stale_future_work_docstring_is_gone(self):
        self.assertNotIn("planned follow-up", overnight.__doc__.lower())
        self.assertNotIn("needs `batch_generation.generate_draft`", overnight.__doc__)


if __name__ == "__main__":
    unittest.main()
