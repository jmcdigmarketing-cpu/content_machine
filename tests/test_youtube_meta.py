"""YouTube snippet helpers: category, language, uniqueness, UFC lint."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.youtube_meta import (
    apply_snippet_defaults,
    audit_made_for_kids,
    category_id_for_domain,
    category_id_for_topic,
    lint_ufc_title,
    normalize_title,
    title_collision,
)


class TestYoutubeMeta(unittest.TestCase):
    def test_sports_and_finance_categories(self):
        self.assertEqual(category_id_for_domain("ufc"), "17")
        self.assertEqual(category_id_for_domain("gaming"), "20")
        self.assertEqual(category_id_for_domain("finance"), "25")

    def test_topic_uses_infer_domain(self):
        with patch("apis.topic_scorer.infer_domain", return_value="ufc"):
            self.assertEqual(category_id_for_topic("fight night", "tapin"), "17")

    def test_language_and_empty_category(self):
        with patch.dict(os.environ, {"YOUTUBE_DEFAULT_LANGUAGE": "en"}):
            with patch("core.youtube_meta.category_id_for_topic", return_value="17"):
                out = apply_snippet_defaults({"title": "UFC 317"}, topic="UFC 317")
        self.assertEqual(out["categoryId"], "17")
        self.assertEqual(out["defaultLanguage"], "en")
        self.assertEqual(out["defaultAudioLanguage"], "en")

    def test_made_for_kids_forced_false(self):
        out = audit_made_for_kids({"selfDeclaredMadeForKids": True, "privacyStatus": "public"})
        self.assertIs(out["selfDeclaredMadeForKids"], False)

    def test_title_collision_block_path(self):
        rows = [SimpleNamespace(id=3, title="Topuria walks in")]
        with (
            patch.dict(os.environ, {"TITLE_UNIQUENESS": "block"}),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda _cid: rows),
            ),
        ):
            hit = title_collision("Topuria walks in", "tapin", exclude_run_id=9)
        self.assertIsNotNone(hit)
        self.assertIn("run #3", hit or "")

    def test_title_uniqueness_off(self):
        with patch.dict(os.environ, {"TITLE_UNIQUENESS": "off"}):
            self.assertIsNone(title_collision("anything", "tapin"))

    def test_normalize_ignores_punct(self):
        self.assertEqual(normalize_title("Topuria: Walks In!"), normalize_title("topuria walks in"))

    def test_ufc_lint_on_gaming_topic(self):
        with patch.dict(os.environ, {"UFC_TITLE_LINT": "true"}):
            warns = lint_ufc_title("UFC x GTA 6", domain="gaming")
        self.assertTrue(warns)

    def test_ufc_lint_ok_on_ufc_domain(self):
        with patch.dict(os.environ, {"UFC_TITLE_LINT": "true"}):
            self.assertEqual(lint_ufc_title("UFC 317 preview", domain="ufc"), [])

    def test_ufc5_game_title_is_not_a_trademark_hit(self):
        with patch.dict(os.environ, {"UFC_TITLE_LINT": "true"}):
            self.assertEqual(lint_ufc_title("UFC 5 career mode", domain="gaming"), [])


if __name__ == "__main__":
    unittest.main()
