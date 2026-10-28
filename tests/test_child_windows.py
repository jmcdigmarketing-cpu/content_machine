"""2026-10-28 (the operator: "a terminal window popping in and out all crazy"): overnight ran at
power-on and its two child processes - `core.batch_review --render-draft` (#1464) and
`core.overnight --draft-job` - started under `pythonw` with no console, so every ffmpeg and ffprobe
call they made opened a window. The parent hides its children's windows (wave 123,
`core.win_shell.hide_child_windows`); each child has to do the same for its own."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class ChildWindowsTests(unittest.TestCase):
    def test_the_render_child_hides_its_windows(self):
        from core import batch_review

        with patch("core.win_shell.hide_child_windows") as hide:
            code = batch_review.main(["--render-draft", str(ROOT / "no-such-draft-folder")])
        self.assertEqual(code, 2)
        hide.assert_called_once()

    def test_the_draft_child_hides_its_windows(self):
        from core import overnight

        with (
            patch("core.win_shell.hide_child_windows") as hide,
            patch.object(overnight, "_draft_job", return_value=0),
        ):
            code = overnight.main(["--draft-job", "job.json"])
        self.assertEqual(code, 0)
        hide.assert_called_once()

    def test_every_python_child_of_core_hides_its_windows(self):
        """The guard: a module that starts itself as `sys.executable -m core.<name>` installs it."""
        started = set()
        for path in (ROOT / "core").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            started |= set(re.findall(r'sys\.executable,\s*"-m",\s*"(core\.[\w.]+)"', text))
        self.assertTrue(started)
        missing = []
        for module in sorted(started):
            source = ROOT.joinpath(*module.split(".")).with_suffix(".py")
            if "hide_child_windows(" not in source.read_text(encoding="utf-8"):
                missing.append(module)
        self.assertEqual(missing, [], "call core.win_shell.hide_child_windows() first in main()")


if __name__ == "__main__":
    unittest.main()
