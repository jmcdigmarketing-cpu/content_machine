"""#833: mypy checks every package the wheel ships, not six of them.

`scripts/mypy_ratchet.py` checked analytics, apis, core, config, storage and desktop;
video, publishing, youtube, jobs, sports and scripts were only seen through imports, and
`video/` had no `__init__.py`, so a direct run stopped at "source file found twice".
The pyproject override for `video.*` / `publishing.*` set a flag nothing had switched on.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MypyTargetTests(unittest.TestCase):
    def test_every_shipped_top_level_package_is_type_checked(self):
        from scripts.mypy_ratchet import TARGETS

        with (ROOT / "pyproject.toml").open("rb") as f:
            config = tomllib.load(f)
        shipped = {p.split(".")[0] for p in config["tool"]["setuptools"]["packages"]}
        # mypy's own `exclude` skips assets/ (media and clip tooling).
        self.assertEqual(sorted(shipped - set(TARGETS) - {"assets"}), [])

    def test_video_is_a_regular_package(self):
        self.assertTrue((ROOT / "video" / "__init__.py").exists())

    def test_the_dead_override_is_gone(self):
        with (ROOT / "pyproject.toml").open("rb") as f:
            overrides = tomllib.load(f)["tool"]["mypy"].get("overrides", [])
        self.assertFalse(
            [o for o in overrides if o.get("disallow_untyped_defs") is False],
            "disallow_untyped_defs is never on, so turning it off per module does nothing",
        )


if __name__ == "__main__":
    unittest.main()
