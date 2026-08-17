"""Running a migration must not switch off the project's logging.

Found while building tests/test_fail_open_visibility.py: those tests passed alone and
failed under `unittest discover`, because `tests/test_alembic_baseline.py` had run a
migration first and every `content_machine.*` logger came back `.disabled = True`.

The cause was `alembic/env.py` calling `fileConfig(...)` with the default
`disable_existing_loggers=True`, which disables every logger that already exists. This is
not test-only: `storage/migrate_schema.py` calls `upgrade_head()` inside an ordinary
process, so after a migration every subsequent log line — fail-open warnings, breaker
notices, plain errors — was dropped in silence for the rest of that process.

That is the same defect shape as decisions §18 and §24, applied to the reporting
mechanism itself: the thing that makes failures visible was being turned off invisibly.
"""

import logging
import unittest
from logging.config import fileConfig

from storage.alembic_runner import _alembic_config


class TestMigrationsKeepLoggingAlive(unittest.TestCase):
    def test_fileconfig_does_not_disable_project_loggers(self):
        """Directly exercise the env.py call shape, with no DB required."""
        from core.logging import get_logger

        log = get_logger("core.quota_governor")
        self.assertFalse(log.disabled, "precondition: logger starts enabled")

        cfg = _alembic_config()
        self.assertIsNotNone(cfg.config_file_name)
        fileConfig(cfg.config_file_name, disable_existing_loggers=False)

        self.assertFalse(
            log.disabled,
            "alembic.ini's fileConfig disabled the content_machine logger tree — "
            "every log line after a migration would be silently dropped",
        )

    def test_the_default_is_what_would_have_broken_it(self):
        """Pins WHY the keyword is there: the default really does disable them."""
        victim = logging.getLogger("content_machine.test_canary")
        victim.disabled = False

        cfg = _alembic_config()
        fileConfig(cfg.config_file_name)  # the old call, defaults to disabling
        self.assertTrue(victim.disabled, "expected the default to disable existing loggers")

        # Restore, and confirm the fixed call shape leaves it alone.
        fileConfig(cfg.config_file_name, disable_existing_loggers=False)
        victim.disabled = False
        fileConfig(cfg.config_file_name, disable_existing_loggers=False)
        self.assertFalse(victim.disabled)

    def test_env_py_passes_the_keyword(self):
        """env.py runs under alembic, not under the suite — assert its source."""
        from pathlib import Path

        env = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
        source = env.read_text(encoding="utf-8")
        self.assertIn("disable_existing_loggers=False", source)


if __name__ == "__main__":
    unittest.main()
