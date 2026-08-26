"""#36 ops topic-clone --run-id calls generate_draft for real."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestTopicClone(unittest.TestCase):
    def test_clone_calls_generate_draft_with_seed_topic(self):
        from core.topic_clone import clone_from_run

        record = SimpleNamespace(
            id=71,
            input_topic="GTA 6 leak forces Take-Two to subpoena Microsoft",
            selected_topic="GTA 6 Leak and Wolverine Rage",
            channel_id="tapin",
            script_preview="unused",
        )
        outcome = SimpleNamespace(ok=True, topic=record.input_topic, run_id=99, error="")
        repo = MagicMock()
        repo.get.return_value = record
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
            patch("core.batch_generation.generate_draft", return_value=outcome) as draft,
        ):
            result = clone_from_run(71, channel_id="tapin")
        self.assertTrue(result.ok)
        draft.assert_called_once()
        self.assertEqual(draft.call_args.args[0], record.input_topic)
        self.assertEqual(draft.call_args.args[1], "tapin")

    def test_ops_command_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("topic-clone", COMMANDS)


if __name__ == "__main__":
    unittest.main()
