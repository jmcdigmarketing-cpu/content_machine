"""#868: `preview-render` and `render-preview` were two verbs that did different things.

One re-renders a voiced Short over today's background for $0; the other makes a 480p
review copy of a run. The first is now `reback-short`; the old name stays one wave as a
tombstone that names the new one and runs nothing.
"""

from __future__ import annotations

import argparse
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


class VerbNameTests(unittest.TestCase):
    def test_the_new_name_runs_the_background_re_render(self):
        from scripts import ops

        self.assertIn("reback-short", ops.COMMANDS)
        with (
            patch("os.path.isfile", return_value=True),
            patch("assets.fast_cut.render_preview", return_value="out.mp4") as render,
            redirect_stdout(io.StringIO()),
        ):
            code = ops.COMMANDS["reback-short"][1](
                argparse.Namespace(path="a.mp3", topic="t", channel="tapin", seconds=0)
            )
        self.assertEqual(code, 0)
        render.assert_called_once()

    def test_the_old_name_runs_nothing_and_names_the_new_one(self):
        from scripts import ops

        out = io.StringIO()
        with patch("assets.fast_cut.render_preview") as render, redirect_stdout(out):
            code = ops.COMMANDS["preview-render"][1](
                argparse.Namespace(path="a.mp3", topic="t", channel="tapin", seconds=0)
            )
        self.assertEqual(code, 2)
        render.assert_not_called()
        self.assertIn("reback-short", out.getvalue())

    def test_render_preview_is_still_the_review_copy(self):
        from scripts import ops

        self.assertIn("480p", ops.COMMANDS["render-preview"][0])


if __name__ == "__main__":
    unittest.main()
