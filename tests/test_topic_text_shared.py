"""One topic-text module (wave 36).

Thirteen modules each kept their own stopword list and tokenizer, so a fix to one never
reached the others: run 98's question-word fix held in 1 of 7 tokenizers, and #852's
entity query in 1 of 11 search builders. `apis/topic_tokens` is the shared base; these
pin its contract and stop a new private stopword list from appearing.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Lists that are deliberately not "words that name nothing" - each says why.
ALLOWED_PRIVATE_STOP_LISTS = {
    (
        "core/fact_grounding.py",
        "_LEADING_STOPWORDS",
    ): "sentence-initial verbs trimmed off entity names",
    ("core/title_generator.py", "_PIN_STOP"): "title pin words, not topic relevance",
    ("core/authenticity.py", "_CONTENT_STOPWORDS"): "script-similarity vocabulary",
    ("video/scene_plan.py", "_STOP"): "visual keyword extraction",
}


class ContentTokensTests(unittest.TestCase):
    def test_min_len_drops_short_tokens(self):
        from apis.topic_tokens import content_tokens

        self.assertEqual(content_tokens("GTA 6 at UFC 320 ok", min_len=3), ["gta", "ufc", "320"])

    def test_default_keeps_todays_behaviour(self):
        from apis.topic_tokens import content_tokens

        self.assertEqual(content_tokens("GTA 6 is out"), ["gta", "6", "out"])

    def test_long_text_is_linear_enough(self):
        from apis.topic_tokens import content_tokens

        text = " ".join(f"word{i}" for i in range(20000))
        self.assertEqual(len(content_tokens(text)), 20000)


class SearchQueryTests(unittest.TestCase):
    def test_question_topic_names_the_subject(self):
        from apis.topic_tokens import search_query

        self.assertEqual(
            search_query("Why is Silksong delayed again, what does Team Cherry say"), "Silksong"
        )

    def test_number_after_the_name_is_kept(self):
        from apis.topic_tokens import search_query

        self.assertEqual(
            search_query("What happened at UFC 320 between Pereira and Ankalaev"), "UFC 320"
        )

    def test_possessive_is_dropped(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("What does Kendrick Lamar's new album say"), "Kendrick Lamar")

    def test_short_statement_keeps_its_words(self):
        from apis.topic_tokens import search_query

        self.assertEqual(
            search_query("Elden Ring Nightreign review", drop=("review",)), "Elden Ring Nightreign"
        )

    def test_lower_case_question_falls_back_to_content_words(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("why is silksong delayed again"), "silksong delayed again")

    def test_always_entity_prefers_the_name_on_a_short_topic(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("Lakers trade rumors", mode="entity"), "Lakers")

    def test_keywords_mode_keeps_content_words_in_order(self):
        from apis.topic_tokens import search_query

        self.assertEqual(
            search_query("What does the Fed rate cut mean for mortgage rates", mode="keywords"),
            "Fed rate cut mortgage rates",
        )

    def test_max_len(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("abcdefghij klmnop", max_len=5), "abcde")


class NoNewPrivateStopListTests(unittest.TestCase):
    def test_stop_lists_derive_from_function_words(self):
        offenders = []
        for folder in ("core", "apis", "analytics", "video"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in tree.body:
                    targets = []
                    if isinstance(node, ast.Assign):
                        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                        targets = [node.target.id]
                    for name in targets:
                        if "STOP" not in name.upper() or name.upper() == "FUNCTION_WORDS":
                            continue
                        source = (
                            ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
                        )
                        if "FUNCTION_WORDS" in source or (rel, name) in ALLOWED_PRIVATE_STOP_LISTS:
                            continue
                        offenders.append(f"{rel}:{name}")
        self.assertEqual(
            offenders, [], "derive from apis.topic_tokens.FUNCTION_WORDS or allowlist with a reason"
        )


if __name__ == "__main__":
    unittest.main()
