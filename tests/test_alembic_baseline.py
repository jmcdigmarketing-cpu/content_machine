import os
import tempfile
import unittest

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from storage.alembic_runner import current_revision


class TestAlembicBaseline(unittest.TestCase):
    def test_head_revision_is_0004(self):
        self.assertEqual(current_revision(), "0004")

    def test_script_chain_loads(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(root, "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        revs = list(script.walk_revisions())
        self.assertEqual(len(revs), 4)
        self.assertEqual(revs[0].revision, "0004")

    def test_upgrade_creates_tables_on_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            url = "sqlite:///" + db_path.replace("\\", "/")
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cfg = Config(os.path.join(root, "alembic.ini"))
            cfg.set_main_option("sqlalchemy.url", url)

            command.upgrade(cfg, "head")

            engine = create_engine(url)
            try:
                tables = set(inspect(engine).get_table_names())
            finally:
                engine.dispose()

            expected = {
                "topic_scores",
                "performance_entries",
                "content_runs",
                "publish_log",
                "jobs",
                "assets",
                "thumbnail_scores",
                "alembic_version",
            }
            self.assertTrue(expected.issubset(tables))


class TestContentRunForeignKeys(unittest.TestCase):
    """0004: content_run_id FKs, and the `0` sentinel -> NULL conversion.

    The live DB had 836 of 870 publish_log rows at content_run_id=0 (imported YouTube
    videos with no originating run); they carry the metrics the learning loop reads, so
    the migration must convert rather than delete.
    """

    def _upgraded_engine(self, tmp, revision="head"):
        url = "sqlite:///" + os.path.join(tmp, "fk.db").replace("\\", "/")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(root, "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, revision)
        return create_engine(url), cfg

    def test_fks_declared_on_all_four_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._upgraded_engine(tmp)
            try:
                insp = inspect(engine)
                for table in ("publish_log", "jobs", "assets", "thumbnail_scores"):
                    targets = [
                        fk["referred_table"]
                        for fk in insp.get_foreign_keys(table)
                        if "content_run_id" in (fk.get("constrained_columns") or [])
                    ]
                    self.assertIn("content_runs", targets, f"{table} missing content_run FK")
            finally:
                engine.dispose()

    def test_sentinel_zero_becomes_null_and_rows_survive(self):
        from sqlalchemy import text

        with tempfile.TemporaryDirectory() as tmp:
            # Stop before 0004, seed legacy sentinel rows, then migrate over them.
            engine, cfg = self._upgraded_engine(tmp, revision="0003")
            try:
                with engine.begin() as conn:
                    for i in range(3):
                        conn.execute(
                            text(
                                "INSERT INTO publish_log (content_run_id, channel_id, "
                                "youtube_video_id, privacy_status, status, metrics_json, "
                                "detail, idempotency_key) VALUES "
                                "(0, 'tapin', :v, 'public', 'imported', :m, '', :k)"
                            ),
                            {"v": f"vid{i}", "k": f"seed-{i}", "m": '{"views": 10}'},
                        )
            finally:
                engine.dispose()

            command.upgrade(cfg, "head")

            engine = create_engine(cfg.get_main_option("sqlalchemy.url"))
            try:
                with engine.begin() as conn:
                    total = conn.execute(text("SELECT count(*) FROM publish_log")).scalar()
                    nulls = conn.execute(
                        text("SELECT count(*) FROM publish_log WHERE content_run_id IS NULL")
                    ).scalar()
                    zeros = conn.execute(
                        text("SELECT count(*) FROM publish_log WHERE content_run_id = 0")
                    ).scalar()
                self.assertEqual(total, 3, "imported rows must be preserved, not deleted")
                self.assertEqual(nulls, 3)
                self.assertEqual(zeros, 0)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
