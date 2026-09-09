"""Real PostgreSQL concurrency proof for ``FOR UPDATE SKIP LOCKED`` (#704).

The normal suite uses SQLite and cannot emit the lock clause. Set
``CONTENT_TEST_DATABASE_URL`` to a dedicated database whose name contains
``test``; CI supplies one. The operator's ``DATABASE_URL`` is never read.
"""

from __future__ import annotations

import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Barrier
from unittest.mock import patch

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

TEST_URL = os.getenv("CONTENT_TEST_DATABASE_URL", "").strip()


def _safe_test_url() -> bool:
    if not TEST_URL:
        return False
    try:
        parsed = make_url(TEST_URL)
    except Exception:
        return False
    return (
        parsed.get_backend_name().startswith("postgresql")
        and "test" in (parsed.database or "").lower()
    )


class TestPayloadJsonSortKeySql(unittest.TestCase):
    def test_postgres_cast_uses_jsonb_because_payload_is_text(self):
        from types import SimpleNamespace

        from storage.repositories.jobs import _payload_sort_key

        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        compiled = str(_payload_sort_key(bind).compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("jsonb", compiled.lower())
        self.assertIn("sort_key", compiled)

    def test_sqlite_keeps_the_type_coerce_path(self):
        from types import SimpleNamespace

        from storage.repositories.jobs import _payload_sort_key

        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
        compiled = str(_payload_sort_key(bind).compile(compile_kwargs={"literal_binds": True}))
        self.assertNotIn("jsonb", compiled.lower())


@unittest.skipUnless(
    _safe_test_url(),
    "set CONTENT_TEST_DATABASE_URL to a dedicated PostgreSQL test database",
)
class TestPostgresAtomicClaim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import storage.db as db
        from config.settings import Settings
        from storage.models import Base

        cls.db = db
        cls.settings_patch = patch.object(Settings, "database_url", TEST_URL)
        cls.settings_patch.start()
        db.get_engine.cache_clear()
        db._engine = None
        db._SessionLocal = None
        cls.engine = db.get_engine()
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.db.get_engine.cache_clear()
        cls.db._engine = None
        cls.db._SessionLocal = None
        cls.settings_patch.stop()

    def setUp(self):
        from storage.models import Job

        with self.engine.begin() as conn:
            conn.execute(delete(Job))

    @staticmethod
    def _repo():
        from storage.repositories.jobs import PostgresJobRepository

        return PostgresJobRepository()

    def _enqueue(self, sort_key: int):
        return self._repo().enqueue(
            {
                "channel_id": "tapin",
                "job_type": "render",
                "payload_json": json.dumps({"sort_key": sort_key}),
            }
        )

    def test_locked_first_row_is_skipped_for_the_next_eligible_job(self):
        from storage.models import Job

        first = self._enqueue(0)
        second = self._enqueue(1)
        locker = self.db.get_session()
        locker.begin()
        locked = locker.scalars(select(Job).where(Job.id == first.id).with_for_update()).one()
        self.assertEqual(locked.id, first.id)

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._repo().claim_next)
        blocked = False
        try:
            claimed = future.result(timeout=2)
        except TimeoutError:
            blocked = True
            locker.rollback()
            claimed = future.result(timeout=5)
        finally:
            if locker.in_transaction():
                locker.rollback()
            locker.close()
            pool.shutdown(wait=True)

        self.assertFalse(blocked, "claim_next blocked instead of using SKIP LOCKED")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, second.id)

    def test_concurrent_claimers_receive_distinct_jobs(self):
        jobs = [self._enqueue(i) for i in range(8)]
        barrier = Barrier(len(jobs))

        def _claim():
            barrier.wait(timeout=5)
            return self._repo().claim_next()

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            claimed = list(pool.map(lambda _i: _claim(), range(len(jobs))))

        ids = [row.id for row in claimed if row is not None]
        self.assertEqual(len(ids), len(jobs))
        self.assertEqual(len(set(ids)), len(jobs))

    def test_one_locked_job_returns_none_without_waiting(self):
        from storage.models import Job

        only = self._enqueue(0)
        locker = self.db.get_session()
        locker.begin()
        locker.scalars(select(Job).where(Job.id == only.id).with_for_update()).one()

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._repo().claim_next)
        blocked = False
        try:
            claimed = future.result(timeout=2)
        except TimeoutError:
            blocked = True
            locker.rollback()
            claimed = future.result(timeout=5)
        finally:
            if locker.in_transaction():
                locker.rollback()
            locker.close()
            pool.shutdown(wait=True)

        self.assertFalse(blocked, "claim_next blocked on the only locked row")
        self.assertIsNone(claimed)


class TestTheProofActuallyRunsInCI(unittest.TestCase):
    """#704's whole point is measuring SKIP LOCKED on real Postgres. If the CI
    service fails to come up, or the env var is renamed, `skipUnless` above turns
    that proof into three silent skips and the run still reports OK -- green
    while proving nothing, which is the shape this repo keeps rediscovering.

    GitHub Actions sets CI=true. There, a missing or unsafe test URL is a failure,
    not a skip. Locally it stays a skip, so a dev without Postgres is unaffected.
    """

    def test_ci_must_not_silently_skip_the_postgres_proof(self):
        if os.getenv("CI", "").strip().lower() not in ("1", "true", "yes"):
            self.skipTest("not CI; the Postgres proof is opt-in locally")
        self.assertTrue(
            _safe_test_url(),
            "CONTENT_TEST_DATABASE_URL is missing or not a *test* PostgreSQL "
            f"database (got {TEST_URL!r}); #704's SKIP LOCKED proof did not run",
        )


if __name__ == "__main__":
    unittest.main()
