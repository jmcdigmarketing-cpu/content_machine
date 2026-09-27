"""#851: a best-bet headline's domain comes from the headline, never the env channel.

`_consider_candidate` called `infer_domain(title)` to keep only on-brand headlines,
"without channel fallback". But `infer_domain` resolves a missing channel through
`CONTENT_CHANNEL_ID`, so on a PC whose `.env` pins `tapin` every headline with no keyword
read "gaming" and passed the filter. `infer_topic_domain` has no channel fallback.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _consider(title: str):
    from core.best_bet import _consider_candidate

    # The operator's `.env` pins CONTENT_CHANNEL_ID; settings read it once, at import.
    pinned = SimpleNamespace(content_channel_id="tapin")
    with patch("config.channels.get_settings", return_value=pinned):
        return _consider_candidate(
            title, "rss", allowed={"gaming", "ufc"}, exclude=set(), seen_local=set()
        )


class HeadlineDomainTests(unittest.TestCase):
    def test_a_keyword_less_headline_is_not_gaming_through_the_env(self):
        self.assertIsNone(_consider("Local man wins the lottery twice"))

    def test_an_on_brand_headline_is_kept(self):
        kept = _consider("GTA 6 delayed again to 2027")
        self.assertIsNotNone(kept)
        self.assertEqual(kept["domain"], "gaming")

    def test_a_learned_game_name_is_kept(self):
        with patch(
            "core.learned_domain_terms.learned_game_names", return_value=frozenset({"silksong"})
        ):
            kept = _consider("Silksong gets a surprise patch")
        self.assertIsNotNone(kept)


if __name__ == "__main__":
    unittest.main()
