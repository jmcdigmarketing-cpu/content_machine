"""Thumbnail provider chain (Pillar 6, U5) — THUMBNAIL_PROVIDER selection + fail-open.

No network and no real image writes: the provider functions and `requests` are
mocked, and the experiment arm is stubbed so nothing touches data/. Default
(THUMBNAIL_PROVIDER unset) must NOT enter the new chain path.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from assets import flux_thumbnail as ft
from assets.flux_thumbnail import ThumbnailResult


class TestProviderChainOrder(unittest.TestCase):
    def test_order(self):
        self.assertEqual(ft._provider_chain("ideogram"), ["ideogram", "flux", "pillow"])
        self.assertEqual(ft._provider_chain("recraft"), ["recraft", "flux", "pillow"])
        self.assertEqual(ft._provider_chain("flux"), ["flux", "pillow"])
        self.assertEqual(ft._provider_chain("pillow"), ["pillow"])
        self.assertEqual(ft._provider_chain("bogus"), ["flux", "pillow"])  # unknown -> flux->pillow


class TestDispatch(unittest.TestCase):
    def test_unset_keeps_default_path(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch.object(ft, "_chain_thumbnail") as chain,
                mock.patch.object(
                    ft, "_flux_thumbnail", return_value=ThumbnailResult(None, "not_configured")
                ),
                mock.patch.object(
                    ft, "_pillow_thumbnail", return_value=ThumbnailResult("p.png", "generated")
                ),
            ):
                ft.generate_thumbnail("topic", "title", "out")
                chain.assert_not_called()  # default path, not the chain

    def test_set_provider_uses_chain(self):
        with mock.patch.dict(os.environ, {"THUMBNAIL_PROVIDER": "ideogram"}, clear=True):
            with mock.patch.object(
                ft, "_chain_thumbnail", return_value=ThumbnailResult("x.png", "generated")
            ) as chain:
                out = ft.generate_thumbnail("topic", "title", "out")
                chain.assert_called_once()
                self.assertEqual(out.path, "x.png")


class TestChainFailOpen(unittest.TestCase):
    def test_falls_through_to_pillow(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("core.experiments.next_arm", return_value=None),
            mock.patch.object(
                ft, "_ideogram_thumbnail", return_value=ThumbnailResult(None, "not_configured")
            ),
            mock.patch.object(
                ft, "_flux_thumbnail", return_value=ThumbnailResult(None, "not_configured")
            ),
            mock.patch.object(
                ft,
                "_pillow_thumbnail",
                return_value=ThumbnailResult("out/pillow.png", "generated", "Pillow"),
            ),
        ):
            out = ft._chain_thumbnail("ideogram", "topic", "title", "out")
            self.assertEqual(out.path, "out/pillow.png")

    def test_first_success_wins(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("core.experiments.next_arm", return_value=None),
            mock.patch.object(
                ft,
                "_ideogram_thumbnail",
                return_value=ThumbnailResult("out/id.png", "generated", "Ideogram"),
            ) as ideo,
            mock.patch.object(ft, "_flux_thumbnail") as flux,
            mock.patch.object(ft, "_pillow_thumbnail") as pillow,
        ):
            out = ft._chain_thumbnail("ideogram", "topic", "title", "out")
            self.assertEqual(out.path, "out/id.png")
            ideo.assert_called_once()
            flux.assert_not_called()
            pillow.assert_not_called()


class TestProviderKeyGating(unittest.TestCase):
    def test_ideogram_no_key(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(ft, "requests") as req,
        ):
            out = ft._ideogram_thumbnail("t", "ti", "out", filename="f.png")
            self.assertEqual(out.status, "not_configured")
            req.post.assert_not_called()

    def test_recraft_no_key(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(ft, "requests") as req,
        ):
            out = ft._recraft_thumbnail("t", "ti", "out", filename="f.png")
            self.assertEqual(out.status, "not_configured")
            req.post.assert_not_called()

    def test_ideogram_http_error_fails_open(self):
        with tempfile.TemporaryDirectory() as d:
            with (
                mock.patch.dict(os.environ, {"IDEOGRAM_API_KEY": "k"}, clear=True),
                mock.patch.object(ft, "requests") as req,
            ):
                req.post.side_effect = RuntimeError("boom")
                out = ft._ideogram_thumbnail("t", "ti", d, filename="f.png")
                self.assertIsNone(out.path)
                self.assertEqual(out.status, "ideogram_failed")


if __name__ == "__main__":
    unittest.main()
