"""publish_log.content_run_id is optional (Alembic 0004).

Rows imported from YouTube analytics have no originating run. That used to be written
as the sentinel 0, which is not a real content_runs.id and blocked the foreign key;
it is NULL now. Both storage backends must agree, and the callers that compare run
ids must not blow up on None.
"""

import unittest
from unittest.mock import patch

from storage.repositories.publish_log import _opt_int, _to_record


class TestOptInt(unittest.TestCase):
    def test_missing_and_empty_are_none(self):
        for value in (None, ""):
            self.assertIsNone(_opt_int(value))

    def test_legacy_zero_sentinel_normalises_to_none(self):
        # The whole point: 0 never meant "run 0", it meant "no run".
        self.assertIsNone(_opt_int(0))
        self.assertIsNone(_opt_int("0"))

    def test_real_ids_survive(self):
        self.assertEqual(_opt_int(65), 65)
        self.assertEqual(_opt_int("65"), 65)

    def test_garbage_is_none_not_an_exception(self):
        self.assertIsNone(_opt_int("not-a-number"))
        self.assertIsNone(_opt_int(object()))


class TestRecordCoercion(unittest.TestCase):
    def test_dict_row_with_null_run(self):
        rec = _to_record({"id": 1, "content_run_id": None, "channel_id": "tapin"})
        self.assertIsNone(rec.content_run_id)

    def test_dict_row_with_legacy_zero(self):
        rec = _to_record({"id": 1, "content_run_id": 0, "channel_id": "tapin"})
        self.assertIsNone(rec.content_run_id)

    def test_dict_row_with_real_run(self):
        rec = _to_record({"id": 1, "content_run_id": 65, "channel_id": "tapin"})
        self.assertEqual(rec.content_run_id, 65)

    def test_orm_row_with_null_run(self):
        class Row:
            id = 1
            content_run_id = None
            channel_id = "tapin"
            youtube_video_id = "abc"
            privacy_status = "public"
            status = "imported"
            metrics_json = '{"views": 1}'
            detail = ""
            idempotency_key = ""
            published_at = None

        rec = _to_record(Row())
        self.assertIsNone(rec.content_run_id)
        self.assertEqual(rec.youtube_video_id, "abc")


class TestRunIdComparisonsAreNoneSafe(unittest.TestCase):
    """`int(r.get("content_run_id", 0))` raised TypeError once the value could be None."""

    def test_queue_manager_filter_skips_null_rows(self):
        from analytics import queue_manager

        rows = [
            {"content_run_id": None, "channel_id": "tapin"},  # imported, no run
            {"content_run_id": 65, "channel_id": "tapin"},
        ]

        class _Repo:
            """JSON-backed shape: `_publish_logs_for_run` reads rows directly."""

            def _read(self):
                return rows

        with patch.object(queue_manager, "get_publish_log_repository", return_value=_Repo()):
            out = queue_manager._publish_logs_for_run("tapin", 65)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["content_run_id"], 65)


if __name__ == "__main__":
    unittest.main()
