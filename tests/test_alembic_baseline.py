import os
import tempfile
import unittest

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from storage.alembic_runner import current_revision


class TestAlembicBaseline(unittest.TestCase):
    def test_head_revision_is_0002(self):
        self.assertEqual(current_revision(), "0002")

    def test_script_chain_loads(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(root, "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        revs = list(script.walk_revisions())
        self.assertEqual(len(revs), 2)
        self.assertEqual(revs[0].revision, "0002")

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


if __name__ == "__main__":
    unittest.main()
