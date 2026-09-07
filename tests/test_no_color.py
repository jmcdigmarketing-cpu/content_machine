"""#487. NO_COLOR must disable ANSI even when stdout looks like a TTY."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.ui_theme import _C, paint


class TestNoColor(unittest.TestCase):
    def test_no_color_env_strips_paint_on_a_tty(self):
        with (
            patch.dict(os.environ, {"NO_COLOR": "1", "CONTENT_UI_COLOR": "true"}, clear=False),
            patch("sys.stdout.isatty", return_value=True),
        ):
            self.assertEqual(paint("hello", _C.RED), "hello")
